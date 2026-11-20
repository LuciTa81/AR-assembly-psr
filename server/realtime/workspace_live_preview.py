"""Finite, local-only camera projection diagnostic; never drives Unity guidance."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import multiprocessing as mp
from pathlib import Path
from queue import Empty, Full
import time

import cv2
import numpy as np

from server.vision.calibrate_marker_layout_v2 import detect_markers
from .camera_calibration import stamp, write_json
from .workspace_projection import CameraModel, MetricWorkspace, estimate_pose, project_targets
from .workspace_registration import local_root
from .workspace_overlay import draw_overlay, project_overlay


def load_profiles(camera_path: Path, workspace_path: Path):
    camera_bytes, workspace_bytes = Path(camera_path).read_bytes(), Path(workspace_path).read_bytes()
    camera_data, workspace_data = json.loads(camera_bytes), json.loads(workspace_bytes)
    camera, workspace = CameraModel.from_profile(camera_data), MetricWorkspace.from_dict(workspace_data)
    binding = workspace_data.get("target_registration", {})
    camera_hash = hashlib.sha256(camera_bytes).hexdigest()
    if (not isinstance(binding, dict) or binding.get("camera_profile_id") != camera.profile_id
            or binding.get("camera_profile_sha256") != camera_hash):
        raise ValueError("Target candidate does not match the supplied camera profile ID/hash")
    if set(workspace.targets) != set("ABCD"):
        raise ValueError("Registered A-D targets are required")
    return camera, workspace, {
        "camera_profile": camera_data, "workspace_profile": workspace_data,
        "camera_profile_sha256": camera_hash,
        "workspace_profile_sha256": hashlib.sha256(workspace_bytes).hexdigest(),
    }


def analyze_frame(image: np.ndarray, camera: CameraModel, workspace: MetricWorkspace, *,
                  corner_refinement: str = 'subpix', max_rms_px: float = 3.) -> dict:
    result = {"status": "pose_rejected", "reason": "", "marker_ids": None,
              "detected_corners_px": {}, "targets": {}, "corner_refinement": corner_refinement}
    try:
        if tuple(image.shape[1::-1]) != camera.image_size:
            raise ValueError("Camera resolution differs from calibration")
        mapping, _, ids = detect_markers(image, 1.0, corner_refinement=corner_refinement)
        known = [int(i) for i in ids.flatten() if int(i) in workspace.markers] if ids is not None else []
        result["marker_ids"] = sorted(known)
        if len(known) != len(set(known)):
            raise ValueError("duplicate known marker ID")
        # Numeric marker evidence permits pose replay without retaining camera images.
        corners = {str(key): np.asarray(mapping[key], dtype=float) for key in sorted(known)}
        if all(value.shape == (4, 2) and np.isfinite(value).all() for value in corners.values()):
            result["detected_corners_px"] = {key: value.tolist() for key, value in corners.items()}
        pose = estimate_pose(mapping, workspace, camera, image.shape[1::-1],
                             max_rms_px=max_rms_px, max_point_error_px=5.)
        result.update(status="tracking", targets=project_targets(pose, workspace, camera),
                      rms_px=pose.rms_px, max_error_px=pose.max_error_px,
                      camera_position_mm=pose.camera_position_mm.tolist(),
                      rvec=pose.rvec.reshape(3).tolist(), tvec_mm=pose.tvec.reshape(3).tolist())
    except (ValueError, cv2.error) as exc:
        result["reason"] = str(exc)
    return result


def offer_latest(queue, item):
    try:
        queue.put_nowait(item)
    except Full:
        try:
            queue.get_nowait()
        except Empty:
            pass
        try:
            queue.put_nowait(item)
        except Full:
            # A multiprocessing feeder may still be serializing the prior item.
            pass


def take_latest(queue):
    item = None
    while True:
        try:
            item = queue.get_nowait()
        except Empty:
            return item


def camera_worker(queue, stop, camera_index: int, camera: CameraModel, workspace: MetricWorkspace, errors,
                  include_image: bool = True, *, corner_refinement: str = 'subpix'):
    cap = None
    frame_id = 0
    try:
        cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, camera.image_size[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, camera.image_size[1])
        if not cap.isOpened():
            raise RuntimeError("Camera could not open")
        while not stop.is_set():
            ok, image = cap.read()
            # Match FrameSource and observation consumers; avoid Windows tick quantization.
            received = time.perf_counter()
            if not ok or image is None:
                raise RuntimeError("Camera read failed")
            frame_id += 1
            analysis = analyze_frame(image, camera, workspace, corner_refinement=corner_refinement)
            packet = {"frame_id": frame_id, "received_at": received, "analysis": analysis}
            if include_image:
                packet["image"] = image
            offer_latest(queue, packet)
    except Exception as exc:
        errors.put_nowait({"frame_id": frame_id, "reason": str(exc)})
    finally:
        if cap is not None:
            cap.release()


def render_preview(packet, now: float, image_size: tuple, max_age_ms: float = 150., *,
                   assembly_profiles=None, target_id: str = 'A', saved_image: bool = False,
                   roi_profiles=None, selection_mode: str = 'manual', diagnostic_banner: bool = True):
    if assembly_profiles is not None and roi_profiles is not None:
        raise ValueError('Assembly and ROI candidate modes are exclusive')
    visual = np.zeros((image_size[1], image_size[0], 3), np.uint8)
    state = {"status": "waiting", "reason": "Waiting for camera", "frame_id": None,
             "age_ms": None, "targets": {}}
    if packet is not None:
        age = (now - packet["received_at"]) * 1000.
        state.update(packet["analysis"], frame_id=packet["frame_id"], age_ms=age if np.isfinite(age) else None,
                     received_at_monotonic=packet["received_at"])
        if not np.isfinite(age) or age < 0 or age > max_age_ms:
            state.update(status="stale", reason="No fresh frame; rings hidden", targets={})
        elif packet["image"] is not None and tuple(packet["image"].shape[1::-1]) == image_size:
            visual = packet["image"].copy()
        else:
            state.update(status="camera_error", reason=state.get("reason") or "Invalid camera image", targets={})
    if state["status"] != "tracking":
        state["targets"] = {}
    if roi_profiles is not None:
        from .workspace_roi_candidate import project_regions, draw_regions
        camera, workspace = roi_profiles
        state['roi_candidate'] = project_regions(visual, camera, workspace, state)
        draw_regions(visual, state['roi_candidate']['regions'])
    elif assembly_profiles is not None:
        camera, workspace = assembly_profiles
        state['assembly_overlay'] = project_overlay(state, camera, workspace, target_id)
        state['assembly_overlay']['selection_mode'] = selection_mode
        draw_overlay(visual, state['assembly_overlay'])
    elif state["status"] == "tracking":
        for name, target in state["targets"].items():
            if target["visible"]:
                x, y = np.rint(target["pixel"]).astype(int)
                cv2.circle(visual, (x, y), 12, (30, 230, 30), 2)
                cv2.putText(visual, name, (x + 15, y), cv2.FONT_HERSHEY_SIMPLEX, .65, (30, 230, 30), 2)
    if not diagnostic_banner:
        return visual, state
    ids = state.get("marker_ids")
    rms = state.get("rms_px")
    marker_text = str(len(ids)) if isinstance(ids, list) and state["status"] not in ("stale", "waiting", "camera_error") else "?"
    detail = f"markers {marker_text} | " + (f"RMS {rms:.2f}px" if state["status"] == "tracking" and rms is not None else state["reason"])
    prefix = 'SAVED IMAGE | CAMERA ONLY' if saved_image else 'CAMERA ONLY'
    if assembly_profiles is not None:
        prefix += f' | {selection_mode.upper()} TARGET {target_id or "NONE"}'
    if roi_profiles is not None:
        prefix += f' | ROI CANDIDATE {state["roi_candidate"]["valid_regions"]}/5 | NOT ACTIVE'
    text = f"{prefix} | {state['status'].upper()} | {detail}"
    cv2.rectangle(visual, (0, 0), (image_size[0], 40), (0, 0, 0), -1)
    cv2.putText(visual, text[:135], (10, 27), cv2.FONT_HERSHEY_SIMPLEX, .5, (255, 255, 255), 1)
    return visual, state


def stop_worker(worker, stop):
    stop.set()
    worker.join(timeout=2.)
    if worker.is_alive():
        worker.terminate()
        worker.join(timeout=2.)
    if worker.is_alive():
        raise RuntimeError("Owned camera worker did not stop")


def save_sample(directory: Path, packet: dict, visual: np.ndarray, state: dict) -> Path:
    folder = directory / f"frame-{packet['frame_id']:06d}"
    folder.mkdir(exist_ok=False)
    for name, image in (("raw.png", packet["image"]), ("preview.png", visual)):
        ok, encoded = cv2.imencode(".png", image)
        if not ok:
            raise RuntimeError("Could not encode sample image")
        with (folder / name).open("xb") as stream:
            stream.write(encoded.tobytes())
    write_json(folder / "report.json", dict(state, received_at_monotonic=packet["received_at"]))
    return folder


class PreviewWindow:
    """Own Tk window, without HighGUI's blocking native Ctrl+S save dialog."""

    def __init__(self, image_size, *, allow_save=True, target_id=None):
        import tkinter as tk
        self.tk = tk
        self.root = tk.Tk()
        self.allow_save = allow_save
        self.root.title("Beast camera projection | Q: stop | " + ("Space: keep sample" if allow_save else "NO IMAGE SAVING"))
        self.root.geometry("+30+30")
        self.root.resizable(False, False)
        self.target_var = None
        if target_id is not None:
            self.target_var = tk.StringVar(master=self.root, value=target_id)
            toolbar = tk.Frame(self.root)
            toolbar.pack(fill='x')
            tk.Label(toolbar, text='Manual target').pack(side='left', padx=8)
            for number, name in enumerate('ABCD', 1):
                tk.Radiobutton(toolbar, text=name, value=name, variable=self.target_var,
                               command=lambda selected=name: self.select_target(selected)).pack(side='left', padx=6)
                self.root.bind(str(number), lambda _event, selected=name: self.select_target(selected))
        self.label = tk.Label(self.root, borderwidth=0)
        self.label.pack()
        self.key = None
        self.photo = None
        self.root.protocol("WM_DELETE_WINDOW", lambda: self._key("quit"))
        for key in ("<Escape>", "q", "Q"):
            self.root.bind(key, lambda _event: self._key("quit"))
        if allow_save:
            self.root.bind("<space>", lambda _event: self._key("save"))
        self.root.bind("<Control-s>", lambda _event: "break")

    def _key(self, key):
        self.key = key

    def select_target(self, target_id):
        if self.target_var is not None and target_id in tuple('ABCD'):
            self.target_var.set(target_id)
            self._key('target:' + target_id)

    def show(self, image):
        height, width = image.shape[:2]
        ppm = f"P6\n{width} {height}\n255\n".encode() + cv2.cvtColor(image, cv2.COLOR_BGR2RGB).tobytes()
        self.photo = self.tk.PhotoImage(data=ppm, format="PPM", master=self.root)
        self.label.configure(image=self.photo)

    def poll(self):
        self.root.update()
        key, self.key = self.key, None
        return None if key == "save" and not self.allow_save else key

    def close(self):
        self.root.destroy()


