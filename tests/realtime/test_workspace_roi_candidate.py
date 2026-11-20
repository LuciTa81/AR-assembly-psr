from __future__ import annotations

import copy
from dataclasses import replace
import hashlib
import json
from unittest.mock import patch

import cv2
import numpy as np
import pytest

from .test_workspace_projection import models
from .test_workspace_live_preview import profiles


def module():
    from server.realtime import workspace_roi_candidate
    return workspace_roi_candidate


def setup_scene():
    camera, workspace, _, rvec, tvec = models()
    state = dict(status='tracking', rvec=rvec.reshape(3).tolist(),
                 tvec_mm=tvec.reshape(3).tolist())
    image = np.full((720, 1280, 3), 91, np.uint8)
    return camera, workspace, state, image


def test_regions_reuse_registered_height_without_mutating_workspace():
    _, workspace, _, _ = setup_scene()
    before = copy.deepcopy(workspace.targets)
    regions = module().roi_quads(workspace)
    assert set(regions) == {'lid_surface', 'screw_a', 'screw_b', 'screw_c', 'screw_d'}
    for name in 'ABCD':
        quad = regions['screw_' + name.lower()]
        np.testing.assert_allclose(quad.mean(axis=0), before[name])
        np.testing.assert_allclose(np.ptp(quad, axis=0), [18, 18, 0])
        np.testing.assert_array_equal(workspace.targets[name], before[name])
    assert np.all(regions['lid_surface'][:, 2] == 60)
    np.testing.assert_allclose(regions['lid_surface'][0], [156, 164, 60])


@pytest.mark.parametrize('side', [0, -1, float('nan'), 41])
def test_invalid_region_size_rejected(side):
    _, workspace, _, _ = setup_scene()
    with pytest.raises(ValueError):
        module().roi_quads(workspace, side)


@pytest.mark.parametrize('change', ['missing', 'height', 'order'])
def test_invalid_screw_surface_rejected(change):
    _, workspace, _, _ = setup_scene()
    if change == 'missing': workspace.targets.pop('D')
    elif change == 'height': workspace.targets['D'][2] = 65
    else: workspace.targets['C'], workspace.targets['D'] = workspace.targets['D'], workspace.targets['C']
    with pytest.raises(ValueError):
        module().roi_quads(workspace)


def test_projection_uses_height_distortion_and_current_pose():
    camera, workspace, state, image = setup_scene()
    quad = module().roi_quads(workspace)['screw_a']
    report, crop = module().sample_region(image, camera, state, quad)
    expected = cv2.projectPoints(quad, np.array(state['rvec']), np.array(state['tvec_mm']),
                                camera.matrix, camera.distortion)[0].reshape(4, 2)
    assert report['valid'] and crop.shape == (64, 64, 3)
    np.testing.assert_allclose(report['corners_raw_px'], expected, atol=1e-4)
    np.testing.assert_allclose(crop, 91)
    ground = quad.copy(); ground[:, 2] = 0
    ground_report, _ = module().sample_region(image, camera, state, ground)
    assert np.linalg.norm(np.array(report['center_raw_px']) - ground_report['center_raw_px']) > 10
    moved = copy.deepcopy(state); moved['tvec_mm'][0] += 25
    moved_report, _ = module().sample_region(image, camera, moved, quad)
    assert np.linalg.norm(np.array(report['center_raw_px']) - moved_report['center_raw_px']) > 10


def test_metric_crop_orientation_and_center_are_not_flipped():
    camera, workspace, state, _ = setup_scene()
    yy, xx = np.indices((720, 1280), dtype=np.float32)
    image = np.dstack([xx, yy, xx * 0])
    quad = module().roi_quads(workspace)['screw_a']
    report, crop = module().sample_region(image, camera, state, quad, size=65)
    expected = np.array(report['corners_raw_px'])
    np.testing.assert_allclose(crop[[0, 0, -1, -1], [0, -1, -1, 0], :2], expected, atol=.04)
    np.testing.assert_allclose(crop[32, 32, :2], report['center_raw_px'], atol=.04)


@pytest.mark.parametrize('change', ['lost', 'future_shape', 'nan', 'behind', 'offscreen'])
def test_unusable_observation_has_no_crop(change):
    camera, workspace, state, image = setup_scene()
    if change == 'lost': state['status'] = 'pose_rejected'
    elif change == 'future_shape': state.pop('rvec')
    elif change == 'nan': state['rvec'][0] = float('nan')
    elif change == 'behind': state.update(rvec=[0, 0, 0], tvec_mm=[0, 0, -1000])
    else: state['tvec_mm'][0] += 3000
    report, crop = module().sample_region(image, camera, state, module().roi_quads(workspace)['screw_a'])
    assert not report['valid'] and report['reason'] and crop is None


