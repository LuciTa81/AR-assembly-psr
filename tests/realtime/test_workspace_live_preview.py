from __future__ import annotations

import hashlib
import json
import multiprocessing as mp
from queue import Queue
import time
from unittest.mock import patch

import numpy as np
import pytest

from .test_workspace_projection import camera_data, workspace_data, models


def module():
    from server.realtime import workspace_live_preview
    return workspace_live_preview


def profiles(tmp_path):
    cam = tmp_path / 'camera.json'
    cam.write_text(json.dumps(camera_data()), encoding='utf-8')
    data = workspace_data()
    data['target_registration'] = {
        'camera_profile_id': camera_data()['profile_id'],
        'camera_profile_sha256': hashlib.sha256(cam.read_bytes()).hexdigest(),
    }
    board = tmp_path / 'workspace.json'
    board.write_text(json.dumps(data), encoding='utf-8')
    return cam, board


def packet():
    return {'frame_id': 1, 'received_at': 10.,
            'image': np.zeros((720, 1280, 3), np.uint8),
            'analysis': {'status': 'tracking', 'reason': '', 'marker_ids': [0, 2, 3, 5],
                         'rms_px': .2, 'targets': {'A': {'visible': True, 'pixel': [500, 300]}}}}


def test_matching_camera_and_targets_load(tmp_path):
    cam, board = profiles(tmp_path)
    camera, workspace, metadata = module().load_profiles(cam, board)
    assert set(workspace.targets) == set('ABCD')
    assert camera.image_size == (1280, 720)
    assert metadata['camera_profile_sha256'] == hashlib.sha256(cam.read_bytes()).hexdigest()


@pytest.mark.parametrize('change', ['hash', 'id', 'missing_binding', 'targets'])
def test_changed_or_unregistered_profile_rejected(tmp_path, change):
    cam, board = profiles(tmp_path)
    data = json.loads(board.read_text())
    if change == 'hash':
        cam.write_text(cam.read_text() + ' ')
    elif change == 'id':
        data['target_registration']['camera_profile_id'] = 'other'
    elif change == 'missing_binding':
        del data['target_registration']
    else:
        data['targets_mm'].pop('D')
    board.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError):
        module().load_profiles(cam, board)


def test_current_frame_pose_uses_real_geometry_and_no_previous_pose():
    camera, workspace, detections, _, _ = models()
    ids = np.array(list(detections)).reshape(-1, 1)
    frame = np.zeros((720, 1280, 3), np.uint8)
    with patch.object(module(), 'detect_markers', return_value=(detections, [], ids)):
        result = module().analyze_frame(frame, camera, workspace)
    assert result['status'] == 'tracking'
    assert result['rms_px'] < .001
    assert set(result['detected_corners_px']) == {str(key) for key in detections}
    assert result['detected_corners_px']['0'] == detections[0].tolist()
    assert all(target['visible'] for target in result['targets'].values())
    with patch.object(module(), 'detect_markers', return_value=({}, [], None)):
        lost = module().analyze_frame(frame, camera, workspace)
    assert lost['status'] == 'pose_rejected'
    assert lost['marker_ids'] == []
    assert lost['targets'] == {}
    assert lost['detected_corners_px'] == {}


def test_duplicate_marker_is_rejected():
    camera, workspace, detections, _, _ = models()
    with patch.object(module(), 'detect_markers', return_value=(detections, [], np.array([0, 0, 2, 3, 5]))):
        result = module().analyze_frame(np.zeros((720, 1280, 3), np.uint8), camera, workspace)
    assert result['targets'] == {}
    assert 'duplicate' in result['reason']
    assert result['detected_corners_px'] == {}


def test_wrong_resolution_rejected_before_detection():
    camera, workspace, _, _, _ = models()
    result = module().analyze_frame(np.zeros((360, 640, 3), np.uint8), camera, workspace)
    assert result['status'] == 'pose_rejected'
    assert 'resolution' in result['reason']


@pytest.mark.parametrize('now,status', [(10.01, 'tracking'), (10.151, 'stale'), (9.99, 'stale')])
def test_render_never_extends_source_timestamp(now, status):
    item = packet()
    image, state = module().render_preview(item, now, (1280, 720))
    assert state['status'] == status
    assert state['frame_id'] == 1
    green = (image[:, :, 1] > 150) & (image[:, :, 0] < 80) & (image[:, :, 2] < 80)
    assert bool(green.any()) == (status == 'tracking')
    assert not item['image'].any()