def write_evidence(directory: Path, records: list, samples: list, summary: dict, ack):
    saved, failed = [], []
    try:
        with (directory / "frames.jsonl").open("x", encoding="utf-8") as stream:
            for record in records:
                stream.write(json.dumps(record, allow_nan=False) + "\n")
        for packet, visual, state in samples:
            try:
                save_sample(directory, packet, visual, state)
                saved.append(packet["frame_id"])
            except (OSError, RuntimeError, cv2.error):
                failed.append(packet["frame_id"])
        write_json(directory / "summary.json", dict(summary, sample_frame_ids=saved, failed_sample_frame_ids=failed))
        ack.put_nowait({"status": "error" if failed else "saved", "reason": "Sample write failed" if failed else ""})
    except Exception as exc:
        ack.put_nowait({"status": "error", "reason": str(exc)})


def persist_evidence(directory: Path, records: list, samples: list, summary: dict):
    context = mp.get_context("spawn")
    ack = context.Queue(maxsize=1)
    writer = context.Process(target=write_evidence, args=(directory, records, samples, summary, ack))
    writer.start()
    try:
        writer.join(timeout=10.)
        if writer.is_alive():
            writer.terminate()
            writer.join(timeout=2.)
            raise RuntimeError("Evidence writer timed out; output may be partial")
        result = take_latest(ack)
        if result is None or result["status"] != "saved":
            raise RuntimeError("Evidence writer failed: " + (result["reason"] if result else "no completion acknowledgement"))
    finally:
        ack.close()
        ack.join_thread()


