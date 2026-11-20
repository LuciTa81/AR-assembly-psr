"""Metadata-only R4 sequence through the real filter and runtime message boundary."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from server.realtime.display_calibration import SyntheticDisplayProfile, project_display
from server.realtime.online_state_filter import OnlineStateFilter
from server.realtime.run_realtime_server import make_filter_input, make_guidance_message
from server.realtime.schemas import FramePacket
from server.realtime.yolo_realtime import YoloRealtimeResult


def build_fixture():
    config = {"guidance_policy": "timed_v1", "min_confidence": 0.55}
    state_filter = OnlineStateFilter.from_config(config)
    data = json.loads((ROOT / "tests/fixtures/spatial_guidance_v1.json").read_text(encoding="utf-8"))
    profile = SyntheticDisplayProfile.from_dict(data["profile"])
    snapshots, rows = [], []
    for i, elapsed in enumerate(range(0, 24001, 50), 1):
        near_target = next((s for start, end, s in (
            (1500, 1800, "b"), (1800, 2000, "a"), (2600, 4300, "a"),
            (5300, 6500, "a"), (7000, 9200, "b"), (9700, 11500, "c"),
            (12500, 13700, "c"), (14200, 16000, "d"),
        ) if start <= elapsed < end), None)
        visible = not 4300 <= elapsed < 4700
        features = {
            "box_present_score": 0.9 if elapsed >= 800 else 0.1,
            "lid_closed_score": 0.9 if elapsed >= 1100 else 0.1,
            "require_yolo_for_screw": 1, "driver_visible": int(visible), "driver_count": int(visible),
            "tool_tip_source": 2, "tool_tip_x": 100, "tool_tip_y": 100,
            "yolo_tool_score_threshold": 0.3, "screw_min_confidence": 0.55,
        }
        for s in "abcd":
            features[f"tool_score_{s}"] = 0.9 if s == near_target else 0.05
            features[f"tip_screw_score_{s}"] = 0.0
            features[f"tool_dist_{s}"] = 20.0 if s == near_target else 300.0
        marker_ok = not 11500 <= elapsed < 12000
        marker = SimpleNamespace(marker_ok=marker_ok, marker_status="OK" if marker_ok else "LOST",
                                 marker_count=6 if marker_ok else 0, warp_quality=0.9 if marker_ok else 0)
        packet = FramePacket(i, 1000 + elapsed, "synthetic_guidance_fixture", None)
        yolo = YoloRealtimeResult(True, available=True, frame_id=i, timestamp_ms=packet.timestamp_ms,
                                  source_marker_ok=marker_ok, reason="ok", features=features)
        inputs = make_filter_input(packet, marker, SimpleNamespace(enabled=True, reason="ok"), yolo, features)
        estimate = state_filter.update(**inputs)
        message = make_guidance_message(packet, marker, estimate, session_id="synthetic-r4").to_dict()
        if estimate.target.startswith("screw_"):
            target = estimate.target[-1].upper()
            offset = "ABCD".index(target)
            message["spatial"] = asdict(project_display(profile, dict(data["input"],
                target_id=target, pose_frame_id=i, pose_timestamp_ms=packet.timestamp_ms,
                camera_xyz_mm=[(offset % 2) * 70 - 35, (offset // 2) * 60 - 30, 500]), packet.timestamp_ms))
            if not marker_ok:
                message["spatial"].update(target_visible=False, reason="no_pose", left_pixel=None, right_pixel=None)
        message["frame_age_ms"] = 0
        snapshots.append(message)
        rows.append(dict(elapsed_ms=elapsed, frame_id=i, filter_input=inputs, state=estimate.state,
            target=estimate.target, next_action=estimate.next_action, held_reason=estimate.held_reason,
            transition_event=estimate.transition_event, guidance=asdict(estimate.guidance)))
    checkpoints = [
        (0, "S0", "box", "GUIDING", "Place"), (900, "S0", "box", "OBSERVING", "Checking"),
        (1150, "S1", "lid", "OBSERVING", "Checking"), (1550, "S2", "screw_a", "GUIDING", "screw A"),
        (1850, "S2", "screw_a", "OBSERVING", "screw A"), (2100, "S2", "screw_a", "GUIDING", "screw A"),
        (3500, "S2", "screw_a", "OBSERVED", "clear of screw A"), (4500, "S2", "screw_a", "PAUSED", "not visible"),
        (5100, "S2", "screw_a", "GUIDING", "screw A"), (6200, "S2", "screw_a", "OBSERVED", "clear of screw A"),
        (6950, "S3", "screw_b", "GUIDING", "screw B"), (7900, "S3", "screw_b", "OBSERVED", "clear of screw B"),
        (9650, "S4", "screw_c", "GUIDING", "screw C"), (10600, "S4", "screw_c", "OBSERVED", "clear of screw C"),
        (11700, "S4", "screw_c", "PAUSED", "markers visible"), (12200, "S4", "screw_c", "GUIDING", "screw C"),
        (13400, "S4", "screw_c", "OBSERVED", "clear of screw C"), (14150, "S5", "screw_d", "GUIDING", "screw D"),
        (15100, "S5", "screw_d", "OBSERVED", "clear of screw D"),
        (16450, "S6", "complete", "AWAITING_CONFIRMATION", "Confirm"), (18500, "S6", "complete", "AWAITING_CONFIRMATION", "Confirm"),
    ]
    expected = [dict(index=t // 50, state=state, target=target, phase=phase, instruction_contains=part)
                for t, state, target, phase, part in checkpoints]
    return dict(config=config, snapshots=snapshots, rows=rows, expected=expected)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    output = parser.parse_args().output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(build_fixture(), indent=2, allow_nan=False), encoding="utf-8")
    print(output)