def test_waiting_and_lost_have_no_targets():
    _, state = module().render_preview(None, 0., (1280, 720))
    assert state['status'] == 'waiting'
    item = packet()
    item['analysis'] = {'status': 'pose_rejected', 'reason': 'missing markers', 'targets': {}}
    image, state = module().render_preview(item, 10.01, (1280, 720))
    assert state['status'] == 'pose_rejected'
    assert not image[100:].any()


def test_diagnostic_banner_can_be_hidden_without_cropping_or_changing_state():
    item = packet()
    item['image'][:] = (60, 80, 100)
    diagnostic, diagnostic_state = module().render_preview(item, 10.01, (1280, 720))
    clean, clean_state = module().render_preview(item, 10.01, (1280, 720), diagnostic_banner=False)
    assert clean.shape == diagnostic.shape == item['image'].shape
    assert np.array_equal(clean[:41], item['image'][:41])
    assert not np.array_equal(diagnostic[:41], clean[:41])
    assert np.array_equal(diagnostic[41:], clean[41:])
    assert clean_state == diagnostic_state
    assert np.all(item['image'] == (60, 80, 100))


def test_queue_keeps_newest_available_packet():
    queue = Queue(maxsize=1)
    module().offer_latest(queue, 1)
    module().offer_latest(queue, 2)
    assert module().take_latest(queue) == 2
    assert module().take_latest(queue) is None


def test_worker_releases_camera_on_read_failure(tmp_path):
    cam, board = profiles(tmp_path)
    camera, workspace, _ = module().load_profiles(cam, board)
    class Capture:
        released = False
        def isOpened(self): return True
        def set(self, *_args): pass
        def read(self): return False, None
        def release(self): self.released = True
    capture = Capture()
    class Stop:
        def is_set(self): return False
    queue, errors = Queue(maxsize=1), Queue(maxsize=1)
    with patch.object(module().cv2, 'VideoCapture', return_value=capture):
        module().camera_worker(queue, Stop(), 1, camera, workspace, errors=errors)
    assert module().take_latest(errors)['reason'] == 'Camera read failed'
    assert capture.released


def test_worker_receive_clock_does_not_round_fresh_frame_to_stale():
    from threading import Event
    camera, workspace, _, _, _ = models()
    stop = Event()
    class Capture:
        def isOpened(self): return True
        def set(self, *_args): pass
        def read(self):
            stop.set()
            return True, np.zeros((720, 1280, 3), np.uint8)
        def release(self): pass
    queue, errors = Queue(1), Queue(1)
    with patch.object(module().cv2, 'VideoCapture', return_value=Capture()), \
         patch.object(module(), 'analyze_frame', return_value=packet()['analysis']), \
         patch.object(module().time, 'monotonic', return_value=10.), \
         patch.object(module().time, 'perf_counter', return_value=10.009):
        module().camera_worker(queue, stop, 0, camera, workspace, errors)
    item = module().take_latest(queue)
    assert item['received_at'] == 10.009
    _, fresh = module().render_preview(item, 10.155, camera.image_size)
    assert fresh['status'] == 'tracking' and fresh['age_ms'] == pytest.approx(146.)
    _, expired = module().render_preview(item, 10.160, camera.image_size)
    assert expired['status'] == 'stale' and expired['targets'] == {}
    _, future = module().render_preview(item, 10.008, camera.image_size)
    assert future['status'] == 'stale'


@pytest.mark.parametrize('include_image', [True, False])
@pytest.mark.parametrize('corner_refinement', ['subpix', 'apriltag'])
def test_camera_worker_optional_metadata_only(include_image, corner_refinement):
    camera, workspace, detections, _, _ = models()
    from threading import Event
    stop = Event()
    class Capture:
        released = False
        def isOpened(self): return True
        def set(self, *_args): pass
        def read(self):
            stop.set()
            return True, np.zeros((720, 1280, 3), np.uint8)
        def release(self): self.released = True
    capture = Capture()
    queue, errors = Queue(1), Queue(1)
    ids = np.array(list(detections)).reshape(-1, 1)
    with patch.object(module().cv2, 'VideoCapture', return_value=capture), \
         patch.object(module(), 'detect_markers', return_value=(detections, [], ids)) as detector:
        module().camera_worker(queue, stop, 1, camera, workspace, errors,
                               include_image=include_image, corner_refinement=corner_refinement)
    assert detector.call_args.kwargs['corner_refinement'] == corner_refinement
    result = module().take_latest(queue)
    assert ('image' in result) == include_image
    assert result['frame_id'] == 1 and result['received_at'] > 0
    assert result['analysis']['status'] == 'tracking'
    assert result['analysis']['corner_refinement'] == corner_refinement
    assert capture.released and errors.empty()


