import json
from dataclasses import replace
from pathlib import Path
import sys

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT.parent / 'beast-preparation-text-20261116/protected-before.json'
REPO = Path(json.loads(MANIFEST.read_text(encoding='utf-8-sig'))[0]['Path']).parents[2]
sys.path.insert(0, str(REPO))

from server.realtime.workspace_projection import CameraModel, WorkspacePose
from pose_quality_continuation import QualityContinuation, project_geometry


def scene(focal=800):
    camera = CameraModel('test-camera', (1280, 720),
                         np.array([[focal, 0, 640], [0, focal, 360], [0, 0, 1.]]),
                         np.zeros(5))
    points = np.array([[-55, 55, 60], [55, 55, 60], [-55, -55, 60],
                       [55, -55, 60], [-62, 62, 0], [62, -62, 0]], float)
    projections = [np.array([[focal, 0, 960, shift], [0, focal, 540, 0],
                             [0, 0, 1, 0]], float) for shift in (25*focal, -25*focal)]
    pose = WorkspacePose(
        cv2.Rodrigues(np.diag([1., -1., -1.]))[0], np.array([[0.], [0.], [500.]]),
        np.array([0., 0., 500.]), (0, 1, 2, 4, 5), np.zeros((5, 2)),
        np.zeros((5, 2)), 2.9, 4.5)
    return camera, points, projections, pose


def policy(focal=800):
    camera, points, projections, pose = scene(focal)
    return QualityContinuation(camera, points, projections), pose


def move(pose, x=0, y=0, z=0):
    return replace(pose, tvec=pose.tvec + np.array([[x], [y], [z]]))


def test_first_quality_rejection_is_not_rescued_without_strict_anchor():
    gate, pose = policy()
    result = gate.update(1, 100, replace(pose, rms_px=3.05))
    assert (result.mode, result.reason, result.pose) == ('hidden', 'no_anchor', None)


def test_rescue_returns_new_measured_pose_not_frozen_anchor():
    gate, pose = policy()
    assert gate.update(1, 100, pose).mode == 'strict'
    current = move(replace(pose, rms_px=3.08), x=1)
    result = gate.update(2, 200, current)
    assert result.mode == 'continued'
    assert result.pose is current
    assert result.pose is not pose
    assert result.delta_eye_px == pytest.approx(800/440)


@pytest.mark.parametrize('age,expected', [(199, 'continued'), (200, 'continued'), (201, 'hidden')])
def test_budget_is_bounded_from_last_strict_frame(age, expected):
    gate, pose = policy()
    gate.update(1, 100, pose)
    assert gate.update(2, 100+age, replace(pose, rms_px=3.05)).mode == expected


def test_rescued_frames_do_not_extend_deadline():
    gate, pose = policy()
    gate.update(1, 100, pose)
    soft = replace(pose, rms_px=3.05)
    assert gate.update(2, 200, soft).mode == 'continued'
    assert gate.update(3, 300, soft).mode == 'continued'
    assert gate.update(4, 301, soft).reason == 'expired'
    assert gate.update(5, 400, soft).reason == 'no_anchor'
    assert gate.update(6, 500, pose).mode == 'strict'
    assert gate.update(7, 600, soft).mode == 'continued'


@pytest.mark.parametrize('rms,maximum,expected', [(3, 5, 'strict'), (3.25, 5, 'continued'),
                                                (3.251, 4, 'hidden'), (3.1, 5.001, 'hidden')])
def test_only_narrow_rms_band_is_eligible(rms, maximum, expected):
    gate, pose = policy()
    gate.update(1, 100, pose)
    assert gate.update(2, 200, replace(pose, rms_px=rms, max_error_px=maximum)).mode == expected


@pytest.mark.parametrize('ids', [(0, 1, 2, 4), (0, 1, 2, 3, 5)])
def test_fewer_or_changed_markers_cannot_continue(ids):
    gate, pose = policy()
    gate.update(1, 100, pose)
    result = gate.update(2, 200, replace(pose, rms_px=3.1, marker_ids=ids))
    assert result.mode == 'hidden'
    assert gate.update(3, 250, replace(pose, rms_px=3.1)).reason == 'no_anchor'


def test_solver_failure_clears_anchor():
    gate, pose = policy()
    gate.update(1, 100, pose)
    assert gate.update(2, 200, None).reason == 'no_current_pose'
    assert gate.update(3, 250, replace(pose, rms_px=3.1)).reason == 'no_anchor'


