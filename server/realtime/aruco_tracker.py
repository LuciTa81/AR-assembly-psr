from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import cv2
import numpy as np
import yaml


@dataclass
class ArUcoResult:
    enabled: bool
    marker_ok: bool
    marker_count: int
    marker_status: str
    warp_quality: float
    homography: Optional[np.ndarray] = None
    homography_source: str = "none"
    fallback_age: int = 0
    warning_code: str = ""
    warning_message: str = ""


class ArUcoRealtimeTracker:
    def __init__(
        self,
        enabled: bool,
        layout_path: str,
        min_markers: int = 4,
        min_quality: float = 0.25,
        detect_scale: float = 1.0,
        use_previous_h: bool = True,
        max_fallback_frames: int = 5,
    ):
        self.enabled = enabled
        self.layout_path = Path(layout_path) if layout_path else None
        self.min_markers = int(min_markers)
        self.min_quality = float(min_quality)
        self.detect_scale = float(detect_scale)
        self.use_previous_h = bool(use_previous_h)
        self.max_fallback_frames = int(max_fallback_frames)
        self.last_homography: Optional[np.ndarray] = None
        self.fallback_age = 0
        self.layout: Dict[str, Any] = {}
        self.marker_corners: Dict[int, np.ndarray] = {}
        self.dictionary_name = "DICT_4X4_50"
        if self.enabled:
            if self.layout_path is None or not self.layout_path.exists():
                raise FileNotFoundError(f"marker layout not found: {self.layout_path}")
            self.layout = yaml.safe_load(self.layout_path.read_text(encoding="utf-8")) or {}
            self.dictionary_name = self.layout.get("dictionary", "DICT_4X4_50")
            for mid_raw, info in self.layout.get("markers", {}).items():
                self.marker_corners[int(mid_raw)] = np.array(info["corners"], dtype=np.float32)

    def _dictionary(self):
        return cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, self.dictionary_name))

    def _detect(self, frame_bgr):
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        if self.detect_scale != 1.0:
            gray_d = cv2.resize(gray, None, fx=self.detect_scale, fy=self.detect_scale, interpolation=cv2.INTER_CUBIC)
        else:
            gray_d = gray
        params = cv2.aruco.DetectorParameters() if hasattr(cv2.aruco, "DetectorParameters") else cv2.aruco.DetectorParameters_create()
        dictionary = self._dictionary()
        if hasattr(cv2.aruco, "ArucoDetector"):
            detector = cv2.aruco.ArucoDetector(dictionary, params)
            corners, ids, _ = detector.detectMarkers(gray_d)
        else:
            corners, ids, _ = cv2.aruco.detectMarkers(gray_d, dictionary, parameters=params)
        corners = corners or []
        if self.detect_scale != 1.0 and corners:
            corners = [c / self.detect_scale for c in corners]
        return corners, ids

    def _correspondences(self, corners, ids):
        src, dst, known = [], [], []
        if ids is None:
            return np.empty((0, 2), np.float32), np.empty((0, 2), np.float32), []
        for corner, mid_raw in zip(corners, ids.flatten()):
            mid = int(mid_raw)
            if mid not in self.marker_corners:
                continue
            src.append(corner.reshape(4, 2).astype(np.float32))
            dst.append(self.marker_corners[mid])
            known.append(mid)
        if not src:
            return np.empty((0, 2), np.float32), np.empty((0, 2), np.float32), []
        return np.concatenate(src, axis=0), np.concatenate(dst, axis=0), known

    def process(self, frame_bgr) -> ArUcoResult:
        if not self.enabled:
            return ArUcoResult(
                enabled=False,
                marker_ok=True,
                marker_count=0,
                marker_status="DISABLED",
                warp_quality=1.0,
                homography_source="disabled",
            )
        corners, ids = self._detect(frame_bgr)
        src, dst, known = self._correspondences(corners, ids)
        marker_count = len(set(known))
        if marker_count < self.min_markers or len(src) < 4:
            fallback = self._fallback(marker_count, "MARKER_LOST", "Move the workspace markers into view")
            if fallback is not None:
                return fallback
            return ArUcoResult(
                enabled=True,
                marker_ok=False,
                marker_count=marker_count,
                marker_status="LOST",
                warp_quality=0.0,
                homography_source="none",
                warning_code="MARKER_LOST",
                warning_message="Move the workspace markers into view",
            )
        homography, mask = cv2.findHomography(src, dst, cv2.RANSAC, 8.0)
        if homography is None or mask is None:
            fallback = self._fallback(marker_count, "HOMOGRAPHY_FAILED", "Workspace alignment failed")
            if fallback is not None:
                return fallback
            return ArUcoResult(
                enabled=True,
                marker_ok=False,
                marker_count=marker_count,
                marker_status="UNSTABLE",
                warp_quality=0.0,
                homography_source="none",
                warning_code="HOMOGRAPHY_FAILED",
                warning_message="Workspace alignment failed",
            )
        inlier_ratio = float(mask.sum()) / max(1, len(mask))
        warp_quality = max(0.0, min(1.0, inlier_ratio))
        marker_ok = warp_quality >= self.min_quality
        if not marker_ok:
            fallback = self._fallback(marker_count, "MARKER_UNSTABLE", "Hold position until markers are stable")
            if fallback is not None:
                return fallback
        self.last_homography = homography.copy()
        self.fallback_age = 0
        return ArUcoResult(
            enabled=True,
            marker_ok=marker_ok,
            marker_count=marker_count,
            marker_status="OK" if marker_ok else "UNSTABLE",
            warp_quality=warp_quality,
            homography=homography,
            homography_source="detected",
            fallback_age=0,
            warning_code="" if marker_ok else "MARKER_UNSTABLE",
            warning_message="" if marker_ok else "Hold position until markers are stable",
        )

    def _fallback(self, marker_count: int, code: str, message: str) -> Optional[ArUcoResult]:
        if not self.use_previous_h or self.last_homography is None:
            return None
        if self.fallback_age >= self.max_fallback_frames:
            return None
        self.fallback_age += 1
        return ArUcoResult(
            enabled=True,
            # Fallback homography can keep the overlay/ROI stable briefly, but
            # state transitions should remain locked until fresh markers return.
            marker_ok=False,
            marker_count=marker_count,
            marker_status="FALLBACK",
            warp_quality=0.0,
            homography=self.last_homography.copy(),
            homography_source="previous_h_fallback",
            fallback_age=self.fallback_age,
            warning_code=code,
            warning_message=message,
        )
