import pytest
from argparse import Namespace

from .test_timed_guidance import arm, make_filter, tick, tool
from server.realtime.run_realtime_server import build_effective_config


def candidate():
    return make_filter(timing={'resume_grace_ms': 600, 'completed_hold_resume_ms': 2000,
                               'source_recovery_boundary': True})


@pytest.mark.parametrize('kind', ['missing', 'tip', 'multiple'])
def test_late_source_failure_does_not_discard_newer_inflight_evidence(kind):
    f = candidate()
    tick(f, 1000)
    tick(f, 1100)
    data = tool()
    if kind == 'missing':
        data.update(driver_visible=0, driver_count=0)
    elif kind == 'tip':
        data['tool_tip_source'] = 0
    else:
        data.update(driver_count=2, nested_driver_dedup=1)
    assert tick(f, 1400, data, observation=1200, observed_at=1200).guidance.phase == 'PAUSED'
    assert f.timed_gate.recovery_after_frame == 1200
    assert tick(f, 1450, data, observation=1200, observed_at=1200).guidance.phase == 'PAUSED'
    recovered = tick(f, 1500, observation=1300, observed_at=1300)
    assert recovered.guidance.phase == 'OBSERVING'
    assert recovered.state == 'S2'
    assert not recovered.transition_event
    assert f.timed_gate.started_at == (1300 if kind == 'multiple' else 1200)


def test_duplicate_gap_does_not_discard_newer_inflight_result_or_count_gap():
    f = candidate()
    tick(f, 1000)
    tick(f, 1100)
    assert tick(f, 1500, observation=1100, observed_at=1100).guidance.phase == 'PAUSED'
    assert f.timed_gate.recovery_after_frame == 1100
    assert tick(f, 1600, observation=1400, observed_at=1400).guidance.phase == 'OBSERVING'
    assert f.timed_gate.started_at == 1300


def test_marker_loss_still_blocks_all_sources_at_or_before_loss():
    f = candidate()
    arm(f)
    f.update(2100, False, tool(), timestamp_ms=2100,
             observation_id=1900, observation_timestamp_ms=1900)
    assert f.timed_gate.recovery_after_frame == 2100
    for t, source in ((2200, 2000), (2300, 2100)):
        assert tick(f, t, observation=source, observed_at=source).guidance.phase == 'PAUSED'
    assert tick(f, 2400, observation=2200, observed_at=2200).guidance.phase == 'OBSERVED'
    assert f.state_index == 2


def test_step_boundary_still_blocks_sources_for_previous_step():
    f = candidate()
    arm(f)
    for t in range(1900, 2301, 100):
        tick(f, t, tool(score=.05))
    assert f.state_index == 3
    assert f.timed_gate.recovery_after_frame == 2300
    assert tick(f, 2400, tool('b'), observation=2300, observed_at=2300).guidance.phase == 'PAUSED'


@pytest.mark.parametrize('source,source_time,valid', [(3000,1900,True), (1900,3000,True),
                                                     (1900,1900,False), (1000,1000,True)])
def test_malformed_or_stale_evidence_keeps_processing_boundary(source, source_time, valid):
    f = candidate()
    result = tick(f, 2200, observation=source, observed_at=source_time, evidence_valid=valid)
    assert result.guidance.phase == 'PAUSED'
    assert f.timed_gate.recovery_after_frame == 2200


def test_default_preserves_original_processing_boundary():
    f = make_filter()
    tick(f, 1400, dict(tool(), driver_visible=0, driver_count=0),
         observation=1200, observed_at=1200)
    assert f.timed_gate.recovery_after_frame == 1400
    assert tick(f, 1500, observation=1300, observed_at=1300).guidance.phase == 'PAUSED'


def test_completed_hold_still_needs_new_visible_withdrawal_after_source_loss():
    f = candidate()
    arm(f)
    missing = dict(tool(), driver_visible=0, driver_count=0)
    assert tick(f, 2200, missing, observation=2000, observed_at=2000).guidance.phase == 'PAUSED'
    assert tick(f, 2300, tool(score=.05), observation=2100, observed_at=2100).state == 'S2'
    for now in (2400, 2450):
        assert tick(f, now, tool(score=.05), observation=2100, observed_at=2100).state == 'S2'
    for now, source in ((2500, 2300), (2600, 2400)):
        assert tick(f, now, tool(score=.05), observation=source, observed_at=source).state == 'S2'
    assert tick(f, 2700, tool(score=.05), observation=2500, observed_at=2500).state == 'S3'


def test_completed_hold_cannot_resume_from_other_screw_after_source_loss():
    f = candidate()
    arm(f)
    tick(f, 2200, dict(tool(), driver_visible=0, driver_count=0),
         observation=2000, observed_at=2000)
    assert tick(f, 2300, tool('b'), observation=2100, observed_at=2100).state == 'S2'
    for now in range(2400, 3100, 100):
        assert tick(f, now, tool(score=.05), observation=now-200, observed_at=now-200).state == 'S2'


@pytest.mark.parametrize('value', [0, 1, 'true', None])
def test_source_boundary_requires_boolean(value):
    with pytest.raises(ValueError):
        make_filter(timing={'source_recovery_boundary': value})


def test_cli_candidate_is_explicit_and_does_not_mutate_successful_config():
    base = {'yolo': {'enabled': True}, 'state_filter': {'timing': {'resume_grace_ms': 600}}}
    args = dict(guidance_mode='hybrid', presentation_config='profiles.json')
    baseline = build_effective_config(base, Namespace(**args))
    trial = build_effective_config(base, Namespace(**args, source_recovery_boundary=True))
    assert trial['state_filter']['timing']['source_recovery_boundary'] is True
    assert baseline['state_filter']['timing'] == base['state_filter']['timing'] == {'resume_grace_ms': 600}
    with pytest.raises(ValueError):
        build_effective_config(base, Namespace(guidance_mode='operator', source_recovery_boundary=True))
