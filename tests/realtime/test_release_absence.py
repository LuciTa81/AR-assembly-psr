import math
from dataclasses import replace
from types import SimpleNamespace

import pytest

from server.realtime.run_realtime_server import make_filter_input
from server.realtime.yolo_realtime import empty_yolo_features
from .test_timed_guidance import arm, make_filter, tick, tool
from .test_yolo_realtime import analyzer_with_result


def candidate(initial="S2", **timing):
    return make_filter(initial, timing=dict(
        release_absence_ms=600, completed_hold_resume_ms=2000,
        source_recovery_boundary=True, **timing))


def absent(**changes):
    return dict(empty_yolo_features(0), driver_count_raw=0.0, **changes)


def test_default_missing_tool_after_clear_still_does_not_advance():
    f = make_filter(timing=dict(completed_hold_resume_ms=2000))
    arm(f)
    tick(f, 1900, tool(score=.05))
    for t in range(2000, 3001, 200):
        assert tick(f, t, absent()).state == "S2"


@pytest.mark.parametrize("initial,target,next_state", [
    ("S2", "a", "S3"), ("S3", "b", "S4"), ("S4", "c", "S5"), ("S5", "d", "S6"),
])
@pytest.mark.parametrize("interval", [100, 200, 300])
def test_clear_then_continuous_negative_results_advance_once(initial, target, next_state, interval):
    f = candidate(initial)
    for t in range(1000, 1801, 100):
        tick(f, t, tool(target))
    tick(f, 1900, tool(score=.05))
    events = []
    for t in range(2000, 2601, interval):
        result = tick(f, t, absent())
        assert result.state == (next_state if t == 2600 else initial)
        if result.transition_event:
            events.append((t, result.transition_event))
    assert events == [(2600, initial + "->" + next_state)]
    for t in range(2700, 3701, 100):
        assert tick(f, t, absent()).state == next_state
    if next_state == "S6":
        assert result.guidance.phase == "AWAITING_CONFIRMATION"


@pytest.mark.parametrize("setup", ["no_hold", "partial_hold", "near_only", "other_target", "neutral"])
def test_absence_requires_completed_hold_and_preceding_all_target_clear(setup):
    f = candidate()
    if setup == "partial_hold":
        for t in (1000, 1200, 1400):
            tick(f, t)
        tick(f, 1500, tool(score=.05))
    elif setup != "no_hold":
        arm(f)
        if setup == "other_target":
            tick(f, 1900, tool("b"))
        elif setup == "neutral":
            tick(f, 1900, tool(score=.22))
    for t in range(2000, 3001, 200):
        assert tick(f, t, absent()).state == "S2"


@pytest.mark.parametrize("bad", [
    dict(driver_count_raw=1), dict(handle_visible=1, handle_count=1),
    dict(driver_count=1), dict(driver_visible=1),
    dict(driver_count_raw=math.nan), dict(handle_count=-1),
    dict(handle_count=None), dict(driver_count_raw=False),
])
def test_partial_visibility_or_bad_counts_are_not_absence(bad):
    f = candidate()
    arm(f)
    tick(f, 1900, tool(score=.05))
    data = absent()
    data.update(bad)
    for t in range(2000, 3001, 200):
        assert tick(f, t, data).state == "S2"


def test_missing_raw_count_is_not_a_confirmed_negative_detection():
    f = candidate()
    arm(f)
    tick(f, 1900, tool(score=.05))
    for t in range(2000, 3001, 200):
        assert tick(f, t, empty_yolo_features()).state == "S2"


@pytest.mark.parametrize("kind", ["marker", "pending", "old", "future", "source_gap", "frame_gap"])
def test_interrupted_absence_cannot_complete_without_new_clear(kind):
    f = candidate()
    arm(f)
    tick(f, 1900, tool(score=.05))
    tick(f, 2000, absent())
    kwargs = dict(frame_id=2200, timestamp_ms=2200, marker_ok=True, features=absent(),
                  observation_id=2200, observation_timestamp_ms=2200, evidence_valid=True)
    if kind == "marker":
        kwargs["marker_ok"] = False
    elif kind == "pending":
        kwargs["evidence_valid"] = False
    elif kind == "old":
        kwargs["observation_timestamp_ms"] = 1200
    elif kind == "future":
        kwargs["observation_timestamp_ms"] = 2300
    elif kind == "source_gap":
        kwargs.update(frame_id=2500, timestamp_ms=2500, observation_id=2500, observation_timestamp_ms=2500)
    elif kind == "frame_gap":
        kwargs.update(frame_id=2500, timestamp_ms=2500)
    assert f.update(**kwargs).state == "S2"
    for t in range(2600, 3601, 200):
        assert tick(f, t, absent()).state == "S2"


def test_first_absence_must_follow_a_recent_clear_source():
    f = candidate()
    arm(f)
    tick(f, 1900, tool(score=.05))
    assert tick(f, 2000, tool(score=.05), observation=1900, observed_at=1900).state == "S2"
    assert tick(f, 2251, absent()).state == "S2"
    for t in range(2400, 3201, 200):
        assert tick(f, t, absent()).state == "S2"


def test_cached_absence_does_not_accrue_receive_time_or_change_features_in_place():
    f = candidate()
    arm(f)
    tick(f, 1900, tool(score=.05))
    tick(f, 2000, absent())
    for t in range(2100, 2801, 100):
        assert tick(f, t, absent(), observation=2000, observed_at=2000).state == "S2"
    for t in range(2900, 3501, 200):
        assert tick(f, t, absent()).state == "S2"


