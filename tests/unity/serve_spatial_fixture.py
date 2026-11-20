"""Finite laptop-only synthetic SBS metadata fixture. No camera or external network."""

import argparse
from copy import deepcopy
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from server.realtime.display_calibration import SyntheticDisplayProfile, project_display
from server.realtime.schemas import OverlayMessage

DATA = json.loads((ROOT / "tests/fixtures/spatial_guidance_v1.json").read_text(encoding="utf-8"))
PROFILE = SyntheticDisplayProfile.from_dict(DATA["profile"])


def make_message(elapsed, frame_id, epoch_ms, session_id):
    now = epoch_ms + int(elapsed * 1000)
    index = min(3, int(elapsed // 2)) if elapsed < 8 else 3 if 20 <= elapsed < 22 else 0
    target_id = "ABCD"[index]
    pose_index = 240 if 12 <= elapsed < 14 else int(elapsed * 20)
    pose_time = pose_index / 20
    target = dict(DATA["input"], target_id=target_id, pose_frame_id=pose_index + 1,
                  pose_timestamp_ms=epoch_ms + pose_index * 50,
                  camera_xyz_mm=[85 * math.sin(pose_time), 60 * math.cos(pose_time), 500])
    spatial = project_display(PROFILE, target, now)
    marker = "LOST" if 8 <= elapsed < 10 else "OK"
    if marker == "LOST":
        spatial.target_visible = False
        spatial.left_pixel = spatial.right_pixel = None
        spatial.reason = "no_pose"
    message = OverlayMessage(session_id=session_id, frame_id=frame_id, timestamp_ms=now,
        source="synthetic_sbs_fixture", system_status="RUNNING", marker_status=marker,
        current_state="S" + str(index + 2), current_label="Assembly step " + str(index + 2),
        target="screw_" + target_id.lower(), next_action="Fasten screw " + target_id,
        spatial=spatial).to_dict()
    if 16 <= elapsed < 18:
        message["spatial"]["display_profile_id"] = "wrong-profile"
    if 18 <= elapsed < 20:
        message["spatial"].pop("pose_age_ms")
    if elapsed >= 22:
        message.update(current_state="S6", current_label="Sequence observed", target="complete",
                       next_action="Confirm assembly sequence completion")
    message["frame_age_ms"] = 0
    return message


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=24)
    parser.add_argument("--guidance", action="store_true", help="Replay the actual timed state filter (no camera).")
    args = parser.parse_args()
    if not math.isfinite(args.seconds) or not 1 <= args.seconds <= 270:
        parser.error("seconds must be 1..270")
    session = "synthetic-sbs-" + uuid.uuid4().hex
    lock = threading.Lock()
    first = None
    sequence = 0
    guidance_messages = None
    if args.guidance:
        from guidance_fixture import build_fixture
        guidance_messages = build_fixture()["snapshots"]

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            nonlocal first, sequence
            if self.path != "/state.json":
                self.send_error(404)
                return
            with lock:
                now = time.perf_counter()
                if first is None:
                    first = now
                sequence += 1
                if guidance_messages is None:
                    message = make_message(now - first, sequence, int(first * 1000), session)
                else:
                    index = min(int((now - first) * 20), len(guidance_messages) - 1)
                    message = deepcopy(guidance_messages[index])
                    offset = int(first * 1000) - 1000
                    message["timestamp_ms"] += offset
                    message["session_id"] = session
                    message["frame_age_ms"] = int(now * 1000) - message["timestamp_ms"]
                    if message["spatial"]:
                        message["spatial"]["pose_timestamp_ms"] += offset
                        message["spatial"]["pose_age_ms"] = message["frame_age_ms"]
            body = json.dumps(message, allow_nan=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except OSError:
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    config = {key: DATA["profile"][key] for key in (
        "camera_profile_id", "workspace_profile_id", "camera_profile_sha256", "workspace_profile_sha256")}
    config.update(schema_version="beast_spatial_preview_config_v1", session_id=session,
                  state_url=f"http://127.0.0.1:{server.server_port}/state.json",
                  display_profile_id=PROFILE.profile_id, duration_seconds=args.seconds + 5)
    args.config.parent.mkdir(parents=True, exist_ok=True)
    with args.config.open("x", encoding="utf-8") as stream:
        json.dump(config, stream, indent=2)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .05}, daemon=True)
    thread.start()
    started = time.perf_counter()
    print(f"Synthetic config: {args.config.resolve()}", flush=True)
    try:
        while time.perf_counter() - started < args.seconds + 60:
            with lock:
                if first is not None and time.perf_counter() - first >= args.seconds:
                    break
            time.sleep(.05)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)
    print(f"Synthetic fixture stopped, requests={sequence}", flush=True)


if __name__ == "__main__":
    main()
