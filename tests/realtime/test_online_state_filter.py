from server.realtime.online_state_filter import OnlineStateFilter


def screw_features():
    return {
        "require_yolo_for_screw": 1, "tool_score_a": 0.9, "tool_score_b": 0.9,
        "screw_min_confidence": 0.55, "screw_confirm_frames": 3,
        "screw_min_dwell_frames": 3,
    }


def make_filter():
    return OnlineStateFilter(initial_state="S2", min_confidence=0.55, min_dwell_frames=1)


def test_marker_gap_clears_unconfirmed_candidate():
    f = make_filter()
    features = screw_features()
    f.update(1, True, features, observation_id=1)
    f.update(2, True, features, observation_id=2)
    for frame_id in range(3, 103):
        f.update(frame_id, False, features)
    assert f.update(103, True, features, observation_id=103).state == "S2"


def test_duplicate_observation_cannot_advance_or_refresh_latch():
    f = make_filter()
    a = f.update(1, True, screw_features(), observation_id=1)
    for frame_id in range(2, 12):
        a = f.update(frame_id, True, screw_features(), observation_id=1)
    assert a.state == "S2"
    assert f.candidate_counts["a"] == 1
    assert f.frames_in_state == 1
    assert f.update(12, True, screw_features(), observation_id=12).state == "S2"
    assert f.update(13, True, screw_features(), observation_id=13).state == "S3"
    assert f.update(14, True, screw_features(), observation_id=13).state == "S3"
    assert f.frames_in_state == 0


def test_expired_evidence_clears_pending_not_confirmed_state():
    f = make_filter()
    for i in (1, 2):
        f.update(i, True, screw_features(), observation_id=i)
    result = f.update(3, True, screw_features(), observation_id=2, evidence_valid=False)
    assert result.state == "S2"
    assert not f.candidate_counts and not f.event_latches
    assert f.update(4, True, screw_features(), observation_id=4).state == "S2"


def test_missing_or_future_observation_id_cannot_advance_yolo_stage():
    f = make_filter()
    for frame_id in range(1, 8):
        result = f.update(frame_id, True, screw_features(), observation_id=100)
    assert result.state == "S2"


def test_roi_and_dummy_modes_remain_usable():
    f = OnlineStateFilter(min_dwell_frames=1, min_confidence=0.55)
    assert f.update(1, True, {"box_present_score": 0.8}, evidence_valid=False).state == "S1"
    assert f.update(2, True, {"lid_closed_score": 0.8}, evidence_valid=False).state == "S2"
    f = OnlineStateFilter(dummy_auto_advance_frames=2, min_dwell_frames=1)
    assert f.update(1, True).state == "S0"
    assert f.update(2, True).state == "S1"