def run_preview(camera_path: Path, workspace_path: Path, camera_index: int, duration: float,
                save_every_seconds: float = 0., *, assembly_overlay: bool = False,
                target_id: str = 'A', no_image_saving: bool = False,
                corner_refinement: str = 'subpix', roi_candidate: bool = False,
                max_samples: int = 12) -> Path:
    if type(max_samples) is not int or not 1 <= max_samples <= 12:
        raise ValueError('Sample limit must be an integer from 1 to 12')
    if assembly_overlay and roi_candidate:
        raise ValueError('Assembly and ROI candidate modes are exclusive')
    if corner_refinement not in ('subpix', 'apriltag'):
        raise ValueError('Unknown corner refinement: ' + corner_refinement)
    if not np.isfinite(duration) or not 1 <= duration <= 300:
        raise ValueError("Duration must be 1-300 seconds")
    if not np.isfinite(save_every_seconds) or save_every_seconds < 0:
        raise ValueError("Sample interval must be finite and nonnegative")
    if no_image_saving and save_every_seconds > 0:
        raise ValueError('Automatic saving conflicts with no-image-saving')
    if target_id not in tuple('ABCD'):
        raise ValueError('Target must be A, B, C or D')
    camera, workspace, metadata = load_profiles(camera_path, workspace_path)
    roi_definition = None
    if roi_candidate:
        from .workspace_roi_candidate import region_definition
        roi_definition = region_definition(workspace)
    directory = local_root() / ("live-" + stamp())
    directory.mkdir(parents=True, exist_ok=False)
    write_json(directory / "session.json", dict(metadata,
        schema_version="beast_live_camera_projection_v1", scope="camera_projection_only",
        activation_status="not_activated", display_alignment_verified=False,
        physical_accuracy_verified=False, camera_index=camera_index, backend="dshow",
        duration_limit_seconds=duration, receive_age_limit_ms=150, opencv_version=cv2.__version__,
        timestamp_clock='time.perf_counter',
        corner_refinement=corner_refinement,
        roi_candidate=roi_candidate, roi_definition=roi_definition,
        save_every_seconds=save_every_seconds, max_samples=0 if no_image_saving else max_samples,
        assembly_overlay=assembly_overlay, selection_mode='manual' if assembly_overlay else None,
        initial_target_id=target_id if assembly_overlay else None, image_saving_enabled=not no_image_saving))
    context = mp.get_context("spawn")
    queue, errors, stop = context.Queue(maxsize=1), context.Queue(maxsize=1), context.Event()
    worker = context.Process(target=camera_worker, args=(queue, stop, camera_index, camera, workspace, errors),
                             kwargs={'corner_refinement': corner_refinement})
    packet, window = None, None
    counts = Counter()
    kept_ids, records, samples = set(), [], []
    previous_display = None
    start = last_save = time.perf_counter()
    ending = "error"
    error_reason = ""
    print(json.dumps({"status": "starting", "directory": str(directory.resolve())}), flush=True)
    worker.start()
    try:
        if assembly_overlay or no_image_saving:
            window = PreviewWindow(camera.image_size, allow_save=not no_image_saving,
                                   target_id=target_id if assembly_overlay else None)
        else:
            window = PreviewWindow(camera.image_size)
        while time.perf_counter() - start < duration:
            incoming = take_latest(queue)
            failure = take_latest(errors)
            if failure is not None:
                ending, error_reason = "camera_error", failure["reason"]
                break
            if incoming is not None:
                packet = incoming
            visual, state = render_preview(packet, time.perf_counter(), camera.image_size,
                assembly_profiles=(camera, workspace) if assembly_overlay else None, target_id=target_id,
                roi_profiles=(camera, workspace) if roi_candidate else None)
            display = (state["frame_id"], state["status"], target_id)
            if incoming is not None:
                counts[state["status"]] += 1
            if incoming is not None or display != previous_display:
                # Memory only while the window is active; no disk I/O on the UI path.
                records.append(dict(state, event="frame" if incoming is not None else "visibility_change",
                                    observed_at_monotonic=time.perf_counter()))
                window.show(visual)
                previous_display = display
            key = window.poll()
            if key == "quit":
                ending = "user_stop"
                break
            if assembly_overlay and key is not None and key.startswith('target:'):
                selected = key.removeprefix('target:')
                if selected in tuple('ABCD'):
                    target_id = selected
            now = time.perf_counter()
            auto_save = save_every_seconds > 0 and now - last_save >= save_every_seconds
            if (not no_image_saving and packet is not None and packet["image"] is not None
                    and state["status"] in ("tracking", "pose_rejected")
                    and len(kept_ids) < max_samples and packet["frame_id"] not in kept_ids
                    and (key == "save" or auto_save)):
                samples.append((packet, visual, state))
                kept_ids.add(packet["frame_id"])
                last_save = now
            if not worker.is_alive():
                ending, error_reason = "camera_error", "Camera worker stopped unexpectedly"
                break
            if packet is None and now - start > 15:
                ending = "camera_start_timeout"
                break
            time.sleep(.005)
        else:
            ending = "duration_limit"
    except BaseException:
        ending = "error"
        raise
    finally:
        if window is not None:
            window.close()
        try:
            stop_worker(worker, stop)
        finally:
            queue.close()
            queue.join_thread()
            errors.close()
            errors.join_thread()
        persist_evidence(directory, records, samples, {
            "ending": ending, "elapsed_seconds": time.perf_counter() - start,
            "error_reason": error_reason, "received_packet_counts": dict(counts),
            "requested_sample_frame_ids": sorted(kept_ids),
            "display_alignment_verified": False, "physical_accuracy_verified": False,
        })
    return directory


