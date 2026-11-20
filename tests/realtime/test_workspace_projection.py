from __future__ import annotations

import copy
import json
from itertools import combinations
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
import pytest


def module():
    from server.realtime import workspace_projection
    return workspace_projection


def camera_data():
    return {
        "schema_version": "beast_camera_intrinsics_candidate_v1",
        "profile_id": "synthetic-camera-only",
        "image_size": [1280, 720],
        "distortion_model": "opencv_pinhole_k1_k2_p1_p2_k3",
        "camera_matrix": [[820., 0, 640.], [0, 824., 374.], [0, 0, 1.]],
        "distortion_coefficients": [.11, -.34, .0023, -.0034, .278],
    }


def workspace_data():
    return {
        "schema_version": "beast_workspace_metric_v1", "profile_id": "synthetic-board-only",
        "units": "mm", "axes": "x_right_y_away_z_up", "origin_marker_id": 3,
        "marker_centers_mm": {"0": [0, 240, 0], "1": [200, 240, 0], "2": [400, 240, 0],
                              "3": [0, 0, 0], "4": [200, 0, 0], "5": [400, 0, 0]},
        "targets_mm": {"A": [145, 175, 60], "B": [255, 175, 60],
                       "C": [145, 65, 60], "D": [255, 65, 60]},
    }


def scene():
    cam, board = camera_data(), workspace_data()
    k = np.array(cam["camera_matrix"], dtype=np.float64)
    d = np.array(cam["distortion_coefficients"], dtype=np.float64)
    position = np.array([200., -180., 500.])
    forward = np.array([200., 120., 0.]) - position
    forward /= np.linalg.norm(forward)
    right = np.array([1., 0., 0.])
    down = np.cross(forward, right)
    rotation = np.vstack([right, down, forward])
    rvec = cv2.Rodrigues(rotation)[0]
    tvec = -rotation @ position
    offsets = np.array([[-35, 35, 0], [35, 35, 0], [35, -35, 0], [-35, -35, 0]])
    detections = {
        int(key): cv2.projectPoints(np.array(center, dtype=float) + offsets, rvec, tvec, k, d)[0].reshape(4, 2)
        for key, center in board["marker_centers_mm"].items()
    }
    return cam, board, detections, rvec, tvec


def models():
    cam, board, detections, rvec, tvec = scene()
    return module().CameraModel.from_profile(cam), module().MetricWorkspace.from_dict(board), detections, rvec, tvec


def corner_scene(ids=(0, 1, 2), camera_shift=(13., 5., 7.)):
    camera, board, _, rvec, tvec = models()
    tvec = tvec - cv2.Rodrigues(rvec)[0] @ np.array(camera_shift)
    offsets = np.array([[-35., 35., 0.], [35., 35., 0.], [35., -35., 0.], [-35., -35., 0.]])
    world, detections = {}, {}
    for key in ids:
        angle = np.radians(key * 37.)
        rotation = np.array([[np.cos(angle), -np.sin(angle), 0],
                             [np.sin(angle), np.cos(angle), 0], [0, 0, 1.]])
        world[key] = offsets @ rotation.T + board.markers[key]
        detections[key] = cv2.projectPoints(world[key], rvec, tvec, camera.matrix,
                                           camera.distortion)[0].reshape(4, 2)
    return camera, board, world, detections, rvec, tvec


@pytest.mark.parametrize('ids', [(0, 1, 2), (0, 1, 2, 4), (0, 2, 4, 5)])
def test_corner_candidate_recovers_pose_with_explicit_rotated_marker_corners(ids):
    camera, board, world, detections, rvec, tvec = corner_scene(ids)
    original = copy.deepcopy(detections)
    with patch('cv2.VideoCapture', side_effect=AssertionError('camera forbidden')):
        pose = module().estimate_corner_pose(detections, world, camera, camera.image_size)
    assert pose.marker_ids == sorted(ids)
    assert pose.observed_corners_px.shape == (4 * len(ids), 2)
    assert pose.projected_corners_px.shape == (4 * len(ids), 2)
    assert not isinstance(pose, module().WorkspacePose)
    assert pose.rms_px < .001
    np.testing.assert_allclose(pose.camera_position_mm, [213., -175., 507.], atol=.01)
    np.testing.assert_allclose(pose.tvec.reshape(3), tvec, atol=.01)
    np.testing.assert_allclose(cv2.Rodrigues(pose.rvec)[0], cv2.Rodrigues(rvec)[0], atol=1e-4)
    projected_a = module().project_targets(pose, board, camera)['A']['pixel']
    expected_a = cv2.projectPoints(board.targets['A'].reshape(1, 3), rvec, tvec,
                                   camera.matrix, camera.distortion)[0].reshape(2)
    np.testing.assert_allclose(projected_a, expected_a, atol=.01)
    for key in ids:
        np.testing.assert_array_equal(detections[key], original[key])


