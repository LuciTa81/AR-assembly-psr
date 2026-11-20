from __future__ import annotations

import copy
import json
import time
import urllib.error
import urllib.request
from queue import Queue
from unittest.mock import patch

import cv2
import numpy as np
import pytest

from .test_workspace_projection import models
from .test_workspace_live_preview import profiles


def module():
    from server.realtime import display_observation_server
    return display_observation_server


def inputs():
    camera, workspace, _, rvec, tvec = models()
    session = {'session_id': 'test-session', 'camera_profile_id': camera.profile_id,
               'workspace_profile_id': workspace.profile_id, 'camera_profile_sha256': 'a' * 64,
               'workspace_profile_sha256': 'b' * 64}
    xyz = workspace.targets['A']
    pixel = cv2.projectPoints(np.array([xyz]), rvec, tvec, camera.matrix, camera.distortion)[0].reshape(2)
    packet = {'frame_id': 1, 'received_at': 10., 'analysis': {
        'status': 'tracking', 'reason': '', 'marker_ids': list(range(6)),
        'rvec': rvec.reshape(3).tolist(), 'tvec_mm': tvec.reshape(3).tolist(),
        'rms_px': .2, 'max_error_px': .3,
        'targets': {'A': {'visible': True, 'pixel': pixel.tolist()}}}}
    return camera, workspace, session, packet


def test_camera_targets_share_the_exact_a_pose_and_registered_workspace():
    c, w, s, p = inputs()
    result = module().make_observation(p, 10.01, s, c, w)
    assert result['status'] == 'tracking'
    assert [point['target_id'] for point in result['camera_targets']] == list('ABCD')
    rotation = cv2.Rodrigues(np.array(p['analysis']['rvec']))[0]
    translation = np.array(p['analysis']['tvec_mm'])
    for point in result['camera_targets']:
        np.testing.assert_allclose(point['camera_xyz_mm'],
                                   rotation @ w.targets[point['target_id']] + translation)
    assert result['camera_targets'][0]['camera_xyz_mm'] == result['camera_xyz_mm']
    json.dumps(result, allow_nan=False)


def test_selected_d_keeps_identity_world_camera_and_pixel_together():
    c, w, s, p = inputs()
    s['target_id'] = 'D'
    a = p['analysis']
    pixel = cv2.projectPoints(np.array([w.targets['D']]), np.array(a['rvec']),
                             np.array(a['tvec_mm']), c.matrix, c.distortion)[0].reshape(2)
    a['targets']['D'] = {'visible': True, 'pixel': pixel.tolist()}
    result = module().make_observation(p, 10.01, s, c, w)
    assert result['status'] == 'tracking' and result['target_id'] == 'D'
    np.testing.assert_allclose(result['world_xyz_mm'], w.targets['D'])
    np.testing.assert_allclose(result['target_pixel'], pixel)
    assert result['camera_xyz_mm'] == result['camera_targets'][3]['camera_xyz_mm']
    assert module().make_observation(None, 10.01, s, c, w)['target_id'] == 'D'


@pytest.mark.parametrize('target', ['E', '', 'AD', None])
def test_invalid_collection_target_rejected_before_camera_or_files(target, tmp_path):
    with patch.object(module(), 'load_profiles') as profiles_mock:
        with pytest.raises(ValueError, match='target_id'):
            module().run_collection(tmp_path/'camera', tmp_path/'workspace', 0, 1,
                                    root=tmp_path, target_id=target)
    profiles_mock.assert_not_called()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('kind', ['stale', 'rejected', 'missing'])
def test_unavailable_observations_never_publish_four_corner_positions(kind):
    c, w, s, p = inputs()
    now = 11. if kind == 'stale' else 10.01
    if kind == 'rejected':
        p['analysis'].update(status='pose_rejected', reason='need four markers')
    if kind == 'missing':
        p = None
    result = module().make_observation(p, now, s, c, w)
    assert result['status'] != 'tracking'
    assert 'camera_targets' not in result


