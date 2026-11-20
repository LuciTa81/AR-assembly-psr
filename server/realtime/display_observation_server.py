"""Finite local metadata channel for manual eye/display correspondence collection."""

from __future__ import annotations

import argparse
from collections import Counter
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import multiprocessing as mp
import os
from pathlib import Path
import secrets
import threading
import time
import uuid

import cv2
import numpy as np

from .workspace_live_preview import PreviewWindow, camera_worker, load_profiles, render_preview, stop_worker, take_latest
from .workspace_projection import CameraModel, MetricWorkspace, finite_array


MAX_POSE_TRACE_RECORDS = 20000


def pose_reason_code(status: str, reason: str = "") -> str:
    """Translate legacy diagnostic exceptions once, not in each UI client."""
    if status in {"tracking", "waiting", "stale", "camera_error"}:
        return status
    if reason == "At least four visible measured markers required for pose":
        return "insufficient_markers"
    if reason.startswith(("Visible marker geometry is degenerate",
                          "Visible metric markers:", "Visible image markers:")):
        return "marker_geometry"
    if reason.startswith(("Workspace pose solver", "Workspace pose refinement failed")):
        return "solver_failed"
    if reason.startswith(("No physical workspace pose", "Workspace pose is ambiguous",
                          "Workspace pose reprojection error")) or reason == "Invalid pose quality":
        return "pose_quality"
    if reason in {"Target is not visible", "Target outside image"}:
        return "target_outside"
    return "pose_unavailable"


def make_observation(packet: dict | None, now: float, session: dict,
                     camera: CameraModel, workspace: MetricWorkspace) -> dict:
    target_id = session.get("target_id", "A")
    if target_id not in ("A", "B", "C", "D"):
        raise ValueError("Invalid target_id")
    result = dict(session, schema_version="beast_display_observation_v1", target_id=target_id,
                  image_size=list(camera.image_size), status="waiting", reason="Waiting for camera", reason_code="waiting",
                  frame_id=-1, age_ms=-1., marker_ids=None, marker_count=-1)
    if packet is None:
        return result
    try:
        frame_id = packet["frame_id"]
        if type(frame_id) is not int or frame_id < 1:
            raise ValueError("Invalid frame ID")
        age = (now - packet["received_at"]) * 1000.
        result.update(frame_id=frame_id, age_ms=float(age) if np.isfinite(age) else -1.)
        if not np.isfinite(age) or not 0 <= age <= 150:
            return dict(result, status="stale", reason="No fresh observation", reason_code="stale")
        analysis = packet["analysis"]
        ids = analysis.get("marker_ids")
        if isinstance(ids, list) and all(type(i) is int and i in workspace.markers for i in ids):
            result.update(marker_ids=list(ids), marker_count=len(ids))
        if analysis.get("status") != "tracking":
            reason = analysis.get("reason", "No pose")
            return dict(result, status="pose_rejected", reason=reason,
                        reason_code=pose_reason_code("pose_rejected", reason))
        ids = analysis["marker_ids"]
        if (not isinstance(ids, list) or len(ids) < 4 or len(set(ids)) != len(ids)
                or any(type(i) is not int or i not in workspace.markers for i in ids)):
            raise ValueError("Invalid marker IDs")
        rvec = finite_array(analysis["rvec"], (3,), "rvec")
        tvec = finite_array(analysis["tvec_mm"], (3,), "tvec")
        rms, maximum = float(analysis["rms_px"]), float(analysis["max_error_px"])
        if not (np.isfinite([rms, maximum]).all() and 0 <= rms <= 3 and rms <= maximum <= 5):
            raise ValueError("Invalid pose quality")
        xyz = workspace.targets[target_id]
        rotation = cv2.Rodrigues(rvec)[0]
        camera_xyz = rotation @ xyz + tvec
        target = analysis["targets"][target_id]
        if not target["visible"] or not np.isfinite(camera_xyz).all() or camera_xyz[2] <= 0:
            raise ValueError("Target is not visible")
        pixel = finite_array(target["pixel"], (2,), "target pixel")
        if not (0 <= pixel[0] < camera.image_size[0] and 0 <= pixel[1] < camera.image_size[1]):
            raise ValueError("Target outside image")
        result.update(status="tracking", reason="", marker_ids=ids, rms_px=rms, max_error_px=maximum,
                      rvec=rvec.tolist(), tvec_mm=tvec.tolist(), world_xyz_mm=xyz.tolist(),
                      camera_xyz_mm=camera_xyz.tolist(), target_pixel=pixel.tolist(),
                      camera_targets=[dict(target_id=name,
                          camera_xyz_mm=(rotation @ workspace.targets[name] + tvec).tolist())
                          for name in "ABCD"])
    except (ValueError, TypeError, KeyError, cv2.error) as exc:
        result.update(status="pose_rejected", reason=str(exc))
    result["reason_code"] = pose_reason_code(result["status"], result["reason"])
    return result


