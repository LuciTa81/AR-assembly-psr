import math
import json
from pathlib import Path

import pytest

from .test_completed_hold_checkpoint import candidate
from .test_release_absence import absent
from .test_timed_guidance import arm, tick, tool


def recovering(initial='S2', **timing):
    values = dict(source_recovery_boundary=True, release_absence_ms=600, release_resume_ms=2000)
    values.update(timing)
    return candidate(initial, **values)


def clear_then_missing(f, start=1900):
    tick(f, start, tool(score=.05))
    tick(f, start + 200, tool(score=.05))
    return tick(f, start + 400, absent(handle_visible=1, handle_count=1))


def test_short_missing_result_keeps_visible_release_time_but_excludes_gap():
    f = candidate(source_recovery_boundary=True, release_absence_ms=600, release_resume_ms=600)
    arm(f)
    tick(f, 1900, tool(score=.05))
    tick(f, 2100, tool(score=.05))
    result = tick(f, 2300, absent(handle_visible=1, handle_count=1))
    assert result.state == 'S2' and result.guidance.phase == 'PAUSED'
    assert tick(f, 2400, absent(), observation=2300, observed_at=2300).state == 'S2'
    # Only the 200 ms before loss count; the unseen 400 ms do not.
    assert tick(f, 2500, tool(score=.05)).state == 'S2'
    assert tick(f, 2600, tool(score=.05)).state == 'S2'
    assert tick(f, 2700, tool(score=.05)).state == 'S3'


@pytest.mark.parametrize('initial,target,next_state', [
    ('S2', 'a', 'S3'), ('S3', 'b', 'S4'), ('S4', 'c', 'S5'), ('S5', 'd', 'S6'),
])
def test_all_screws_resume_after_bounded_missing_without_counting_unseen_time(initial, target, next_state):
    f = recovering(initial)
    for t in range(1000, 1801, 100):
        tick(f, t, tool(target))
    tick(f, 1900, tool(score=.05))
    tick(f, 2100, tool(score=.05))
    tick(f, 2298, tool(score=.05))
    for t in range(2500, 3901, 200):
        assert tick(f, t, absent(handle_visible=1, handle_count=3)).state == initial
    assert tick(f, 4100, tool(score=.05)).state == initial
    assert tick(f, 4200, tool(score=.05)).state == next_state
    assert f.timed_gate._release_suspended is None
    assert tick(f, 4300, tool(score=.05)).state == next_state


def test_default_option_keeps_previous_release_restart_behavior():
    f = recovering(release_resume_ms=0)
    arm(f)
    clear_then_missing(f)
    for t in (2500, 2700, 2900):
        assert tick(f, t, tool(score=.05)).state == ('S3' if t == 2900 else 'S2')


@pytest.mark.parametrize('return_at,transition_at', [(4100, 4300), (4101, None)])
def test_deadline_uses_last_visible_source_and_is_not_extended_by_missing(return_at, transition_at):
    f = recovering()
    arm(f)
    clear_then_missing(f)
    for t in range(2500, 4001, 200):
        tick(f, t, absent(handle_visible=1, handle_count=1))
    for t in range(return_at, (transition_at or 4501) + 1, 100):
        assert tick(f, t, tool(score=.05)).state == ('S3' if t == transition_at else 'S2')
    if transition_at is None:
        # HOLD history survives, but its direct-away authorization has expired too.
        assert f.timed_gate.completed_hold and f.timed_gate._release_suspended is None
        assert tick(f, 4601).guidance.phase == 'OBSERVED'
        for t in range(4701, 5102, 100):
            assert tick(f, t, tool(score=.05)).state == ('S3' if t == 5101 else 'S2')


def test_absence_alone_cannot_finish_suspended_visible_release():
    f = recovering()
    arm(f)
    clear_then_missing(f)
    for t in range(2500, 6001, 200):
        assert tick(f, t, absent()).state == 'S2'
    assert f.timed_gate.completed_hold and f.timed_gate._release_suspended is None


@pytest.mark.parametrize('data', [tool(), tool('b'), tool(score=.22),
    dict(tool(), driver_count=2), dict(tool(), tool_tip_source=0),
    dict(tool(), tool_tip_x=math.nan)])
def test_contradictory_or_malformed_return_cancels_saved_release(data):
    f = recovering()
    arm(f)
    clear_then_missing(f)
    assert tick(f, 2500, data).state == 'S2'
    for t in (2700, 2800, 2900):
        assert tick(f, t, tool(score=.05)).state == 'S2'