@pytest.mark.parametrize('reason,code', [
    ('At least four visible measured markers required for pose', 'insufficient_markers'),
    ('Visible marker geometry is degenerate for IPPE; show a wider marker arrangement', 'marker_geometry'),
    ('Workspace pose solver returned no candidates', 'solver_failed'),
    ('Workspace pose solver returned only nonfinite candidates', 'solver_failed'),
    ('No physical workspace pose above the mat', 'pose_quality'),
    ('Workspace pose is ambiguous; use a more oblique or closer view', 'pose_quality'),
    ('Workspace pose reprojection error too high: RMS 5.00px, max 6.00px', 'pose_quality'),
    ('unrecognized error text', 'pose_unavailable'),
])
def test_pose_reason_code_is_shared_and_stale_overrides_rejection(reason, code):
    c, w, s, p = inputs()
    p['analysis'].update(status='pose_rejected', reason=reason)
    assert module().make_observation(p, 10.01, s, c, w)['reason_code'] == code
    assert module().make_observation(p, 11., s, c, w)['reason_code'] == 'stale'
    assert module().make_observation(None, 11., s, c, w)['reason_code'] == 'waiting'
    store = module().ObservationStore(s, c, w)
    store.update(p)
    store.invalidate('camera stopped')
    assert store.snapshot(10.01)['reason_code'] == 'camera_error'
    p['analysis'].update(status='tracking', reason='')
    assert module().make_observation(p, 10.01, s, c, w)['reason_code'] == 'tracking'


@pytest.mark.parametrize('ids,expected', [([], 0), ([0, 3], 2), (None, -1)])
def test_rejected_diagnostics_distinguish_unknown_from_zero(ids, expected):
    c, w, s, p = inputs()
    p['analysis'] = {'status': 'pose_rejected', 'reason': 'need four markers'}
    if ids is not None:
        p['analysis']['marker_ids'] = ids
    result = module().make_observation(p, 10.01, s, c, w)
    assert result['marker_count'] == expected
    assert result['marker_ids'] == ids
    assert result['status'] == 'pose_rejected' and 'camera_xyz_mm' not in result


def test_unknown_or_stale_diagnostics_do_not_report_current_zero():
    c, w, s, p = inputs()
    for packet, now in [(None, 10.), (p, 11.)]:
        result = module().make_observation(packet, now, s, c, w)
        assert result['marker_count'] == -1 and result['marker_ids'] is None


@pytest.mark.parametrize('failure', ['resolution', 'detector_error'])
def test_detection_not_performed_is_unknown_through_analysis_and_http_payload(failure):
    from server.realtime import workspace_live_preview as preview
    c, w, s, p = inputs()
    size = (360, 640) if failure == 'resolution' else (720, 1280)
    with patch.object(preview, 'detect_markers', side_effect=cv2.error('detector failed')) as detector:
        p['analysis'] = preview.analyze_frame(np.zeros((*size, 3), np.uint8), c, w)
    assert detector.call_count == (0 if failure == 'resolution' else 1)
    result = module().make_observation(p, 10.01, s, c, w)
    assert result['marker_ids'] is None and result['marker_count'] == -1
    p['image'] = np.zeros((*size, 3), np.uint8)
    _, state = preview.render_preview(p, 10.01, c.image_size)
    assert state['marker_ids'] is None


def test_store_never_copies_or_retains_preview_image():
    c, w, s, p = inputs()
    class Image:
        def __deepcopy__(self, _memo):
            raise AssertionError('image must not be copied into metadata store')
    p['image'] = Image()
    store = module().ObservationStore(s, c, w)
    store.update(p)
    assert 'image' not in store.packet
    assert store.snapshot(10.01)['marker_count'] == 6


def test_optional_pose_trace_links_numeric_evidence_without_images_or_secrets():
    c, w, s, p = inputs()
    p['analysis']['detected_corners_px'] = {'0': [[10., 20.], [30., 20.], [30., 40.], [10., 40.]]}
    p['analysis']['unrelated_secret'] = 'must-not-record'
    store = module().ObservationStore(s, c, w, record_pose_trace=True)
    with patch.object(module().time, 'perf_counter', return_value=10.01):
        store.update(p)
    row = store.pose_trace[0]
    assert row['schema_version'] == 'beast_display_pose_trace_v1'
    assert row['timestamp_clock'] == 'time.perf_counter'
    assert row['session_id'] == s['session_id'] and row['frame_id'] == 1
    assert row['camera_profile_sha256'] == s['camera_profile_sha256']
    assert row['received_at_monotonic'] == 10. and row['ingested_at_monotonic'] == 10.01
    assert row['camera_xyz_mm'] == store.snapshot(10.01)['camera_xyz_mm']
    assert row['detected_corners_px'] == p['analysis']['detected_corners_px']
    p['analysis']['detected_corners_px']['0'][0][0] = 999
    assert row['detected_corners_px']['0'][0][0] == 10.
    assert 'must-not-record' not in json.dumps(row, allow_nan=False)


