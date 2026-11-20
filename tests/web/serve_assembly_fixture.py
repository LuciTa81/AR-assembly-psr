"""Bounded, camera-free fixture using the real assembly controller and confirmation API."""
import argparse
from pathlib import Path
import sys
import time
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'tests'))
from server.realtime.assembly_session import AssemblySession
from server.realtime.online_state_filter import OnlineStateFilter
from server.realtime.overlay_http_server import OverlayHttpServer
from server.realtime.run_realtime_server import make_guidance_message
from server.realtime.schemas import FramePacket
from realtime.test_assembly_session import inputs, settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview', action='store_true', help='Interactive synthetic rehearsal; no camera or Unity')
    parser.add_argument('--seconds', type=int)
    parser.add_argument('--open', action='store_true', help='Open the local supervisor in a browser')
    args = parser.parse_args()
    seconds = args.seconds if args.seconds is not None else (3600 if args.preview else 40)
    if not 1 <= seconds <= 3600:
        parser.error('--seconds must be between 1 and 3600')
    if args.open and not args.preview:
        parser.error('--open requires --preview')
    config = settings()
    if args.preview:
        sys.path.insert(0, str(ROOT/'tests'/'unity'))
        from serve_snapshot_fixture import demo_image
        config['timing'] = dict(resume_grace_ms=600, completed_hold_resume_ms=2000)
    session_id = 'synthetic-rehearsal-' + str(time.time_ns()) if args.preview else 'test'
    control = AssemblySession(session_id, OnlineStateFilter.from_config(config))
    server = OverlayHttpServer('127.0.0.1', 0, ROOT/'web_overlay', operator=control)
    server.start()
    print('overlay=' + server.url, flush=True)
    if args.open:
        import webbrowser
        webbrowser.open(server.url + '/supervisor.html')
    start = changed = time.perf_counter()
    previous, frame_id, completed = 'S0', 0, None
    try:
        while time.perf_counter() - start < seconds:
            now = time.perf_counter()
            frame_id += 1
            marker_ok = previous != 'S6'
            # A short, synthetic C interruption makes progress retention visible in rehearsal.
            if args.preview and previous == 'S4' and 1.2 <= now-changed < 2.2:
                marker_ok = False
            item = inputs(int(now*1000), 'abcd'[max(0, min(3, int(previous[1])-2))],
                          .9 if now-changed < (3.2 if args.preview else 1.8) else .05, marker_ok)
            result = control.update(item, True)
            if result.state != previous:
                previous, changed = result.state, now
            marker = SimpleNamespace(marker_ok=marker_ok, marker_status='OK' if marker_ok else 'LOST',
                                     marker_count=6 if marker_ok else 0, warp_quality=1. if marker_ok else 0.)
            packet = FramePacket(frame_id, int(now*1000), 'synthetic_assembly_fixture', None)
            message = make_guidance_message(packet, marker, result, session_id=session_id).to_dict()
            message['extra']['operator'] = control.metadata()
            if args.preview:
                message['extra'].update(item['features'])
                message['extra']['yolo_reason'] = 'synthetic_fixture'
                message['fps'] = 20
            server.update(message, demo_image(message) if args.preview else np.zeros((8,8,3), np.uint8))
            if result.guidance.phase == 'COMPLETED':
                completed = now if completed is None else completed
                if not args.preview and now-completed > 1:
                    break
            time.sleep(.05)
    finally:
        server.stop()
    if completed is None and not args.preview:
        raise RuntimeError('Assembly fixture did not complete')


if __name__ == '__main__':
    main()