def render_saved_image(camera_path: Path, workspace_path: Path, image_path: Path, target_id: str = 'A', *,
                        corner_refinement: str = 'subpix', roi_candidate: bool = False) -> Path:
    camera, workspace, metadata = load_profiles(camera_path, workspace_path)
    source = Path(image_path).read_bytes()
    image = cv2.imdecode(np.frombuffer(source, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError('Could not decode saved image')
    analysis = analyze_frame(image, camera, workspace, corner_refinement=corner_refinement)
    packet = dict(frame_id=1, received_at=0., image=image, analysis=analysis)
    visual, state = render_preview(packet, 0., camera.image_size,
        assembly_profiles=None if roi_candidate else (camera, workspace), target_id=target_id, saved_image=True,
        roi_profiles=(camera, workspace) if roi_candidate else None)
    if roi_candidate:
        from .workspace_roi_candidate import region_definition
        state['roi_definition'] = region_definition(workspace)
    directory = local_root() / ('overlay-still-' + stamp())
    directory.mkdir(parents=True, exist_ok=False)
    ok, encoded = cv2.imencode('.png', visual)
    if not ok:
        raise RuntimeError('Could not encode preview')
    with (directory / 'preview.png').open('xb') as stream:
        stream.write(encoded.tobytes())
    write_json(directory / 'report.json', dict(state, source_mode='saved_image',
        age_ms=None, received_at_monotonic=None,
        source_path=str(Path(image_path).resolve()), source_sha256=hashlib.sha256(source).hexdigest(),
        camera_profile_sha256=metadata['camera_profile_sha256'],
        workspace_profile_sha256=metadata['workspace_profile_sha256'],
        display_alignment_verified=False, physical_accuracy_verified=False))
    return directory


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera-profile", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--camera", type=int)
    source.add_argument("--image", type=Path, help='Render a saved photo without opening a camera')
    parser.add_argument("--duration", type=float, default=60.)
    parser.add_argument("--save-every-seconds", type=float, default=0.)
    parser.add_argument('--max-samples', type=int, default=12, help='Live raw-photo limit, 1-12; each also saves a preview')
    display = parser.add_mutually_exclusive_group()
    display.add_argument('--assembly-overlay', action='store_true')
    display.add_argument('--roi-candidate', action='store_true', help='Diagnostic regions only; no recognition activation')
    parser.add_argument('--target', choices=list('ABCD'), default='A')
    parser.add_argument('--corner-refinement', choices=['subpix', 'apriltag'], default='subpix',
                        help='Diagnostic detector choice; ArUco dictionary and pose gates stay unchanged')
    parser.add_argument('--no-image-saving', action='store_true', help='Live mode: disable both Space and automatic photo saving')
    args = parser.parse_args(argv)
    try:
        if args.image is not None:
            if args.no_image_saving or args.save_every_seconds:
                raise ValueError('Image saving options are for live camera mode; saved-image mode writes a preview PNG')
            directory = render_saved_image(args.camera_profile, args.workspace, args.image, args.target,
                                           corner_refinement=args.corner_refinement, roi_candidate=args.roi_candidate)
            report = json.loads((directory / 'report.json').read_text(encoding='utf-8'))
            print(json.dumps(dict(directory=str(directory.resolve()), status=report['status'], source_mode='saved_image')), flush=True)
            overlay = report['roi_candidate'] if args.roi_candidate else report['assembly_overlay']
            return 0 if report['status'] == 'tracking' and overlay['visible'] else 1
        directory = run_preview(args.camera_profile, args.workspace, args.camera, args.duration, args.save_every_seconds,
            assembly_overlay=args.assembly_overlay, target_id=args.target, no_image_saving=args.no_image_saving,
            corner_refinement=args.corner_refinement, roi_candidate=args.roi_candidate, max_samples=args.max_samples)
        summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
        print(json.dumps({"directory": str(directory.resolve()), **summary}), flush=True)
        return 0 if summary["ending"] in ("duration_limit", "user_stop") else 1
    except (OSError, ValueError, RuntimeError, KeyError, cv2.error) as exc:
        print(f"[ERROR] {exc}", flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