@pytest.mark.parametrize('mode', ['rejected', 'stale', 'invalid_numeric'])
def test_pose_trace_keeps_rejected_evidence_and_never_promotes_it(mode):
    c, w, s, p = inputs()
    p['analysis']['detected_corners_px'] = {'0': [[10., 20.]] * 4}
    if mode == 'rejected':
        p['analysis'].update(status='pose_rejected', reason='No physical workspace pose')
    if mode == 'invalid_numeric':
        p['analysis']['rvec'][0] = float('nan')
        p['analysis']['detected_corners_px']['0'][0][0] = float('nan')
    now = 11. if mode == 'stale' else 10.01
    store = module().ObservationStore(s, c, w, record_pose_trace=True)
    with patch.object(module().time, 'perf_counter', return_value=now):
        store.update(p)
    row = store.pose_trace[0]
    assert row['status'] != 'tracking' and 'camera_xyz_mm' not in row
    assert row['analysis_status'] == p['analysis']['status']
    assert row['analysis_marker_ids'] == p['analysis']['marker_ids']
    if mode == 'invalid_numeric':
        assert row['detected_corners_px'] == {}
    else:
        assert row['detected_corners_px'] == p['analysis']['detected_corners_px']
    json.dumps(row, allow_nan=False)


def test_pose_trace_defaults_off_and_is_bounded_without_blocking_live_updates():
    c, w, s, p = inputs()
    store = module().ObservationStore(s, c, w)
    store.update(p)
    assert store.pose_trace is None
    store = module().ObservationStore(s, c, w, record_pose_trace=True)
    with patch.object(module(), 'MAX_POSE_TRACE_RECORDS', 1), \
         patch.object(module().time, 'perf_counter', return_value=10.01):
        store.update(p)
        p['frame_id'] = 2
        store.update(p)
    assert len(store.pose_trace) == 1 and store.trace_dropped == 1
    assert store.snapshot(10.01)['frame_id'] == 2


def test_numeric_trace_can_replay_pose_with_existing_profile_bound_solver():
    from server.realtime.tracking_report import replay_pose
    c, w, s, p = inputs()
    detections = models()[2]
    p['analysis']['detected_corners_px'] = {str(key): value.tolist() for key, value in detections.items()}
    store = module().ObservationStore(s, c, w, record_pose_trace=True)
    with patch.object(module().time, 'perf_counter', return_value=10.01):
        store.update(p)
    row = json.loads(json.dumps(store.pose_trace[0], allow_nan=False))
    replayed = replay_pose(row, c, w, s['camera_profile_sha256'], s['workspace_profile_sha256'])
    assert replayed['reason_code'] == 'tracking'
    np.testing.assert_allclose(replayed['targets']['A']['pixel'], row['target_pixel'], atol=.01)


@pytest.mark.parametrize('enabled', [False, True])
def test_pose_trace_cli_is_explicit_opt_in(enabled):
    argv = ['collection', '--camera-profile', 'camera.json', '--workspace-profile', 'workspace.json']
    if enabled:
        argv.append('--record-pose-trace')
    with patch('sys.argv', argv), patch.object(module(), 'run_collection') as run:
        module().main()
    assert run.call_args.kwargs['record_pose_trace'] is enabled


