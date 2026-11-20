"""Offline display-only candidate. Does not authorize workflow evidence."""

from dataclasses import dataclass
import math

import cv2
import numpy as np


@dataclass(frozen=True)
class Geometry:
    xyz: np.ndarray
    camera_px: np.ndarray
    eye_px: np.ndarray


@dataclass(frozen=True)
class Decision:
    mode: str
    reason: str
    pose: object = None
    delta_xyz_mm: float = 0
    delta_camera_px: float = 0
    delta_eye_px: float = 0


def project_geometry(pose, camera, points, projections, require_in_view=True):
    xyz = points @ cv2.Rodrigues(pose.rvec)[0].T + pose.tvec.reshape(3)
    pixels = cv2.projectPoints(points, pose.rvec, pose.tvec,
                              camera.matrix, camera.distortion)[0].reshape(-1, 2)
    homogeneous = np.column_stack((xyz, np.ones(len(points))))
    screens = [homogeneous @ projection.T for projection in projections]
    if (not np.isfinite(xyz).all() or not np.isfinite(pixels).all()
            or np.any(xyz[:, 2] <= 0)
            or any(not np.isfinite(s).all() or np.any(s[:, 2] <= 0) for s in screens)):
        raise ValueError('Invalid projection')
    eyes = np.array([s[:, :2] / s[:, 2, None] for s in screens])
    if not np.isfinite(eyes).all():
        raise ValueError('Invalid projection')
    if require_in_view and (np.any(pixels < 0)
            or np.any(pixels >= np.array(camera.image_size))
            or np.any(eyes < 0) or np.any(eyes >= [1920, 1080])):
        raise ValueError('Projection outside frame')
    return Geometry(xyz, pixels, eyes)


class QualityContinuation:
    def __init__(self, camera, points, projections, soft_rms=3.25):
        if not 3 < soft_rms <= 3.5:
            raise ValueError('Offline candidate RMS must be in (3, 3.5]')
        self.camera = camera
        self.points = np.array(points, dtype=float, copy=True)
        self.projections = np.array(projections, dtype=float, copy=True)
        if (self.points.ndim != 2 or self.points.shape[1] != 3
                or len(self.points) < 4 or not np.isfinite(self.points).all()
                or self.projections.shape != (2, 3, 4)
                or not np.isfinite(self.projections).all()):
            raise ValueError('Expected finite object points and two 3x4 eye projections')
        self.soft_rms = soft_rms
        self.anchor = None
        self.last_frame = -1
        self.last_time = -math.inf

    def _hidden(self, reason, **deltas):
        self.anchor = None
        return Decision('hidden', reason, **deltas)

    def update(self, frame, timestamp_ms, pose, publish_age_ms=0):
        if (not math.isfinite(timestamp_ms) or frame <= self.last_frame
                or timestamp_ms <= self.last_time):
            return self._hidden('non_monotonic_input')
        self.last_frame, self.last_time = frame, timestamp_ms
        if pose is None:
            return self._hidden('no_current_pose')
        if (not math.isfinite(pose.rms_px) or not math.isfinite(pose.max_error_px)
                or pose.rms_px < 0 or pose.max_error_px < 0):
            return self._hidden('invalid_quality')
        strict = pose.rms_px <= 3 and pose.max_error_px <= 5
        if not math.isfinite(publish_age_ms) or not 0 <= publish_age_ms <= 150:
            self.anchor = None
            return Decision('strict', 'baseline', pose) if strict else Decision('hidden', 'stale_input')
        if not strict and (pose.rms_px > self.soft_rms or pose.max_error_px > 5):
            return self._hidden('quality_limit')
        try:
            current = project_geometry(pose, self.camera, self.points, self.projections)
        except (ValueError, cv2.error):
            self.anchor = None
            # A new safeguard must not change the existing strict acceptance policy.
            return Decision('strict', 'baseline', pose) if strict else Decision('hidden', 'projection_invalid')
        ids = tuple(pose.marker_ids)
        if strict:
            self.anchor = (timestamp_ms, ids, current) if len(ids) >= 5 else None
            return Decision('strict', 'baseline', pose)
        if self.anchor is None:
            return self._hidden('no_anchor')
        anchor_time, anchor_ids, previous = self.anchor
        if timestamp_ms - anchor_time > 200:
            return self._hidden('expired')
        if len(ids) < 5 or ids != anchor_ids:
            return self._hidden('marker_set_changed')
        deltas = dict(
            delta_xyz_mm=float(np.max(np.linalg.norm(current.xyz-previous.xyz, axis=-1))),
            delta_camera_px=float(np.max(np.linalg.norm(current.camera_px-previous.camera_px, axis=-1))),
            delta_eye_px=float(np.max(np.linalg.norm(current.eye_px-previous.eye_px, axis=-1))))
        if any(value > 5 for value in deltas.values()):
            return self._hidden('motion_limit', **deltas)
        # Continuation returns the current measurement and never renews the deadline.
        return Decision('continued', 'bounded_quality_continuation', pose, **deltas)