def test_shutdown_terminates_only_owned_stalled_process():
    class Worker:
        terminated = False
        def join(self, timeout): pass
        def is_alive(self): return not self.terminated
        def terminate(self): self.terminated = True
    class Stop:
        set_called = False
        def set(self): self.set_called = True
    worker, stop = Worker(), Stop()
    module().stop_worker(worker, stop)
    assert worker.terminated and stop.set_called


def test_saving_evidence_does_not_overwrite_and_keeps_frame_id(tmp_path):
    item = packet()
    visual, state = module().render_preview(item, 10.01, (1280, 720))
    folder = module().save_sample(tmp_path, item, visual, state)
    assert (folder / 'raw.png').exists()
    assert (folder / 'preview.png').exists()
    assert json.loads((folder / 'report.json').read_text())['frame_id'] == 1
    with pytest.raises(FileExistsError):
        module().save_sample(tmp_path, item, visual, state)


def _synthetic_packets(queue, stop):
    item = packet()
    item['received_at'] = time.perf_counter()
    module().offer_latest(queue, item)
    stop.wait(10)


def test_spawn_transport_expires_a_stalled_source_without_hardware():
    context = mp.get_context('spawn')
    queue, stop = context.Queue(maxsize=1), context.Event()
    worker = context.Process(target=_synthetic_packets, args=(queue, stop))
    worker.start()
    try:
        deadline, item = time.monotonic() + 8, None
        while time.monotonic() < deadline and item is None:
            item = module().take_latest(queue)
            time.sleep(.005)
        assert item is not None
        _, current = module().render_preview(item, item['received_at'] + .01, (1280, 720))
        image, stale = module().render_preview(item, item['received_at'] + .2, (1280, 720))
        assert current['status'] == 'tracking'
        assert stale['status'] == 'stale' and stale['targets'] == {}
        assert not image[100:].any()
    finally:
        module().stop_worker(worker, stop)
        queue.close()
        queue.join_thread()
    assert not worker.is_alive()


def test_preview_error_is_not_recorded_as_successful_duration(tmp_path):
    cam, board = profiles(tmp_path)
    context = mp.get_context('spawn')
    class Worker:
        def start(self): pass
        def join(self, timeout): pass
        def is_alive(self): return False
    class Context:
        def Queue(self, maxsize): return context.Queue(maxsize=maxsize)
        def Event(self): return context.Event()
        def Process(self, **kwargs):
            return Worker() if kwargs['target'] == module().camera_worker else context.Process(**kwargs)
    with patch.object(module(), 'local_root', return_value=tmp_path), \
         patch.object(module().mp, 'get_context', return_value=Context()), \
         patch.object(module(), 'PreviewWindow', side_effect=RuntimeError('GUI unavailable')):
        with pytest.raises(RuntimeError, match='GUI unavailable'):
            module().run_preview(cam, board, 1, 2.)
    summary = json.loads(next(tmp_path.glob('live-*/summary.json')).read_text())
    assert summary['ending'] == 'error'


def test_camera_failure_survives_full_frame_transport(tmp_path):
    cam, board = profiles(tmp_path)
    camera, workspace, _ = module().load_profiles(cam, board)
    class BusyQueue:
        def put_nowait(self, _item):
            from queue import Full
            raise Full
        def get_nowait(self):
            from queue import Empty
            raise Empty
    class Stop:
        def is_set(self): return False
    class Capture:
        def set(self, *_args): pass
        def isOpened(self): return True
        def read(self): return False, None
        def release(self): pass
    errors = Queue(maxsize=1)
    with patch.object(module().cv2, 'VideoCapture', return_value=Capture()):
        module().camera_worker(BusyQueue(), Stop(), 1, camera, workspace, errors=errors)
    assert module().take_latest(errors)['reason'] == 'Camera read failed'