@pytest.mark.parametrize('record_pose_trace', [False, True])
@pytest.mark.parametrize('failure', [None, 'show', 'init'])
def test_same_source_preview_uses_one_worker_never_saves_and_always_cleans_up(tmp_path, failure, record_pose_trace):
    cam, board = profiles(tmp_path)
    events = []
    class Stop:
        flagged = False
        def set(self): self.flagged = True
    stop = Stop()
    class Worker:
        def start(self): events.append('start')
        def is_alive(self): return not stop.flagged
        def join(self, timeout): events.append('join')
    class Context:
        def Queue(self, maxsize): return Queue(maxsize)
        def Event(self): return stop
        def Process(self, **kwargs):
            events.append('process')
            assert kwargs['kwargs']['include_image'] is True
            p = inputs()[-1]
            p.update(received_at=time.perf_counter(), image=np.zeros((720, 1280, 3), np.uint8))
            kwargs['args'][0].put(p)
            return Worker()
    class Window:
        polls = 0
        def __init__(self, size, *, allow_save):
            assert allow_save is False and size == (1280, 720)
            if failure == 'init': raise RuntimeError('test init failure')
        def show(self, image):
            assert image.shape == (720, 1280, 3)
            events.append('show')
            if failure == 'show': raise RuntimeError('test show failure')
        def poll(self):
            self.polls += 1
            return 'save' if self.polls == 1 else 'quit'
        def close(self): events.append('close')
    with patch.object(module().mp, 'get_context', return_value=Context()), \
         patch.object(module(), 'PreviewWindow', Window):
        if failure:
            with pytest.raises(RuntimeError, match='test .* failure'):
                module().run_collection(cam, board, 1, 1., root=tmp_path / 'runs', preview=True,
                                        record_pose_trace=record_pose_trace)
        else:
            module().run_collection(cam, board, 1, 1., root=tmp_path / 'runs', preview=True,
                                    record_pose_trace=record_pose_trace)
    directory = next((tmp_path / 'runs').iterdir())
    summary = json.loads((directory / 'summary.json').read_text())
    config = json.loads((directory / 'client-config.json').read_text())
    assert events.count('process') == events.count('start') == 1 and stop.flagged
    assert summary['ending'] == ('error' if failure else 'user_exit')
    assert failure == 'init' or 'close' in events
    expected_files = {'client-config.json', 'summary.json'}
    if record_pose_trace:
        expected_files.add('pose-trace.jsonl')
        rows = [json.loads(line) for line in (directory / 'pose-trace.jsonl').read_text().splitlines()]
        assert len(rows) == (0 if failure == 'init' else 1)
        assert summary['pose_trace']['status'] == 'written'
        assert summary['pose_trace']['records'] == len(rows)
        assert config['token'] not in (directory / 'pose-trace.jsonl').read_text()
        assert all('image' not in row and row['session_id'] == config['session_id'] for row in rows)
    assert set(p.name for p in directory.iterdir()) == expected_files
    with pytest.raises(urllib.error.URLError):
        urllib.request.urlopen(config['observation_url'], timeout=1)


def test_observation_preserves_geometry_and_age():
    c, w, s, p = inputs()
    result = module().make_observation(p, 10.1, s, c, w)
    assert result['status'] == 'tracking' and result['age_ms'] == pytest.approx(100.)
    expected = cv2.Rodrigues(np.array(p['analysis']['rvec']))[0] @ w.targets['A'] + p['analysis']['tvec_mm']
    np.testing.assert_allclose(result['camera_xyz_mm'], expected)
    assert result['target_pixel'] == p['analysis']['targets']['A']['pixel']
    assert result['schema_version'] == 'beast_display_observation_v1'
    assert result['image_size'] == [1280, 720] and result['target_id'] == 'A'
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize('change', ['stale', 'future', 'nan', 'lost', 'behind', 'offimage', 'duplicate'])
def test_invalid_observation_never_exposes_old_target(change):
    c, w, s, p = inputs()
    if change == 'stale': p['received_at'] = 9.
    if change == 'future': p['received_at'] = 11.
    if change == 'nan': p['analysis']['rvec'][0] = float('nan')
    if change == 'lost': p['analysis'] = {'status': 'pose_rejected', 'reason': 'lost'}
    if change == 'behind': p['analysis']['tvec_mm'][2] = -10000.
    if change == 'offimage': p['analysis']['targets']['A'] = {'visible': False, 'pixel': None}
    if change == 'duplicate': p['analysis']['marker_ids'] = [0, 0, 2, 3]
    result = module().make_observation(p, 10.01, s, c, w)
    assert result['status'] != 'tracking'
    assert result.get('camera_xyz_mm') is None and result.get('target_pixel') is None
    json.dumps(result, allow_nan=False)


