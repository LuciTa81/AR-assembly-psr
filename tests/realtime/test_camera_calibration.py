from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
import pytest


def module():
    from server.realtime import camera_calibration
    return camera_calibration


def board_image():
    image = np.full((480, 640, 3), 255, np.uint8)
    for row in range(7):
        for column in range(10):
            if (row + column) % 2 == 0:
                image[60 + row * 40:100 + row * 40, 100 + column * 40:140 + column * 40] = 0
    return image


def test_object_points_have_physical_scale_and_row_major_order():
    points = module().checkerboard_object_points(9, 6, 25)
    assert points.shape == (54, 3)
    assert points.dtype == np.float32
    np.testing.assert_array_equal(points[[0, 1, 9, -1]], [[0, 0, 0], [25, 0, 0], [0, 25, 0], [200, 125, 0]])


@pytest.mark.parametrize("columns,rows,square", [(0, 6, 25), (9, 1, 25), (9.5, 6, 25), (9, 6, 0), (9, 6, float("nan"))])
def test_invalid_target_geometry_is_rejected(columns, rows, square):
    with pytest.raises(ValueError):
        module().checkerboard_object_points(columns, rows, square)


def test_detector_finds_real_rendered_board_and_rejects_blank():
    corners = module().detect_checkerboard(board_image(), (9, 6))
    assert corners.shape == (54, 2)
    assert module().detect_checkerboard(np.full((480, 640), 255, np.uint8), (9, 6)) is None


@pytest.mark.parametrize("image", [None, np.zeros((0, 0), np.uint8), np.zeros((20, 20, 4), np.uint8)])
def test_detector_rejects_invalid_images(image):
    with pytest.raises(ValueError):
        module().detect_checkerboard(image, (9, 6))


def make_session(tmp_path):
    return module().CaptureSession(tmp_path, camera_index=1, backend="dshow", image_size=(640, 480),
                                   pattern_size=(9, 6), square_mm=25, inventory={"scope": "test"})