def test_evidence_summary_lists_only_completed_samples(tmp_path):
    item = packet()
    visual, state = module().render_preview(item, 10.01, (1280, 720))
    ack = Queue()
    with patch.object(module(), 'save_sample', side_effect=OSError('disk full')):
        module().write_evidence(tmp_path, [], [(item, visual, state)], {'ending': 'user_stop'}, ack)
    report = json.loads((tmp_path / 'summary.json').read_text())
    assert report['sample_frame_ids'] == []
    assert report['failed_sample_frame_ids'] == [1]
    assert module().take_latest(ack)['status'] == 'error'


def test_slow_writer_stops_with_timeout_instead_of_waiting_forever(tmp_path):
    class Worker:
        terminated = False
        def start(self): pass
        def join(self, timeout): assert timeout <= 10
        def is_alive(self): return not self.terminated
        def terminate(self): self.terminated = True
    worker = Worker()
    class Channel(Queue):
        def close(self): pass
        def join_thread(self): pass
    class Context:
        def Queue(self, **_kwargs): return Channel()
        def Process(self, **_kwargs): return worker
    with patch.object(module().mp, 'get_context', return_value=Context()):
        with pytest.raises(RuntimeError, match='Evidence writer'):
            module().persist_evidence(tmp_path, [], [], {})
    assert worker.terminated


def test_preview_performs_no_disk_io_until_window_and_camera_closed(tmp_path):
    cam, board = profiles(tmp_path)
    events = []
    class Worker:
        def start(self): pass
        def join(self, timeout): events.append('camera_closed')
        def is_alive(self): return False
    class Channel(Queue):
        def close(self): pass
        def join_thread(self): pass
    class Context:
        def Queue(self, **_kwargs): return Channel()
        def Event(self): return mp.get_context('spawn').Event()
        def Process(self, **_kwargs): return Worker()
    context = Context()
    context.Event = lambda: type('Stop', (), {'set': lambda self: None})()
    class Window:
        def __init__(self, *_args): pass
        def show(self, image): pass
        def poll(self): return 'quit'
        def close(self): events.append('window_closed')
    def persist(_directory, records, samples, summary):
        assert 'window_closed' in events and 'camera_closed' in events
        events.append('disk_write')
    item = packet()
    item['received_at'] = time.perf_counter()
    with patch.object(module(), 'local_root', return_value=tmp_path), \
         patch.object(module().mp, 'get_context', return_value=context), \
         patch.object(module(), 'PreviewWindow', Window), \
         patch.object(module(), 'take_latest', side_effect=[item, None]), \
         patch.object(module(), 'persist_evidence', side_effect=persist):
        module().run_preview(cam, board, 1, 2.)
    assert events[-1] == 'disk_write'


def test_tk_window_draws_and_clears_pixels_without_native_save_dialog():
    import subprocess
    import sys
    code = '''
import time
import numpy as np
from server.realtime.workspace_live_preview import PreviewWindow, render_preview
window = PreviewWindow((1280,720))
window.root.withdraw()
try:
    packet = {"frame_id":1,"received_at":10.,"image":np.zeros((720,1280,3),np.uint8),
              "analysis":{"status":"tracking","reason":"","targets":{"A":{"visible":True,"pixel":[500,300]}}}}
    image,_ = render_preview(packet,10.01,(1280,720))
    window.show(image)
    assert window.photo.get(512,300)[1] > 150
    window.root.event_generate("<Control-s>")
    assert window.poll() is None
    image,state = render_preview(packet,10.2,(1280,720))
    window.show(image)
    assert window.photo.get(512,300) == (0,0,0)
    assert state["status"] == "stale"
finally:
    window.close()
'''
    result = subprocess.run([sys.executable, '-X', 'utf8', '-B', '-c', code], capture_output=True, text=True, timeout=8)
    assert result.returncode == 0, result.stderr


def _synthetic_preview_worker(queue, stop, _index, _camera, _workspace, _errors, *, corner_refinement):
    assert corner_refinement in ('subpix', 'apriltag')
    for index in range(20):
        item = packet()
        item.update(frame_id=index + 1, received_at=time.perf_counter())
        module().offer_latest(queue, item)
        time.sleep(.05)
    stop.wait(10)


