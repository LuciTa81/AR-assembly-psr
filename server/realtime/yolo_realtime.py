from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
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

    def age_frames(self, current_frame_id: int) -> int:
        if self.frame_id < 0:
            return -1
        return max(0, int(current_frame_id) - int(self.frame_id))


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


def transform_points(homography: np.ndarray, pts: np.ndarray) -> np.ndarray:
    return cv2.perspectiveTransform(pts.reshape(-1, 1, 2).astype(np.float32), homography).reshape(-1, 2)


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
    rect = cv2.minAreaRect(poly.astype(np.float32))
    box = cv2.boxPoints(rect).astype(np.float32)
    lens = [np.linalg.norm(box[(i + 1) % 4] - box[i]) for i in range(4)]
    i = int(np.argmax(lens))
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
    ):
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
        if not layout.exists():
            self.reason = f"layout_missing:{layout}"
            self._result.reason = self.reason
            return

        try:
            from ultralytics import YOLO

            self.model = YOLO(str(weights_path))
            self.centers = load_screw_centers(layout)
            self.available = True
            self.reason = "ok"
            self._result = YoloRealtimeResult(enabled=True, available=True, reason="warming_up")
            self._thread = threading.Thread(target=self._worker, name="RealtimeYoloAnalyzer", daemon=True)
            self._thread.start()
        except Exception as exc:
            self.reason = f"{type(exc).__name__}:{exc}"
            self._result.reason = self.reason

    def submit(self, frame_id: int, frame_bgr, homography) -> None:
        if not self.enabled or not self.available:
            return
        if homography is None or frame_id % self.interval_frames != 0:
            return
        with self._pending_lock:
            self._pending = (int(frame_id), frame_bgr.copy(), np.array(homography, dtype=np.float64).copy())

    def get_result(self, current_frame_id: int) -> YoloRealtimeResult:
        with self._result_lock:
            result = self._result
        age = result.age_frames(current_frame_id)
        if self.enabled and self.available and age > self.max_age_frames:
            return YoloRealtimeResult(
                enabled=True,
                available=True,
                frame_id=result.frame_id,
                latency_ms=result.latency_ms,
                reason="stale",
                features=empty_yolo_features(age),
            )
        result.features["yolo_age_frames"] = float(age)
        return result

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
            frame_id, frame_bgr, homography = item
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
            with self._result_lock:
                self._result = result

    def _process(self, frame_id: int, frame_bgr, homography: np.ndarray) -> YoloRealtimeResult:
        assert self.model is not None
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
            driver_poly = transform_points(homography, make_bbox_points(best_driver))
            if polygon_intersects_workspace(driver_poly, self.workspace_width, self.workspace_height):
                best_handle = self._pick_handle(handles, best_driver)
                handle_poly = None
                if best_handle is not None:
                    handle_poly = transform_points(homography, make_bbox_points(best_handle))
                if handle_poly is not None and polygon_intersects_workspace(handle_poly, self.workspace_width, self.workspace_height):
                    tip = handle_guided_tip(driver_poly, handle_poly)
                    features["tool_tip_source"] = 2.0
                else:
                    e1, e2 = long_axis_endpoints(driver_poly)
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

        if tip is not None and screws:
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

    def _pick_handle(self, handles: List[Dict[str, Any]], driver: Dict[str, Any]):
        if not handles:
            return None
        driver_center = bbox_center(driver)
        return max(
            handles,
            key=lambda h: float(h["confidence"]) - 0.002 * float(np.linalg.norm(bbox_center(h) - driver_center)),
        )
