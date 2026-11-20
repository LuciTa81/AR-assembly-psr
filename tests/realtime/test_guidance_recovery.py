import math
from argparse import Namespace

import pytest

from .test_timed_guidance import arm, make_filter, tick, tool
from server.realtime.run_realtime_server import build_effective_config


def recovering():
    return make_filter(timing={'resume_grace_ms': 600})


def loss(f, t, kind='marker'):
    data = tool()
    if kind == 'missing':
        data.update(driver_count=0, driver_visible=0)
    if kind == 'tip':
        data['tool_tip_source'] = 0
    return f.update(t, kind != 'marker', data, timestamp_ms=t,
                    observation_id=t, observation_timestamp_ms=t, evidence_valid=kind != 'pending')


@pytest.mark.parametrize('kind', ['marker', 'missing', 'tip', 'pending'])
def test_short_loss_preserves_hold_but_does_not_count_the_gap(kind):
    f = recovering()
    for t in range(1000, 1401, 100):
        tick(f, t)
    assert loss(f, 1500, kind).guidance.phase == 'PAUSED'
    assert tick(f, 1800).guidance.phase == 'OBSERVING'
    for t in (1900, 2000, 2100):
        assert tick(f, t).guidance.phase == 'OBSERVING'
    assert tick(f, 2200).guidance.phase == 'OBSERVED'


def test_observed_engagement_resumes_but_release_starts_from_new_observations():
    f = recovering()
    arm(f)
    tick(f, 1900, tool(score=.05))
    tick(f, 2000, tool(score=.05))
    assert loss(f, 2100).guidance.phase == 'PAUSED'
    assert tick(f, 2300).guidance.phase == 'OBSERVED'
    for t in range(2400, 2801, 100):
        assert tick(f, t, tool(score=.05)).state == ('S3' if t == 2800 else 'S2')


@pytest.mark.parametrize('data', [tool(score=.05), tool('b'), dict(tool(), tool_score_b=.9),
                                  dict(tool(), driver_count=2), dict(tool(), tool_tip_x=math.nan)])
def test_invalid_or_nonmatching_recovery_cannot_finish_old_engagement(data):
    f = recovering()
    arm(f)
    loss(f, 1900)
    assert tick(f, 2000, data).state == 'S2'
    assert tick(f, 2100).guidance.phase == 'OBSERVING'
    for t in range(2200, 2801, 100):
        assert tick(f, t, tool(score=.05)).state == 'S2'


def test_multiple_short_pauses_exclude_each_gap_and_do_not_refresh_deadline():
    f = recovering()
    tick(f, 1000)
    tick(f, 1100)
    for t in (1200, 1300, 1400):
        loss(f, t)
    assert tick(f, 1500).guidance.phase == 'OBSERVING'
    tick(f, 1600)
    for t in (1700, 1800, 1900):
        loss(f, t)
    assert tick(f, 2000).guidance.phase == 'OBSERVING'
    for t in range(2100, 2600, 100):
        assert tick(f, t).guidance.phase == 'OBSERVING'
    assert tick(f, 2600).guidance.phase == 'OBSERVED'
    for t in range(2700, 3401, 100):
        loss(f, t)
    assert tick(f, 3500).guidance.phase == 'OBSERVING'


@pytest.mark.parametrize('recovered_at,expected', [(2400,'OBSERVED'), (2401,'OBSERVING')])
def test_deadline_is_bounded_from_last_valid_source(recovered_at, expected):
    f = recovering()
    arm(f)
    loss(f, 1900)
    assert tick(f, recovered_at).guidance.phase == expected


def test_cached_pre_loss_data_cannot_resume_or_extend_grace():
    f = recovering()
    arm(f)
    loss(f, 1900)
    for t in (2000, 2100, 2200, 2300, 2400):
        assert tick(f, t, observation=1850, observed_at=1850).guidance.phase == 'PAUSED'
    assert tick(f, 2500).guidance.phase == 'OBSERVING'


def test_silent_observation_gap_is_not_counted_as_work():
    f = recovering()
    tick(f, 1000)
    tick(f, 1100)
    assert tick(f, 1600).guidance.phase == 'OBSERVING'
    for t in range(1700, 2300, 100):
        assert tick(f, t).guidance.phase == 'OBSERVING'
    assert tick(f, 2300).guidance.phase == 'OBSERVED'


def test_late_receipt_cannot_recover_using_a_fresh_looking_source_time():
    f = recovering()
    arm(f)
    loss(f, 1900)
    assert tick(f, 2600, observation=2200, observed_at=2200).guidance.phase == 'OBSERVING'


def test_default_remains_immediate_reset():
    f = make_filter()
    arm(f)
    loss(f, 1900)
    assert tick(f, 2000).guidance.phase == 'OBSERVING'


@pytest.mark.parametrize('observation,observed_at', [(2100,2000), (2000,None), (2000,2100), (2000,1799)])
def test_malformed_identity_discards_suspended_work(observation, observed_at):
    f = recovering()
    arm(f)
    loss(f, 1900)
    result = f.update(2000, True, tool(), timestamp_ms=2000,
                      observation_id=observation, observation_timestamp_ms=observed_at)
    assert result.guidance.phase == 'PAUSED'
    assert tick(f, 2200).guidance.phase == 'OBSERVING'


def test_explicit_step_boundary_clears_suspended_work():
    f = recovering()
    arm(f)
    loss(f, 1900)
    f.timed_gate.reset_step(after_frame=1950)
    assert tick(f, 2000).guidance.phase == 'OBSERVING'


def test_cached_samples_after_recovery_cannot_fill_hold_time():
    f = recovering()
    for t in range(1000,1401,100):
        tick(f,t)
    loss(f,1500)
    assert tick(f,1800).guidance.phase == 'OBSERVING'
    for t in (1900,2000,2100):
        assert tick(f,t,observation=1800,observed_at=1800).guidance.phase == 'OBSERVING'
    assert tick(f,2200,observation=1800,observed_at=1800).guidance.phase == 'PAUSED'
    for t in (2300,2400,2500,2600):
        assert tick(f,t).guidance.phase == 'OBSERVING'
    assert tick(f,2700).guidance.phase == 'OBSERVED'


@pytest.mark.parametrize('value', [True, -1, 1001, .5])
def test_invalid_grace_is_rejected(value):
    with pytest.raises(ValueError):
        make_filter(timing={'resume_grace_ms':value})


def test_opt_in_configuration_does_not_change_baseline():
    base = dict(yolo=dict(enabled=True), state_filter=dict(timing=dict(engage_ms=800)))
    args = dict(guidance_mode='hybrid', presentation_config='profiles.json')
    assert build_effective_config(base, Namespace(**args))['state_filter']['timing'] == {'engage_ms':800}
    result = build_effective_config(base, Namespace(**args, screw_resume_ms=600))
    assert result['state_filter']['timing'] == {'engage_ms':800, 'resume_grace_ms':600}
    assert base['state_filter']['timing'] == {'engage_ms':800}
    with pytest.raises(ValueError):
        build_effective_config(base, Namespace(guidance_mode='operator', screw_resume_ms=600))