class ObservationStore:
    def __init__(self, session: dict, camera: CameraModel, workspace: MetricWorkspace, *,
                 record_pose_trace: bool = False):
        self.session, self.camera, self.workspace = session, camera, workspace
        self.lock = threading.Lock()
        self.packet = None
        self.error = None
        self.requests = Counter()
        self.worker = self.errors = None
        self.pose_trace = [] if record_pose_trace else None
        self.trace_dropped = 0

    def bind_source(self, worker, errors):
        self.worker, self.errors = worker, errors

    def _refresh_source(self):
        if self.worker is not None and self.error is None:
            error = take_latest(self.errors)
            if error is not None or not self.worker.is_alive():
                self.error = error["reason"] if error else "Camera worker exited"
                self.packet = None

    def source_available(self):
        with self.lock:
            self._refresh_source()
            return self.error is None

    def update(self, packet):
        with self.lock:
            self._refresh_source()
            if self.error is None:
                self.packet = copy.deepcopy({key: packet[key] for key in ("frame_id", "received_at", "analysis")})
                if self.pose_trace is not None:
                    if len(self.pose_trace) < MAX_POSE_TRACE_RECORDS:
                        self._record_pose_trace(time.perf_counter())
                    else:
                        self.trace_dropped += 1

    def _record_pose_trace(self, now: float):
        # Join to existing eye-pair saves by session_id/frame_id; never retain images.
        packet, analysis = self.packet, self.packet["analysis"]
        corners = {}
        try:
            raw = analysis.get("detected_corners_px", {})
            if isinstance(raw, dict):
                corners = {str(key): finite_array(raw[str(key)], (4, 2), "marker corners").tolist()
                           for key in self.workspace.markers if str(key) in raw}
        except (ValueError, TypeError):
            corners = {}
        ids = analysis.get("marker_ids")
        ids = list(ids) if isinstance(ids, list) and all(type(i) is int for i in ids) else None
        row = make_observation(packet, now, self.session, self.camera, self.workspace)
        row.update(schema_version="beast_display_pose_trace_v1",
                   timestamp_clock="time.perf_counter",
                   received_at_monotonic=packet["received_at"] if np.isfinite(packet["received_at"]) else None,
                   ingested_at_monotonic=now, detected_corners_px=corners,
                   analysis_status=analysis.get("status"), analysis_reason=analysis.get("reason", ""),
                   analysis_marker_ids=ids)
        self.pose_trace.append(row)

    def invalidate(self, reason: str):
        with self.lock:
            self.error, self.packet = reason, None

    def snapshot(self, now: float) -> dict:
        with self.lock:
            self._refresh_source()
            result = make_observation(self.packet, now, self.session, self.camera, self.workspace)
            if self.error is not None:
                result.update(status="camera_error", reason=self.error, reason_code="camera_error")
            self.requests[result["status"]] += 1
            return result


