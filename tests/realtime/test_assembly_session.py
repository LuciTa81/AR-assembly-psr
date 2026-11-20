from argparse import Namespace
from dataclasses import asdict

import pytest

from server.realtime.assembly_session import AssemblySession
from server.realtime.online_state_filter import OnlineStateFilter
from server.realtime.run_realtime_server import build_effective_config
from .test_timed_guidance import tool


def settings():
    return dict(initial_state='S2', max_state='S6', min_confidence=.55, guidance_policy='timed_v1')


def inputs(t, target='a', score=.9, marker=True):
    return dict(frame_id=t, timestamp_ms=t, marker_ok=marker, features=tool(target, score),
                observation_id=t, observation_timestamp_ms=t, evidence_valid=True, roi_valid=False)


def session():
    return AssemblySession('test', OnlineStateFilter.from_config(settings()))


def start_screws(s):
    for t in (100, 200):
        s.request('test', s.metadata()['revision'])
        result = s.update(inputs(t), True)
        assert result.transition_event == 'operator_confirmation'
    assert result.state == 'S2'


def test_boundaries_are_explicit_and_screws_cannot_be_skipped():
    s = session()
    for t in (10, 20, 30):
        assert s.update(inputs(t), True).state == 'S0'
    for sid, revision in [('old', 0), ('test', True), ('test', 1)]:
        with pytest.raises(ValueError):
            s.request(sid, revision)
    start_screws(s)
    assert not s.metadata()['can_confirm']
    with pytest.raises(ValueError):
        s.request('test', s.metadata()['revision'])


@pytest.mark.parametrize('fresh,marker', [(False, True), (True, False)])
def test_initial_confirmations_need_fresh_tracked_input(fresh, marker):
    s = session()
    s.request('test', 0)
    with pytest.raises(ValueError):
        s.request('test', 0)
    assert s.update(inputs(100, marker=marker), fresh).state == 'S0'
    assert s.last_input == dict(confirmation_revision=0, fresh_input=fresh)
    assert s.update(inputs(200), True).state == 'S0'
    assert s.last_input['confirmation_revision'] is None


def complete_screws(s):
    rows = []
    t = 1000
    for target in 'abcd':
        for score, count in ((.9, 10), (.05, 5)):
            for _ in range(count):
                item = inputs(t, target, score)
                result = s.update(item, True)
                rows.append(dict(filter_input=item, assembly_input=s.last_input.copy(),
                                 state=result.state, transition_event=result.transition_event,
                                 target=result.target, next_action=result.next_action,
                                 held_reason=result.held_reason, guidance=asdict(result.guidance)))
                t += 100
    return result, rows


def test_same_timed_gate_reaches_final_but_never_auto_confirms():
    s = session()
    start_screws(s)
    result, rows = complete_screws(s)
    assert [r['transition_event'] for r in rows if r['transition_event']] == [
        'S2->S3', 'S3->S4', 'S4->S5', 'S5->S6']
    assert result.guidance.phase == 'AWAITING_CONFIRMATION'
    assert s.metadata()['can_confirm'] and not s.requires_tracking
    assert s.update(inputs(8000, marker=False), True).guidance.phase == 'AWAITING_CONFIRMATION'
    s.request('test', s.metadata()['revision'])
    assert s.update(inputs(8100, marker=False), False).guidance.phase != 'COMPLETED'
    s.request('test', s.metadata()['revision'])
    result = s.update(inputs(8200, marker=False), True)
    assert result.guidance.phase == 'COMPLETED'
    assert result.guidance.reason == 'operator_confirmation'
    assert result.transition_event == 'operator_confirmation'
    assert s.update(inputs(8300, marker=False), True).guidance.phase == 'COMPLETED'
    with pytest.raises(ValueError):
        s.request('test', s.metadata()['revision'])


def test_hybrid_config_reuses_metric_screw_settings_and_keeps_yolo():
    base = dict(source=dict(type='camera'), yolo=dict(enabled=True), roi=dict(enabled=True))
    result = build_effective_config(base, Namespace(guidance_mode='hybrid', presentation_config='profiles.json'))
    assert result['yolo']['enabled'] and not result['roi']['enabled']
    assert result['state_filter']['initial_state'] == 'S2'
    assert result['state_filter']['max_state'] == 'S6'
    assert not result['screw_auto_trial']
    assert base['roi']['enabled']


def test_hybrid_replay_uses_recorded_confirmation_inputs_not_output_states():
    from server.realtime.realtime_replay import replay_filter_inputs
    s = session()
    rows = []
    for t in (100, 200):
        s.request('test', s.metadata()['revision'])
        item = inputs(t)
        result = s.update(item, True)
        rows.append(dict(filter_input=item, assembly_input=s.last_input.copy(),
                         state=result.state, transition_event=result.transition_event))
    result, screw_rows = complete_screws(s)
    rows.extend(screw_rows)
    s.request('test', s.metadata()['revision'])
    item = inputs(9000, marker=False)
    result = s.update(item, True)
    rows.append(dict(filter_input=item, assembly_input=s.last_input.copy(),
                     state=result.state, transition_event=result.transition_event))
    predictions = replay_filter_inputs(rows, settings(), guidance_mode='hybrid')
    assert [(r['state'], r['transition_event']) for r in rows] == [
        (r['state'], r['transition_event']) for r in predictions]
    assert predictions[-1]['guidance']['phase'] == 'COMPLETED'
    del rows[0]['assembly_input']
    with pytest.raises(ValueError, match='confirmation'):
        replay_filter_inputs(rows, settings(), guidance_mode='hybrid')


@pytest.mark.parametrize('override', [dict(screw_auto_trial=True), dict(presentation_config=None),
                                    dict(save_frames=True), dict(host='0.0.0.0')])
def test_hybrid_config_rejects_ambiguous_or_unsafe_modes(override):
    args = dict(guidance_mode='hybrid', presentation_config='profiles.json')
    args.update(override)
    with pytest.raises(ValueError):
        build_effective_config(dict(yolo=dict(enabled=True)), Namespace(**args))


def test_final_http_confirmation_allows_lost_markers_but_not_stale_input():
    import json
    import time
    import urllib.error
    import urllib.request
    import numpy as np
    from server.realtime.overlay_http_server import OverlayHttpServer

    s = session()
    server = OverlayHttpServer('127.0.0.1', 0, 'web_overlay', operator=s)
    server.start()
    try:
        def post(marker, age=0):
            server.update(dict(session_id='test', frame_id=1, system_status='RUNNING',
                timestamp_ms=int(time.perf_counter()*1000)-age, marker_status=marker),
                np.zeros((8,8,3), np.uint8))
            request = urllib.request.Request(server.url + '/operator/confirm',
                json.dumps(dict(session_id='test', revision=s.metadata()['revision'])).encode(),
                headers={'Content-Type':'application/json', 'X-AR-Operator':'confirm', 'Origin':server.url})
            try:
                with urllib.request.urlopen(request, timeout=2) as response:
                    return response.status
            except urllib.error.HTTPError as error:
                return error.code
        assert post('LOST') == 409
        start_screws(s)
        assert post('OK') == 409
        complete_screws(s)
        assert post('LOST', age=1000) == 409
        assert post('LOST') == 202
        assert post('LOST') == 409
        assert s.update(inputs(9000, marker=False), True).guidance.phase == 'COMPLETED'
        assert post('OK') == 409
    finally:
        server.stop()