def test_output_refuses_existing_folder_and_never_opens_camera(tmp_path):
    cam, board = profiles(tmp_path)
    _, _, state, image = setup_scene()
    source = tmp_path / 'saved.png'
    ok, encoded = cv2.imencode('.png', image); assert ok
    source.write_bytes(encoded.tobytes())
    original = {p: p.read_bytes() for p in (cam, board, source)}
    output = tmp_path / 'candidate'
    with patch('cv2.VideoCapture', side_effect=AssertionError('camera forbidden')), \
         patch.object(module(), 'analyze_frame', return_value=state):
        result = module().inspect_images(cam, board, [source], output)
        assert result['images'][0]['valid_regions'] == 5
        with pytest.raises(FileExistsError):
            module().inspect_images(cam, board, [source], output)
    candidate = json.loads((output / 'candidate.json').read_text())
    report = json.loads((output / 'image-001' / 'report.json').read_text())
    assert candidate['activation_status'] == 'not_activated'
    assert not candidate['physical_accuracy_verified']
    assert candidate['workspace_profile_sha256'] == hashlib.sha256(original[board]).hexdigest()
    assert report['source_sha256'] == hashlib.sha256(original[source]).hexdigest()
    assert len(list((output / 'image-001').glob('screw_*.png'))) == 4
    for p, content in original.items(): assert p.read_bytes() == content


def test_rejected_saved_image_creates_no_regions_or_stale_crops(tmp_path):
    cam, board = profiles(tmp_path)
    _, _, _, image = setup_scene()
    source = tmp_path / 'blur.png'
    source.write_bytes(cv2.imencode('.png', image)[1].tobytes())
    with patch('cv2.VideoCapture', side_effect=AssertionError('camera forbidden')), \
         patch.object(module(), 'analyze_frame', return_value=dict(status='pose_rejected', reason='No markers')):
        result = module().inspect_images(cam, board, [source], tmp_path / 'out')
    assert result['images'][0]['valid_regions'] == 0
    assert sorted(p.name for p in (tmp_path / 'out' / 'image-001').glob('*.png')) == ['preview.png']


def test_visible_center_does_not_allow_partially_offscreen_patch():
    camera, workspace, _, image = setup_scene()
    camera = replace(camera, distortion=np.zeros(5))
    quad = module().roi_quads(workspace)['screw_a']
    target = workspace.targets['A']
    depth = 1060.
    tx = (camera.image_size[0]-2-camera.matrix[0, 2])*depth/camera.matrix[0, 0]-target[0]
    state = dict(status='tracking', rvec=[0., 0., 0.], tvec_mm=[tx, -target[1], 1000.])
    expected = cv2.projectPoints(quad, np.zeros(3), np.array(state['tvec_mm']),
                                camera.matrix, camera.distortion)[0].reshape(4, 2)
    assert expected[:, 0].min() < camera.image_size[0]-1 < expected[:, 0].max()
    report, crop = module().sample_region(image, camera, state, quad)
    assert not report['valid'] and crop is None
    assert 'fully inside' in report['reason']


def test_valid_then_rejected_photo_does_not_reuse_previous_regions(tmp_path):
    cam, board = profiles(tmp_path)
    _, _, state, image = setup_scene()
    source = tmp_path / 'saved.png'
    source.write_bytes(cv2.imencode('.png', image)[1].tobytes())
    with patch('cv2.VideoCapture', side_effect=AssertionError('camera forbidden')), \
         patch.object(module(), 'analyze_frame', side_effect=[state, dict(status='pose_rejected', reason='No markers')]):
        result = module().inspect_images(cam, board, [source, source], tmp_path / 'out')
    assert [row['valid_regions'] for row in result['images']] == [5, 0]
    assert sorted(p.name for p in (tmp_path / 'out' / 'image-002').glob('*.png')) == ['preview.png']


def test_display_only_projection_skips_crop_without_changing_geometry():
    camera, workspace, state, image = setup_scene()
    quad = module().roi_quads(workspace)['screw_a']
    expected, _ = module().sample_region(image, camera, state, quad)
    with patch.object(module().cv2, 'remap', side_effect=AssertionError('No display-only crops')):
        actual, crop = module().sample_region(image, camera, state, quad, make_crop=False)
    assert actual == expected and crop is None