def test_no_save_window_suppresses_save_key_without_camera():
    from server.realtime.workspace_live_preview import PreviewWindow
    window = PreviewWindow((1280, 720), allow_save=False)
    window.root.withdraw()
    try:
        assert 'NO IMAGE SAVING' in window.root.title()
        assert not window.root.bind('<space>')
        window._key('save')
        assert window.poll() is None
        window._key('quit')
        assert window.poll() == 'quit'
    finally:
        window.close()


@pytest.mark.parametrize('corner_refinement', ['subpix', 'apriltag'])
def test_finite_preview_records_stall_and_persists_completed_samples(tmp_path, corner_refinement):
    cam, board = profiles(tmp_path)
    context = mp.get_context('spawn')
    class Context:
        def Queue(self, **kwargs): return context.Queue(**kwargs)
        def Event(self): return context.Event()
        def Process(self, **kwargs):
            if kwargs['target'] == module().camera_worker:
                kwargs['target'] = _synthetic_preview_worker
            return context.Process(**kwargs)
    class Window:
        def __init__(self, *_args): pass
        def show(self, _image): pass
        def poll(self): return None
        def close(self): pass
    with patch.object(module(), 'local_root', return_value=tmp_path), \
         patch.object(module().mp, 'get_context', return_value=Context()), \
         patch.object(module(), 'PreviewWindow', Window):
        directory = module().run_preview(cam, board, 1, 2.5, .2, corner_refinement=corner_refinement)
    assert json.loads((directory / 'session.json').read_text())['corner_refinement'] == corner_refinement
    assert json.loads((directory / 'session.json').read_text())['timestamp_clock'] == 'time.perf_counter'
    records = [json.loads(line) for line in (directory / 'frames.jsonl').read_text().splitlines()]
    summary = json.loads((directory / 'summary.json').read_text())
    assert any(r['status'] == 'tracking' and r['targets'] for r in records)
    assert any(r['status'] == 'stale' and r['event'] == 'visibility_change' for r in records)
    assert summary['ending'] == 'duration_limit'
    assert summary['sample_frame_ids'] and not summary['failed_sample_frame_ids']
    for frame_id in summary['sample_frame_ids']:
        assert (directory / f'frame-{frame_id:06d}' / 'report.json').exists()


def roi_scene_packet():
    from .test_workspace_roi_candidate import setup_scene
    camera, workspace, analysis, image = setup_scene()
    analysis.update(targets={}, marker_ids=[0, 1, 2, 3, 4, 5])
    return camera, workspace, dict(frame_id=1, received_at=10., image=image, analysis=analysis)


def test_opt_in_roi_preview_matches_offline_regions_and_preserves_packet():
    import copy
    from server.realtime.workspace_roi_candidate import roi_quads, sample_region
    camera, workspace, item = roi_scene_packet()
    before = copy.deepcopy(item['analysis'])
    original = item['image'].copy()
    visual, state = module().render_preview(item, 10.01, camera.image_size, roi_profiles=(camera, workspace))
    overlay = state['roi_candidate']
    assert overlay['visible'] and overlay['valid_regions'] == 5
    assert overlay['activation_status'] == 'not_activated'
    assert 'assembly_overlay' not in state
    for name, quad in roi_quads(workspace).items():
        expected, _ = sample_region(original, camera, before, quad)
        assert overlay['regions'][name] == expected
    assert item['analysis'] == before
    np.testing.assert_array_equal(item['image'], original)
    assert not np.array_equal(visual[40:], original[40:])
    assert 'roi_candidate' not in module().render_preview(item, 10.01, camera.image_size)[1]


@pytest.mark.parametrize('now', [10.151, 9.99, float('nan')])
def test_stale_roi_preview_has_no_geometry_or_image(now):
    camera, workspace, item = roi_scene_packet()
    visual, state = module().render_preview(item, now, camera.image_size, roi_profiles=(camera, workspace))
    assert state['status'] == 'stale'
    assert not state['roi_candidate']['visible'] and state['roi_candidate']['valid_regions'] == 0
    assert not visual[40:].any()
    assert all(not r['valid'] and not r['boundary_raw_px'] for r in state['roi_candidate']['regions'].values())