def start_server(store: ObservationStore, token: str) -> tuple:
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(1.)

        def log_message(self, *_args):
            pass

        def do_GET(self):
            if not secrets.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token):
                self.send_error(401)
                return
            if self.path != "/observation":
                self.send_error(404)
                return
            body = json.dumps(store.snapshot(time.perf_counter()), allow_nan=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (OSError, TimeoutError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    server.block_on_close = False
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .05}, daemon=True)
    thread.start()
    return server, thread


def _write_json(path: Path, data: dict):
    temporary = path.with_suffix(".tmp")
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
    if path.exists():
        raise FileExistsError(path)
    temporary.rename(path)


def saved_depths(directory: Path, session_id: str, setup_id: str, target_id: str) -> list[float]:
    rows = []
    for path in directory.glob("diagnostic-frame-*.json"):
        try:
            row = json.loads(path.read_text(encoding="utf-8-sig"))
            obs = row["observation"]
            if (row["schema_version"] == "beast_tracked_alignment_diagnostic_v1"
                    and row["binocular_confirmed_by_user"] is True and row["rendered_view"] == "Both"
                    and row["setup_id"] == setup_id and obs["session_id"] == session_id
                    and obs["target_id"] == target_id and obs["status"] == "tracking"):
                z = float(obs["camera_xyz_mm"][2])
                if np.isfinite(z) and z > 0:
                    rows.append((int(obs["frame_id"]), z))
        except (OSError, ValueError, TypeError, IndexError, KeyError):
            continue
    depths = []
    for _, z in sorted(rows):
        if not depths or z >= depths[-1] + 40:
            depths.append(z)
            if len(depths) == 3:
                break
    return depths


