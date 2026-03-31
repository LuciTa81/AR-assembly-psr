from __future__ import annotations

from typing import Dict, Tuple

import cv2
import numpy as np


def build_source_points_from_centers(
    centers: Dict[int, Tuple[float, float]],
    required_ids=(0, 1, 2, 3),
) -> np.ndarray:
    """
    Build source points in the order:
    top-left, top-right, bottom-right, bottom-left
    """
    for marker_id in required_ids:
        if marker_id not in centers:
            raise ValueError(f"Required marker ID missing: {marker_id}")

    pts = np.array(
        [
            centers[0],
            centers[1],
            centers[2],
            centers[3],
        ],
        dtype=np.float32,
    )
    return pts


def build_destination_points(
    width: int = 800,
    height: int = 800,
) -> np.ndarray:
    """
    Destination rectangle points.
    """
    return np.array(
        [
            [0, 0],
            [width - 1, 0],
            [width - 1, height - 1],
            [0, height - 1],
        ],
        dtype=np.float32,
    )


def compute_homography(
    src_points: np.ndarray,
    dst_points: np.ndarray,
) -> np.ndarray:
    """
    Compute perspective transform matrix.
    """
    return cv2.getPerspectiveTransform(src_points, dst_points)


def warp_to_top_view(
    image: np.ndarray,
    H: np.ndarray,
    width: int = 800,
    height: int = 800,
) -> np.ndarray:
    """
    Warp image into a top-view reference plane.
    """
    return cv2.warpPerspective(image, H, (width, height))