def test_symmetric_corner_scene_returns_correct_pose_or_rejects_nonfinite_solver_output():
    # OpenCV 4.14 IPPE returns NaN for this exact round-trip input on this host.
    # Other numerical implementations may solve it; neither may return a bad pose.
    camera, _, world, detections, _, _ = corner_scene((0, 1, 2, 4), camera_shift=(0., 0., 0.))
    try:
        pose = module().estimate_corner_pose(detections, world, camera, camera.image_size)
    except ValueError as exc:
        assert 'pose solver returned only nonfinite candidates' in str(exc)
    else:
        np.testing.assert_allclose(pose.camera_position_mm, [200., -180., 500.], atol=.01)
        assert pose.rms_px < .001


def test_corner_candidate_does_not_change_live_center_requirements():
    camera, board, world, detections, _, _ = corner_scene()
    assert module().estimate_corner_pose(detections, world, camera, camera.image_size).rms_px < .001
    with pytest.raises(ValueError, match='four visible'):
        module().estimate_pose(detections, board, camera, camera.image_size)


def test_corner_candidate_ignores_unregistered_ids_without_inventing_geometry():
    camera, _, world, detections, _, _ = corner_scene()
    detections = dict(reversed(list(detections.items())))
    detections[37] = np.full((4, 2), np.nan)
    pose = module().estimate_corner_pose(detections, world, camera, camera.image_size)
    assert pose.marker_ids == [0, 1, 2]
    assert pose.rms_px < .001


def test_corner_candidate_rejects_reversed_small_marker_even_below_error_limits():
    camera, _, world, detections, rvec, tvec = corner_scene()
    center = world[0].mean(axis=0)
    world[0] = center + (world[0] - center) * .04
    detections[0] = cv2.projectPoints(world[0], rvec, tvec, camera.matrix,
                                     camera.distortion)[0].reshape(4, 2)
    valid = module().estimate_corner_pose(detections, world, camera, camera.image_size)
    assert valid.rms_px < .001
    detections[0] = detections[0][::-1].copy()
    with pytest.raises(ValueError, match='Image marker corner winding'):
        module().estimate_corner_pose(detections, world, camera, camera.image_size)


@pytest.mark.parametrize('fault', [
    'two_markers', 'resolution', 'centers_only', 'nonplanar', 'nonfinite_world',
    'reversed_world', 'crossed_world', 'bad_id', 'outside', 'nonfinite_image',
    'collapsed_image', 'wrong_corner_start', 'outlier',
])
def test_corner_candidate_refuses_invalid_or_inconsistent_evidence(fault):
    camera, _, world, detections, _, _ = corner_scene()
    size = camera.image_size
    if fault == 'two_markers':
        detections.pop(2)
    elif fault == 'resolution':
        size = (640, 480)
    elif fault == 'centers_only':
        world = {key: value.mean(axis=0) for key, value in world.items()}
    elif fault == 'nonplanar':
        world[0][0, 2] = 1.
    elif fault == 'nonfinite_world':
        world[0][0, 0] = np.nan
    elif fault == 'reversed_world':
        world[0] = world[0][::-1].copy()
    elif fault == 'crossed_world':
        world[0] = world[0][[0, 2, 1, 3]].copy()
    elif fault == 'bad_id':
        world['0'] = world.pop(0)
    elif fault == 'outside':
        detections[0][0, 0] = -1.
    elif fault == 'nonfinite_image':
        detections[0][0, 0] = np.nan
    elif fault == 'collapsed_image':
        detections[0][:] = detections[0][0]
    elif fault == 'wrong_corner_start':
        detections[0] = np.roll(detections[0], 1, axis=0)
    else:
        detections[0] += [45., 15.]
    with pytest.raises(ValueError):
        module().estimate_corner_pose(detections, world, camera, size)


@pytest.mark.parametrize('limit,value', [
    ('max_rms_px', 0), ('max_point_error_px', -1), ('ambiguity_gap_px', np.nan),
])
def test_corner_candidate_rejects_invalid_diagnostic_limits(limit, value):
    camera, _, world, detections, _, _ = corner_scene()
    with pytest.raises(ValueError, match='finite and positive'):
        module().estimate_corner_pose(detections, world, camera, camera.image_size, **{limit: value})


