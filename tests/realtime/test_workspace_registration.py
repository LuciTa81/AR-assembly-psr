from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
import pytest

from .test_workspace_projection import camera_data, models, scene, workspace_data


def module():
    from server.realtime import workspace_registration
    return workspace_registration


def inputs(tmp_path):
    camera, workspace, detections, _, _ = scene()
    image = np.full((720, 1280, 3), 255, np.uint8)
    paths = [tmp_path / "input.png", tmp_path / "camera.json", tmp_path / "workspace.json"]
    paths[0].write_bytes(cv2.imencode(".png", image)[1].tobytes())
    paths[1].write_text(json.dumps(camera), encoding="utf-8")
    paths[2].write_text(json.dumps(workspace), encoding="utf-8")
    corners = [v.reshape(1, 4, 2).astype(np.float32) for v in detections.values()]
    ids = np.array(list(detections), np.int32).reshape(-1, 1)
    return paths, (detections, corners, ids)


def test_inspection_preserves_sources_records_provenance_and_outputs_unique_diagnostics(tmp_path):
    paths, detected = inputs(tmp_path)
    original = [p.read_bytes() for p in paths]
    with patch.object(module(), "detect_markers", return_value=detected):
        out = module().inspect_image(*paths, tmp_path / "results")
        second = module().inspect_image(*paths, tmp_path / "results")
    assert out != second
    assert [p.read_bytes() for p in paths] == original
    report = json.loads((out / "report.json").read_text())
    assert report["scope"] == "offline_camera_projection_only"
    assert report["status"] == "pose_estimated"
    assert report["activation_status"] == "not_activated"
    assert report["display_alignment_verified"] is False
    assert report["physical_accuracy_verified"] is False
    assert report["source_sha256"] == hashlib.sha256(original[0]).hexdigest()
    assert report["camera_profile_sha256"] == hashlib.sha256(original[1]).hexdigest()
    assert report["workspace_profile_sha256"] == hashlib.sha256(original[2]).hexdigest()
    assert report["pose"]["rms_undistorted_px"] < .001
    assert all(t["visible"] for t in report["targets"].values())
    assert cv2.imdecode(np.frombuffer((out / "diagnostic.png").read_bytes(), np.uint8), 1).shape == (720, 1280, 3)
    assert (out / "camera-profile.json").is_file()
    assert (out / "workspace-profile.json").is_file()


def test_inspection_reports_lost_markers_without_target_or_old_pose(tmp_path):
    paths, _ = inputs(tmp_path)
    with patch.object(module(), "detect_markers", return_value=({}, [], None)):
        out = module().inspect_image(*paths, tmp_path / "results")
    report = json.loads((out / "report.json").read_text())
    assert report["status"] == "pose_rejected"
    assert report["pose"] is None and report["targets"] == {}
    assert "four" in report["reason"]


def test_pose_only_does_not_invent_screw_positions(tmp_path):
    paths, detected = inputs(tmp_path)
    data = workspace_data()
    data["targets_mm"] = {}
    paths[2].write_text(json.dumps(data), encoding="utf-8")
    with patch.object(module(), "detect_markers", return_value=detected):
        out = module().inspect_image(*paths, tmp_path / "results")
    report = json.loads((out / "report.json").read_text())
    assert report["status"] == "pose_estimated"
    assert report["target_registration"] == "not_registered"
    assert report["targets"] == {}


def test_resolution_mismatch_and_unmeasured_layout_refuse_output(tmp_path):
    paths, _ = inputs(tmp_path)
    data = camera_data()
    data["image_size"] = [1920, 1080]
    paths[1].write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="resolution"):
        module().inspect_image(*paths, tmp_path / "results")
    assert not (tmp_path / "results").exists()
    paths[1].write_text(json.dumps(camera_data()), encoding="utf-8")
    data = workspace_data()
    data["marker_centers_mm"]["0"] = None
    paths[2].write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        module().inspect_image(*paths, tmp_path / "results")
    assert not (tmp_path / "results").exists()


def test_duplicate_known_id_detections_rejected(tmp_path):
    paths, (mapping, corners, ids) = inputs(tmp_path)
    with patch.object(module(), "detect_markers", return_value=(mapping, corners + [corners[0]], np.vstack([ids, ids[:1]]))):
        out = module().inspect_image(*paths, tmp_path / "results")
    report = json.loads((out / "report.json").read_text())
    assert report["status"] == "pose_rejected"
    assert "duplicate" in report["reason"]
    assert report["pose"] is None

def test_register_clicked_heads_uses_pick_height_then_fixed_target_height():
    from server.realtime import workspace_projection as geometry
    camera, board, detections, rvec, tvec = models()
    pose = geometry.estimate_pose(detections, board, camera, (1280, 720))
    clicks = {}
    for name, xyz in board.targets.items():
        head = xyz.copy()
        head[2] = 65
        clicks[name] = cv2.projectPoints(head.reshape(1, 3), rvec, tvec, camera.matrix, camera.distortion)[0].reshape(2)
    registered = module().register_target_points(clicks, 65., 60., pose, camera)
    for name, xyz in board.targets.items():
        np.testing.assert_allclose(registered[name], xyz, atol=.01)


