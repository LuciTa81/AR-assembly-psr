from __future__ import annotations

import copy
import json
from unittest.mock import patch

import cv2
import numpy as np
import pytest

from .test_workspace_projection import models
from .test_workspace_live_preview import profiles


def module():
    from server.realtime import workspace_overlay
    return workspace_overlay


def scene_packet():
    from server.realtime.workspace_projection import estimate_pose, project_targets
    camera, workspace, detections, rvec, tvec = models()
    pose = estimate_pose(detections, workspace, camera, camera.image_size)
    packet = {
        'frame_id': 7, 'received_at': 10.,
        'image': np.zeros((720, 1280, 3), np.uint8),
        'analysis': {'status': 'tracking', 'reason': '', 'marker_ids': list(detections),
                     'targets': project_targets(pose, workspace, camera), 'rms_px': pose.rms_px,
                     'rvec': rvec.reshape(3).tolist(), 'tvec_mm': tvec.reshape(3).tolist()},
    }
    return camera, workspace, packet


@pytest.mark.parametrize('target_id', list('ABCD'))
def test_world_geometry_joins_perimeter_and_arrow_is_above_selected_screw(target_id):
    _, workspace, _ = scene_packet()
    segments = module().world_segments(workspace, target_id)
    edges = [s for s in segments if s['kind'] == 'edge']
    assert [s['name'] for s in edges] == ['AB', 'BD', 'DC', 'CA']
    for segment in edges:
        np.testing.assert_allclose(segment['points_mm'], [workspace.targets[k] for k in segment['name']])
    shaft = next(s for s in segments if s['name'] == 'shaft')
    np.testing.assert_allclose(shaft['points_mm'],
                               [workspace.targets[target_id] + [0, 0, 30],
                                workspace.targets[target_id] + [0, 0, 8]])
    assert all(np.asarray(s['points_mm'])[:, 2].min() > workspace.targets[target_id][2]
               for s in segments if s['kind'] == 'arrow')


def test_projection_uses_current_pose_and_distortion_without_mutating_input():
    camera, workspace, packet = scene_packet()
    before = copy.deepcopy(packet['analysis'])
    actual = module().project_overlay(packet['analysis'], camera, workspace, 'A')
    assert actual['visible'] and actual['target_id'] == 'A'
    assert actual['selection_mode'] == 'manual'
    first = actual['segments'][0]
    expected = cv2.projectPoints(np.linspace(workspace.targets['A'], workspace.targets['B'], 9),
        np.array(before['rvec']), np.array(before['tvec_mm']), camera.matrix, camera.distortion)[0].reshape(-1, 2)
    np.testing.assert_allclose(first['pixels'], expected)
    assert packet['analysis'] == before
    changed = copy.deepcopy(before)
    changed['tvec_mm'][0] += 25
    shifted = module().project_overlay(changed, camera, workspace, 'A')
    assert not np.allclose(shifted['segments'][0]['pixels'], first['pixels'])


@pytest.mark.parametrize('bad', ['lost', 'missing_pose', 'nonfinite', 'behind_camera'])
def test_rejected_or_invalid_pose_has_no_drawable_geometry(bad):
    camera, workspace, packet = scene_packet()
    state = packet['analysis']
    if bad == 'lost': state['status'] = 'pose_rejected'
    elif bad == 'missing_pose': state.pop('rvec')
    elif bad == 'nonfinite': state['rvec'][0] = float('nan')
    else: state.update(rvec=[0, 0, 0], tvec_mm=[0, 0, -1000])
    projected = module().project_overlay(state, camera, workspace, 'A')
    assert not projected['visible'] and projected['segments'] == []


def test_offscreen_target_does_not_get_an_edge_clamped_arrow():
    camera, workspace, packet = scene_packet()
    packet['analysis']['tvec_mm'][0] += 3000
    projected = module().project_overlay(packet['analysis'], camera, workspace, 'A')
    assert not projected['target_visible']
    assert not any(s['kind'] == 'arrow' for s in projected['segments'])