def test_corner_candidate_keeps_ambiguity_guard_before_refinement():
    camera, _, world, detections, _, _ = corner_scene()
    with pytest.raises(ValueError, match='ambiguous'):
        module().estimate_corner_pose(detections, world, camera, camera.image_size,
                                     ambiguity_gap_px=1000.)


@pytest.mark.parametrize('failure', ['solver', 'no_candidates', 'nonfinite', 'refinement', 'unphysical'])
def test_corner_candidate_never_returns_pose_after_solver_or_physical_failure(failure):
    camera, _, world, detections, rvec, tvec = corner_scene()
    function = 'solvePnPGeneric'
    if failure == 'solver':
        settings = dict(side_effect=cv2.error('solver failed'))
    elif failure == 'no_candidates':
        settings = dict(return_value=(0, (), (), None))
    elif failure == 'nonfinite':
        settings = dict(return_value=(1, (np.full((3, 1), np.nan),), (tvec,), None))
    else:
        function = 'solvePnPRefineLM'
        settings = (dict(side_effect=cv2.error('refinement failed')) if failure == 'refinement'
                    else dict(return_value=(rvec, -tvec)))
    with patch.object(cv2, function, **settings), pytest.raises(ValueError):
        module().estimate_corner_pose(detections, world, camera, camera.image_size)


def test_marker_center_is_diagonal_intersection_after_undistortion():
    cam, board, detections, rvec, tvec = scene()
    camera = module().CameraModel.from_profile(cam)
    actual = module().marker_center_px(detections[0], camera)
    expected = cv2.projectPoints(np.array([board["marker_centers_mm"]["0"]], float), rvec, tvec,
                                 np.array(cam["camera_matrix"]), None)[0].reshape(2)
    np.testing.assert_allclose(actual, expected, atol=.001)
    naive = cv2.undistortPoints(detections[0].reshape(-1, 1, 2), camera.matrix,
                                camera.distortion, P=camera.matrix).reshape(4, 2).mean(axis=0)
    assert np.linalg.norm(naive - expected) > .1


def test_pose_recovers_above_board_camera_and_height_aware_targets():
    camera, board, detections, rvec, tvec = models()
    pose = module().estimate_pose(detections, board, camera, (1280, 720))
    assert pose.rms_px < .001
    np.testing.assert_allclose(cv2.Rodrigues(pose.rvec)[0], cv2.Rodrigues(rvec)[0], atol=1e-4)
    np.testing.assert_allclose(pose.tvec.reshape(3), tvec, atol=.01)
    assert pose.camera_position_mm[2] > 0
    targets = module().project_targets(pose, board, camera)
    for name, xyz in board.targets.items():
        expected = cv2.projectPoints(np.array([xyz]), rvec, tvec, camera.matrix, camera.distortion)[0].reshape(2)
        assert targets[name]["visible"]
        np.testing.assert_allclose(targets[name]["pixel"], expected, atol=.01)
        recovered = module().pixel_to_plane(expected, 60., pose, camera)
        np.testing.assert_allclose(recovered, xyz, atol=.01)
    flat = cv2.projectPoints(np.array([[145., 175., 0.]]), rvec, tvec, camera.matrix, camera.distortion)[0].reshape(2)
    assert np.linalg.norm(np.array(targets["A"]["pixel"]) - flat) > 10


def test_order_independent_and_unknown_ids_ignored():
    camera, board, detections, _, _ = models()
    baseline = module().estimate_pose(detections, board, camera, (1280, 720))
    reordered = dict(reversed(list(detections.items())))
    reordered[37] = detections[0]
    actual = module().estimate_pose(reordered, board, camera, (1280, 720))
    assert actual.marker_ids == [0, 1, 2, 3, 4, 5]
    np.testing.assert_allclose(actual.tvec, baseline.tvec)


def test_only_four_spread_markers_can_estimate_pose():
    camera, board, detections, _, _ = models()
    subset = {k: detections[k] for k in (0, 2, 3, 5)}
    assert module().estimate_pose(subset, board, camera, (1280, 720)).rms_px < .001