@pytest.mark.parametrize('frame,time', [(1, 200), (0, 200), (2, 100), (2, 99), (2, float('nan'))])
def test_duplicate_or_invalid_timing_clears_anchor(frame, time):
    gate, pose = policy()
    gate.update(1, 100, pose)
    assert gate.update(frame, time, replace(pose, rms_px=3.1)).reason == 'non_monotonic_input'
    assert gate.update(3, 250, replace(pose, rms_px=3.1)).mode == 'hidden'


def test_large_3d_motion_rejected_even_with_small_screen_motion():
    gate, pose = policy(focal=100)
    gate.update(1, 100, pose)
    result = gate.update(2, 200, move(replace(pose, rms_px=3.1), x=6))
    assert (result.mode, result.reason) == ('hidden', 'motion_limit')
    assert result.delta_xyz_mm == pytest.approx(6)


def test_screen_motion_rejected_even_with_small_3d_motion():
    gate, pose = policy()
    gate.update(1, 100, pose)
    result = gate.update(2, 200, move(replace(pose, rms_px=3.1), x=4))
    assert (result.mode, result.reason) == ('hidden', 'motion_limit')
    assert result.delta_xyz_mm == pytest.approx(4)
    assert result.delta_eye_px > 5


def test_eye_projection_is_checked_separately_from_camera_projection():
    camera, points, projections, pose = scene(focal=100)
    projections[0][0, 0] = 2000
    gate = QualityContinuation(camera, points, projections)
    gate.update(1, 100, pose)
    result = gate.update(2, 200, move(replace(pose, rms_px=3.1), x=2))
    assert result.delta_camera_px < 5 < result.delta_eye_px
    assert result.mode == 'hidden'


def test_strict_pose_is_unchanged_even_for_large_motion():
    gate, pose = policy()
    gate.update(1, 100, pose)
    current = move(pose, x=50)
    result = gate.update(2, 200, current)
    assert result.mode == 'strict'
    assert result.pose is current


@pytest.mark.parametrize('offset', [800, float('nan')])
def test_out_of_frame_or_nonfinite_geometry_cannot_seed_continuation(offset):
    gate, pose = policy()
    invalid = move(pose, x=offset)
    # Baseline acceptance is not changed; only continuation is disabled.
    assert gate.update(1, 100, invalid).mode == 'strict'
    assert gate.update(2, 200, replace(pose, rms_px=3.1)).mode == 'hidden'


def test_projection_uses_current_pose_and_all_points():
    camera, points, projections, pose = scene()
    geometry = project_geometry(pose, camera, points, projections)
    assert geometry.xyz.shape == (6, 3)
    assert geometry.camera_px.shape == (6, 2)
    assert geometry.eye_px.shape == (2, 6, 2)
    np.testing.assert_allclose(geometry.xyz[0], [-55, -55, 440])
    np.testing.assert_allclose(geometry.camera_px[0], [540, 260])
    np.testing.assert_allclose(geometry.eye_px[0, 0], [960-800*30/440, 440])


def test_half_pixel_candidate_still_requires_recent_continuity():
    camera, points, projections, pose = scene()
    gate = QualityContinuation(camera, points, projections, soft_rms=3.5)
    gate.update(1, 100, pose)
    assert gate.update(2, 200, replace(pose, rms_px=3.5)).mode == 'continued'
    assert gate.update(3, 301, replace(pose, rms_px=3.5)).mode == 'hidden'


@pytest.mark.parametrize('age', [151, -1, float('nan')])
def test_stale_or_invalid_publish_age_cannot_continue(age):
    gate, pose = policy()
    gate.update(1, 100, pose)
    assert gate.update(2, 200, replace(pose, rms_px=3.1), publish_age_ms=age).mode == 'hidden'


def test_stale_strict_pose_cannot_seed_continuation():
    gate, pose = policy()
    assert gate.update(1, 100, pose, publish_age_ms=151).mode == 'strict'
    assert gate.update(2, 200, replace(pose, rms_px=3.1)).mode == 'hidden'


def test_outside_view_coordinates_are_available_for_offline_error_analysis_only():
    camera, points, projections, pose = scene()
    outside = move(pose, x=800)
    with pytest.raises(ValueError, match='outside frame'):
        project_geometry(outside, camera, points, projections)
    geometry = project_geometry(outside, camera, points, projections, require_in_view=False)
    assert geometry.eye_px[0, 0, 0] > 1920


def test_point_two_candidate_uses_3p2_not_rounded_log_text():
    camera, points, projections, pose = scene()
    gate = QualityContinuation(camera, points, projections, soft_rms=3.2)
    gate.update(1, 100, pose)
    assert gate.update(2, 200, replace(pose, rms_px=3.2)).mode == 'continued'
    assert gate.update(3, 250, replace(pose, rms_px=3.20001)).reason == 'quality_limit'
