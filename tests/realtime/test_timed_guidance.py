import math

import pytest

from server.realtime.online_state_filter import OnlineStateFilter


def make_filter(initial="S2", **kwargs):
    return OnlineStateFilter(initial_state=initial, min_confidence=0.55,
                             guidance_policy="timed_v1", **kwargs)


def tool(target="a", score=0.9):
    data = {
        "require_yolo_for_screw": 1, "driver_visible": 1, "driver_count": 1,
        "tool_tip_source": 2, "tool_tip_x": 100, "tool_tip_y": 100,
        "yolo_tool_score_threshold": 0.3, "yolo_target_dominance_ratio": 0.75,
        "screw_min_confidence": 0.55,
    }
    for name in "abcd":
        data[f"tool_score_{name}"] = score if name == target else 0.05
        data[f"tip_screw_score_{name}"] = 0.0
        data[f"tool_dist_{name}"] = 20.0 if name == target else 300.0
    return data


def tick(f, t, data=None, *, frame=None, observation=None, observed_at=None, **kwargs):
    frame = t if frame is None else frame
    return f.update(frame, True, tool() if data is None else data,
                    timestamp_ms=t, observation_id=frame if observation is None else observation,
                    observation_timestamp_ms=t if observed_at is None else observed_at, **kwargs)


def arm(f):
    for t in range(1000, 1801, 100):
        result = tick(f, t)
    assert result.state == "S2"
    assert result.guidance.phase == "OBSERVED"
    assert result.target == "screw_a"
    return result


def test_long_engagement_keeps_current_screw_until_positive_withdrawal():
    f = make_filter()
    for t in range(1000, 4001, 100):
        result = tick(f, t)
        assert result.state == "S2" and result.target == "screw_a"
        assert not result.transition_event
    assert result.guidance.phase == "OBSERVED"
    assert "screw A" in result.next_action


@pytest.mark.parametrize("interval", [50, 100, 200])
def test_source_time_not_number_of_frames_controls_engagement_and_release(interval):
    f = make_filter()
    for t in range(1000, 1801, interval):
        result = tick(f, t)
        assert result.state == "S2"
    assert result.guidance.phase == "OBSERVED"
    events = []
    for t in range(2000, 2401, interval):
        result = tick(f, t, tool(score=0.05))
        if result.transition_event:
            events.append((t, result.transition_event))
    assert events == [(2400, "S2->S3")]
    assert result.target == "screw_b" and result.next_action == "Fasten screw B"
    assert result.guidance.phase == "GUIDING"
    assert "A" in result.guidance.acknowledgement


def test_brief_touch_then_far_is_not_a_completed_interaction():
    f = make_filter()
    tick(f, 1000)
    tick(f, 1100)
    for t in range(1200, 3001, 100):
        result = tick(f, t, tool(score=0.05))
    assert result.state == "S2" and result.guidance.phase == "GUIDING"


@pytest.mark.parametrize("kind", ["wrong", "equal", "other_stronger", "hand_only"])
def test_other_target_ambiguous_scores_or_hand_changes_cannot_arm(kind):
    f = make_filter()
    data = tool("b") if kind == "wrong" else tool()
    if kind == "equal":
        data["tool_score_b"] = 0.9
    if kind == "other_stronger":
        data["tool_score_b"] = 0.95
    if kind == "hand_only":
        data.update(driver_visible=0, driver_count=0, screw_a_done_score=1,
                    screw_a_done_score_delta=1)
    for t in range(1000, 3001, 100):
        result = tick(f, t, data)
    for t in range(3100, 3601, 100):
        result = tick(f, t, tool(score=0.05))
    assert result.state == "S2"


@pytest.mark.parametrize("kind", ["no_driver", "no_tip", "two_drivers", "nan",
                                  "missing_score", "invalid", "old", "marker"])
def test_missing_or_invalid_evidence_is_not_withdrawal_and_disarms(kind):
    f = make_filter()
    arm(f)
    data = tool(score=0.05)
    if kind == "no_driver":
        data.update(driver_visible=0, driver_count=0)
    if kind == "no_tip":
        data["tool_tip_source"] = 0
    if kind == "two_drivers":
        data["driver_count"] = 2
    if kind == "nan":
        data["tool_tip_x"] = math.nan
    if kind == "missing_score":
        del data["tool_score_b"]
    for t in range(1900, 2501, 100):
        result = f.update(t, kind != "marker", data, timestamp_ms=t,
                          observation_id=t, observation_timestamp_ms=t - 900 if kind == "old" else t,
                          evidence_valid=kind != "invalid")
        assert result.state == "S2"
        assert result.guidance.phase == "PAUSED"
    for t in range(2600, 3101, 100):
        result = tick(f, t, tool(score=0.05))
    assert result.state == "S2", "Recovery away from A must not finish a pre-loss interaction"


def test_cached_yolo_result_and_long_gaps_never_accrue_engagement():
    f = make_filter()
    tick(f, 1000)
    for t in range(1100, 2301, 100):
        result = tick(f, t, observation=1000, observed_at=1000)
    assert result.state == "S2" and result.guidance.phase == "PAUSED"
    result = tick(f, 2400)
    assert result.guidance.phase == "OBSERVING"
    result = tick(f, 3000)
    assert result.guidance.phase == "OBSERVING", "Unobserved gaps are not work time"


def test_return_to_screw_cancels_partial_release():
    f = make_filter()
    arm(f)
    tick(f, 1900, tool(score=0.05))
    tick(f, 2200, tool(score=0.05))
    assert tick(f, 2300).state == "S2"
    for t in (2400, 2600, 2800):
        result = tick(f, t, tool(score=0.05))
        assert result.state == ("S3" if t == 2800 else "S2")


