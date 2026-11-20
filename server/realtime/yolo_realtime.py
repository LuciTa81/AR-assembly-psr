from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import yaml


SCREW_NAMES = ["a", "b", "c", "d"]


def empty_yolo_features(age_frames: int = -1) -> Dict[str, float]:
    features: Dict[str, float] = {
        "yolo_available": 1.0,
        "driver_visible": 0.0,
        "handle_visible": 0.0,
        "screw_visible": 0.0,
        "driver_count": 0.0,
        "handle_count": 0.0,
        "screw_count": 0.0,
        "tool_tip_x": -1.0,
        "tool_tip_y": -1.0,
        "yolo_age_frames": float(age_frames),
    }
    for screw in SCREW_NAMES:
        features[f"tool_dist_{screw}"] = -1.0
        features[f"tool_score_{screw}"] = 0.0
        features[f"tool_near_{screw}"] = 0.0
        features[f"tip_screw_score_{screw}"] = 0.0
    return features


@dataclass
class YoloRealtimeResult:
    enabled: bool
    available: bool = False
    frame_id: int = -1
    latency_ms: int = 0
    reason: str = ""
    features: Dict[str, float] = field(default_factory=dict)
    detections: List[Dict[str, Any]] = field(default_factory=list)
    session_id: str = ""
    timestamp_ms: int = -1
    source_marker_ok: bool = False

    @property
    def evidence_valid(self) -> bool:
        return self.enabled and self.available and self.reason == "ok" and self.source_marker_ok

    def age_ms(self, now_ms: int) -> int:
        return int(now_ms) - self.timestamp_ms if self.timestamp_ms >= 0 else -1

    def age_frames(self, current_frame_id: int) -> int:
        if self.frame_id < 0:
            return -1
        return int(current_frame_id) - int(self.frame_id)


def parse_rect(value: Any) -> Tuple[float, float, float, float]:
    if isinstance(value, dict):
        if all(k in value for k in ["x", "y", "w", "h"]):
            return float(value["x"]), float(value["y"]), float(value["w"]), float(value["h"])
        if all(k in value for k in ["x1", "y1", "x2", "y2"]):
            x1, y1, x2, y2 = map(float, (value["x1"], value["y1"], value["x2"], value["y2"]))
            return x1, y1, x2 - x1, y2 - y1
    if isinstance(value, (list, tuple)) and len(value) == 4:
        return float(value[0]), float(value[1]), float(value[2]), float(value[3])
    raise ValueError(f"Invalid ROI rect: {value}")


def load_screw_centers(layout_path: Path) -> Dict[str, Tuple[float, float]]:
    data = yaml.safe_load(layout_path.read_text(encoding="utf-8")) or {}
    centers: Dict[str, Tuple[float, float]] = {}
    for name in ["screw_a", "screw_b", "screw_c", "screw_d"]:
        x, y, w, h = parse_rect(data.get("rois", {}).get(name))
        centers[name.replace("screw_", "")] = (x + w / 2.0, y + h / 2.0)
    return centers


def make_bbox_points(det: Dict[str, Any]) -> np.ndarray:
    x1, y1, x2, y2 = map(float, (det["x1"], det["y1"], det["x2"], det["y2"]))
    return np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], dtype=np.float32)


def transform_points(homography: np.ndarray, pts: np.ndarray, camera=None) -> np.ndarray:
    import cv2
    if camera is not None:
        pts = cv2.undistortPoints(pts.reshape(-1, 1, 2).astype(np.float64),
                                 camera.matrix, camera.distortion, P=camera.matrix)
    return cv2.perspectiveTransform(pts.reshape(-1, 1, 2).astype(np.float32), homography).reshape(-1, 2)


