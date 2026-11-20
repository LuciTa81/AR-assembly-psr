"""Bounded local P1 UI fixture. No camera, model, or external network is used."""
from __future__ import annotations

import argparse
from copy import deepcopy
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from server.realtime.overlay_http_server import OverlayHttpServer
from server.realtime.schemas import OverlayMessage


def demo_image(message):
    import cv2
    image = np.full((540, 960, 3), (225, 234, 230), np.uint8)
    for x in range(0, 960, 40):
        cv2.line(image, (x, 0), (x, 540), (203, 215, 208), 1)
    for y in range(0, 540, 40):
        cv2.line(image, (0, y), (960, y), (203, 215, 208), 1)
    cv2.rectangle(image, (280, 90), (680, 400), (247, 249, 248), -1)
    cv2.rectangle(image, (280, 90), (680, 400), (105, 122, 111), 5)
    target = message["target"].removeprefix("screw_").upper()
    phase = message["guidance"]["phase"]
    points = [(300, 110), (660, 110), (300, 380), (660, 380)]
    for name, point in zip("ABCD", points):
        active = name == target and message["marker_status"] == "OK"
        color = (65, 153, 209) if active else (104, 122, 112)
        cv2.circle(image, point, 21 if active else 11, color, 3 if active else -1)
        cv2.putText(image, name, (point[0] + 25, point[1] + 8), cv2.FONT_HERSHEY_SIMPLEX, .8, color, 2)
        if active and phase in ("OBSERVING", "OBSERVED"):
            x, y = point
            cv2.line(image, (x, y - 90), point, (100, 105, 106), 8)
            cv2.rectangle(image, (x - 12, y - 140), (x + 12, y - 90), (30, 173, 220), -1)
    cv2.rectangle(image, (20, 457), (940, 520), (250, 250, 250), -1)
    cv2.putText(image, "SYNTHETIC WORKSPACE | " + message["current_state"] + " | " + phase,
                (35, 495), cv2.FONT_HERSHEY_SIMPLEX, .7, (63, 79, 68), 2)
    return image


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--guidance", action="store_true", help="Replay the R4 state/instruction sequence")
    parser.add_argument("--supervisor-demo", action="store_true", help="Synthetic workspace image and R4 guidance; no camera")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--seconds", type=int, default=24)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 3600:
        parser.error("--seconds must be between 1 and 3600")
    snapshots = None
    fixture = None
    if args.guidance or args.supervisor_demo:
        from guidance_fixture import build_fixture
        fixture = build_fixture()
        snapshots = fixture["snapshots"]
    server = OverlayHttpServer("127.0.0.1", args.port, "web_overlay")
    server.start()
    started = time.perf_counter()
    frame_id = 0
    image = np.zeros((16, 16, 3), np.uint8)
    print("R4 timed guidance: S0-S6 metadata, loss/recovery, then stop." if snapshots is not None
          else "P1 fixture: 0-8s live, 8-12s lost, 12-16s live, 16-20s frozen, 20-24s live, then stop.", flush=True)
    try:
        while (elapsed := time.perf_counter() - started) < args.seconds:
            if snapshots is not None:
                cycle = int(elapsed // 24) if args.supervisor_demo else 0
                index = min(int((elapsed - cycle * 24) * 20), len(snapshots) - 1)
                message = deepcopy(snapshots[index])
                message["timestamp_ms"] += int((started + cycle * 24) * 1000) - 1000
                message["spatial"] = None  # Normal text preview makes no positional claim.
                if args.supervisor_demo:
                    message["session_id"] += "-demo-" + str(cycle)
                    message["extra"] = dict(fixture["rows"][index]["filter_input"]["features"],
                        yolo_reason="ok" if message["marker_status"] == "OK" else "before_tracking_recovery")
                    message["fps"] = 20
                    image = demo_image(message)
                server.update(message, image)
                time.sleep(.05)
                continue
            if 16 <= elapsed < 20:
                time.sleep(0.05)
                continue
            frame_id += 1
            message = OverlayMessage(
                session_id="p1-fixture-" + str(int(started * 1000)),
                frame_id=frame_id, timestamp_ms=int(time.perf_counter() * 1000),
                source="p1_fixture", system_status="RUNNING",
                marker_status="LOST" if 8 <= elapsed < 12 else "OK",
                current_state="S2", current_label="Lid closed",
                next_action="Fasten screw A", target="screw_a",
            )
            server.update(message.to_dict(), image)
            time.sleep(0.1)
    finally:
        server.stop()
    print("P1 fixture stopped.", flush=True)


if __name__ == "__main__":
    main()
