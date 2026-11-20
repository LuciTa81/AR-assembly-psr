"""Metric workspace projection for offline diagnostics, not eye/display alignment."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .camera_calibration import validate_size


def finite_array(value, shape, name):
    try:
        array = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name}: numeric coordinates required") from exc
    if array.shape != shape or not np.isfinite(array).all():
        raise ValueError(f"{name}: expected finite shape {shape}")
    return array


@dataclass(frozen=True)
class CameraModel:
    profile_id: str
    image_size: tuple[int, int]
    matrix: np.ndarray
    distortion: np.ndarray

    @classmethod
    def from_profile(cls, data: dict) -> "CameraModel":
        if data.get("schema_version") != "beast_camera_intrinsics_candidate_v1":
            raise ValueError("Unsupported camera profile schema")
        if data.get("distortion_model") != "opencv_pinhole_k1_k2_p1_p2_k3":
            raise ValueError("Expected the calibrated five-coefficient pinhole model")
        profile_id = data.get("profile_id")
        if not isinstance(profile_id, str) or not profile_id.strip():
            raise ValueError("Camera profile_id is required")
        try:
            size = validate_size(data.get("image_size"))
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid camera image_size") from exc
        k = finite_array(data.get("camera_matrix"), (3, 3), "camera_matrix")
        d = finite_array(data.get("distortion_coefficients"), (5,), "distortion_coefficients")
        if (k[0, 0] <= 0 or k[1, 1] <= 0 or not np.allclose(k[2], [0, 0, 1])
                or k[0, 1] != 0 or k[1, 0] != 0 or not 0 <= k[0, 2] < size[0]
                or not 0 <= k[1, 2] < size[1]):
            raise ValueError("Invalid camera intrinsics")
        return cls(profile_id, size, k, d)


def require_spread(points, name):
    xy = np.asarray(points, dtype=np.float64).reshape(-1, 2)
    if len(np.unique(xy, axis=0)) != len(xy):
        raise ValueError(f"{name}: duplicate points")
    singular = np.linalg.svd(xy - xy.mean(axis=0), compute_uv=False)
    if singular[0] < 1 or singular[1] / singular[0] < .03:
        raise ValueError(f"{name}: points must span a plane, not a line")


def require_ippe_support(points):
    xy = np.asarray(points, dtype=np.float64).reshape(-1, 2)
    require_spread(xy, "Visible metric markers")
    centered = xy - xy.mean(axis=0)
    xy = centered / np.sqrt(np.mean(np.sum(centered ** 2, axis=1)))
    p = np.column_stack([xy, np.ones(len(xy))])
    # The identity homography must have eight independent constraints. Planar
    # spread alone misses four centers with three collinear. Normalize for units.
    design = np.zeros((2 * len(xy), 9), dtype=np.float64)
    design[0::2, :3] = p
    design[1::2, 3:6] = p
    design[0::2, 6:] = -xy[:, 0, None] * p
    design[1::2, 6:] = -xy[:, 1, None] * p
    if np.linalg.matrix_rank(design, tol=1e-10) < 8:
        raise ValueError("Visible marker geometry is degenerate for IPPE; show a wider marker arrangement")


@dataclass(frozen=True)
class MetricWorkspace:
    profile_id: str
    markers: dict[int, np.ndarray]
    targets: dict[str, np.ndarray]

    @classmethod
    def from_dict(cls, data: dict) -> "MetricWorkspace":
        if (data.get("schema_version") != "beast_workspace_metric_v1"
                or data.get("units") != "mm" or data.get("axes") != "x_right_y_away_z_up"
                or data.get("origin_marker_id") != 3):
            raise ValueError("Expected metric workspace in mm with marker 3 origin and X-right/Y-away/Z-up")
        profile_id = data.get("profile_id")
        if not isinstance(profile_id, str) or not profile_id.strip():
            raise ValueError("Workspace profile_id is required")
        source = data.get("marker_centers_mm")
        if not isinstance(source, dict) or not 4 <= len(source) <= 50:
            raise ValueError("At least four measured marker centers are required")
        markers = {}
        for key, value in source.items():
            if not isinstance(key, str) or not key.isdecimal() or not 0 <= int(key) < 50 or int(key) in markers:
                raise ValueError("Marker IDs must be unique DICT_4X4_50 IDs")
            point = finite_array(value, (3,), f"marker {key}")
            if point[2] != 0:
                raise ValueError("Marker centers must lie on the mat plane Z=0")
            markers[int(key)] = point
        if 3 not in markers or not np.array_equal(markers[3], [0, 0, 0]):
            raise ValueError("Marker 3 must be the origin [0,0,0]")
        require_spread(np.array(list(markers.values()))[:, :2], "Metric markers")
        targets = {}
        target_source = data.get("targets_mm", {})
        if not isinstance(target_source, dict):
            raise ValueError("targets_mm must be a mapping, or empty while unregistered")
        for key, value in target_source.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("Target names must be nonempty strings")
            point = finite_array(value, (3,), f"target {key}")
            if point[2] < 0:
                raise ValueError("Target height cannot be below the mat")
            targets[key] = point
        return cls(profile_id, markers, targets)


def _undistorted_marker_corners(corners, camera: CameraModel) -> np.ndarray:
    points = finite_array(np.asarray(corners).reshape(-1, 2), (4, 2), "marker corners")
    width, height = camera.image_size
    if (points < 0).any() or (points[:, 0] >= width).any() or (points[:, 1] >= height).any():
        raise ValueError("Marker corners outside calibrated image")
    points = cv2.undistortPoints(points.reshape(-1, 1, 2), camera.matrix,
                                 camera.distortion, P=camera.matrix).reshape(4, 2)
    contour = points.astype(np.float32)
    if not np.isfinite(points).all() or not cv2.isContourConvex(contour) or abs(cv2.contourArea(contour)) < 4:
        raise ValueError("Degenerate or unordered marker corners")
    return points


def marker_center_px(corners, camera: CameraModel) -> np.ndarray:
    # Diagonals meet at the physical square center only in the undistorted image.
    points = _undistorted_marker_corners(corners, camera)
    homogeneous = np.column_stack([points, np.ones(4)])
    first = np.cross(homogeneous[0], homogeneous[2])
    second = np.cross(homogeneous[1], homogeneous[3])
    intersection = np.cross(first, second)
    if not np.isfinite(intersection).all() or abs(intersection[2]) < 1e-9:
        raise ValueError("Marker diagonal intersection is invalid")
    return intersection[:2] / intersection[2]


@dataclass(frozen=True)
class WorkspacePose:
    rvec: np.ndarray
    tvec: np.ndarray
    camera_position_mm: np.ndarray
    marker_ids: list[int]
    observed_centers_px: np.ndarray
    projected_centers_px: np.ndarray
    rms_px: float
    max_error_px: float


@dataclass(frozen=True)
class CornerPoseCandidate:
    """Offline result; residuals cover all corners, not the marker centers."""

    rvec: np.ndarray
    tvec: np.ndarray
    camera_position_mm: np.ndarray
    marker_ids: list[int]
    observed_corners_px: np.ndarray
    projected_corners_px: np.ndarray
    rms_px: float
    max_error_px: float


def _physical_pose(rvec, tvec, objects, observed, ids, camera, *, result_type=WorkspacePose):
    if not np.isfinite(rvec).all() or not np.isfinite(tvec).all():
        return None
    rotation = cv2.Rodrigues(rvec)[0]
    tvec = np.asarray(tvec).reshape(3, 1)
    position = (-rotation.T @ tvec).reshape(3)
    depths = (rotation @ objects.T + tvec)[2]
    if position[2] <= 0 or (depths <= 0).any():
        return None
    projected = cv2.projectPoints(objects, rvec, tvec, camera.matrix, None)[0].reshape(-1, 2)
    errors = np.linalg.norm(projected - observed, axis=1)
    if not np.isfinite(errors).all():
        return None
    return result_type(rvec, tvec, position, ids, observed, projected,
                       float(np.sqrt(np.mean(errors ** 2))), float(errors.max()))


def estimate_pose(detections: dict, workspace: MetricWorkspace, camera: CameraModel,
                  image_size, *, max_rms_px=3., max_point_error_px=5.,
                  ambiguity_gap_px=.25) -> WorkspacePose:
    if tuple(image_size) != camera.image_size:
        raise ValueError("Frame resolution differs from camera calibration")
    limits = np.array([max_rms_px, max_point_error_px, ambiguity_gap_px], float)
    if not np.isfinite(limits).all() or (limits <= 0).any():
        raise ValueError("Pose diagnostic limits must be finite and positive")
    ids = sorted(set(detections) & set(workspace.markers))
    if len(ids) < 4:
        raise ValueError("At least four visible measured markers required for pose")
    objects = np.array([workspace.markers[key] for key in ids], np.float64)
    observed = np.array([marker_center_px(detections[key], camera) for key in ids], np.float64)
    return _estimate_planar_pose(objects, observed, ids, camera,
                                 max_rms_px, max_point_error_px, ambiguity_gap_px)


def estimate_corner_pose(detections: dict, marker_corners_mm: dict, camera: CameraModel,
                         image_size, *, max_rms_px=3., max_point_error_px=5.,
                         ambiguity_gap_px=.25) -> CornerPoseCandidate:
    """Offline only: explicit world corners in detector order, X-right/Y-away/Z-up.

    Each marker is a clockwise quad in workspace XY at Z=0. Its first corner
    must match that decoded marker's first detected corner, not image top-left.
    This function never infers side length/orientation or loads a live profile.
    """
    if tuple(image_size) != camera.image_size:
        raise ValueError("Frame resolution differs from camera calibration")
    limits = np.array([max_rms_px, max_point_error_px, ambiguity_gap_px], float)
    if not np.isfinite(limits).all() or (limits <= 0).any():
        raise ValueError("Pose diagnostic limits must be finite and positive")
    if (not isinstance(marker_corners_mm, dict) or not marker_corners_mm
            or any(type(key) is not int or not 0 <= key < 50 for key in marker_corners_mm)):
        raise ValueError("Explicit metric corners with integer DICT_4X4_50 IDs required")
    ids = sorted(set(detections) & set(marker_corners_mm))
    if len(ids) < 3:
        raise ValueError("At least three visible registered markers required for corner candidate")
    objects, observed = [], []
    for key in ids:
        quad = finite_array(marker_corners_mm[key], (4, 3), f"marker {key} world corners")
        contour = np.ascontiguousarray(quad[:, :2], dtype=np.float32)
        if ((quad[:, 2] != 0).any() or not cv2.isContourConvex(contour)
                or cv2.contourArea(contour, oriented=True) >= -1.):
            raise ValueError("Metric marker corners must be clockwise convex quads on Z=0")
        objects.append(quad)
        image_corners = _undistorted_marker_corners(detections[key], camera)
        if cv2.contourArea(image_corners.astype(np.float32), oriented=True) <= 0:
            raise ValueError("Image marker corner winding must match the decoded front face")
        observed.append(image_corners)
    return _estimate_planar_pose(np.concatenate(objects), np.concatenate(observed), ids, camera,
                                 max_rms_px, max_point_error_px, ambiguity_gap_px,
                                 result_type=CornerPoseCandidate)


def _estimate_planar_pose(objects, observed, ids, camera, max_rms_px, max_point_error_px,
                          ambiguity_gap_px, *, result_type=WorkspacePose,
                          solver=cv2.SOLVEPNP_IPPE):
    if solver == cv2.SOLVEPNP_IPPE:
        require_ippe_support(objects[:, :2])
    elif solver == cv2.SOLVEPNP_SQPNP:
        require_spread(objects[:, :2], "Visible metric markers")
    else:
        raise ValueError("Unsupported workspace pose solver")
    require_spread(observed, "Visible image markers")
    try:
        count, rotations, translations, _ = cv2.solvePnPGeneric(
            objects, observed, camera.matrix, None, flags=solver)
    except cv2.error as exc:
        raise ValueError("Workspace pose solver failed") from exc
    if not count:
        raise ValueError("Workspace pose solver returned no candidates")
    candidates = []
    finite_candidates = 0
    for rvec, tvec in zip(rotations, translations):
        if not np.isfinite(rvec).all() or not np.isfinite(tvec).all():
            continue
        finite_candidates += 1
        candidate = _physical_pose(rvec, tvec, objects, observed, ids, camera, result_type=result_type)
        if candidate is not None:
            candidates.append(candidate)
    if not finite_candidates:
        raise ValueError("Workspace pose solver returned only nonfinite candidates")
    if not candidates:
        raise ValueError("No physical workspace pose above the mat")
    candidates.sort(key=lambda pose: pose.rms_px)
    best = candidates[0]
    if len(candidates) > 1:
        other = candidates[1]
        relative = cv2.Rodrigues(best.rvec)[0] @ cv2.Rodrigues(other.rvec)[0].T
        angle = np.degrees(np.arccos(np.clip((np.trace(relative) - 1) / 2, -1, 1)))
        distance = np.linalg.norm(best.camera_position_mm - other.camera_position_mm)
        if other.rms_px - best.rms_px < ambiguity_gap_px and (angle > 2 or distance > 5):
            raise ValueError("Workspace pose is ambiguous; use a more oblique or closer view")
    # Reject ambiguous seeds before refinement can merge them into the same solution.
    try:
        rvec, tvec = cv2.solvePnPRefineLM(
            objects, observed, camera.matrix, None, best.rvec.copy(), best.tvec.copy())
    except cv2.error as exc:
        raise ValueError("Workspace pose refinement failed") from exc
    refined = _physical_pose(rvec, tvec, objects, observed, ids, camera, result_type=result_type)
    if refined is None:
        raise ValueError("No physical workspace pose after refinement")
    best = refined
    if best.rms_px > max_rms_px or best.max_error_px > max_point_error_px:
        raise ValueError(f"Workspace pose reprojection error too high: RMS {best.rms_px:.2f}px, max {best.max_error_px:.2f}px")
    return best


def project_targets(pose: WorkspacePose, workspace: MetricWorkspace, camera: CameraModel) -> dict:
    rotation = cv2.Rodrigues(pose.rvec)[0]
    result = {}
    width, height = camera.image_size
    for name, xyz in workspace.targets.items():
        depth = float((rotation @ xyz + pose.tvec.reshape(3))[2])
        if depth <= 0:
            result[name] = {"visible": False, "pixel": None, "reason": "behind_camera"}
            continue
        pixel = cv2.projectPoints(xyz.reshape(1, 3), pose.rvec, pose.tvec, camera.matrix,
                                   camera.distortion)[0].reshape(2)
        visible = bool(np.isfinite(pixel).all() and 0 <= pixel[0] < width and 0 <= pixel[1] < height)
        result[name] = {"visible": visible, "pixel": pixel.tolist() if visible else None,
                        "reason": "" if visible else "outside_image"}
    return result


def pixel_to_plane(pixel, height_mm: float, pose: WorkspacePose, camera: CameraModel) -> np.ndarray:
    point = finite_array(pixel, (2,), "pixel")
    width, height = camera.image_size
    if not 0 <= point[0] < width or not 0 <= point[1] < height:
        raise ValueError("Pixel outside calibrated image")
    if not np.isfinite(height_mm) or height_mm < 0:
        raise ValueError("Plane height must be finite and nonnegative")
    normalized = cv2.undistortPoints(point.reshape(1, 1, 2), camera.matrix, camera.distortion).reshape(2)
    direction = cv2.Rodrigues(pose.rvec)[0].T @ np.array([*normalized, 1.])
    if not np.isfinite(direction).all() or abs(direction[2]) < 1e-9:
        raise ValueError("Viewing ray parallel to target plane")
    distance = (height_mm - pose.camera_position_mm[2]) / direction[2]
    if not np.isfinite(distance) or distance <= 0:
        raise ValueError("Target plane is behind camera along this viewing ray")
    return pose.camera_position_mm + distance * direction
