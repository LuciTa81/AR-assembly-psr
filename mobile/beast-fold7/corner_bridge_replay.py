"""Offline-only view-to-view planar corner transfer; no calibration writes."""
import cv2
import numpy as np
import pose_replay_compare as replay


def warp(points, homography):
    p = np.column_stack([np.asarray(points).reshape(-1, 2), np.ones(len(points))]) @ homography.T
    if not np.isfinite(p).all() or np.any(p[:, 2] <= 1e-8):
        raise ValueError('invalid_transfer')
    return p[:, :2] / p[:, 2:]


def fit_homography(source, target):
    h, _ = cv2.findHomography(source, target, 0)
    if h is None or not np.isfinite(h).all():
        raise ValueError('invalid_homography')
    return h / h[2, 2]


class CornerBridge:
    def __init__(self, workspace, camera, max_age_ms=3000, conservative_three=False,retain_reference_on_loss=False):
        self.workspace, self.camera = workspace, camera
        self.max_age_ms = max_age_ms
        self.conservative_three = conservative_three
        self.retain_reference_on_loss=retain_reference_on_loss
        self.anchor = None
        self.anchor_centers = None
        self.anchor_ms = None
        self.last_ms = None

    def update(self, timestamp, detections, precise=None):
        if self.last_ms is not None and timestamp <= self.last_ms:
            self.anchor = None
            self.last_ms = timestamp
            return None, {'reason': 'nonmonotonic_time'}
        self.last_ms = timestamp
        try:
            if set(detections) - set(self.workspace.markers):
                raise ValueError('unknown_marker')
            # Validate the real quadrilaterals through the unchanged center routine.
            centers = {k: replay.marker_center_px(q, self.camera) for k, q in detections.items()}
            refined = detections if precise is None else {k:q for k,q in precise.items() if k in detections}
            if len(detections) >= 5:
                pose, reason = replay.baseline(detections, self.workspace, self.camera)
                if pose is not None:
                    if set(refined) == set(detections):
                        self.anchor = {k: np.array(q, dtype=float).copy() for k, q in refined.items()}
                        self.anchor_centers = centers
                        self.anchor_ms = timestamp
                return pose, {'reason': reason, 'method': 'baseline'}
            if len(detections) < 3:
                if not self.retain_reference_on_loss:self.anchor = None
                raise ValueError('need_three_markers')
            if self.anchor is None or timestamp - self.anchor_ms > self.max_age_ms:
                raise ValueError('reference_expired')
            if set(detections) - set(self.anchor):
                raise ValueError('reference_missing_marker')
            if set(refined) != set(detections):
                raise ValueError('precise_corners_missing')
            for q in refined.values():
                replay.marker_center_px(q, self.camera)
            keys = sorted(detections)
            if len(keys)==3 and self.conservative_three:
                xy=np.array([self.workspace.markers[k][:2] for k in keys])
                singular=np.linalg.svd(xy-xy.mean(axis=0),compute_uv=False)
                if singular[1]/singular[0]<.05:
                    raise ValueError('three_marker_collinear')
            def undistort(q):
                return cv2.undistortPoints(np.asarray(q).reshape(-1, 1, 2), self.camera.matrix,
                                          self.camera.distortion, P=self.camera.matrix).reshape(-1, 2)
            source = np.concatenate([undistort(self.anchor[k]) for k in keys])
            target = np.concatenate([undistort(refined[k]) for k in keys])
            h = fit_homography(source, target)
            errors = np.linalg.norm(warp(source, h) - target, axis=1)
            rms = float(np.sqrt(np.mean(errors ** 2)))
            if rms > 1.5 or errors.max() > 3:
                raise ValueError('corner_transfer_residual')
            all_keys = sorted(self.anchor)
            original = np.array([self.anchor_centers[k] for k in all_keys])
            transferred = warp(original, h)
            # Whole-marker holdout detects extrapolation and one-marker dominance.
            spread = 0.
            alternatives=[]
            for i in range(len(keys)):
                keep = np.ones(len(source), dtype=bool)
                keep[i*4:i*4+4] = False
                alternate = fit_homography(source[keep], target[keep])
                alternatives.append(warp(original,alternate))
                spread = max(spread, float(np.linalg.norm(warp(original, alternate)-transferred, axis=1).max()))
            if spread > 3:
                raise ValueError('transfer_uncertain')
            observed = np.array([centers[k] if k in centers else transferred[i] for i, k in enumerate(all_keys)])
            objects = np.array([self.workspace.markers[k] for k in all_keys])
            pose = replay._estimate_planar_pose(objects, observed, all_keys, self.camera, 3.2, 5., .25)
            if len(keys)==3 and self.conservative_three:
                for points in alternatives:
                    alternate_observed=np.array([centers[k] if k in centers else points[i] for i,k in enumerate(all_keys)])
                    alternate_pose=replay._estimate_planar_pose(objects,alternate_observed,all_keys,self.camera,3.2,5.,.25)
                    delta=replay.target_deltas(pose,alternate_pose,self.workspace,self.camera)
                    if delta['max_target_delta_px']>3 or delta['max_target_delta_mm']>3:
                        raise ValueError('three_marker_pose_uncertain')
            return pose, dict(reason='tracking', method='corner_bridge', age_ms=timestamp-self.anchor_ms,
                              transfer_rms=rms, transfer_spread=spread, visible_ids=keys)
        except (ValueError, cv2.error) as exc:
            return None, {'reason': str(exc)}