def test_duplicate_release_samples_do_not_count_elapsed_receive_time():
    f = make_filter()
    arm(f)
    tick(f, 1900, tool(score=0.05))
    for t in (2000, 2100, 2200):
        assert tick(f, t, tool(score=0.05), observation=1900, observed_at=1900).state == "S2"
    assert tick(f, 2300, tool(score=0.05)).state == "S2", "Gap clears armed state"


def test_loss_blocks_late_pre_loss_observation_even_if_it_is_new_to_filter():
    f = make_filter()
    arm(f)
    f.update(1900, False, tool(), timestamp_ms=1900, observation_id=1800, observation_timestamp_ms=1800)
    result = tick(f, 2000, observation=1850, observed_at=1850)
    assert result.guidance.phase == "PAUSED"
    assert tick(f, 2100).guidance.phase == "OBSERVING"


@pytest.mark.parametrize("bad", ["missing_time", "future_time", "older_time", "future_id"])
def test_bad_observation_identity_cannot_arm_or_be_repaired_in_place(bad):
    f = make_filter()
    tick(f, 1000)
    obs, stamp = (1200, 1100)
    if bad == "missing_time": stamp = None
    if bad == "future_time": stamp = 1300
    if bad == "older_time": stamp = 999
    if bad == "future_id": obs = 1300
    result = f.update(1200, True, tool(), timestamp_ms=1200, observation_id=obs, observation_timestamp_ms=stamp)
    assert result.guidance.phase == "PAUSED"
    result = tick(f, 1250, observation=1200, observed_at=1200)
    assert result.guidance.phase == "PAUSED"
    assert tick(f, 1300).guidance.phase == "OBSERVING"


def test_placement_dwell_is_continuous_and_does_not_require_yolo():
    f = make_filter("S0")
    for t, score in ((1000, 0.9), (1100, 0.9), (1200, 0.1),
                     (1300, 0.9), (1500, 0.9), (1600, 0.9)):
        result = tick(f, t, {"box_present_score": score}, evidence_valid=False, roi_valid=True)
        assert result.state == ("S1" if t == 1600 else "S0")
    for t in (1700, 1800, 2000):
        result = tick(f, t, {"lid_closed_score": 0.9}, evidence_valid=False, roi_valid=True)
    assert result.state == "S2"


def test_invalid_roi_cannot_advance_and_max_state_is_respected():
    f = make_filter("S0", max_state="S1")
    for t in (1000, 1200, 1300):
        assert tick(f, t, {"box_present_score": 0.9}, roi_valid=False).state == "S0"
    for t in (1400, 1600, 1700):
        result = tick(f, t, {"box_present_score": 0.9}, roi_valid=True)
    assert result.state == "S1"
    for t in (1800, 2000, 2200):
        assert tick(f, t, {"lid_closed_score": 0.9}, roi_valid=True).state == "S1"


def test_acknowledgement_expires_without_replacing_next_target_or_instruction():
    f = make_filter()
    arm(f)
    for t in (1900, 2100, 2300):
        result = tick(f, t, tool(score=0.05))
    assert result.state == "S3"
    for t in range(2400, 3601, 100):
        result = tick(f, t, tool(score=0.05))
        assert result.target == "screw_b" and result.next_action == "Fasten screw B"
    assert not result.guidance.acknowledgement
    assert result.guidance.acknowledgement_remaining_ms == 0


def test_terminal_stage_only_requests_user_confirmation():
    f = make_filter("S5")
    for t in range(1000, 1801, 100):
        tick(f, t, tool("d"))
    for t in (1900, 2100, 2300):
        result = tick(f, t, tool("d", score=0.05))
    assert result.state == "S6" and result.target == "complete"
    assert result.guidance.phase == "AWAITING_CONFIRMATION"
    assert result.next_action == "Confirm assembly sequence completion"


def test_async_observation_from_before_transition_cannot_start_next_screw():
    f = make_filter()
    arm(f)
    tick(f, 1900, tool(score=0.05))
    tick(f, 2100, tool(score=0.05))
    result = tick(f, 3000, tool(score=0.05), observation=2300, observed_at=2300)
    assert result.state == "S3"
    result = tick(f, 3050, tool("b"), observation=2900, observed_at=2900)
    assert result.guidance.phase == "PAUSED"
    assert tick(f, 3100, tool("b")).guidance.phase == "OBSERVING"


@pytest.mark.parametrize("delay", [1, 3])
@pytest.mark.parametrize("boundary", ["transition", "loss"])
def test_delayed_yolo_can_recover_without_chasing_a_moving_barrier(delay, boundary):
    f = make_filter("S1" if boundary == "transition" else "S2")
    if boundary == "transition":
        for frame in range(1, 5):
            result = tick(f, 1000 + frame * 100, {"lid_closed_score": 0.9},
                          frame=frame, roi_valid=True)
        assert result.state == "S2"
    else:
        f.update(4, False, tool(), timestamp_ms=1400,
                 observation_id=3, observation_timestamp_ms=1300)
    for frame in range(5, 22):
        source = frame - delay
        result = tick(f, 1000 + frame * 100, frame=frame,
                      observation=source, observed_at=1000 + source * 100)
        assert result.state == "S2"
        if source <= 4:
            assert result.guidance.phase == "PAUSED"
    assert result.guidance.phase == "OBSERVED"


@pytest.mark.parametrize("settings", [{"engage_ms": 0}, {"max_gap_ms": -1},
                                     {"release_score_max": math.nan}, {"ack_ms": 999999}])
def test_invalid_timing_configuration_is_rejected(settings):
    with pytest.raises(ValueError):
        make_filter(timing=settings)