def test_marker_loss_discards_release_but_not_completed_hold():
    f = recovering()
    arm(f)
    clear_then_missing(f)
    f.update(2400, False, tool(), timestamp_ms=2400, observation_id=2400,
             observation_timestamp_ms=2400, evidence_valid=True)
    assert f.timed_gate.completed_hold and f.timed_gate._release_suspended is None
    for t in (2500, 2700, 2900):
        assert tick(f, t, tool(score=.05)).state == ('S3' if t == 2900 else 'S2')


def test_frame_gap_cannot_restore_release_via_recent_but_delayed_source():
    f = recovering()
    arm(f)
    clear_then_missing(f)
    # Receipt gap is 500 ms, but source gap is 300 ms and its age is 200 ms.
    assert tick(f, 2800, tool(score=.05), observation=2600, observed_at=2600).state == 'S2'
    assert tick(f, 2900, tool(score=.05), observation=2700, observed_at=2700).state == 'S2'
    assert tick(f, 3000, tool(score=.05), observation=2800, observed_at=2800).state == 'S2'


def test_cached_clear_does_not_consume_new_time_or_restore_pending_release():
    f = recovering()
    arm(f)
    clear_then_missing(f)
    for t in (2400, 2500, 2600):
        assert tick(f, t, tool(score=.05), observation=2300, observed_at=2300).state == 'S2'
    assert tick(f, 2700, tool(score=.05)).state == 'S2'


@pytest.mark.parametrize('data', [tool(), tool('b'), tool(score=.22),
    dict(tool(), driver_count=2), dict(tool(), tool_tip_source=0),
    dict(tool(), tool_tip_x=math.nan)])
def test_pre_boundary_contradiction_discards_release_without_advancing(data):
    f = recovering()
    arm(f)
    tick(f, 1900, tool(score=.05))
    tick(f, 2100, tool(score=.05))
    tick(f, 2200, evidence_valid=False, observation=0, observed_at=0)
    assert tick(f, 2300, data, observation=2200, observed_at=2200).state == 'S2'
    assert f.timed_gate._release_suspended is None
    for t in (2400, 2600):
        assert tick(f, t, tool(score=.05)).state == 'S2'


def test_pre_boundary_clear_can_preserve_but_cannot_add_release_time():
    f = recovering()
    arm(f)
    tick(f, 1900, tool(score=.05))
    tick(f, 2100, tool(score=.05))
    tick(f, 2200, evidence_valid=False, observation=0, observed_at=0)
    assert tick(f, 2300, tool(score=.05), observation=2200, observed_at=2200).state == 'S2'
    assert f.timed_gate._release_suspended == (2100, 200)
    assert tick(f, 2400, tool(score=.05)).state == 'S2'
    assert tick(f, 2600, tool(score=.05)).state == 'S3'


def test_explicit_reset_and_new_session_cannot_reuse_release():
    f = recovering()
    arm(f)
    clear_then_missing(f)
    f.timed_gate.reset_step(after_frame=2300)
    assert f.timed_gate._release_suspended is None
    for state in (f, recovering()):
        for t in range(2400, 3001, 100):
            assert tick(state, t, tool(score=.05)).state == 'S2'


@pytest.mark.parametrize('value', [-1, 2001, True, 600.0, '600', None])
def test_release_recovery_option_is_strict_and_bounded(value):
    with pytest.raises(ValueError, match='release_resume_ms'):
        recovering(release_resume_ms=value)


@pytest.mark.parametrize('changes', [dict(retain_completed_hold=False), dict(completed_hold_resume_ms=1000)])
def test_release_recovery_cannot_outlive_completed_hold_authorization(changes):
    with pytest.raises(ValueError, match='release recovery'):
        recovering(**changes)


@pytest.mark.parametrize('budget,next_state', [(0, 'S2'), (600, 'S2'), (2000, 'S3')])
def test_recorded_a1118_advances_only_after_new_visible_clearance(budget, next_state):
    fixture = json.loads((Path(__file__).parent / 'fixtures' /
                          'release_recovery_a1118.json').read_text(encoding='utf-8'))
    f = recovering(release_resume_ms=budget)
    for item in fixture['inputs']:
        result = f.update(**item)
        assert result.state == (next_state if item['frame_id'] == 1118 else 'S2')
        if result.transition_event:
            assert item['evidence_valid'] and item['marker_ok']
            assert item['features']['driver_visible'] == item['features']['driver_count'] == 1
            assert max(item['features']['tool_score_' + n] for n in 'abcd') <= .15