@pytest.mark.parametrize('ids', list(combinations(range(6), 4)))
def test_four_marker_support_depends_on_geometry_not_count(ids):
    camera, board, detections, _, _ = models()
    subset = {key: detections[key] for key in ids}
    three_on_one_row = set((0, 1, 2)).issubset(ids) or set((3, 4, 5)).issubset(ids)
    points = np.array([board.markers[key][:2] for key in ids])
    with patch.object(cv2, 'solvePnPGeneric', wraps=cv2.solvePnPGeneric) as solve:
        if three_on_one_row:
            with pytest.raises(ValueError, match='marker geometry.*IPPE'):
                module().estimate_pose(subset, board, camera, camera.image_size)
            solve.assert_not_called()
        else:
            # Geometry support is necessary, not sufficient: the solver can still fail.
            module().require_ippe_support(points)


def test_five_markers_with_three_on_one_row_still_constrain_pose():
    camera, board, detections, _, _ = models()
    pose = module().estimate_pose({k: detections[k] for k in (0, 1, 2, 4, 5)},
                                  board, camera, camera.image_size)
    assert pose.rms_px < .001
    np.testing.assert_allclose(pose.camera_position_mm, [200., -180., 500.], atol=.01)


def test_nonfinite_ippe_candidates_are_reported_as_solver_failure():
    camera, board, detections, _, tvec = models()
    with patch.object(cv2, 'solvePnPGeneric', return_value=(
            2, (np.full((3, 1), np.nan),) * 2, (tvec,) * 2, None)):
        with pytest.raises(ValueError, match='pose solver.*nonfinite'):
            module().estimate_pose(detections, board, camera, camera.image_size)


def test_no_ippe_candidates_are_reported_separately_from_unphysical_pose():
    camera, board, detections, _, _ = models()
    with patch.object(cv2, 'solvePnPGeneric', return_value=(0, (), (), None)):
        with pytest.raises(ValueError, match='pose solver.*no candidates'):
            module().estimate_pose(detections, board, camera, camera.image_size)


@pytest.mark.parametrize('ids,expected_rms', [
    ((0, 1, 2, 4, 5), 2.5755988),
    ((0, 1, 2, 4), None), ((0, 1, 2, 5), None),
    ((0, 1, 4, 5), 2.7958810), ((0, 2, 4, 5), 1.6991407),
    ((1, 2, 4, 5), 1.5854646),
])
def test_saved_numeric_observations_preserve_valid_subsets_and_explain_failure(ids, expected_rms):
    fixture = json.loads((Path(__file__).parent/'fixtures/workspace_pose_comfort.json').read_text())
    camera = module().CameraModel.from_profile(fixture['camera'])
    board = module().MetricWorkspace.from_dict(fixture['workspace'])
    detections = {key: np.array(fixture['detected_corners_px'][str(key)]) for key in ids}
    if expected_rms is None:
        with pytest.raises(ValueError, match='marker geometry.*IPPE'):
            module().estimate_pose(detections, board, camera, camera.image_size)
    else:
        pose = module().estimate_pose(detections, board, camera, camera.image_size)
        assert pose.rms_px == pytest.approx(expected_rms, abs=1e-4)
        assert pose.camera_position_mm[2] > 0


def test_pose_refines_noisy_initial_estimate_before_unchanged_error_gates():
    camera, board, detections, _, _ = models()
    rng = np.random.default_rng(9)
    noisy = {key: corners + rng.normal(0, 2.5, 2) for key, corners in detections.items()}
    objects = np.array(list(board.markers.values()))
    observed = np.array([module().marker_center_px(corners, camera) for corners in noisy.values()])
    _, rotations, translations, _ = cv2.solvePnPGeneric(
        objects, observed, camera.matrix, None, flags=cv2.SOLVEPNP_IPPE)
    initial = cv2.projectPoints(objects, rotations[0], translations[0], camera.matrix, None)[0].reshape(-1, 2)
    assert np.sqrt(np.mean(np.sum((initial - observed) ** 2, axis=1))) > 3.

    pose = module().estimate_pose(noisy, board, camera, camera.image_size)
    assert pose.rms_px < 2.9
    assert pose.max_error_px < 5.
    assert pose.camera_position_mm[2] > 0
    with pytest.raises(ValueError, match="reprojection error"):
        module().estimate_pose(noisy, board, camera, camera.image_size, max_rms_px=2.)


def test_pose_refinement_failure_refuses_pose():
    camera, board, detections, _, _ = models()
    with patch.object(cv2, "solvePnPRefineLM", side_effect=cv2.error("refinement failed")):
        with pytest.raises(ValueError, match="refinement failed"):
            module().estimate_pose(detections, board, camera, camera.image_size)


