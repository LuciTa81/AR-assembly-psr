import json
import math
from pathlib import Path

import pytest

from .test_guidance_recovery import loss
from .test_timed_guidance import arm, make_filter, tick, tool


def candidate(initial='S2', **changes):
    timing = dict(resume_grace_ms=600, completed_hold_resume_ms=2000,
                  retain_neutral_recovery=True, retain_completed_hold=True)
    timing.update(changes)
    return make_filter(initial=initial, timing=timing)


@pytest.mark.parametrize('kind', ['marker', 'missing', 'tip', 'pending'])
@pytest.mark.parametrize('initial,target', [('S2', 'a'), ('S3', 'b'), ('S4', 'c'), ('S5', 'd')])
def test_completed_checkpoint_survives_timeout_without_repeating_hold(kind, initial, target):
    f = candidate(initial)
    for t in range(1000, 1801, 100):
        tick(f, t, tool(target))
    for t in range(1900, 5001, 100):
        result = loss(f, t, kind)
        assert result.state == initial and not result.transition_event
    assert f.timed_gate.completed_hold
    assert result.guidance.hold_progress == 'checkpoint'
    assert result.guidance.hold_remaining_ms == 0
    # Clear/neutral observations alone cannot authorize departure after a long blind gap.
    for t in range(5100, 6101, 100):
        result = tick(f, t, tool(target, score=.05 if t % 200 else .22))
        assert result.guidance.phase == 'PAUSED' and result.state == initial
        assert f.timed_gate.release_at is None
    assert tick(f, 6200, tool(target)).guidance.phase == 'OBSERVED'
    for t in range(6300, 6701, 100):
        result = tick(f, t, tool(target, score=.05))
        assert bool(result.transition_event) == (t == 6700)
    assert not f.timed_gate.completed_hold


def test_expired_checkpoint_never_accepts_absence_as_release():
    f = candidate(release_absence_ms=600)
    arm(f)
    tick(f, 1900, tool(score=.05))
    for t in range(2000, 5001, 100):
        loss(f, t)
    negative = dict(tool(score=.05), driver_count=0, driver_visible=0,
                    driver_count_raw=0, handle_visible=0, handle_count=0)
    for t in range(5100, 8001, 100):
        assert tick(f, t, negative).state == 'S2'
    assert f.timed_gate.completed_hold and not f.timed_gate.armed


def test_checkpoint_does_not_preserve_incomplete_hold():
    f = candidate()
    for t in range(1000, 1401, 100):
        tick(f, t)
    for t in range(1500, 3001, 100):
        loss(f, t)
    assert not f.timed_gate.completed_hold
    assert tick(f, 3100).guidance.phase == 'OBSERVING'


@pytest.mark.parametrize('bad', [dict(tool(), tool_tip_x=math.nan),
    dict(tool(), driver_count=math.nan), dict(tool(), yolo_tool_score_threshold=-1)])
def test_malformed_evidence_invalidates_checkpoint(bad):
    f = candidate()
    arm(f)
    for t in range(1900, 4001, 100):
        loss(f, t)
    tick(f, 4100, bad)
    assert not f.timed_gate.completed_hold
    assert tick(f, 4200).guidance.phase == 'OBSERVING'


@pytest.mark.parametrize('bad_field', [dict(tool_tip_x=math.nan),
    dict(yolo_tool_score_threshold=-1), dict(tool_score_a=math.nan),
    dict(tool_dist_a=-1), dict(tool_tip_source=99)])
def test_ambiguity_cannot_mask_malformed_payload(bad_field):
    f = candidate()
    arm(f)
    tick(f, 1900, dict(tool(), driver_count=2, **bad_field))
    assert not f.timed_gate.completed_hold


def test_ambiguity_cannot_restore_release_authorization_through_later_pauses_or_cache():
    f = candidate(release_absence_ms=600)
    arm(f)
    tick(f, 1900, dict(tool(), driver_count=2))
    loss(f, 2000)
    tick(f, 2100, observation=1900, observed_at=1900)
    assert not f.timed_gate.armed
    for t in (2700, 2800, 2900, 3000, 3100, 3200):
        assert tick(f, t, tool(score=.05)).state == 'S2'
    assert tick(f, 3300).guidance.phase == 'OBSERVED'


@pytest.mark.parametrize('ambiguous', [tool('b'), dict(tool(), tool_score_b=.9),
    dict(tool(), driver_count=2), dict(tool(), tool_tip_x=-1)])
@pytest.mark.parametrize('after_expiry', [False, True])
def test_visual_ambiguity_keeps_history_but_revokes_clear_authorization(ambiguous, after_expiry):
    f = candidate()
    arm(f)
    end = 4000 if after_expiry else 1900
    for t in range(1900, end + 1, 100):
        loss(f, t)
    result = tick(f, end + 100, ambiguous)
    assert result.guidance.phase == 'PAUSED'
    assert result.guidance.hold_progress == 'checkpoint'
    assert f.timed_gate.completed_hold and not f.timed_gate.armed
    assert f.timed_gate._suspended is None
    for t in range(end + 200, end + 1001, 100):
        assert tick(f, t, tool(score=.05)).state == 'S2'
    assert tick(f, end + 1100).guidance.phase == 'OBSERVED'
    for t in range(end + 1200, end + 1601, 100):
        assert bool(tick(f, t, tool(score=.05)).transition_event) == (t == end + 1600)


