import argparse
import itertools
import json
from pathlib import Path

import pytest

from server.realtime import realtime_replay as replay
from server.realtime import run_realtime_server as runtime


def test_filter_replay_preserves_boundary_precision():
    inputs = [
        {"frame_id": 1, "marker_ok": True, "features": {"box_present_score": 0.5499996},
         "observation_id": -1, "evidence_valid": False},
        {"frame_id": 2, "marker_ok": True, "features": {"box_present_score": 0.55},
         "observation_id": -1, "evidence_valid": False},
    ]
    rows = [{"filter_input": item} for item in inputs]
    settings = {"initial_state": "S0", "min_confidence": 0.55, "min_dwell_frames": 1}
    want = [{"frame_id": 1, "state": "S0", "transition_event": ""},
            {"frame_id": 2, "state": "S1", "transition_event": "S0->S1"}]
    assert replay.replay_filter_inputs(iter(rows), settings) == want
    assert replay.replay_filter_inputs(json.loads(json.dumps(rows)), settings) == want


def test_old_logs_are_not_claimed_as_validated():
    with pytest.raises(ValueError, match="filter_input"):
        replay.replay_filter_inputs([{"frame_id": 1, "state": "S0"}], {})


def test_session_ids_do_not_collide_within_one_second():
    ids = {runtime.make_session_id() for _ in range(20)}
    assert len(ids) == 20


@pytest.mark.parametrize("time_column,path_column", [
    ("timestamp_ms", "saved_frame"),
    ("timestamp_unix_ms", "image_path"),
])
def test_finite_images_preserve_original_ids_and_timestamps(tmp_path, time_column, path_column):
    cv2 = pytest.importorskip("cv2", exc_type=ImportError)
    import numpy as np
    from server.realtime.frame_source import FrameSourceConfig, SessionFrameSource
    for name in ("a.png", "b.png"):
        ok, encoded = cv2.imencode(".png", np.zeros((8, 8, 3), dtype=np.uint8))
        assert ok
        (tmp_path / name).write_bytes(encoded.tobytes())
    (tmp_path / "frames.csv").write_text(
        f"frame_id,{time_column},{path_column}\n42,100,a.png\n46,600,b.png\n", encoding="utf-8")
    source = SessionFrameSource(FrameSourceConfig("session", session_path=str(tmp_path), replay_fps=10000))
    packets = list(itertools.islice(source, 3))
    assert len(packets) == 2
    assert [p.source_frame_id for p in packets] == [42, 46]
    assert [p.source_timestamp_ms for p in packets] == [100, 600]
    assert [p.frame_id for p in packets] == [1, 2]
    assert packets[0].timestamp_ms != 100


def test_empty_image_session_fails_without_loop(tmp_path):
    from server.realtime.frame_source import FrameSourceConfig, SessionFrameSource
    with pytest.raises(ValueError, match="No"):
        SessionFrameSource(FrameSourceConfig("session", session_path=str(tmp_path)))


def test_declared_missing_image_fails(tmp_path):
    from server.realtime.frame_source import FrameSourceConfig, SessionFrameSource
    (tmp_path / "frames.csv").write_text("frame_id,path\n1,missing.jpg\n")
    with pytest.raises(FileNotFoundError):
        SessionFrameSource(FrameSourceConfig("session", session_path=str(tmp_path)))


def test_validate_filter_uses_saved_effective_config_and_detects_mismatch(tmp_path):
    import yaml
    row = {"filter_input": {"frame_id": 1, "marker_ok": True,
                           "features": {"box_present_score": 0.6},
                           "observation_id": -1, "evidence_valid": False},
           "frame_id": 1, "state": "S1", "transition_event": "S0->S1"}
    (tmp_path / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    (tmp_path / "config_used.yaml").write_text(
        yaml.safe_dump({"state_filter": {"min_confidence": 0.55, "min_dwell_frames": 1}}))
    assert replay.validate_session(tmp_path)["matched"] is True
    row["state"] = "S0"
    (tmp_path / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mismatch"):
        replay.validate_session(tmp_path)