@pytest.mark.parametrize("invalid", ["nan", "below_mat"])
def test_refined_pose_is_rechecked_for_finite_and_physical_coordinates(invalid):
    camera, board, detections, rvec, tvec = models()
    if invalid == "nan":
        rvec = np.full((3, 1), float("nan"))
    else:
        tvec = -tvec
    with patch.object(cv2, "solvePnPRefineLM", return_value=(rvec, tvec)):
        with pytest.raises(ValueError, match="No physical"):
            module().estimate_pose(detections, board, camera, camera.image_size)


@pytest.mark.parametrize("field,value", [
    ("image_size", [640, 0]), ("camera_matrix", [[0, 0, 640], [0, 824, 374], [0, 0, 1]]),
    ("distortion_coefficients", [0, 0, float("nan"), 0, 0]),
    ("distortion_coefficients", [0, 0, 0, 0]), ("distortion_model", "fisheye"),
    ("profile_id", ""), ("schema_version", "unknown"),
])
def test_invalid_camera_profile_rejected(field, value):
    data = camera_data()
    data[field] = value
    with pytest.raises(ValueError):
        module().CameraModel.from_profile(data)


@pytest.mark.parametrize("change", ["null", "units", "axes", "nonplanar", "duplicate", "collinear", "origin", "target"])
def test_bad_metric_layout_rejected(change):
    data = workspace_data()
    if change == "null":
        data["marker_centers_mm"]["0"] = None
    elif change in ("units", "axes"):
        data[change] = "wrong"
    elif change == "nonplanar":
        data["marker_centers_mm"]["0"][2] = 1
    elif change == "duplicate":
        data["marker_centers_mm"]["0"] = [0, 0, 0]
    elif change == "collinear":
        data["marker_centers_mm"] = {str(i): [i * 100 - 300, 0, 0] for i in range(6)}
    elif change == "origin":
        data["marker_centers_mm"]["3"] = [1, 0, 0]
    else:
        data["targets_mm"]["A"][2] = -60
    with pytest.raises(ValueError):
        module().MetricWorkspace.from_dict(data)


@pytest.mark.parametrize("fault", ["missing", "resolution", "corners_nan", "outside", "collapsed", "misregistered"])
def test_bad_frame_refuses_pose_instead_of_fallback(fault):
    camera, board, detections, _, _ = models()
    size = (1280, 720)
    if fault == "missing":
        detections = {k: detections[k] for k in (0, 1, 2)}
    elif fault == "resolution":
        size = (640, 480)
    elif fault == "corners_nan":
        detections[0][0, 0] = float("nan")
    elif fault == "outside":
        detections[0][0, 0] = -1
    elif fault == "collapsed":
        detections[0][:] = detections[0][0]
    else:
        detections[0] += [45, 15]
    with pytest.raises(ValueError):
        module().estimate_pose(detections, board, camera, size)


def test_failed_solver_and_materially_different_ambiguous_candidates_refused():
    camera, board, detections, rvec, tvec = models()
    with patch.object(cv2, "solvePnPGeneric", return_value=(0, (), (), None)):
        with pytest.raises(ValueError, match="pose"):
            module().estimate_pose(detections, board, camera, (1280, 720))
    # A deliberately loose ambiguity gate exercises the alternate planar solution.
    with pytest.raises(ValueError, match="ambiguous"):
        module().estimate_pose(detections, board, camera, (1280, 720), ambiguity_gap_px=1000.)


def test_offscreen_or_behind_targets_hidden_and_inverse_plane_rejects_invalid():
    camera, board, detections, _, _ = models()
    pose = module().estimate_pose(detections, board, camera, (1280, 720))
    data = workspace_data()
    data["targets_mm"] = {"outside": [5000, 120, 60], "behind": [200, 120, 2000]}
    far_board = module().MetricWorkspace.from_dict(data)
    result = module().project_targets(pose, far_board, camera)
    assert not result["outside"]["visible"]
    assert result["outside"]["reason"] == "outside_image"
    assert not result["behind"]["visible"]
    assert result["behind"]["reason"] == "behind_camera"
    for pixel, height in [([-1, 10], 60), ([640, 360], float("nan")), ([640, 360], 2000)]:
        with pytest.raises(ValueError):
            module().pixel_to_plane(pixel, height, pose, camera)


def test_pose_only_workspace_has_no_fabricated_targets():
    camera, _, detections, _, _ = models()
    data = workspace_data()
    data["targets_mm"] = {}
    board = module().MetricWorkspace.from_dict(data)
    pose = module().estimate_pose(detections, board, camera, (1280, 720))
    assert module().project_targets(pose, board, camera) == {}
