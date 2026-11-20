from dataclasses import asdict

import json
import pytest
import yaml

from server.realtime.realtime_replay import replay_filter_inputs, validate_session

from .test_timed_guidance import arm, make_filter, tick, tool


def pause(f, t):
    return f.update(t, False, tool(), timestamp_ms=t, observation_id=t, observation_timestamp_ms=t)


def progress(result):
    g = asdict(result.guidance)
    return g.get('hold_progress'), g.get('hold_remaining_ms')


def test_completed_hold_pause_has_bounded_remaining_time_and_recovers():
    f = make_filter(timing=dict(resume_grace_ms=600, completed_hold_resume_ms=2000))
    arm(f)
    assert progress(pause(f, 1900)) == ('retained', 1900)
    assert progress(pause(f, 2000)) == ('retained', 1800)
    result = tick(f, 2100)
    assert progress(result) == ('none', 0)
    assert result.guidance.phase == 'OBSERVED' and result.state == 'S2'


def test_expired_hold_requests_recheck_until_new_target_engagement():
    f = make_filter(timing=dict(completed_hold_resume_ms=2000))
    arm(f)
    pause(f, 1900)
    assert progress(pause(f, 3901)) == ('recheck', 0)
    assert progress(tick(f, 4001, tool(score=.05))) == ('recheck', 0)
    result = tick(f, 4101)
    assert progress(result) == ('none', 0)
    assert result.guidance.phase == 'OBSERVING' and result.state == 'S2'


def test_partial_hold_uses_partial_budget_not_completed_budget():
    f = make_filter(timing=dict(resume_grace_ms=600, completed_hold_resume_ms=2000))
    tick(f, 1000)
    tick(f, 1100)
    assert progress(pause(f, 1200)) == ('retained', 500)
    assert progress(pause(f, 1701)) == ('recheck', 0)


def test_ambiguity_clears_hold_without_changing_completed_steps():
    f = make_filter(timing=dict(completed_hold_resume_ms=2000))
    arm(f)
    r = tick(f, 1900, dict(tool(), driver_count=2, nested_driver_dedup=1.))
    assert progress(r) == ('recheck', 0)
    assert r.state == 'S2' and not r.transition_event
    assert progress(pause(f, 2000)) == ('recheck', 0)
    assert progress(tick(f, 2100)) == ('none', 0)


def test_recovery_at_other_target_requires_recheck():
    f = make_filter(timing=dict(completed_hold_resume_ms=2000))
    arm(f)
    pause(f, 1900)
    result = tick(f, 2000, tool('b'))
    assert progress(result) == ('recheck', 0)
    assert result.state == 'S2' and result.guidance.phase == 'GUIDING'


def test_startup_and_real_stage_transition_have_no_old_hold_claim():
    f = make_filter(timing=dict(completed_hold_resume_ms=2000))
    assert progress(pause(f, 900)) == ('none', 0)
    arm(f)
    for t in range(1900, 2301, 100):
        r = tick(f, t, tool(score=.05))
    assert r.state == 'S3' and progress(r) == ('none', 0)
    assert progress(pause(f, 2400)) == ('none', 0)
    assert progress(pause(make_filter(initial='S6'), 1000)) == ('none', 0)


@pytest.mark.parametrize('legacy', [False, True])
def test_replay_checks_new_metadata_but_preserves_old_log_contract(tmp_path, legacy):
    config = dict(guidance_policy='timed_v1', initial_state='S2')
    row = dict(filter_input=dict(frame_id=1, timestamp_ms=1000, marker_ok=False, features=tool(),
        observation_id=1, observation_timestamp_ms=1000, evidence_valid=True, roi_valid=False))
    row.update(replay_filter_inputs([row], config)[0])
    if legacy:
        row['guidance'].pop('hold_progress')
        row['guidance'].pop('hold_remaining_ms')
    (tmp_path/'config_used.yaml').write_text(yaml.safe_dump(dict(state_filter=config)))
    path = tmp_path/'results.jsonl'
    path.write_text(json.dumps(row))
    assert validate_session(tmp_path)['matched']
    if legacy:
        row['next_action'] = 'wrong action'
    else:
        row['guidance']['hold_progress'] = 'recheck'
    path.write_text(json.dumps(row))
    with pytest.raises(ValueError, match='mismatch'):
        validate_session(tmp_path)