def test_no_selected_screw_keeps_neutral_perimeter_without_arrow():
    camera, workspace, packet = scene_packet()
    projected = module().project_overlay(packet['analysis'], camera, workspace, None)
    assert projected['visible'] and projected['target_id'] is None
    assert not projected['target_visible']
    assert len(projected['segments']) == 4
    assert all(s['kind'] == 'edge' for s in projected['segments'])
    image = packet['image'].copy()
    module().draw_overlay(image, projected)
    assert image.any()


@pytest.mark.parametrize('now', [10.151, 9.99, float('nan')])
def test_stale_preview_hides_entire_overlay(now):
    from server.realtime.workspace_live_preview import render_preview
    camera, workspace, packet = scene_packet()
    image, state = render_preview(packet, now, camera.image_size,
                                  assembly_profiles=(camera, workspace), target_id='A')
    assert state['status'] == 'stale'
    assert not state['assembly_overlay']['visible']
    assert not image[100:].any()


def test_manual_selection_moves_only_arrow_not_geometry_or_recognition():
    from server.realtime.workspace_live_preview import render_preview
    camera, workspace, packet = scene_packet()
    before = copy.deepcopy(packet['analysis'])
    previews = []
    for target in 'ABCD':
        image, state = render_preview(packet, 10.01, camera.image_size,
                                      assembly_profiles=(camera, workspace), target_id=target)
        assert state['frame_id'] == 7 and state['status'] == 'tracking'
        assert state['assembly_overlay']['target_id'] == target
        assert state['assembly_overlay']['visible']
        assert np.count_nonzero(image[100:]) > 1500
        previews.append(image)
    assert not np.array_equal(previews[0][100:], previews[1][100:])
    assert packet['analysis'] == before
    assert not packet['image'].any()


def test_lost_markers_clear_previously_rendered_lines_and_arrow():
    from server.realtime.workspace_live_preview import render_preview
    camera, workspace, packet = scene_packet()
    render_preview(packet, 10.01, camera.image_size, assembly_profiles=(camera, workspace))
    packet['analysis'].update(status='pose_rejected', reason='missing markers', targets={})
    image, state = render_preview(packet, 10.01, camera.image_size, assembly_profiles=(camera, workspace))
    assert not state['assembly_overlay']['visible']
    assert not image[100:].any()


def test_offline_preview_never_opens_camera_and_keeps_original(tmp_path):
    from server.realtime import workspace_live_preview as preview
    camera_path, workspace_path = profiles(tmp_path)
    _, _, packet = scene_packet()
    source = tmp_path / 'source.png'
    source.write_bytes(cv2.imencode('.png', packet['image'])[1].tobytes())
    original = source.read_bytes()
    with patch.object(preview.cv2, 'VideoCapture', side_effect=AssertionError('Camera must remain off')), \
         patch.object(preview, 'analyze_frame', return_value=packet['analysis']), \
         patch.object(preview, 'local_root', return_value=tmp_path):
        directory = preview.render_saved_image(camera_path, workspace_path, source, 'B')
    result = json.loads((directory / 'report.json').read_text())
    assert result['source_mode'] == 'saved_image'
    assert result['display_alignment_verified'] is False
    assert result['assembly_overlay']['target_id'] == 'B'
    assert (directory / 'preview.png').exists()
    assert source.read_bytes() == original


def test_manual_target_window_selection_and_no_image_saving():
    from server.realtime.workspace_live_preview import PreviewWindow
    window = PreviewWindow((1280, 720), allow_save=False, target_id='A')
    window.root.withdraw()
    try:
        assert window.target_var.get() == 'A'
        window.select_target('C')
        assert window.target_var.get() == 'C'
        assert window.poll() == 'target:C'
        assert not window.root.bind('<space>')
        window._key('save')
        assert window.poll() is None
    finally:
        window.close()