def test_capture_requires_preview_confirmation_and_preserves_original_pixels(tmp_path):
    session = make_session(tmp_path)
    image = board_image()
    with pytest.raises(ValueError, match="confirm"):
        session.save(image, frame_id=1)
    assert not list(session.directory.glob("*.png"))
    session.confirm_preview()
    row = session.save(image, frame_id=2)
    actual = cv2.imdecode(np.frombuffer((session.directory / row["image_path"]).read_bytes(), np.uint8), cv2.IMREAD_COLOR)
    np.testing.assert_array_equal(actual, image)
    manifest = json.loads((session.directory / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["camera"]["identity_confirmation"] == "user_preview"
    assert manifest["images"][0]["frame_id"] == 2
    assert manifest["image_size"] == [640, 480]


def test_capture_refuses_duplicates_blank_and_size_changes(tmp_path):
    session = make_session(tmp_path)
    session.confirm_preview()
    session.save(board_image(), frame_id=1)
    with pytest.raises(ValueError, match="duplicate"):
        session.save(board_image(), frame_id=2)
    with pytest.raises(ValueError, match="checkerboard"):
        session.save(np.zeros((480, 640, 3), np.uint8), frame_id=3)
    with pytest.raises(ValueError, match="resolution"):
        session.save(np.zeros((720, 1280, 3), np.uint8), frame_id=4)
    assert len(session.manifest["images"]) == 1


def test_sessions_are_unique_and_close_records_status(tmp_path):
    first, second = make_session(tmp_path), make_session(tmp_path)
    assert first.directory != second.directory
    first.close("cancelled")
    assert json.loads((first.directory / "manifest.json").read_text())["status"] == "cancelled"


class FakeCamera:
    def __init__(self, image=None, fail=False):
        self.image = board_image() if image is None else image
        self.fail = fail
        self.released = False

    def isOpened(self):
        return True

    def set(self, *_):
        return True

    def get(self, *_):
        return 0

    def read(self):
        return (False, None) if self.fail else (True, self.image.copy())

    def release(self):
        self.released = True


def run_fake_capture(tmp_path, camera, keys):
    args = module().parse_args(["capture", "--camera-index", "1", "--width", "640", "--height", "480",
                                "--square-mm", "25", "--out-root", str(tmp_path)])
    with patch.object(cv2, "VideoCapture", return_value=camera), \
         patch.object(cv2, "namedWindow"), patch.object(cv2, "resizeWindow"), \
         patch.object(cv2, "imshow"), patch.object(cv2, "destroyAllWindows"), \
         patch.object(cv2, "getWindowProperty", return_value=1), \
         patch.object(cv2, "waitKey", side_effect=keys), \
         patch.object(module(), "device_inventory", return_value={"scope": "test"}):
        return module().capture(args)


def test_cancel_releases_camera_without_saving_preview(tmp_path):
    camera = FakeCamera()
    result = run_fake_capture(tmp_path, camera, [ord("q")])
    assert camera.released
    assert not list(result.glob("*.png"))


def test_capture_read_failure_releases_camera(tmp_path):
    camera = FakeCamera(fail=True)
    with pytest.raises(RuntimeError, match="read"):
        run_fake_capture(tmp_path, camera, [-1] * 20)
    assert camera.released


def test_capture_negotiated_resolution_mismatch_releases_camera(tmp_path):
    camera = FakeCamera(image=np.zeros((720, 1280, 3), np.uint8))
    with pytest.raises(ValueError, match="resolution"):
        run_fake_capture(tmp_path, camera, [-1])
    assert camera.released


def synthetic_views(count=20):
    obj = np.zeros((54, 3), np.float32)
    obj[:, :2] = np.mgrid[0:9, 0:6].T.reshape(-1, 2) * 25
    k = np.array([[880., 0, 642.], [0, 875., 358.], [0, 0, 1.]])
    distortion = np.array([-.08, .02, .001, -.002, .0])
    rng = np.random.default_rng(41)
    views = []
    for _ in range(count):
        rotation = rng.uniform([-.5, -.45, -.3], [.5, .45, .3])
        translation = rng.uniform([-180., -110., 550.], [-20., -10., 850.])
        points, _ = cv2.projectPoints(obj, rotation, translation, k, distortion)
        views.append(points.reshape(-1, 2).astype(np.float32))
    return views, k


def test_calibration_recovers_synthetic_intrinsics_and_reserves_holdouts():
    views, expected = synthetic_views()
    original = cv2.calibrateCamera
    with patch.object(cv2, "calibrateCamera", wraps=original) as fit:
        result = module().calibrate_views(views, (1280, 720), (9, 6), 25)
    assert result["fit_indices"] == [i for i in range(20) if i % 5 != 4]
    assert result["holdout_indices"] == [4, 9, 14, 19]
    assert len(fit.call_args.args[1]) == 16
    for actual, i in zip(fit.call_args.args[1], result["fit_indices"]):
        np.testing.assert_array_equal(actual.reshape(-1, 2), views[i])
    np.testing.assert_allclose(result["camera_matrix"], expected, atol=.05)
    assert result["holdout_rms_px"] < .01
    assert len(result["distortion_coefficients"]) == 5
    assert result["status"] == "candidate"
    assert result["display_alignment_verified"] is False


def test_calibration_refuses_too_few_duplicate_nonfinite_and_outside_points():
    views, _ = synthetic_views()
    for invalid in (views[:14], [views[0]] * 20,
                    [np.full((54, 2), np.nan, np.float32)] + views[1:],
                    [np.full((54, 2), -1., np.float32)] + views[1:]):
        with pytest.raises(ValueError):
            module().calibrate_views(invalid, (1280, 720), (9, 6), 25)


def test_solve_rejects_tampered_image_and_records_failure_report(tmp_path):
    session = make_session(tmp_path)
    session.confirm_preview()
    row = session.save(board_image(), frame_id=1)
    (session.directory / row["image_path"]).write_bytes(b"broken")
    with pytest.raises(ValueError, match="usable"):
        module().solve_session(session.directory)
    reports = list(session.directory.glob("analysis-*.json"))
    assert len(reports) == 1
    report = json.loads(reports[0].read_text())
    assert report["status"] == "failed"
    assert "hash" in report["rejected_images"][0]["reason"]
    assert not list(session.directory.glob("candidate-*.json"))


def test_solve_records_mixed_resolution_and_does_not_read_outside_session(tmp_path):
    session = make_session(tmp_path)
    session.confirm_preview()
    row = session.save(board_image(), frame_id=1)
    session.manifest["image_size"] = [1280, 720]
    session.manifest["images"].append({"image_path": "../outside.png", "sha256": "x"})
    session._persist()
    with pytest.raises(ValueError, match="usable"):
        module().solve_session(session.directory)
    report = json.loads(next(session.directory.glob("analysis-*.json")).read_text())
    assert len(report["rejected_images"]) == 2
    assert "resolution" in report["rejected_images"][0]["reason"]
    assert "outside" in report["rejected_images"][1]["reason"]


def test_full_image_capture_to_offline_candidate_pipeline(tmp_path):
    session = module().CaptureSession(tmp_path, camera_index=1, backend="dshow", image_size=(1280, 720),
                                     pattern_size=(9, 6), square_mm=25, inventory={"scope": "synthetic_test"})
    session.confirm_preview()
    source = np.array([[140, 100], [460, 100], [460, 300], [140, 300]], np.float32)
    objects = np.array([[0, 0, 0], [200, 0, 0], [200, 125, 0], [0, 125, 0]], np.float32)
    expected = np.array([[880., 0, 642.], [0, 875., 358.], [0, 0, 1.]])
    rng = np.random.default_rng(41)
    for index in range(20):
        rotation = rng.uniform([-.5, -.45, -.3], [.5, .45, .3])
        translation = rng.uniform([-180., -110., 550.], [-20., -10., 850.])
        target, _ = cv2.projectPoints(objects, rotation, translation, expected, np.zeros(5))
        matrix = cv2.getPerspectiveTransform(source, target.reshape(-1, 2))
        rendered = cv2.warpPerspective(board_image(), matrix, (1280, 720), borderValue=(255, 255, 255))
        session.save(rendered, frame_id=index + 1)
    session.close("captured")
    output = module().solve_session(session.directory)
    candidate = json.loads(output.read_text())
    assert len(candidate["images"]) == 20
    assert candidate["rejected_images"] == []
    assert candidate["holdout_rms_px"] < .5
    np.testing.assert_allclose(np.array(candidate["camera_matrix"])[[0, 1], [0, 1]], [880, 875], atol=5)
    second_output = module().solve_session(session.directory)
    assert output != second_output and output.exists()
