import json
import math
from pathlib import Path

import pytest

from .test_guidance_recovery import loss
from .test_timed_guidance import arm, make_filter, tick, tool


def candidate(**timing):
    return make_filter(timing=dict(resume_grace_ms=600, completed_hold_resume_ms=2000,
                                   retain_neutral_recovery=True, **timing))


@pytest.mark.parametrize('enabled', [False, True])
def test_d1364_retains_completed_hold_without_starting_release(enabled):
    saved = json.loads((Path(__file__).parent / 'fixtures' /
                        'neutral_hold_recovery_d1364.json').read_text(encoding='utf-8'))
    timing = dict(resume_grace_ms=600, completed_hold_resume_ms=2000,
                  source_recovery_boundary=True)
    if enabled:
        timing['retain_neutral_recovery'] = True
    f = make_filter(initial=saved['initial_state'], timing=timing)
    for item in saved['inputs']:
        result = f.update(**item)
        assert result.state == 'S5' and not result.transition_event
        if item['frame_id'] == 1363:
            assert f.timed_gate._suspended == (233134836, 4399, True)
        if item['frame_id'] == 1364:
            assert result.guidance.hold_progress == ('retained' if enabled else 'recheck')
            if enabled:
                assert result.guidance.hold_remaining_ms == 1200
                assert result.guidance.phase == 'PAUSED'
                assert f.timed_gate.release_at is None
        if enabled and item['frame_id'] == 1365:
            assert result.guidance.phase == 'OBSERVED'
            assert f.timed_gate.release_at == 233135636


@pytest.mark.parametrize('initial,target', [('S2','a'), ('S3','b'), ('S4','c'), ('S5','d')])
def test_neutral_recovery_keeps_completed_hold_for_every_target(initial, target):
    f = make_filter(initial=initial, timing=dict(completed_hold_resume_ms=2000,
                                                retain_neutral_recovery=True))
    for t in range(1000, 1801, 100):
        tick(f, t, tool(target))
    loss(f, 1900)
    for t in (2000, 2100):
        r = tick(f, t, tool(target, score=.22))
        assert r.guidance.hold_progress == 'retained'
        assert r.state == initial and not r.transition_event
    assert tick(f, 2200, tool(target)).guidance.phase == 'OBSERVED'


def test_partial_neutral_recovery_does_not_accrue_hold_time():
    f = candidate()
    for t in range(1000, 1401, 100):
        tick(f, t)
    loss(f, 1500)
    for t in (1600, 1700):
        r = tick(f, t, tool(score=.22))
        assert r.guidance.hold_progress == 'retained'
        assert r.state == 'S2' and not r.transition_event
    for t in range(1800, 2201, 100):
        assert tick(f, t).guidance.phase == ('OBSERVED' if t == 2200 else 'OBSERVING')


def test_neutral_recovery_requires_full_new_release_and_cannot_skip_next_step():
    f = candidate()
    arm(f)
    tick(f, 1900, tool(score=.05))
    tick(f, 2000, tool(score=.05))
    loss(f, 2100)
    for t in (2200, 2300):
        assert tick(f, t, tool(score=.22)).guidance.hold_progress == 'retained'
    for t in range(2400, 2801, 100):
        assert tick(f, t, tool(score=.05)).state == ('S3' if t == 2800 else 'S2')
    for t in range(2900, 3601, 100):
        assert tick(f, t, tool('b', score=.22)).state == 'S3'


@pytest.mark.parametrize('partial,last_valid,budget', [(False,1800,2000), (True,1400,600)])
def test_neutral_samples_never_extend_original_deadline(partial, last_valid, budget):
    f = candidate()
    for t in range(1000, last_valid + 1, 100):
        tick(f, t)
    loss(f, last_valid + 100)
    for t in range(last_valid + 200, last_valid + budget, 100):
        r = tick(f, t, tool(score=.22))
        assert r.guidance.hold_progress == 'retained'
        assert r.guidance.hold_remaining_ms == last_valid + budget - t
    r = tick(f, last_valid + budget + 1, tool(score=.22))
    assert r.guidance.hold_progress == 'recheck'
    assert f.timed_gate._suspended is None
    assert tick(f, last_valid + budget + 101).guidance.phase == 'OBSERVING'


def test_cached_neutral_data_cannot_extend_deadline_or_count_as_release():
    f = candidate()
    arm(f)
    loss(f, 1900)
    tick(f, 2000, tool(score=.22))
    for t in range(2100, 3901, 100):
        r = tick(f, t, tool(score=.05), observation=2000, observed_at=2000)
        assert r.state == 'S2' and not r.transition_event
    assert f.timed_gate._suspended is None
    for t in range(4000, 4501, 100):
        assert tick(f, t, tool(score=.05)).state == 'S2'


@pytest.mark.parametrize('bad', [
    tool('b'), dict(tool(score=.22), tool_score_b=.2),
    dict(tool(score=.22), driver_count=2),
    dict(tool(score=.22), tool_tip_x=math.nan),
])
def test_neutral_option_does_not_preserve_wrong_target_or_ambiguous_evidence(bad):
    f = candidate()
    arm(f)
    loss(f, 1900)
    tick(f, 2000, tool(score=.22))
    tick(f, 2100, bad)
    assert f.timed_gate._suspended is None
    for t in range(2200, 2701, 100):
        assert tick(f, t, tool(score=.05)).state == 'S2'


@pytest.mark.parametrize('kind', ['marker', 'missing', 'tip', 'pending'])
def test_another_loss_after_neutral_does_not_refresh_progress(kind):
    f = candidate()
    arm(f)
    loss(f, 1900)
    tick(f, 2000, tool(score=.22))
    for t in range(2100, 3901, 100):
        assert loss(f, t, kind).state == 'S2'
    assert f.timed_gate._suspended is None
    assert tick(f, 4000).guidance.phase == 'OBSERVING'


def test_explicit_reset_discards_neutral_recovery_progress():
    f = candidate()
    arm(f)
    loss(f, 1900)
    tick(f, 2000, tool(score=.22))
    f.timed_gate.reset_step(after_frame=2000)
    for t in range(2100, 2701, 100):
        assert tick(f, t, tool(score=.05)).state == 'S2'
    assert tick(f, 2800).guidance.phase == 'OBSERVING'


def test_neutral_option_cannot_create_progress_without_prior_hold():
    f = candidate()
    loss(f, 1000)
    for t in range(1100, 3101, 100):
        r = tick(f, t, tool(score=.22))
        assert r.guidance.hold_progress == 'none'
        assert r.state == 'S2'
    assert tick(f, 3200).guidance.phase == 'OBSERVING'


@pytest.mark.parametrize('value', [0, 1, None, 'true'])
def test_neutral_option_requires_boolean(value):
    with pytest.raises(ValueError, match='retain_neutral_recovery'):
        make_filter(timing=dict(retain_neutral_recovery=value))