@pytest.mark.parametrize("data", [tool(), tool("b"), tool(score=.22),
                                  dict(tool(), driver_count=2), dict(tool(), tool_tip_source=0)])
def test_visible_or_uncertain_return_cancels_absence_evidence(data):
    f = candidate()
    arm(f)
    tick(f, 1900, tool(score=.05))
    tick(f, 2000, absent())
    tick(f, 2200, absent())
    assert tick(f, 2300, data).state == "S2"
    for t in range(2400, 3401, 200):
        assert tick(f, t, absent()).state == "S2"


def test_visible_far_return_requires_a_new_visible_release_interval():
    f = candidate()
    arm(f)
    tick(f, 1900, tool(score=.05))
    tick(f, 2000, absent())
    tick(f, 2200, absent())
    for t in (2300, 2500, 2700):
        assert tick(f, t, tool(score=.05)).state == ("S3" if t == 2700 else "S2")


def test_new_clear_after_cancelled_absence_can_start_a_new_attempt():
    f = candidate()
    arm(f)
    tick(f, 1900, tool(score=.05))
    tick(f, 2000, absent())
    tick(f, 2200)
    tick(f, 2300, tool(score=.05))
    for t in range(2400, 3001, 200):
        assert tick(f, t, absent()).state == ("S3" if t == 3000 else "S2")


@pytest.mark.parametrize("initial,target,other", [
    ("S2", "a", "b"), ("S3", "b", "c"), ("S4", "c", "d"), ("S5", "d", "a"),
])
def test_other_screw_reappearance_cannot_complete_previous_screw(initial, target, other):
    f = candidate(initial)
    for t in range(1000, 1801, 100):
        tick(f, t, tool(target))
    tick(f, 1900, tool(score=.05))
    for t in (2000, 2200):
        tick(f, t, absent())
    for t in range(2300, 3301, 200):
        assert tick(f, t, tool(other)).state == initial
    for t in range(3400, 4001, 200):
        assert tick(f, t, tool(score=.05)).state == initial


def test_neutral_reappearance_keeps_original_hold_deadline():
    f = candidate(retain_neutral_recovery=True)
    arm(f)
    tick(f, 1900, tool(score=.05))
    for t in (2000, 2200):
        tick(f, t, absent())
    for t in range(2300, 4101, 200):
        result = tick(f, t, tool(score=.22))
        assert result.state == "S2"
        if t == 2300:
            assert result.guidance.hold_progress == "retained"
            assert result.guidance.hold_remaining_ms == 1600
    for t in range(4200, 4801, 200):
        assert tick(f, t, tool(score=.05)).state == "S2"


@pytest.mark.parametrize("first_after_gap", ["neutral", "cached_negative"])
def test_frame_gap_during_absence_preserves_original_hold_deadline(first_after_gap):
    f = candidate(retain_neutral_recovery=True)
    arm(f)
    tick(f, 1900, tool(score=.05))
    tick(f, 2000, absent())
    tick(f, 2100, absent(), observation=2000, observed_at=2000)
    tick(f, 2200, absent(), observation=2100, observed_at=2100)
    if first_after_gap == "neutral":
        result = tick(f, 2600, tool(score=.22), observation=2200, observed_at=2200)
    else:
        result = tick(f, 2600, absent(), observation=2100, observed_at=2100)
    assert result.state == "S2"
    assert result.guidance.hold_progress == "retained"
    assert result.guidance.hold_remaining_ms == 1300
    for t in range(2700, 4001, 100):
        assert tick(f, t, tool(score=.22), observation=t - 100, observed_at=t - 100).state == "S2"
    for t in range(4100, 4501, 100):
        assert tick(f, t, tool(score=.05), observation=t - 100, observed_at=t - 100).state == "S2"


def test_explicit_reset_clears_absence_history():
    f = candidate()
    arm(f)
    tick(f, 1900, tool(score=.05))
    tick(f, 2000, absent())
    f.timed_gate.reset_step(after_frame=2000)
    for t in range(2200, 3201, 200):
        assert tick(f, t, absent()).state == "S2"


@pytest.mark.parametrize("reason,source_marker,advance", [
    ("ok", True, True), ("ok", False, False),
    ("warming_up", True, False), ("RuntimeError: inference failed", True, False),
    ("stale", True, False),
])
def test_server_accepts_only_completed_negative_detection_results(reason, source_marker, advance):
    f = candidate()
    arm(f)
    tick(f, 1900, tool(score=.05))
    analyzer = analyzer_with_result()
    for t in range(2000, 2601, 200):
        analyzer._result = replace(analyzer._result, frame_id=t, timestamp_ms=t,
                                  reason=reason, source_marker_ok=source_marker, features=absent())
        yolo = analyzer.get_result(t, now_ms=t)
        item = make_filter_input(SimpleNamespace(frame_id=t, timestamp_ms=t),
                                 SimpleNamespace(marker_ok=True),
                                 SimpleNamespace(enabled=True, reason="ok"), yolo, yolo.features)
        result = f.update(**item)
    assert result.state == ("S3" if advance else "S2")
    analyzer.close()


@pytest.mark.parametrize("value", [-1, 1, 399, 1001, True, 600.0, "600", None])
def test_absence_option_rejects_invalid_or_overaggressive_windows(value):
    with pytest.raises(ValueError, match="release_absence_ms"):
        make_filter(timing=dict(release_absence_ms=value))