class MetricToolPlane:
    """Project tool evidence onto the seated screw plane, not the old mat warp.

    This estimates image proximity, not physical contact or tightening torque.
    """

    def __init__(self, camera, workspace):
        from .workspace_projection import finite_array
        self.camera = camera
        targets = np.array([finite_array(workspace.targets[name], (3,), name) for name in "ABCD"])
        if np.ptp(targets[:, 2]) > .5:
            raise ValueError("Metric tool trial requires a common seated screw height")
        self.height = float(np.mean(targets[:, 2]))
        self.offset = 100. - targets[:, :2].min(axis=0)
        self.centers = {name: tuple(xy + self.offset) for name, xy in zip("abcd", targets[:, :2])}
        self.width_mm, self.depth_mm = np.ceil(np.ptp(targets[:, :2], axis=0) + 200).astype(int)

    def homography(self, observation, now):
        import cv2
        from .workspace_projection import finite_array
        if observation is None:
            return None
        age = now - observation["received_at"]
        analysis = observation["analysis"]
        if analysis["status"] != "tracking" or not 0 <= age <= .150:
            return None
        try:
            r = cv2.Rodrigues(finite_array(analysis["rvec"], (3,), "rvec"))[0]
            t = finite_array(analysis["tvec_mm"], (3,), "tvec")
            plane = self.camera.matrix @ np.column_stack((r[:, 0], r[:, 1], t + r[:, 2] * self.height))
            shift = np.array([[1., 0., self.offset[0]], [0., 1., self.offset[1]], [0., 0., 1.]])
            matrix = shift @ np.linalg.inv(plane)
            return matrix if np.isfinite(matrix).all() else None
        except (KeyError, ValueError, np.linalg.LinAlgError):
            return None


def polygon_intersects_workspace(poly: Optional[np.ndarray], width: int, height: int) -> bool:
    if poly is None or len(poly) == 0:
        return False
    if np.any((poly[:, 0] >= 0) & (poly[:, 0] < width) & (poly[:, 1] >= 0) & (poly[:, 1] < height)):
        return True
    x0, x1 = float(np.min(poly[:, 0])), float(np.max(poly[:, 0]))
    y0, y1 = float(np.min(poly[:, 1])), float(np.max(poly[:, 1]))
    return not (x1 < 0 or y1 < 0 or x0 >= width or y0 >= height)


def bbox_center(det: Dict[str, Any]) -> np.ndarray:
    return np.array([(float(det["x1"]) + float(det["x2"])) / 2.0, (float(det["y1"]) + float(det["y2"])) / 2.0], dtype=np.float32)


def long_axis_endpoints(poly: np.ndarray):
    import cv2
    rect = cv2.minAreaRect(poly.astype(np.float32))
    box = cv2.boxPoints(rect).astype(np.float32)
    lens = [np.linalg.norm(box[(i + 1) % 4] - box[i]) for i in range(4)]
    # Long-axis ends are the midpoints of the two SHORT edges.
    i = int(np.argmin(lens))
    mid1 = (box[i] + box[(i + 1) % 4]) / 2.0
    j = (i + 2) % 4
    mid2 = (box[j] + box[(j + 1) % 4]) / 2.0
    return mid1, mid2


def handle_guided_tip(driver_poly: np.ndarray, handle_poly: np.ndarray) -> np.ndarray:
    handle_center = np.mean(handle_poly, axis=0)
    e1, e2 = long_axis_endpoints(driver_poly)
    return e1 if np.linalg.norm(e1 - handle_center) >= np.linalg.norm(e2 - handle_center) else e2


def dist_score(dist: float, radius: float, softness: float) -> float:
    x = max(-60.0, min(60.0, (float(dist) - float(radius)) / max(float(softness), 1e-6)))
    return float(1.0 / (1.0 + np.exp(x)))


