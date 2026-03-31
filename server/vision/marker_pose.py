from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

import cv2
import numpy as np


def detect_aruco_markers(
    image: np.ndarray,
    dictionary_name: str = "DICT_4X4_50",
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Detect ArUco markers from an input image.

    Returns:
        corners: detected corners
        ids: detected marker ids
    """
    aruco = cv2.aruco

    if not hasattr(aruco, dictionary_name):
        raise ValueError(f"Unknown ArUco dictionary: {dictionary_name}")

    dictionary = aruco.getPredefinedDictionary(getattr(aruco, dictionary_name))
    detector_params = aruco.DetectorParameters()
    detector = aruco.ArucoDetector(dictionary, detector_params)

    corners, ids, _ = detector.detectMarkers(image)
    return corners, ids


def marker_centers(
    corners: np.ndarray,
    ids: np.ndarray,
) -> Dict[int, Tuple[float, float]]:
    """
    Convert detected marker corners into marker center points.
    """
    result: Dict[int, Tuple[float, float]] = {}

    if ids is None or len(ids) == 0:
        return result

    for marker_corners, marker_id in zip(corners, ids.flatten()):
        pts = marker_corners[0]
        cx = float(np.mean(pts[:, 0]))
        cy = float(np.mean(pts[:, 1]))
        result[int(marker_id)] = (cx, cy)

    return result


def draw_detected_markers(
    image: np.ndarray,
    corners: np.ndarray,
    ids: np.ndarray,
) -> np.ndarray:
    """
    Draw detected markers for debugging.
    """
    vis = image.copy()
    if ids is not None and len(ids) > 0:
        cv2.aruco.drawDetectedMarkers(vis, corners, ids)
    return vis


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python server/vision/marker_pose.py <image_path>")
        sys.exit(1)

    image_path = Path(sys.argv[1])
    image = cv2.imread(str(image_path))

    if image is None:
        raise FileNotFoundError(f"Failed to read image: {image_path}")

    corners, ids = detect_aruco_markers(image)
    centers = marker_centers(corners, ids)

    print("Detected marker centers:")
    for k, v in centers.items():
        print(f"  ID {k}: {v}")

    vis = draw_detected_markers(image, corners, ids)
    cv2.imshow("aruco detection", vis)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
