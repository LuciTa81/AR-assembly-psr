from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Tuple

import cv2
import numpy as np

from warp import (
    build_source_points_from_centers,
    build_destination_points,
    compute_perspective_transform,
    warp_to_top_view,
)


def detect_aruco_centers(
    image: np.ndarray,
) -> tuple[Dict[int, Tuple[float, float]], np.ndarray]:
    """
    Detect ArUco markers and return marker center points.

    Returns:
        centers:
            {
                marker_id: (center_x, center_y)
            }

        debug_image:
            image with detected markers drawn
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    params = cv2.aruco.DetectorParameters()

    # OpenCV newer API
    if hasattr(cv2.aruco, "ArucoDetector"):
        detector = cv2.aruco.ArucoDetector(aruco_dict, params)
        corners, ids, rejected = detector.detectMarkers(gray)
    else:
        # OpenCV older API fallback
        corners, ids, rejected = cv2.aruco.detectMarkers(
            gray,
            aruco_dict,
            parameters=params,
        )

    debug_image = image.copy()

    if ids is None or len(ids) == 0:
        return {}, debug_image

    cv2.aruco.drawDetectedMarkers(debug_image, corners, ids)

    centers: Dict[int, Tuple[float, float]] = {}

    for marker_corners, marker_id in zip(corners, ids.flatten()):
        pts = marker_corners.reshape(4, 2)

        center_x = float(np.mean(pts[:, 0]))
        center_y = float(np.mean(pts[:, 1]))

        centers[int(marker_id)] = (center_x, center_y)

        cv2.circle(
            debug_image,
            (int(center_x), int(center_y)),
            5,
            (0, 0, 255),
            -1,
        )

        cv2.putText(
            debug_image,
            f"ID {int(marker_id)}",
            (int(center_x) + 8, int(center_y) - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 255),
            2,
            cv2.LINE_AA,
        )

    return centers, debug_image


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--image",
        required=True,
        help="Input frame image path",
    )

    parser.add_argument(
        "--out",
        default="outputs/warped/warped.jpg",
        help="Output warped image path",
    )

    parser.add_argument(
        "--debug",
        default="outputs/debug_markers/debug_markers.jpg",
        help="Output debug marker image path",
    )

    parser.add_argument(
        "--width",
        type=int,
        default=800,
        help="Warped image width",
    )

    parser.add_argument(
        "--height",
        type=int,
        default=600,
        help="Warped image height",
    )

    args = parser.parse_args()

    image_path = Path(args.image)
    out_path = Path(args.out)
    debug_path = Path(args.debug)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    debug_path.parent.mkdir(parents=True, exist_ok=True)

    image = cv2.imread(str(image_path))

    if image is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")

    centers, debug_image = detect_aruco_centers(image)

    print(f"Detected marker centers: {centers}")

    cv2.imwrite(str(debug_path), debug_image)
    print(f"Saved debug marker image: {debug_path}")

    required_ids = {0, 1, 2, 3}
    detected_ids = set(centers.keys())
    missing_ids = required_ids - detected_ids

    if missing_ids:
        raise RuntimeError(
            f"Missing required marker IDs: {sorted(missing_ids)}. "
            f"Detected IDs: {sorted(detected_ids)}"
        )

    src_points = build_source_points_from_centers(centers)
    dst_points = build_destination_points(width=args.width, height=args.height)

    print("Source points:")
    print(src_points)

    print("Destination points:")
    print(dst_points)

    H = compute_perspective_transform(src_points, dst_points)

    print("Perspective transform matrix H:")
    print(H)

    warped = warp_to_top_view(
        image=image,
        H=H,
        width=args.width,
        height=args.height,
    )

    cv2.imwrite(str(out_path), warped)
    print(f"Saved warped image: {out_path}")


if __name__ == "__main__":
    main()