@pytest.mark.parametrize("kind", ["missing", "same_point", "wrong_order", "wrong_spacing", "nan_height"])
def test_register_rejects_bad_clicks_or_inconsistent_measured_square(kind):
    from server.realtime import workspace_projection as geometry
    camera, board, detections, rvec, tvec = models()
    pose = geometry.estimate_pose(detections, board, camera, (1280, 720))
    clicks = {name: cv2.projectPoints(xyz.reshape(1, 3), rvec, tvec, camera.matrix, camera.distortion)[0].reshape(2)
              for name, xyz in board.targets.items()}
    height = 60.
    if kind == "missing":
        del clicks["D"]
    elif kind == "same_point":
        clicks["D"] = clicks["A"]
    elif kind == "wrong_order":
        clicks["B"], clicks["C"] = clicks["C"], clicks["B"]
    elif kind == "wrong_spacing":
        clicks["A"] = clicks["A"] + [40, 0]
    else:
        height = float("nan")
    with pytest.raises(ValueError):
        module().register_target_points(clicks, height, 60., pose, camera)


def test_picker_cancel_closes_window():
    image = np.zeros((720, 1280, 3), np.uint8)
    with patch.object(cv2, "namedWindow"), patch.object(cv2, "imshow"), \
         patch.object(cv2, "setMouseCallback"), patch.object(cv2, "waitKey", return_value=ord("q")), \
         patch.object(cv2, "destroyWindow") as close:
        assert module().collect_target_clicks(image) is None
        close.assert_called_once()


def test_interactive_registration_writes_only_unactivated_candidate(tmp_path):
    paths, detected = inputs(tmp_path)
    camera, board, _, rvec, tvec = models()
    clicks = {name: cv2.projectPoints(xyz.reshape(1, 3), rvec, tvec, camera.matrix, camera.distortion)[0].reshape(2).tolist()
              for name, xyz in board.targets.items()}
    original = paths[2].read_bytes()
    with patch.object(module(), "detect_markers", return_value=detected), \
         patch.object(module(), "collect_target_clicks", return_value=clicks):
        candidate_path = module().pick_workspace_targets(*paths, tmp_path / "results", pick_height_mm=60., target_height_mm=60.)
    candidate = json.loads(candidate_path.read_text())
    assert candidate["activation_status"] == "not_activated"
    assert candidate["display_alignment_verified"] is False
    assert candidate["status"] == "target_candidate_pending_validation"
    assert candidate["target_registration"]["source_image_sha256"] == hashlib.sha256(paths[0].read_bytes()).hexdigest()
    for name, xyz in board.targets.items():
        np.testing.assert_allclose(candidate["targets_mm"][name], xyz, atol=.01)
    assert paths[2].read_bytes() == original


def test_cancel_never_writes_target_candidate(tmp_path):
    paths, detected = inputs(tmp_path)
    with patch.object(module(), "detect_markers", return_value=detected), \
         patch.object(module(), "collect_target_clicks", return_value=None):
        result = module().pick_workspace_targets(*paths, tmp_path / "results", pick_height_mm=60., target_height_mm=60.)
    assert result is None
    assert not list((tmp_path / "results").rglob("target-candidate.json"))


def test_picker_four_click_confirmation_closes_window():
    image = np.zeros((720, 1280, 3), np.uint8)

    def click_four(_window, callback):
        for x, y in [(200, 200), (400, 200), (200, 400), (400, 400)]:
            callback(cv2.EVENT_LBUTTONDOWN, x, y, 0, None)

    with patch.object(cv2, "namedWindow"), patch.object(cv2, "imshow"), \
         patch.object(cv2, "setMouseCallback", side_effect=click_four), \
         patch.object(cv2, "waitKey", return_value=13), patch.object(cv2, "destroyWindow") as close:
        clicks = module().collect_target_clicks(image)
        assert clicks == {"A": [200, 200], "B": [400, 200], "C": [200, 400], "D": [400, 400]}
        close.assert_called_once()


@pytest.mark.parametrize("order", ["BDAC", "CADB", "DCBA"])
def test_cyclic_label_shifts_are_rejected_even_when_square_geometry_matches(order):
    from server.realtime import workspace_projection as geometry
    camera, board, detections, rvec, tvec = models()
    pose = geometry.estimate_pose(detections, board, camera, (1280, 720))
    correct = {name: cv2.projectPoints(xyz.reshape(1, 3), rvec, tvec, camera.matrix, camera.distortion)[0].reshape(2)
               for name, xyz in board.targets.items()}
    rotated = {name: correct[wrong] for name, wrong in zip("ABCD", order)}
    with pytest.raises(ValueError, match="labels"):
        module().register_target_points(rotated, 60., 60., pose, camera)
