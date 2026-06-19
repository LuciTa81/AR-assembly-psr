from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np
import yaml


Rect = Tuple[int, int, int, int]


@dataclass
class RoiRealtimeResult:
    enabled: bool
    scores: Dict[str, float] = field(default_factory=dict)
    deltas: Dict[str, float] = field(default_factory=dict)
    warped_frame: Optional[Any] = None
    reason: str = ""


def parse_rect(name: str, value: Any) -> Rect:
    if isinstance(value, dict):
        if all(k in value for k in ["x", "y", "w", "h"]):
            return int(value["x"]), int(value["y"]), int(value["w"]), int(value["h"])
        if all(k in value for k in ["x1", "y1", "x2", "y2"]):
            x1, y1, x2, y2 = int(value["x1"]), int(value["y1"]), int(value["x2"]), int(value["y2"])
            return x1, y1, x2 - x1, y2 - y1
    if isinstance(value, (list, tuple)) and len(value) == 4:
        return int(value[0]), int(value[1]), int(value[2]), int(value[3])
    raise ValueError(f"Invalid ROI format for {name}: {value}")


def clamp_rect(rect: Rect, image_width: int, image_height: int) -> Rect:
    x, y, w, h = rect
    x = max(0, min(x, image_width - 1))
    y = max(0, min(y, image_height - 1))
    w = max(1, min(w, image_width - x))
    h = max(1, min(h, image_height - y))
    return x, y, w, h


def load_image(path: Path):
    image = cv2.imread(str(path))
    if image is None:
        raise FileNotFoundError(f"failed to read image: {path}")
    return image


def preprocess(img_bgr, size: Tuple[int, int] = (64, 64)) -> np.ndarray:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, size, interpolation=cv2.INTER_AREA)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    gray_eq = cv2.equalizeHist(gray)
    edges = cv2.Canny(gray_eq, 50, 150)
    gray_f = gray_eq.astype(np.float32) / 255.0
    edge_f = edges.astype(np.float32) / 255.0
    return np.concatenate([gray_f.reshape(-1), 0.7 * edge_f.reshape(-1)])


def distance(crop_bgr, ref_bgr) -> float:
    return float(np.mean(np.abs(preprocess(crop_bgr) - preprocess(ref_bgr))))


def positive_score(crop_bgr, negative_ref, positive_ref) -> float:
    d_neg = distance(crop_bgr, negative_ref)
    d_pos = distance(crop_bgr, positive_ref)
    score = d_neg / (d_neg + d_pos + 1e-8)
    return max(0.0, min(1.0, float(score)))


class RoiRealtimeAnalyzer:
    def __init__(
        self,
        enabled: bool,
        layout_path: str,
        refs_dir: str,
        box_threshold: float = 0.50,
        lid_threshold: float = 0.52,
        score_alpha: float = 0.35,
    ):
        self.enabled = bool(enabled)
        self.layout_path = Path(layout_path) if layout_path else None
        self.refs_dir = Path(refs_dir) if refs_dir else None
        self.box_threshold = float(box_threshold)
        self.lid_threshold = float(lid_threshold)
        self.score_alpha = max(0.01, min(1.0, float(score_alpha)))
        self.prev_scores: Dict[str, float] = {}
        self.smooth_scores: Dict[str, float] = {}
        self.layout: Dict[str, Any] = {}
        self.refs: Dict[str, Any] = {}
        self.image_width = 800
        self.image_height = 600

        if not self.enabled:
            return
        if self.layout_path is None or not self.layout_path.exists():
            raise FileNotFoundError(f"ROI layout not found: {self.layout_path}")
        if self.refs_dir is None or not self.refs_dir.exists():
            raise FileNotFoundError(f"ROI refs dir not found: {self.refs_dir}")

        self.layout = yaml.safe_load(self.layout_path.read_text(encoding="utf-8")) or {}
        image_info = self.layout.get("image", {})
        self.image_width = int(image_info.get("width", 800))
        self.image_height = int(image_info.get("height", 600))
        self.refs = {
            "box_absent": load_image(self.refs_dir / "box_absent.jpg"),
            "box_present": load_image(self.refs_dir / "box_present.jpg"),
            "lid_open": load_image(self.refs_dir / "lid_open.jpg"),
            "lid_closed": load_image(self.refs_dir / "lid_closed.jpg"),
        }
        for screw in ["a", "b", "c", "d"]:
            self.refs[f"screw_{screw}_empty"] = load_image(self.refs_dir / f"screw_{screw}_empty.jpg")
            self.refs[f"screw_{screw}_done"] = load_image(self.refs_dir / f"screw_{screw}_done.jpg")

    def _crop(self, warped_frame, roi_name: str):
        raw = self.layout.get("rois", {}).get(roi_name)
        if raw is None:
            raise KeyError(f"ROI missing in layout: {roi_name}")
        x, y, w, h = clamp_rect(parse_rect(roi_name, raw), self.image_width, self.image_height)
        return warped_frame[y : y + h, x : x + w]

    def process(self, frame_bgr, homography) -> RoiRealtimeResult:
        if not self.enabled:
            return RoiRealtimeResult(enabled=False, reason="disabled")
        if homography is None:
            return RoiRealtimeResult(enabled=True, reason="missing_homography")

        warped = cv2.warpPerspective(frame_bgr, homography, (self.image_width, self.image_height))
        raw_scores: Dict[str, float] = {}
        scores: Dict[str, float] = {}
        deltas: Dict[str, float] = {}

        enclosure = self._crop(warped, "enclosure")
        lid = self._crop(warped, "lid")
        raw_scores["box_present_score"] = positive_score(enclosure, self.refs["box_absent"], self.refs["box_present"])
        raw_scores["lid_closed_score"] = positive_score(lid, self.refs["lid_open"], self.refs["lid_closed"])
        for screw in ["a", "b", "c", "d"]:
            crop = self._crop(warped, f"screw_{screw}")
            raw_scores[f"screw_{screw}_done_score"] = positive_score(
                crop,
                self.refs[f"screw_{screw}_empty"],
                self.refs[f"screw_{screw}_done"],
            )

        for key, value in raw_scores.items():
            prev = self.prev_scores.get(key, value)
            prev_smooth = self.smooth_scores.get(key, value)
            smooth = self.score_alpha * value + (1.0 - self.score_alpha) * prev_smooth
            scores[key] = value
            scores[f"{key}_smooth"] = smooth
            deltas[f"{key}_delta"] = float(value - prev)
            deltas[f"{key}_delta_smooth"] = float(smooth - prev_smooth)
            self.prev_scores[key] = value
            self.smooth_scores[key] = smooth

        return RoiRealtimeResult(enabled=True, scores=scores, deltas=deltas, warped_frame=warped, reason="ok")