def test_rejected_roi_pose_keeps_raw_view_without_regions():
    camera, workspace, item = roi_scene_packet()
    item['analysis']['status'] = 'pose_rejected'
    visual, state = module().render_preview(item, 10.01, camera.image_size, roi_profiles=(camera, workspace))
    assert not state['roi_candidate']['visible']
    np.testing.assert_array_equal(visual[41:], item['image'][41:])


def test_roi_and_assembly_modes_conflict_before_camera_open(tmp_path):
    with patch.object(module().cv2, 'VideoCapture', side_effect=AssertionError('camera forbidden')):
        with pytest.raises(ValueError, match='exclusive'):
            module().run_preview(tmp_path/'missing', tmp_path/'missing', 0, 2,
                                 assembly_overlay=True, roi_candidate=True)


def test_roi_session_records_definition_and_passes_option_without_camera(tmp_path):
    cam, board = profiles(tmp_path)
    camera, workspace, item = roi_scene_packet()
    class Worker:
        def start(self): pass
        def join(self, timeout): pass
        def is_alive(self): return False
    class Channel(Queue):
        def close(self): pass
        def join_thread(self): pass
    class Context:
        def Queue(self, **kwargs): return Channel()
        def Event(self): return type('Stop', (), {'set': lambda self: None})()
        def Process(self, **kwargs): return Worker()
    class Window:
        def __init__(self, *args, **kwargs): pass
        def show(self, image): pass
        def poll(self): return 'quit'
        def close(self): pass
    item['received_at'] = time.perf_counter()
    saved = {}
    def persist(directory, records, samples, summary):
        saved.update(records=records, samples=samples, summary=summary)
    with patch.object(module(), 'local_root', return_value=tmp_path), \
         patch.object(module().mp, 'get_context', return_value=Context()), \
         patch.object(module(), 'PreviewWindow', Window), \
         patch.object(module(), 'take_latest', side_effect=[item, None]), \
         patch.object(module(), 'persist_evidence', side_effect=persist):
        directory = module().run_preview(cam, board, 0, 2, roi_candidate=True, no_image_saving=True)
    session = json.loads((directory/'session.json').read_text())
    assert session['roi_candidate'] is True and session['roi_definition']['screw_side_mm'] == 18
    assert session['roi_definition']['lid_inset_fraction'] == .1
    assert not session['image_saving_enabled'] and not session['assembly_overlay']
    assert saved['records'][0]['roi_candidate']['valid_regions'] == 5
    assert saved['samples'] == [] and saved['summary']['ending'] == 'user_stop'


def test_saved_roi_cli_preserves_metric_definition_without_camera(tmp_path):
    import cv2
    cam, board = profiles(tmp_path)
    camera, workspace, item = roi_scene_packet()
    source = tmp_path/'saved.png'
    source.write_bytes(cv2.imencode('.png', item['image'])[1].tobytes())
    with patch.object(module(), 'local_root', return_value=tmp_path), \
         patch.object(module(), 'analyze_frame', return_value=item['analysis']), \
         patch.object(module().cv2, 'VideoCapture', side_effect=AssertionError('camera forbidden')):
        assert module().main(['--camera-profile', str(cam), '--workspace', str(board),
                              '--image', str(source), '--roi-candidate']) == 0
    report = json.loads(next(tmp_path.glob('overlay-still-*/report.json')).read_text())
    assert report['roi_definition']['screw_side_mm'] == 18
    assert report['roi_definition']['lid_inset_fraction'] == .1
    quad = np.array(report['roi_definition']['regions_mm']['screw_a'])
    np.testing.assert_allclose(quad.mean(axis=0), workspace.targets['A'])
    assert report['roi_candidate']['valid_regions'] == 5


def test_saved_image_preserves_detector_choice_without_camera(tmp_path):
    cam, board = profiles(tmp_path)
    _, _, detections, _, _ = models()
    image_path = tmp_path / 'input.png'
    assert module().cv2.imwrite(str(image_path), np.zeros((720, 1280, 3), np.uint8))
    ids = np.array(list(detections)).reshape(-1, 1)
    with patch.object(module(), 'local_root', return_value=tmp_path), \
         patch.object(module(), 'detect_markers', return_value=(detections, [], ids)) as detector, \
         patch.object(module().cv2, 'VideoCapture') as capture:
        directory = module().render_saved_image(cam, board, image_path, corner_refinement='apriltag')
    assert detector.call_args.kwargs['corner_refinement'] == 'apriltag'
    capture.assert_not_called()
    report = json.loads((directory / 'report.json').read_text())
    assert report['corner_refinement'] == 'apriltag'
    assert report['status'] == 'tracking'
    assert report['physical_accuracy_verified'] is False


