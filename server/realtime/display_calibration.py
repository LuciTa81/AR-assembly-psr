"""Synthetic eye projection math; no fitted Beast calibration or runtime activation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .schemas import SPATIAL_POSE_BUDGET_MS, SpatialGuidance, pose_age_ms
from .workspace_projection import finite_array


BINDING_FIELDS = ("camera_profile_id", "workspace_profile_id",
                  "camera_profile_sha256", "workspace_profile_sha256")


@dataclass(frozen=True)
class SyntheticDisplayProfile:
    profile_id: str
    camera_profile_id: str
    workspace_profile_id: str
    camera_profile_sha256: str
    workspace_profile_sha256: str
    left_projection: np.ndarray
    right_projection: np.ndarray

    @classmethod
    def from_dict(cls, data: dict) -> "SyntheticDisplayProfile":
        expected = {
            "schema_version": "beast_display_projection_synthetic_v1",
            "calibration_status": "synthetic",
            "units": "mm",
            "camera_axes": "x_right_y_down_z_forward",
            "coordinate_convention": "eye_local_pixels_top_left",
            "channel_order": "left_half_left_eye_right_half_right_eye",
            "display_mode": "full_sbs",
        }
        if (not isinstance(data, dict) or any(data.get(k) != v for k, v in expected.items())
                or data.get("display_alignment_verified") is not False
                or data.get("eye_size") != [1920, 1080]):
            raise ValueError("Expected an explicit unverified synthetic Full SBS profile")
        for name in ("profile_id", *BINDING_FIELDS):
            value = data.get(name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Missing {name}")
            if name.endswith("_sha256") and (len(value) != 64 or any(c not in "0123456789abcdef" for c in value)):
                raise ValueError(f"Invalid {name}")
        matrices = []
        for eye in ("left", "right"):
            matrix = finite_array(data.get(f"{eye}_projection"), (3, 4), f"{eye} projection").copy()
            if np.linalg.matrix_rank(matrix[:, :3]) != 3:
                raise ValueError("Projection must have a nonsingular 3x3 camera block")
            matrix.setflags(write=False)
            matrices.append(matrix)
        return cls(data["profile_id"], *(data[name] for name in BINDING_FIELDS), *matrices)


def project_display(profile: SyntheticDisplayProfile, target: dict, current_ms: int) -> SpatialGuidance:
    """Input xyz is Rodrigues(pose.rvec) @ workspace target + pose.tvec, in mm.

    The caller supplies only accepted poses, retaining the original capture-return
    perf_counter timestamp. target_visible permits a synthetic preview, not real AR.
    """
    result = SpatialGuidance(display_profile_id=profile.profile_id,
                             **{name: getattr(profile, name) for name in BINDING_FIELDS})
    if not isinstance(target, dict):
        result.reason = "invalid_target"
        return result
    result.target_id = target.get("target_id") if target.get("target_id") in ("A", "B", "C", "D") else ""
    frame_id, timestamp = target.get("pose_frame_id"), target.get("pose_timestamp_ms")
    if type(frame_id) is int and 0 < frame_id < 2**63:
        result.pose_frame_id = frame_id
    if type(timestamp) is int and 0 < timestamp < 2**63:
        result.pose_timestamp_ms = timestamp
    result.pose_age_ms = pose_age_ms(result.pose_timestamp_ms, current_ms)
    if any(target.get(name) != getattr(profile, name) for name in BINDING_FIELDS):
        result.reason = "profile_mismatch"
        return result
    if result.pose_frame_id < 1 or result.pose_age_ms < 0:
        result.reason = "invalid_pose"
        return result
    if result.pose_age_ms > SPATIAL_POSE_BUDGET_MS:
        result.reason = "stale_pose"
        return result
    try:
        xyz = finite_array(target.get("camera_xyz_mm"), (3,), "camera_xyz_mm")
        if not result.target_id:
            raise ValueError("Unknown target")
    except ValueError:
        result.reason = "invalid_target"
        return result
    if xyz[2] <= 0:
        result.reason = "behind_camera"
        return result
    pixels = []
    for matrix in (profile.left_projection, profile.right_projection):
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            homogeneous = matrix @ np.append(xyz, 1.)
            if not np.isfinite(homogeneous).all() or homogeneous[2] <= 1e-9:
                result.reason = "behind_eye"
                return result
            pixel = homogeneous[:2] / homogeneous[2]
        if (not np.isfinite(pixel).all() or not 0 <= pixel[0] < result.eye_width
                or not 0 <= pixel[1] < result.eye_height):
            result.reason = "outside_display"
            return result
        pixels.append(pixel.tolist())
    result.left_pixel, result.right_pixel = pixels
    result.target_visible, result.reason = True, ""
    return result
