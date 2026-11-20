from dataclasses import asdict
from types import SimpleNamespace

import pytest

from server.realtime import run_realtime_server as runtime
from server.realtime.harness_check import validate_config
from server.realtime.online_state_filter import OnlineStateFilter
from server.realtime.realtime_replay import replay_filter_inputs
from server.realtime.schemas import FramePacket
from server.realtime.yolo_realtime import YoloRealtimeResult


def test_runtime_preserves_original_yolo_time_and_does_not_relabel_missing_roi():
    packet = FramePacket(10, 2000, "fixture", None)
    marker = SimpleNamespace(marker_ok=True)
    roi = SimpleNamespace(enabled=True, reason="missing_homography")
    yolo = YoloRealtimeResult(True, available=True, frame_id=8, timestamp_ms=1800,
                              source_marker_ok=True, reason="ok")
    data = {"tool_score_a": 0.9}
    item = runtime.make_filter_input(packet, marker, roi, yolo, data)
    assert item == dict(frame_id=10, timestamp_ms=2000, marker_ok=True, features=data,
                        observation_id=8, observation_timestamp_ms=1800, evidence_valid=True,
                        roi_valid=False)
    assert not runtime.make_filter_input(packet, marker, roi,
        YoloRealtimeResult(True, reason="stale"), data)["evidence_valid"]


def test_timed_message_never_replaces_target_instruction_with_legacy_ack():
    f = OnlineStateFilter(guidance_policy="timed_v1", min_confidence=0.55)
    estimate = f.update(1, True, {"box_present_score": 0.9}, timestamp_ms=1000, roi_valid=True)
    estimate = f.update(2, True, {"box_present_score": 0.9}, timestamp_ms=1300, roi_valid=True)
    marker = SimpleNamespace(marker_status="OK", marker_count=6, warp_quality=0.9)
    packet = FramePacket(2, 1300, "fixture", None)
    message = runtime.make_guidance_message(packet, marker, estimate, session_id="s",
                                            legacy_action="Detected: unrelated old target").to_dict()
    assert message["current_state"] == "S1" and message["target"] == "lid"
    assert message["next_action"] == "Close the lid"
    assert message["guidance"]["acknowledgement"] == "Box placed"
    assert message["guidance"]["acknowledgement_remaining_ms"] == 1200


def test_timed_replay_preserves_ui_and_requires_source_time_fields():
    config = {"guidance_policy": "timed_v1", "min_confidence": 0.55}
    f = OnlineStateFilter.from_config(config)
    rows, want = [], []
    for i, t in enumerate((1000, 1100, 1300), 1):
        item = dict(frame_id=i, timestamp_ms=t, marker_ok=True, features={"box_present_score": 0.9},
                    observation_id=-1, observation_timestamp_ms=-1, evidence_valid=False, roi_valid=True)
        estimate = f.update(**item)
        rows.append({"filter_input": item})
        want.append(dict(frame_id=i, state=estimate.state, transition_event=estimate.transition_event,
                         target=estimate.target, next_action=estimate.next_action,
                         held_reason=estimate.held_reason, guidance=asdict(estimate.guidance)))
    assert replay_filter_inputs(rows, config) == want
    assert want[-1]["state"] == "S1" and want[-1]["target"] == "lid"
    for field in ("timestamp_ms", "observation_timestamp_ms", "roi_valid"):
        damaged = {"filter_input": {k: v for k, v in rows[0]["filter_input"].items() if k != field}}
        with pytest.raises(ValueError, match="filter_input"):
            replay_filter_inputs([damaged], config)


@pytest.mark.parametrize("state", [{"guidance_policy": "typo"},
    {"guidance_policy": "timed_v1", "timing": {"engage_ms": 0}},
    {"guidance_policy": "timed_v1", "dummy_auto_advance_frames": 1}])
def test_invalid_policy_fails_preflight_before_any_hardware(state):
    with pytest.raises(ValueError):
        validate_config({"state_filter": state})