@pytest.mark.parametrize('saved_image', [False, True])
def test_cli_passes_detector_choice_to_selected_source(tmp_path, saved_image):
    (tmp_path / 'report.json').write_text(json.dumps({'status': 'tracking', 'assembly_overlay': {'visible': True}}))
    (tmp_path / 'summary.json').write_text(json.dumps({'ending': 'duration_limit'}))
    source = ['--image', 'input.png'] if saved_image else ['--camera', '0']
    with patch.object(module(), 'render_saved_image', return_value=tmp_path) as still, \
         patch.object(module(), 'run_preview', return_value=tmp_path) as live:
        code = module().main(['--camera-profile', 'camera.json', '--workspace', 'workspace.json',
                              '--corner-refinement', 'apriltag', *source])
    assert code == 0
    selected, other = (still, live) if saved_image else (live, still)
    assert selected.call_args.kwargs['corner_refinement'] == 'apriltag'
    other.assert_not_called()


@pytest.mark.parametrize('limit', [0, 13, True, 1.5])
def test_invalid_sample_limit_rejected_before_camera(limit, tmp_path):
    with patch.object(module().cv2, 'VideoCapture', side_effect=AssertionError('camera forbidden')):
        with pytest.raises(ValueError, match='Sample limit'):
            module().run_preview(tmp_path/'missing', tmp_path/'missing', 0, 2, max_samples=limit)


@pytest.mark.parametrize('save_key', [False, True])
def test_sample_limit_caps_automatic_and_manual_saving(tmp_path, save_key):
    cam, board = profiles(tmp_path)
    clock, frames, saved = [0.], [0], {}
    class Worker:
        alive = True
        def start(self): pass
        def join(self, timeout): self.alive = False
        def is_alive(self): return self.alive
    class Channel(Queue):
        def close(self): pass
        def join_thread(self): pass
    class Context:
        def Queue(self, **kwargs): return Channel()
        def Event(self): return type('Stop', (), {'set': lambda self: None})()
        def Process(self, **kwargs): return Worker()
    class Window:
        def __init__(self, *args, **kwargs): pass
        def show(self, image): pass
        def poll(self): return 'quit' if frames[0] == 15 else 'save' if save_key else None
        def close(self): pass
    def packets(channel):
        if getattr(channel, 'errors', False): return None
        item = packet()
        frames[0] += 1
        clock[0] += .02
        item.update(frame_id=frames[0], received_at=clock[0])
        return item
    channels = [Channel(), Channel()]
    channels[1].errors = True
    context = Context()
    context.Queue = lambda **kwargs: channels.pop(0)
    def persist(directory, records, samples, summary): saved.update(samples=samples, summary=summary)
    with patch.object(module(), 'local_root', return_value=tmp_path), \
         patch.object(module().mp, 'get_context', return_value=context), \
         patch.object(module(), 'PreviewWindow', Window), \
         patch.object(module(), 'take_latest', side_effect=packets), \
         patch.object(module().time, 'perf_counter', side_effect=lambda: clock[0]), \
         patch.object(module().time, 'sleep'), \
         patch.object(module(), 'persist_evidence', side_effect=persist), \
         patch.object(module().cv2, 'VideoCapture', side_effect=AssertionError('camera forbidden')):
        directory = module().run_preview(cam, board, 0, 2, 0 if save_key else .01, max_samples=10)
    assert len(saved['samples']) == 10
    assert saved['summary']['requested_sample_frame_ids'] == list(range(1, 11))
    assert json.loads((directory/'session.json').read_text())['max_samples'] == 10


def test_cli_passes_explicit_sample_limit(tmp_path):
    (tmp_path/'summary.json').write_text(json.dumps({'ending': 'duration_limit'}))
    with patch.object(module(), 'run_preview', return_value=tmp_path) as live:
        assert module().main(['--camera-profile', 'c.json', '--workspace', 'w.json',
                              '--camera', '0', '--max-samples', '10']) == 0
    assert live.call_args.kwargs['max_samples'] == 10
