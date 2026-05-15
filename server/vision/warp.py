from __future__ import annotations

from typing import Dict, Tuple

import cv2
import numpy as np


# marker ID 배치도 이 순서로 고정한다고 가정:
# 0 = top-left
# 1 = top-right
# 2 = bottom-left
# 3 = bottom-right
MARKER_LAYOUT = {
    "top_left": 0,
    "top_right": 1,
    "bottom_left": 2,
    "bottom_right": 3,
}


def build_source_points_from_centers(
    centers: Dict[int, Tuple[float, float]],
    marker_layout: Dict[str, int] = MARKER_LAYOUT,
) -> np.ndarray:
    """
    Build source points in the order:
    top-left, top-right, bottom-left, bottom-right
    """
    ordered_keys = ["top_left", "top_right", "bottom_left", "bottom_right"]

    for key in ordered_keys:
        marker_id = marker_layout[key]
        if marker_id not in centers:
            raise ValueError(f"Required marker ID missing: {marker_id} ({key})")

    pts = np.array(
        [
            centers[marker_layout["top_left"]],
            centers[marker_layout["top_right"]],
            centers[marker_layout["bottom_left"]],
            centers[marker_layout["bottom_right"]],
        ],
        dtype=np.float32,
    )

    return pts


def build_destination_points(
    width: int = 800,
    height: int = 600,
) -> np.ndarray:
    """
    Destination rectangle points in the order:
    top-left, top-right, bottom-left, bottom-right
    """
    return np.array(
        [
            [0, 0],                  # top-left
            [width - 1, 0],          # top-right
            [0, height - 1],         # bottom-left
            [width - 1, height - 1], # bottom-right
        ],
        dtype=np.float32,
    )


def compute_perspective_transform(
    src_points: np.ndarray,
    dst_points: np.ndarray,
) -> np.ndarray:
    """
    Compute perspective transform matrix.

    IMPORTANT:
    src_points and dst_points must have the same point order:
    top-left, top-right, bottom-left, bottom-right
    """
    if src_points.shape != (4, 2):
        raise ValueError(f"src_points must be shape (4, 2), got {src_points.shape}")

    if dst_points.shape != (4, 2):
        raise ValueError(f"dst_points must be shape (4, 2), got {dst_points.shape}")

    return cv2.getPerspectiveTransform(src_points, dst_points)


def warp_to_top_view(
    image: np.ndarray,
    H: np.ndarray,
    width: int = 800,
    height: int = 600,
) -> np.ndarray:
    """
    Warp image into a top-view reference plane.
    """
    return cv2.warpPerspective(image, H, (width, height))