def test_reset_and_new_session_cannot_reuse_checkpoint():
    f = candidate()
    arm(f)
    assert not candidate().timed_gate.completed_hold
    f.timed_gate.reset_step(after_frame=1900)
    for t in range(2000, 2501, 100):
        assert tick(f, t, tool(score=.05)).state == 'S2'
    assert tick(f, 2600).guidance.phase == 'OBSERVING'


def test_one_completed_step_does_not_arm_next_screw():
    f = candidate()
    arm(f)
    for t in range(1900, 2301, 100):
        tick(f, t, tool(score=.05))
    assert f.state_index == 3
    assert not f.timed_gate.completed_hold
    for t in range(2400, 3001, 100):
        assert tick(f, t, tool(score=.05)).state == 'S3'
    assert tick(f, 3100, tool('b')).guidance.phase == 'OBSERVING'


def test_repeated_cached_source_cannot_reconfirm_checkpoint():
    f = candidate()
    arm(f)
    for t in range(1900, 4001, 100):
        loss(f, t)
    for t in range(4100, 4401, 100):
        result = tick(f, t, observation=4000, observed_at=4000)
        assert result.guidance.phase == 'PAUSED' and not f.timed_gate.armed
    assert tick(f, 4500).guidance.phase == 'OBSERVED'


def test_regressed_frame_invalidates_checkpoint():
    f = candidate()
    arm(f)
    tick(f, 1800)
    assert not f.timed_gate.completed_hold
    assert tick(f, 1900).guidance.phase == 'OBSERVING'


def test_stale_well_formed_result_keeps_history_but_needs_fresh_near():
    f = candidate()
    arm(f)
    # A delayed but otherwise consistent result is missing evidence, not undone work.
    result = tick(f, 4000, observation=2000, observed_at=2000)
    assert f.timed_gate.completed_hold and not f.timed_gate.armed
    assert result.guidance.hold_progress == 'checkpoint'
    # Even a new near result cannot reauthorize while older than the source-gap budget.
    result = tick(f, 4100, observation=3600, observed_at=3600)
    assert result.guidance.phase == 'PAUSED' and not f.timed_gate.armed
    assert tick(f, 4200).guidance.phase == 'OBSERVED'


def test_new_but_delayed_near_cannot_reauthorize_checkpoint():
    f = candidate()
    arm(f)
    tick(f, 1900, dict(tool(), driver_count=2))
    result = tick(f, 2500, observation=2000, observed_at=2000)
    assert result.guidance.phase == 'PAUSED' and not f.timed_gate.armed
    assert f.timed_gate.completed_hold
    assert tick(f, 2600).guidance.phase == 'OBSERVED'


def test_missing_tip_sentinels_are_not_malformed_payload():
    from server.realtime.yolo_realtime import empty_yolo_features
    f = candidate()
    arm(f)
    for t in range(1900, 4101, 100):
        tick(f, t, empty_yolo_features())
    assert f.timed_gate.completed_hold and not f.timed_gate.armed
    assert tick(f, 4200).guidance.phase == 'OBSERVED'


@pytest.mark.parametrize('observation,observed_at', [(5000, 2000), (2000, 5000), (1800, 1700)])
def test_invalid_source_identity_drops_checkpoint(observation, observed_at):
    f = candidate()
    arm(f)
    tick(f, 4000, observation=observation, observed_at=observed_at)
    assert not f.timed_gate.completed_hold


@pytest.mark.parametrize('value', [1, 0, None, 'true'])
def test_checkpoint_flag_is_strict(value):
    with pytest.raises(ValueError):
        candidate(retain_completed_hold=value)


def test_checkpoint_requires_bounded_direct_recovery():
    with pytest.raises(ValueError):
        candidate(completed_hold_resume_ms=0)


@pytest.mark.parametrize('enabled', [False, True])
def test_recorded_d219_expiry_preserves_checkpoint_only_when_enabled(enabled):
    fixture = json.loads((Path(__file__).parent / 'fixtures' /
                          'completed_hold_checkpoint_d219.json').read_text(encoding='utf-8'))
    f = candidate('S5', retain_completed_hold=enabled, source_recovery_boundary=True,
                  release_absence_ms=600)
    for item in fixture['inputs']:
        result = f.update(**item)
        assert not result.transition_event
    assert result.state == 'S5' and result.guidance.phase == 'PAUSED'
    assert result.guidance.hold_progress == ('checkpoint' if enabled else 'recheck')
    assert f.timed_gate.completed_hold is enabled
    assert not f.timed_gate.armed