def run_collection(camera_path: Path, workspace_path: Path, camera_index: int,
                   seconds: float, root: Path | None = None, *, preview: bool = False,
                   setup_id: str | None = None, record_pose_trace: bool = False,
                   target_id: str = "A", three_depth_pairs: bool = False) -> Path:
    if target_id not in ("A", "B", "C", "D"):
        raise ValueError("target_id must be A, B, C or D")
    limit = 600 if three_depth_pairs else 300
    if not np.isfinite(seconds) or not 1 <= seconds <= limit:
        raise ValueError(f"Duration must be 1..{limit} seconds")
    if three_depth_pairs and not setup_id:
        raise ValueError("Three-depth collection requires an unchanged wearing setup")
    if setup_id is not None and (not isinstance(setup_id, str) or not setup_id.strip() or len(setup_id) > 128):
        raise ValueError("setup_id must identify one unchanged wearing/display setup (1..128 characters)")
    camera, workspace, metadata = load_profiles(camera_path, workspace_path)
    root = root or Path(os.environ["LOCALAPPDATA"]) / "ARAssembly/beast-mvp/display_correspondence"
    session_id = uuid.uuid4().hex
    directory = Path(root).resolve() / session_id
    directory.mkdir(parents=True, exist_ok=False)
    session = {"session_id": session_id, "camera_profile_id": camera.profile_id, "target_id": target_id,
               "timestamp_clock": "time.perf_counter",
               "workspace_profile_id": workspace.profile_id,
               "camera_profile_sha256": metadata["camera_profile_sha256"],
               "workspace_profile_sha256": metadata["workspace_profile_sha256"]}
    store = ObservationStore(session, camera, workspace, record_pose_trace=record_pose_trace)
    context = mp.get_context("spawn")
    queue, errors, stop = context.Queue(maxsize=1), context.Queue(maxsize=1), context.Event()
    worker = context.Process(target=camera_worker, args=(queue, stop, camera_index, camera, workspace, errors),
                             kwargs={"include_image": preview})
    server = thread = None
    window = packet = previous_display = None
    started = False
    ending = "error"
    counts = Counter()
    started_at = time.perf_counter()
    try:
        worker.start()
        started = True
        store.bind_source(worker, errors)
        token = secrets.token_urlsafe(32)
        server, thread = start_server(store, token)
        config = dict(session, schema_version="beast_display_collection_config_v1", token=token,
                      observation_url=f"http://127.0.0.1:{server.server_port}/observation",
                      image_size=list(camera.image_size), directory=str(directory), setup_id=setup_id)
        _write_json(directory / "client-config.json", config)
        print(f"Client config: {directory / 'client-config.json'}", flush=True)
        if preview:
            window = PreviewWindow(camera.image_size, allow_save=False)
        next_check, depths = 0., []
        while time.perf_counter() - started_at < seconds:
            if three_depth_pairs and time.perf_counter() >= next_check:
                next_check = time.perf_counter() + .5
                found = saved_depths(directory, session_id, setup_id, target_id)
                if found != depths:
                    depths = found
                    print("Confirmed depths (mm):", depths, flush=True)
                    if len(depths) == 3:
                        ending = "three_depth_pairs"
                        break
            if not store.source_available():
                ending = "camera_error"
                break
            incoming = take_latest(queue)
            if incoming is not None:
                packet = incoming
                store.update(incoming)
                counts[incoming["analysis"]["status"]] += 1
            if window is not None:
                visual, state = render_preview(packet, time.perf_counter(), camera.image_size)
                display = (state["frame_id"], state["status"])
                if incoming is not None or display != previous_display:
                    window.show(visual)
                    previous_display = display
                if window.poll() == "quit":
                    ending = "user_exit"
                    break
            time.sleep(.005)
        else:
            ending = "deadline"
    except KeyboardInterrupt:
        ending = "user_exit"
    finally:
        store.invalidate("Collection ended")
        try:
            try:
                if window is not None:
                    window.close()
            finally:
                if server is not None:
                    server.shutdown()
                    server.server_close()
                    thread.join(2.)
        finally:
            try:
                if started:
                    stop_worker(worker, stop)
            finally:
                for channel in (queue, errors):
                    if hasattr(channel, "close"):
                        channel.close()
                        channel.join_thread()
                trace_status = "disabled"
                try:
                    if store.pose_trace is not None:
                        trace_status = "write_failed"
                        with (directory / "pose-trace.jsonl").open("x", encoding="utf-8") as stream:
                            for row in store.pose_trace:
                                stream.write(json.dumps(row, allow_nan=False) + "\n")
                        trace_status = "written"
                finally:
                    _write_json(directory / "summary.json", dict(session, ending=ending, frames=dict(counts),
                        requests=dict(store.requests), elapsed_seconds=time.perf_counter() - started_at,
                        pose_trace={"status": trace_status, "records": len(store.pose_trace or []),
                                    "dropped_records": store.trace_dropped},
                        candidate_only=True, calibration_valid=False, display_alignment_verified=False))
    return directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera-profile", required=True, type=Path)
    parser.add_argument("--workspace-profile", required=True, type=Path)
    parser.add_argument("--camera-index", type=int, default=1)
    parser.add_argument("--seconds", type=float, default=300.)
    parser.add_argument("--three-depth-pairs", action="store_true",
                        help="Stop after three binocular saves, each at least 40 mm farther than the previous")
    parser.add_argument("--preview", action="store_true", help="Show the same camera input locally; image saving disabled")
    parser.add_argument("--setup-id", help="Required for paired saves; change after re-wearing or changing display settings")
    parser.add_argument("--target-id", choices=list("ABCD"), default="A")
    parser.add_argument("--record-pose-trace", action="store_true",
                        help="Keep bounded numeric marker/pose history locally; no images; written on exit")
    args = parser.parse_args()
    run_collection(args.camera_profile, args.workspace_profile, args.camera_index, args.seconds,
                   preview=args.preview, setup_id=args.setup_id, record_pose_trace=args.record_pose_trace,
                   target_id=args.target_id, three_depth_pairs=args.three_depth_pairs)


if __name__ == "__main__":
    main()
