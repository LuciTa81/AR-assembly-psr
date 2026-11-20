import math
from argparse import Namespace

import pytest

from server.realtime.run_realtime_server import build_effective_config
from .test_guidance_recovery import loss
from .test_timed_guidance import arm, make_filter, tick, tool


def completed_recovery():
    return make_filter(timing={'resume_grace_ms': 600, 'completed_hold_resume_ms': 2000})


@pytest.mark.parametrize('kind', ['marker', 'missing', 'tip', 'pending'])
def test_completed_hold_survives_loss_but_requires_new_visible_release(kind):
    f = completed_recovery()
    arm(f)
    for t in range(1900, 2801, 100):
        result = loss(f, t, kind)
        assert result.state == 'S2' and result.guidance.phase == 'PAUSED'
    for t in range(2900, 3301, 100):
        result = tick(f, t, tool(score=.05))
        assert result.state == ('S3' if t == 3300 else 'S2')


def test_partial_hold_does_not_get_completed_hold_budget():
    f = completed_recovery()
    for t in range(1000, 1401, 100):
        tick(f, t)
    for t in range(1500, 2501, 100):
        loss(f, t)
    for t in range(2600, 3101, 100):
        assert tick(f, t, tool(score=.05)).state == 'S2'
    assert tick(f, 3200).guidance.phase == 'OBSERVING'


@pytest.mark.parametrize('recovered_at,expected', [(3800, 'OBSERVED'), (3801, 'GUIDING')])
def test_completed_hold_deadline_cannot_be_renewed_by_pauses(recovered_at, expected):
    f = completed_recovery()
    arm(f)
    for t in range(1900, 3800, 100):
        assert loss(f, t).state == 'S2'
    assert tick(f, recovered_at, tool(score=.05)).guidance.phase == expected


def test_cached_recovery_does_not_count_as_release():
    f = completed_recovery()
    arm(f)
    loss(f, 1900)
    for t in (2000, 2100):
        assert tick(f, t, observation=1800, observed_at=1800).guidance.phase == 'PAUSED'
    assert tick(f, 2200, tool(score=.05)).state == 'S2'
    for t in (2300, 2400, 2500, 2600):
        assert tick(f, t, tool(score=.05), observation=2200, observed_at=2200).state == 'S2'
    for t in range(2700, 3101, 100):
        assert tick(f, t, tool(score=.05)).state == ('S3' if t == 3100 else 'S2')


def test_partial_release_before_loss_is_discarded():
    f = completed_recovery()
    arm(f)
    for t in (1900, 2000):
        tick(f, t, tool(score=.05))
    loss(f, 2100)
    for t in range(2200, 2601, 100):
        assert tick(f, t, tool(score=.05)).state == ('S3' if t == 2600 else 'S2')


@pytest.mark.parametrize('data', [tool('b'), dict(tool(), tool_score_b=.9),
                                  dict(tool(), driver_count=2), dict(tool(), tool_tip_x=math.nan)])
def test_wrong_or_ambiguous_recovery_discards_completed_hold(data):
    f = completed_recovery()
    arm(f)
    loss(f, 1900)
    tick(f, 2000, data)
    for t in range(2100, 2701, 100):
        assert tick(f, t, tool(score=.05)).state == 'S2'
    assert tick(f, 2800).guidance.phase == 'OBSERVING'


def test_other_target_during_recovered_release_cannot_complete_old_screw():
    f = completed_recovery()
    arm(f)
    loss(f, 1900)
    for t in (2000, 2100):
        tick(f, t, tool(score=.05))
    tick(f, 2200, tool('b'))
    for t in range(2300, 3001, 100):
        assert tick(f, t, tool(score=.05)).state == 'S2'


def test_recovery_at_same_screw_restores_hold_not_partial_release():
    f = completed_recovery()
    arm(f)
    for t in range(1900, 2801, 100):
        loss(f, t)
    assert tick(f, 2900).guidance.phase == 'OBSERVED'
    for t in range(3000, 3401, 100):
        assert tick(f, t, tool(score=.05)).state == ('S3' if t == 3400 else 'S2')


def test_completed_hold_cannot_carry_into_next_screw():
    f = completed_recovery()
    arm(f)
    loss(f, 1900)
    for t in range(2000, 2401, 100):
        tick(f, t, tool(score=.05))
    assert f.state_index == 3
    loss(f, 2500)
    for t in range(2600, 3301, 100):
        assert tick(f, t, tool(score=.05)).state == 'S3'
    assert tick(f, 3400, tool('b')).guidance.phase == 'OBSERVING'


@pytest.mark.parametrize('observation,observed_at', [(2100, 2000), (2000, None),
                                                   (2000, 2100), (2000, 1799)])
def test_malformed_identity_discards_completed_hold(observation, observed_at):
    f = completed_recovery()
    arm(f)
    loss(f, 1900)
    result = f.update(2000, True, tool(score=.05), timestamp_ms=2000,
                      observation_id=observation, observation_timestamp_ms=observed_at)
    assert result.guidance.phase == 'PAUSED'
    for t in range(2100, 2801, 100):
        assert tick(f, t, tool(score=.05)).state == 'S2'


def test_completed_hold_option_alone_does_not_enable_partial_recovery():
    f = make_filter(timing={'completed_hold_resume_ms': 2000})
    for t in range(1000, 1401, 100):
        tick(f, t)
    loss(f, 1500)
    for t in range(1600, 2401, 100):
        assert tick(f, t).guidance.phase == ('OBSERVED' if t == 2400 else 'OBSERVING')


def test_return_to_current_screw_restarts_recovered_release():
    f = completed_recovery()
    arm(f)
    loss(f, 1900)
    for t in (2000, 2100, 2200):
        tick(f, t, tool(score=.05))
    assert tick(f, 2300).guidance.phase == 'OBSERVED'
    for t in range(2400, 2801, 100):
        assert tick(f, t, tool(score=.05)).state == ('S3' if t == 2800 else 'S2')


@pytest.mark.parametrize('value', [True, -1, 3001, .5])
def test_completed_hold_budget_is_bounded(value):
    with pytest.raises(ValueError):
        make_filter(timing={'completed_hold_resume_ms': value})


def test_completed_hold_mode_is_opt_in_and_limited_to_screw_flow():
    base = dict(yolo=dict(enabled=True), state_filter=dict(timing=dict(engage_ms=800)))
    args = dict(guidance_mode='hybrid', presentation_config='profiles.json')
    result = build_effective_config(base, Namespace(**args, completed_hold_resume_ms=2000))
    assert result['state_filter']['timing']['completed_hold_resume_ms'] == 2000
    assert base['state_filter']['timing'] == {'engage_ms': 800}
    assert 'completed_hold_resume_ms' not in build_effective_config(base, Namespace(**args))['state_filter']['timing']
    with pytest.raises(ValueError):
        build_effective_config(base, Namespace(guidance_mode='operator', completed_hold_resume_ms=2000))