def test_no_image_saving_rejects_auto_save_before_camera_open(tmp_path):
    from server.realtime.workspace_live_preview import run_preview
    with pytest.raises(ValueError, match='saving'):
        run_preview(tmp_path / 'missing', tmp_path / 'missing2', 0, 10., 1., no_image_saving=True)


def test_edge_sample_joints_do_not_have_dark_cap_gaps():
    camera, workspace, packet = scene_packet()
    overlay = module().project_overlay(packet['analysis'], camera, workspace, 'A')
    image = packet['image'].copy()
    module().draw_overlay(image, overlay)
    edge = next(s for s in overlay['segments'] if s['name'] == 'AB')
    for x, y in np.rint(edge['pixels'][2:-2]).astype(int):
        assert image[y, x, 0] >= 180 and image[y, x, 1] >= 160


def test_stroke_outline_does_not_paint_over_adjacent_colored_segments():
    camera, workspace, packet = scene_packet()
    projected = module().project_overlay(packet['analysis'], camera, workspace, 'A')
    edge = next(s for s in projected['segments'] if s['name'] == 'AB')
    actual, expected = packet['image'].copy(), packet['image'].copy()
    module().draw_overlay(actual, dict(visible=True, segments=[edge], targets={}))
    points = np.rint(edge['pixels']).astype(int)
    for color, thickness in [((20, 20, 20), 4), (module().EDGE_COLOR, 2)]:
        for first, second in zip(points[:-1], points[1:]):
            cv2.line(expected, tuple(first), tuple(second), color, thickness, cv2.LINE_AA)
    np.testing.assert_array_equal(actual, expected)


def test_live_target_selection_redraws_same_frame_and_cannot_save_images(tmp_path):
    import time
    from queue import Queue
    from server.realtime import workspace_live_preview as preview
    camera_path, workspace_path = profiles(tmp_path)
    _, _, packet = scene_packet()
    packet['received_at'] = time.perf_counter()
    events, evidence = [], {}
    class Channel(Queue):
        def close(self): pass
        def join_thread(self): pass
    class Stop:
        stopped = False
        def set(self): self.stopped = True
    stop = Stop()
    class Worker:
        def start(self): pass
        def join(self, timeout): events.append('camera_closed')
        def is_alive(self): return not stop.stopped
    class Context:
        def Queue(self, **kwargs): return Channel(**kwargs)
        def Event(self): return stop
        def Process(self, **kwargs): return Worker()
    class Window:
        def __init__(self, size, **kwargs):
            assert kwargs == {'allow_save': False, 'target_id': 'A'}
            self.keys = iter(['target:B', 'save', 'quit'])
        def show(self, image): events.append('draw')
        def poll(self): return next(self.keys)
        def close(self): events.append('window_closed')
    def persist(directory, records, samples, summary):
        assert events[-2:] == ['window_closed', 'camera_closed']
        evidence.update(records=records, samples=samples)
    with patch.object(preview, 'local_root', return_value=tmp_path), \
         patch.object(preview.mp, 'get_context', return_value=Context()), \
         patch.object(preview, 'PreviewWindow', Window), \
         patch.object(preview, 'take_latest', side_effect=[packet, None, None, None, None, None]), \
         patch.object(preview, 'persist_evidence', side_effect=persist):
        directory = preview.run_preview(camera_path, workspace_path, 0, 2.,
                                       assembly_overlay=True, no_image_saving=True)
    assert not evidence['samples']
    assert [r['assembly_overlay']['target_id'] for r in evidence['records']] == ['A', 'B']
    assert all(r['frame_id'] == 7 for r in evidence['records'])
    assert events.count('draw') == 2
    session = json.loads((directory / 'session.json').read_text())
    assert session['max_samples'] == 0 and not session['image_saving_enabled']