def test_store_invalidates_permanently_after_camera_error():
    c, w, s, p = inputs()
    store = module().ObservationStore(s, c, w)
    assert store.snapshot(10.)['status'] == 'waiting'
    store.update(p)
    assert store.snapshot(10.01)['status'] == 'tracking'
    assert store.snapshot(10.2)['status'] == 'stale'
    store.invalidate('camera stopped')
    store.update(p)
    assert store.snapshot(10.01)['status'] == 'camera_error'


def test_loopback_http_auth_routes_and_live_age():
    c, w, s, p = inputs()
    p['received_at'] = time.perf_counter()
    store = module().ObservationStore(s, c, w)
    store.update(p)
    server, thread = module().start_server(store, 'token-one')
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        assert server.server_address[0] == '127.0.0.1'
        for token in ['', 'other-session-token']:
            with pytest.raises(urllib.error.HTTPError) as exc:
                urllib.request.urlopen(urllib.request.Request(base + '/observation', headers={'Authorization': 'Bearer ' + token}), timeout=2)
            assert exc.value.code == 401
        headers = {'Authorization': 'Bearer token-one'}
        request = urllib.request.Request(base + '/observation', headers=headers)
        with urllib.request.urlopen(request, timeout=2) as response:
            first = json.load(response)
            assert response.headers.get('Access-Control-Allow-Origin') is None
        with urllib.request.urlopen(request, timeout=2) as response:
            second = json.load(response)
        assert second['age_ms'] >= first['age_ms'] and second['session_id'] == s['session_id']
        for path in ['/frame.jpg', '/state.json', '/observation?token=foo']:
            with pytest.raises(urllib.error.HTTPError) as exc:
                urllib.request.urlopen(urllib.request.Request(base + path, headers=headers), timeout=2)
            assert exc.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)
    assert not thread.is_alive()


def test_http_freshness_uses_same_precise_clock_as_source():
    c, w, s, p = inputs()
    p['received_at'] = 10.009
    store = module().ObservationStore(s, c, w, record_pose_trace=True)
    with patch.object(module().time, 'perf_counter', return_value=10.155), \
         patch.object(module().time, 'monotonic', return_value=10.172):
        store.update(p)
    assert store.pose_trace[0]['age_ms'] == pytest.approx(146.)
    server, thread = module().start_server(store, 'clock-test')
    request = urllib.request.Request(f'http://127.0.0.1:{server.server_port}/observation',
                                     headers={'Authorization': 'Bearer clock-test'})
    try:
        with patch.object(module().time, 'perf_counter', return_value=10.155) as clock, \
             patch.object(module().time, 'monotonic', return_value=10.172):
            with urllib.request.urlopen(request, timeout=2) as response:
                fresh = json.load(response)
            assert fresh['status'] == 'tracking' and fresh['age_ms'] == pytest.approx(146.)
            clock.return_value = 10.160
            with urllib.request.urlopen(request, timeout=2) as response:
                stale = json.load(response)
            assert stale['status'] == 'stale'
            assert 'camera_xyz_mm' not in stale
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)
    assert not thread.is_alive()


