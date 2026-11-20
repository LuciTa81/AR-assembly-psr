import copy
from dataclasses import asdict
import importlib
import json
from pathlib import Path

import numpy as np
import pytest

from server.realtime.schemas import OverlayMessage


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/spatial_guidance_v1.json"


def fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def project(changes=None, now=1025):
    module = importlib.import_module("server.realtime.display_calibration")
    data = fixture()
    target = dict(data["input"], **(changes or {}))
    return module.project_display(module.SyntheticDisplayProfile.from_dict(data["profile"]), target, now)


def test_known_asymmetric_eye_projection_matches_shared_wire_fixture():
    actual = asdict(project())
    expected = fixture()["expected"]["spatial"]
    assert actual.keys() == expected.keys()
    for key in expected:
        if key.endswith("_pixel"):
            assert actual[key] == pytest.approx(expected[key])
        else:
            assert actual[key] == expected[key]
    envelope = OverlayMessage(spatial=project()).to_dict()
    assert envelope["schema_version"] == "realtime_v1"
    assert envelope["spatial"] == actual
    json.dumps(envelope, allow_nan=False)


@pytest.mark.parametrize("xyz,left,right", [
    ([50, 25, 500], [1088, 580], [990.8, 580.12]),
    ([-50, -25, 500], [928, 500], [826.8, 499.12]),
    ([0, 0, 1000], [984, 540], [933.4, 538.81]),
])
def test_opencv_axes_and_mm_eye_baseline_are_not_camera_image_pixels(xyz, left, right):
    actual = project({"camera_xyz_mm": xyz})
    assert actual.left_pixel == pytest.approx(left)
    assert actual.right_pixel == pytest.approx(right)


@pytest.mark.parametrize("changes,reason", [
    ({"camera_xyz_mm": [0, 0, -1]}, "behind_camera"),
    ({"camera_xyz_mm": [0, 0, 0]}, "behind_camera"),
    ({"camera_xyz_mm": [1000, 0, 500]}, "outside_display"),
    ({"camera_xyz_mm": [0, -1000, 500]}, "outside_display"),
    ({"camera_xyz_mm": [float("nan"), 0, 500]}, "invalid_target"),
    ({"camera_xyz_mm": [0, float("inf"), 500]}, "invalid_target"),
    ({"camera_xyz_mm": [0, 500]}, "invalid_target"),
    ({"camera_xyz_mm": None}, "invalid_target"),
    ({"target_id": "unknown"}, "invalid_target"),
    ({"camera_profile_id": "another-camera"}, "profile_mismatch"),
    ({"workspace_profile_id": "another-board"}, "profile_mismatch"),
    ({"camera_profile_sha256": "c" * 64}, "profile_mismatch"),
    ({"workspace_profile_sha256": "d" * 64}, "profile_mismatch"),
    ({"pose_frame_id": 0}, "invalid_pose"),
    ({"pose_frame_id": True}, "invalid_pose"),
    ({"pose_timestamp_ms": None}, "invalid_pose"),
    ({"pose_timestamp_ms": float("nan")}, "invalid_pose"),
    ({"pose_timestamp_ms": 1026}, "invalid_pose"),
])
def test_invalid_targets_return_hidden_strict_json_not_old_coordinates(changes, reason):
    actual = project(changes)
    assert not actual.target_visible
    assert actual.left_pixel is None and actual.right_pixel is None
    assert actual.reason == reason
    json.dumps(asdict(actual), allow_nan=False)


def test_freshness_boundary_and_no_synthetic_verified_promotion():
    assert project(now=1150).target_visible
    old = project(now=1151)
    assert not old.target_visible and old.reason == "stale_pose"
    assert old.pose_age_ms == 151
    assert old.calibration_status == "synthetic"
    assert old.display_alignment_verified is False
    assert old.left_pixel is None and old.right_pixel is None


@pytest.mark.parametrize("field,value", [
    ("schema_version", "beast_display_calibrated_v1"),
    ("calibration_status", "verified"),
    ("display_alignment_verified", True),
    ("display_alignment_verified", None),
    ("units", "m"), ("camera_axes", "unity"), ("display_mode", "mono"),
    ("coordinate_convention", "framebuffer_pixels"),
    ("channel_order", "swapped"), ("eye_size", [3840, 1080]),
    ("profile_id", ""), ("camera_profile_sha256", "a"),
    ("workspace_profile_id", ""),
    ("left_projection", [[0, 0, 0, 0]] * 3),
    ("right_projection", [[1, 0, 0, 0], [0, 1, 0, 0]]),
    ("right_projection", [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, float("nan"), 0]]),
])
def test_profile_is_explicit_synthetic_geometry_not_a_real_calibration(field, value):
    module = importlib.import_module("server.realtime.display_calibration")
    data = fixture()["profile"]
    data[field] = value
    with pytest.raises(ValueError):
        module.SyntheticDisplayProfile.from_dict(data)


def test_eye_behind_projection_and_one_eye_outside_hide_both():
    module = importlib.import_module("server.realtime.display_calibration")
    data = fixture()
    profile = copy.deepcopy(data["profile"])
    profile["right_projection"][2][3] = -600
    result = module.project_display(module.SyntheticDisplayProfile.from_dict(profile), data["input"], 1025)
    assert result.reason == "behind_eye"
    assert result.left_pixel is None and result.right_pixel is None
    # Left x=1952 is outside; right x=1876.4 remains inside. No half-valid pair.
    result = project({"camera_xyz_mm": [590, 0, 500]})
    assert result.reason == "outside_display"
    assert result.left_pixel is None and result.right_pixel is None


def test_profile_copies_arrays_and_legacy_message_has_no_fabricated_spatial():
    module = importlib.import_module("server.realtime.display_calibration")
    data = fixture()
    data["profile"]["left_projection"] = np.array(data["profile"]["left_projection"], float)
    profile = module.SyntheticDisplayProfile.from_dict(data["profile"])
    data["profile"]["left_projection"][0, 0] = 0
    result = module.project_display(profile, dict(data["input"], camera_xyz_mm=[50, 0, 500]), 1025)
    assert result.left_pixel[0] == pytest.approx(1088)
    assert OverlayMessage().to_dict()["spatial"] is None

