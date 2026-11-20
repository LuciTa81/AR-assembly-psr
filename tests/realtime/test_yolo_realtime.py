from dataclasses import replace

import numpy as np
import pytest


def analyzer_with_result():
    from server.realtime.yolo_realtime import RealtimeYoloAnalyzer, YoloRealtimeResult
    analyzer = RealtimeYoloAnalyzer(False, "", "", session_id="one", interval_frames=1)
    # Inject only the model-worker boundary; acceptance logic remains real.
    analyzer.enabled = analyzer.available = True
    analyzer._result = YoloRealtimeResult(
        enabled=True, available=True, reason="ok", frame_id=10,
        session_id="one", timestamp_ms=1000, source_marker_ok=True,
        features={"driver_visible": 1.0, "tool_score_a": 0.9},
    )
    return analyzer


@pytest.mark.parametrize("changes,current,now,min_id,reason", [
    ({}, 11, 1801, 0, "stale"),
    ({}, 11, 999, 0, "future_timestamp"),
    ({}, 9, 1100, 0, "future_frame"),
    ({"session_id": "old"}, 11, 1100, 0, "session_mismatch"),
    ({"source_marker_ok": False}, 11, 1100, 0, "source_marker_invalid"),
    ({}, 12, 1100, 11, "before_tracking_recovery"),
    ({"reason": "RuntimeError: inference failed"}, 11, 1100, 0, "RuntimeError: inference failed"),
])
def test_invalid_result_has_no_positive_evidence(changes, current, now, min_id, reason):
    analyzer = analyzer_with_result()
    analyzer._result = replace(analyzer._result, **changes)
    result = analyzer.get_result(current, now_ms=now, min_valid_frame_id=min_id)
    assert result.reason == reason
    assert result.features["driver_visible"] == 0
    assert result.features["tool_score_a"] == 0
    assert not result.evidence_valid


def test_valid_result_keeps_source_clock_without_mutating_cache():
    analyzer = analyzer_with_result()
    original = dict(analyzer._result.features)
    result = analyzer.get_result(11, now_ms=1800)
    assert result.evidence_valid
    assert result.timestamp_ms == 1000
    assert result.age_ms(1800) == 800
    assert result.features["driver_visible"] == 1
    result.features["driver_visible"] = 0
    assert analyzer._result.features == original


def test_submission_preserves_matching_frame_homography_and_time():
    analyzer = analyzer_with_result()
    frame = np.zeros((2, 2, 3), dtype=np.uint8)
    h = np.eye(3)
    analyzer.submit(12, frame, h, timestamp_ms=1100, marker_ok=False)
    assert analyzer._pending is None
    analyzer.submit(13, frame, h, timestamp_ms=1200, marker_ok=True)
    frame[:] = 255
    h[:] = 2
    frame_id, image, matrix, timestamp, valid = analyzer._pending
    assert (frame_id, timestamp, valid) == (13, 1200, True)
    assert image.sum() == 0
    assert np.array_equal(matrix, np.eye(3))


@pytest.mark.parametrize("polygon,expected", [
    ([[0, 0], [20, 0], [20, 100], [0, 100]], [[10, 0], [10, 100]]),
    ([[0, 0], [100, 0], [100, 20], [0, 20]], [[0, 10], [100, 10]]),
    ([[0, 0], [16, -12], [76, 68], [60, 80]], [[8, -6], [68, 74]]),
])
def test_tip_candidates_are_long_axis_ends_not_sides_of_driver(polygon, expected):
    from server.realtime.yolo_realtime import long_axis_endpoints
    actual = long_axis_endpoints(np.array(polygon, dtype=np.float32))
    assert np.allclose(sorted(p.tolist() for p in actual), sorted(expected), atol=1e-4)


@pytest.mark.parametrize("handle,expected", [
    ([[0, 0], [20, 0], [20, 20], [0, 20]], [10, 100]),
    ([[0, 80], [20, 80], [20, 100], [0, 100]], [10, 0]),
])
def test_tip_is_end_opposite_detected_handle(handle, expected):
    from server.realtime.yolo_realtime import handle_guided_tip
    driver = np.array([[0, 0], [20, 0], [20, 100], [0, 100]], dtype=np.float32)
    tip = handle_guided_tip(driver, np.array(handle, dtype=np.float32))
    assert np.allclose(tip, expected, atol=1e-4)