@pytest.mark.parametrize('record_pose_trace', [False, True])
@pytest.mark.parametrize('mode', ['normal', 'dead', 'error', 'stalled'])
def test_finite_runner_stops_owned_worker_and_writes_no_images(tmp_path, mode, record_pose_trace):
    cam, board = profiles(tmp_path)
    class Stop:
        flagged = False
        def set(self): self.flagged = True
    stop = Stop()
    class Worker:
        terminated = False
        started = False
        def start(self): self.started = True
        def is_alive(self):
            if mode == 'dead': return False
            return not self.terminated and (mode == 'stalled' or not stop.flagged)
        def join(self, timeout): pass
        def terminate(self): self.terminated = True
    worker = Worker()
    class Context:
        def Queue(self, maxsize): return Queue(maxsize)
        def Event(self): return stop
        def Process(self, **kwargs):
            assert kwargs['kwargs']['include_image'] is False
            if mode == 'error': kwargs['args'][-1].put({'reason': 'read failed'})
            return worker
    with patch.object(module().mp, 'get_context', return_value=Context()):
        directory = module().run_collection(cam, board, 1, 1., root=tmp_path / 'runs',
                                            record_pose_trace=record_pose_trace)
    config = json.loads((directory / 'client-config.json').read_text())
    summary = json.loads((directory / 'summary.json').read_text())
    assert config['session_id'] and config['token'] and config['observation_url'].startswith('http://127.0.0.1:')
    assert summary['ending'] == ('camera_error' if mode in ['dead', 'error'] else 'deadline')
    assert 'token' not in summary
    assert summary['pose_trace']['status'] == ('written' if record_pose_trace else 'disabled')
    assert (directory / 'pose-trace.jsonl').exists() is record_pose_trace
    assert worker.started and stop.flagged and not worker.is_alive()
    assert worker.terminated == (mode == 'stalled')
    assert not list(directory.rglob('*.png')) and not list(directory.rglob('*.jpg'))
    with pytest.raises(urllib.error.URLError):
        urllib.request.urlopen(config['observation_url'], timeout=1)


@pytest.mark.parametrize('seconds', [0, 301, float('nan'), float('inf')])
def test_duration_invalid_before_start(tmp_path, seconds):
    with pytest.raises(ValueError):
        module().run_collection(tmp_path / 'no', tmp_path / 'no', 1, seconds, root=tmp_path)


def test_three_depth_pairs_require_same_session_confirmed_and_increasing(tmp_path):
    def put(frame, z, session='test', confirmed=True):
        row = dict(schema_version='beast_tracked_alignment_diagnostic_v1', rendered_view='Both',
                   binocular_confirmed_by_user=confirmed, setup_id='fit',
                   observation=dict(target_id='C', session_id=session, frame_id=frame,
                                    status='tracking', camera_xyz_mm=[0, 0, z]))
        (tmp_path / f'diagnostic-frame-{frame}.json').write_text(json.dumps(row))
    put(8, 330)
    put(10, 335)
    put(20, 428)
    put(21, 500, session='old')
    put(22, 508, confirmed=False)
    check = module().saved_depths
    assert check(tmp_path, 'test', 'fit', 'C') == [330, 428]
    put(30, 500)
    assert check(tmp_path, 'test', 'fit', 'C') == [330, 428, 500]


@pytest.mark.parametrize('failure', ['dead', 'error'])
def test_get_checks_source_before_next_monitor_iteration(tmp_path, failure):
    cam, board = profiles(tmp_path)
    from threading import Event
    stop = Event()
    state = {'alive': True, 'checked': False}
    class Worker:
        def start(self): pass
        def is_alive(self): return state['alive'] and not stop.is_set()
        def join(self, timeout): pass
        def terminate(self): state['alive'] = False
    class Context:
        def Queue(self, maxsize): return Queue(maxsize)
        def Event(self): return stop
        def Process(self, **kwargs):
            packet = inputs()[-1]
            packet['received_at'] = time.perf_counter()
            kwargs['args'][0].put(packet)
            state['errors'] = kwargs['args'][-1]
            return Worker()
    def between_polls(_delay):
        if state['checked']: return
        state['checked'] = True
        if failure == 'dead': state['alive'] = False
        else: state['errors'].put({'reason': 'read failed'})
        config = json.loads(next((tmp_path / 'runs').glob('*/client-config.json')).read_text())
        request = urllib.request.Request(config['observation_url'], headers={'Authorization': 'Bearer ' + config['token']})
        with urllib.request.urlopen(request, timeout=2) as response:
            state['response'] = json.load(response)
    with patch.object(module().mp, 'get_context', return_value=Context()), \
         patch.object(module().time, 'sleep', side_effect=between_polls):
        module().run_collection(cam, board, 1, 1., root=tmp_path / 'runs')
    assert state['checked']
    assert state['response']['status'] == 'camera_error'
    assert state['response'].get('camera_xyz_mm') is None