class RealtimeYoloAnalyzer:
    def __init__(
        self,
        enabled: bool,
        weights: str,
        layout_path: str,
        conf: float = 0.30,
        imgsz: int = 640,
        interval_frames: int = 3,
        workspace_width: int = 800,
        workspace_height: int = 600,
        tool_score_radius: float = 90.0,
        tool_score_softness: float = 45.0,
        max_age_frames: int = 10,
        session_id: str = "",
        max_age_ms: int = 800,
        metric_plane: Optional[MetricToolPlane] = None,
        nested_driver_dedup: bool = False,
        handle_linked_driver: bool = False,
    ):
        if type(nested_driver_dedup) is not bool or (nested_driver_dedup and metric_plane is None):
            raise ValueError('nested_driver_dedup requires a boolean and metric tool plane')
        self.nested_driver_dedup = nested_driver_dedup
        if type(handle_linked_driver) is not bool or (handle_linked_driver and metric_plane is None):
            raise ValueError('handle_linked_driver requires a boolean and metric tool plane')
        self.handle_linked_driver = handle_linked_driver
        self.enabled = bool(enabled)
        self.available = False
        self.reason = "disabled"
        self.conf = float(conf)
        self.imgsz = int(imgsz)
        self.interval_frames = max(1, int(interval_frames))
        self.workspace_width = int(workspace_width)
        self.workspace_height = int(workspace_height)
        self.tool_score_radius = float(tool_score_radius)
        self.tool_score_softness = float(tool_score_softness)
        self.max_age_frames = max(1, int(max_age_frames))
        self.session_id = session_id
        self.max_age_ms = int(max_age_ms)
        self.metric_plane = metric_plane
        if metric_plane is not None:
            self.workspace_width, self.workspace_height = metric_plane.width_mm, metric_plane.depth_mm
            # Trial-only distances in mm on the screw plane. Not the legacy pixel thresholds.
            self.tool_score_radius, self.tool_score_softness = 12., 4.
        if self.max_age_ms <= 0:
            raise ValueError("max_age_ms must be positive")
        self.model = None
        self.centers: Dict[str, Tuple[float, float]] = {}
        self._pending = None
        self._pending_lock = threading.Lock()
        self._result_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._result = YoloRealtimeResult(enabled=self.enabled, available=False, reason=self.reason)

        if not self.enabled:
            return

        weights_path = Path(weights)
        layout = Path(layout_path)
        if not weights_path.exists():
            self.reason = f"weights_missing:{weights_path}"
            self._result.reason = self.reason
            return
        if metric_plane is None and not layout.exists():
            self.reason = f"layout_missing:{layout}"
            self._result.reason = self.reason
            return

        try:
            from ultralytics import YOLO

            self.model = YOLO(str(weights_path))
            self.centers = dict(metric_plane.centers) if metric_plane is not None else load_screw_centers(layout)
            self.available = True
            self.reason = "ok"
            self._result = YoloRealtimeResult(enabled=True, available=True, reason="warming_up")
            self._thread = threading.Thread(target=self._worker, name="RealtimeYoloAnalyzer", daemon=True)
            self._thread.start()
        except Exception as exc:
            self.reason = f"{type(exc).__name__}:{exc}"
            self._result.reason = self.reason

    def submit(self, frame_id: int, frame_bgr, homography, *, timestamp_ms: int, marker_ok: bool) -> None:
        if not self.enabled or not self.available:
            return
        if not marker_ok or timestamp_ms < 0 or homography is None or frame_id % self.interval_frames != 0:
            return
        with self._pending_lock:
            self._pending = (
                int(frame_id), frame_bgr.copy(), np.array(homography, dtype=np.float64).copy(),
                int(timestamp_ms), bool(marker_ok),
            )

    def get_result(self, current_frame_id: int, *, now_ms: int, min_valid_frame_id: int = 0) -> YoloRealtimeResult:
        with self._result_lock:
            result = self._result
        age = result.age_frames(current_frame_id)
        reason = result.reason
        if reason == "ok":
            if result.session_id != self.session_id:
                reason = "session_mismatch"
            elif not result.source_marker_ok:
                reason = "source_marker_invalid"
            elif result.frame_id > current_frame_id:
                reason = "future_frame"
            elif result.frame_id < min_valid_frame_id:
                reason = "before_tracking_recovery"
            elif result.timestamp_ms < 0:
                reason = "missing_timestamp"
            elif result.age_ms(now_ms) < 0:
                reason = "future_timestamp"
            elif result.age_ms(now_ms) > self.max_age_ms:
                reason = "stale"
        features = dict(result.features) if reason == "ok" else empty_yolo_features(age)
        features["yolo_age_frames"] = float(age)
        features["yolo_age_ms"] = float(result.age_ms(now_ms))
        features["yolo_available"] = float(result.available)
        return replace(
            result, reason=reason, features=features,
            detections=[dict(d) for d in result.detections] if reason == "ok" else [],
        )

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def _worker(self) -> None:
        while not self._stop.is_set():
            item = None
            with self._pending_lock:
                if self._pending is not None:
                    item = self._pending
                    self._pending = None
            if item is None:
                time.sleep(0.01)
                continue
            frame_id, frame_bgr, homography, timestamp_ms, marker_ok = item
            start = time.perf_counter()
            try:
                result = self._process(frame_id, frame_bgr, homography)
            except Exception as exc:
                result = YoloRealtimeResult(
                    enabled=True,
                    available=self.available,
                    frame_id=frame_id,
                    reason=f"{type(exc).__name__}:{exc}",
                )
            result.latency_ms = int((time.perf_counter() - start) * 1000)
            result.session_id = self.session_id
            result.timestamp_ms = timestamp_ms
            result.source_marker_ok = marker_ok
            with self._result_lock:
                self._result = result

    def _process(self, frame_id: int, frame_bgr, homography: np.ndarray) -> YoloRealtimeResult:
        assert self.model is not None
        def project(points):
            return transform_points(homography, points, self.metric_plane.camera if self.metric_plane else None)
        pred = self.model.predict(source=frame_bgr, conf=self.conf, imgsz=self.imgsz, verbose=False)[0]
        detections: List[Dict[str, Any]] = []
        if pred.boxes is not None and len(pred.boxes) > 0:
            for box in pred.boxes:
                class_id = int(box.cls[0].item())
                class_name = str(pred.names.get(class_id, str(class_id))).lower()
                if class_name not in {"driver", "handle", "screw"}:
                    continue
                conf = float(box.conf[0].item())
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                detections.append(
                    {
                        "class": class_name,
                        "confidence": conf,
                        "x1": float(x1),
                        "y1": float(y1),
                        "x2": float(x2),
                        "y2": float(y2),
                    }
                )

        features = empty_yolo_features(0)

        drivers = [d for d in detections if d["class"] == "driver"]
        handles = [d for d in detections if d["class"] == "handle"]
        selected_handle = None
        if self.metric_plane is not None:
            # Scope both ambiguity counting and selection; keep all boxes in diagnostics.
            features["driver_count_raw"] = float(len(drivers))
            local_drivers = []
            for detection in drivers:
                poly = project(make_bbox_points(detection))
                if np.isfinite(poly).all() and polygon_intersects_workspace(
                        poly, self.workspace_width, self.workspace_height):
                    local_drivers.append(detection)
            drivers = local_drivers
            features["driver_count_in_workspace"] = float(len(drivers))
            if len(drivers) > 1:
                import cv2
                # The same thin shaft can survive the detector's looser default NMS.
                boxes = [[d['x1'], d['y1'], d['x2']-d['x1'], d['y2']-d['y1']] for d in drivers]
                keep = cv2.dnn.NMSBoxes(boxes, [d['confidence'] for d in drivers], 0., .5)
                drivers = [drivers[int(i)] for i in np.asarray(keep).reshape(-1)]
            if self.nested_driver_dedup:
                before = len(drivers)
                drivers = self._merge_nested_drivers(drivers, handles)
                features['nested_driver_dedup'] = 1.
                features['driver_nested_duplicates'] = float(before - len(drivers))
            if self.handle_linked_driver:
                before = len(drivers)
                drivers, selected_handle = self._select_handle_linked(drivers, handles)
                features['handle_linked_driver'] = 1.
                features['driver_unlinked_candidates'] = float(before - len(drivers))
        screws = [d for d in detections if d["class"] == "screw"]
        features["driver_visible"] = 1.0 if drivers else 0.0
        features["handle_visible"] = 1.0 if handles else 0.0
        features["screw_visible"] = 1.0 if screws else 0.0
        features["driver_count"] = float(len(drivers))
        features["handle_count"] = float(len(handles))
        features["screw_count"] = float(len(screws))

        best_driver = max(drivers, key=lambda d: d["confidence"], default=None)
        tip = None
        if best_driver is not None:
            driver_poly = project(make_bbox_points(best_driver))
            if polygon_intersects_workspace(driver_poly, self.workspace_width, self.workspace_height):
                best_handle = selected_handle or self._pick_handle(handles, best_driver)
                handle_poly = None
                if best_handle is not None:
                    handle_poly = project(make_bbox_points(best_handle))
                if handle_poly is not None and (selected_handle is not None or
                        polygon_intersects_workspace(handle_poly, self.workspace_width, self.workspace_height)):
                    if self.metric_plane is not None:
                        tip = handle_guided_tip(make_bbox_points(best_driver), make_bbox_points(best_handle))
                        tip = project(np.array([tip]))[0]
                    else:
                        tip = handle_guided_tip(driver_poly, handle_poly)
                    features["tool_tip_source"] = 2.0
                else:
                    # Endpoint estimation is not invariant under a perspective warp.
                    e1, e2 = long_axis_endpoints(make_bbox_points(best_driver) if self.metric_plane else driver_poly)
                    if self.metric_plane is not None:
                        e1, e2 = project(np.array([e1, e2]))
                    min1 = min(np.linalg.norm(e1 - np.array(c, dtype=np.float32)) for c in self.centers.values())
                    min2 = min(np.linalg.norm(e2 - np.array(c, dtype=np.float32)) for c in self.centers.values())
                    tip = e1 if min1 <= min2 else e2
                    features["tool_tip_source"] = 1.0
                features["tool_tip_x"] = float(tip[0])
                features["tool_tip_y"] = float(tip[1])
                for screw, center in self.centers.items():
                    dist = float(np.linalg.norm(np.array(tip, dtype=np.float32) - np.array(center, dtype=np.float32)))
                    score = dist_score(dist, self.tool_score_radius, self.tool_score_softness)
                    features[f"tool_dist_{screw}"] = dist
                    features[f"tool_score_{screw}"] = score
                    features[f"tool_near_{screw}"] = 1.0 if score >= 0.35 else 0.0

        # Legacy screw-box scores use pixel radii; metric trial uses registered centers only.
        if tip is not None and screws and self.metric_plane is None:
            for det in screws:
                screw_poly = transform_points(homography, make_bbox_points(det))
                screw_center = np.mean(screw_poly, axis=0)
                conf = float(det["confidence"])
                for screw, center in self.centers.items():
                    layout_dist = float(np.linalg.norm(screw_center - np.array(center, dtype=np.float32)))
                    layout_score = dist_score(layout_dist, 70.0, 25.0)
                    tip_dist = float(np.linalg.norm(np.array(tip, dtype=np.float32) - screw_center))
                    tip_score = dist_score(tip_dist, 100.0, 30.0)
                    features[f"tip_screw_score_{screw}"] = max(features[f"tip_screw_score_{screw}"], conf * layout_score * tip_score)

        return YoloRealtimeResult(
            enabled=True,
            available=True,
            frame_id=frame_id,
            reason="ok",
            features=features,
            detections=detections,
        )

    def _select_handle_linked(self, drivers, handles):
        if len(drivers) < 2 or not handles:
            return drivers, None
        rects = np.array([[d[k] for k in ('x1', 'y1', 'x2', 'y2')]
                          for d in drivers + handles], dtype=float)
        if not np.isfinite(rects).all() or np.any(rects[:, 2:] <= rects[:, :2]):
            return drivers, None
        links = []
        for driver in drivers:
            ends = np.array(long_axis_endpoints(make_bbox_points(driver)))
            for handle in handles:
                rect = np.array([handle[k] for k in ('x1', 'y1', 'x2', 'y2')])
                gap = np.maximum(0., np.maximum(rect[:2] - ends, ends - rect[2:]))
                attached = np.linalg.norm(gap, axis=1) <= max(4., .25 * min(rect[2:] - rect[:2]))
                if np.count_nonzero(attached) == 1:
                    links.append((driver, handle))
        # Opt-in single-tool setup: keep one unambiguous shaft/handle pair.
        if len(links) != 1:
            return drivers, None
        chosen, handle = links[0]
        return [chosen], handle

    def _merge_nested_drivers(self, drivers, handles):
        kept = []
        for driver in sorted(drivers, key=lambda d: (-d['confidence'], d['x1'], d['y1'], d['x2'], d['y2'])):
            handle = self._pick_handle(handles, driver)
            if handle is not None and any(
                    self._pick_handle(handles, other) is handle
                    and self._same_nested_tip(other, driver, handle) for other in kept):
                continue
            kept.append(driver)
        return kept

    @staticmethod
    def _same_nested_tip(best, fragment, handle):
        # Trial-only: contained shaft fragments must agree on the handle and tip.
        rects = np.array([[d[k] for k in ('x1','y1','x2','y2')] for d in (best, fragment)], dtype=float)
        sizes = rects[:, 2:] - rects[:, :2]
        if not np.isfinite(rects).all() or np.any(sizes <= 0):
            return False
        short = sizes.min(axis=1)
        if (np.any(sizes.max(axis=1) < 2.5 * short)
                or np.argmax(sizes[0]) != np.argmax(sizes[1])
                or min(short) < .5 * max(short)
                or best['confidence'] - fragment['confidence'] < .15):
            return False
        overlap = np.maximum(0., rects[:, 2:].min(axis=0) - rects[:, :2].max(axis=0)).prod()
        if overlap < .75 * sizes.prod(axis=1).min():
            return False
        handle_poly = make_bbox_points(handle)
        if not np.isfinite(handle_poly).all():
            return False
        tips = [handle_guided_tip(make_bbox_points(d), handle_poly) for d in (best, fragment)]
        return np.linalg.norm(tips[0] - tips[1]) <= min(6., .3 * min(short))

    def _pick_handle(self, handles: List[Dict[str, Any]], driver: Dict[str, Any]):
        if not handles:
            return None
        driver_center = bbox_center(driver)
        return max(
            handles,
            key=lambda h: float(h["confidence"]) - 0.002 * float(np.linalg.norm(bbox_center(h) - driver_center)),
        )
