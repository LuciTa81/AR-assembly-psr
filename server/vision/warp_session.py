from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


# 확정된 마커 배치
# ID 0 = top-left
# ID 1 = top-right
# ID 2 = bottom-left
# ID 3 = bottom-right
REQUIRED_IDS = {
    "tl": 0,
    "tr": 1,
    "bl": 2,
    "br": 3,
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Warp Quest session frames to fixed 800x600 top-view using ArUco markers."
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--session", type=str, help="Session folder with frames.csv and frames/*.jpg")
    group.add_argument("--image-dir", type=str, help="Directory containing images")

    parser.add_argument("--out-dir", type=str, required=True, help="Output warped image directory")
    parser.add_argument("--debug-dir", type=str, required=True, help="Output marker debug image directory")
    parser.add_argument("--homography-csv", type=str, required=True, help="Output homography csv path")
    parser.add_argument("--session-id", type=str, default=None)
    parser.add_argument("--width", type=int, default=800)
    parser.add_argument("--height", type=int, default=600)

    return parser.parse_args()


def collect_images_from_dir(image_dir: Path) -> List[Dict[str, str]]:
    paths = sorted(p for p in image_dir.rglob("*") if p.suffix.lower() in IMAGE_EXTS)

    rows = []
    for i, p in enumerate(paths, start=1):
        rows.append(
            {
                "frame_id": str(i),
                "image_path": str(p),
                "display_path": p.name,
            }
        )

    return rows


def collect_images_from_session(session_dir: Path) -> List[Dict[str, str]]:
    frames_csv = session_dir / "frames.csv"

    if frames_csv.exists():
        rows = []
        with frames_csv.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader, start=1):
                frame_id = str(row.get("frame_id", i))
                image_rel = row.get("image_path", "")
                image_path = session_dir / image_rel

                rows.append(
                    {
                        "frame_id": frame_id,
                        "image_path": str(image_path),
                        "display_path": image_rel,
                    }
                )
        return rows

    frames_dir = session_dir / "frames"
    if frames_dir.exists():
        return collect_images_from_dir(frames_dir)

    return collect_images_from_dir(session_dir)


def frame_stem(frame_id: str, image_path: str) -> str:
    try:
        return f"{int(frame_id):06d}"
    except Exception:
        return Path(image_path).stem


def get_aruco_dictionary():
    # 네가 기존에 쓴 마커가 보통 DICT_4X4_50일 가능성이 높음
    return cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)


def detect_aruco(image_bgr):
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    dictionary = get_aruco_dictionary()

    if hasattr(cv2.aruco, "DetectorParameters"):
        params = cv2.aruco.DetectorParameters()
    else:
        params = cv2.aruco.DetectorParameters_create()

    if hasattr(cv2.aruco, "ArucoDetector"):
        detector = cv2.aruco.ArucoDetector(dictionary, params)
        corners, ids, rejected = detector.detectMarkers(gray)
    else:
        corners, ids, rejected = cv2.aruco.detectMarkers(gray, dictionary, parameters=params)

    return corners, ids


def centers_from_markers(corners, ids) -> Dict[int, np.ndarray]:
    centers: Dict[int, np.ndarray] = {}

    if ids is None or len(ids) == 0:
        return centers

    ids_flat = ids.flatten()

    for marker_id, corner in zip(ids_flat, corners):
        pts = corner.reshape(4, 2).astype(np.float32)
        center = pts.mean(axis=0)
        centers[int(marker_id)] = center

    return centers


def compute_homography(centers: Dict[int, np.ndarray], width: int, height: int):
    required = [REQUIRED_IDS["tl"], REQUIRED_IDS["tr"], REQUIRED_IDS["bl"], REQUIRED_IDS["br"]]
    if not all(marker_id in centers for marker_id in required):
        return None

    # 중요:
    # ID 0 = TL
    # ID 1 = TR
    # ID 2 = BL
    # ID 3 = BR
    # PerspectiveTransform 순서는 TL, TR, BR, BL
    src = np.array(
        [
            centers[REQUIRED_IDS["tl"]],
            centers[REQUIRED_IDS["tr"]],
            centers[REQUIRED_IDS["br"]],
            centers[REQUIRED_IDS["bl"]],
        ],
        dtype=np.float32,
    )

    dst = np.array(
        [
            [0, 0],
            [width - 1, 0],
            [width - 1, height - 1],
            [0, height - 1],
        ],
        dtype=np.float32,
    )

    H = cv2.getPerspectiveTransform(src, dst)
    return H


def draw_debug(image_bgr, corners, ids, centers: Dict[int, np.ndarray]):
    debug = image_bgr.copy()

    if ids is not None and len(ids) > 0:
        cv2.aruco.drawDetectedMarkers(debug, corners, ids)

    for marker_id, center in centers.items():
        x, y = int(center[0]), int(center[1])
        cv2.circle(debug, (x, y), 6, (0, 255, 255), -1)
        cv2.putText(
            debug,
            f"ID {marker_id}",
            (x + 8, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )

    return debug


def main():
    args = parse_args()

    if args.session:
        input_root = Path(args.session)
        items = collect_images_from_session(input_root)
        session_id = args.session_id or input_root.name
    else:
        input_root = Path(args.image_dir)
        items = collect_images_from_dir(input_root)
        session_id = args.session_id or input_root.name

    if not items:
        raise FileNotFoundError(f"No images found: {input_root}")

    out_dir = Path(args.out_dir)
    debug_dir = Path(args.debug_dir)
    homography_csv = Path(args.homography_csv)

    out_dir.mkdir(parents=True, exist_ok=True)
    debug_dir.mkdir(parents=True, exist_ok=True)
    homography_csv.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "session_id",
        "frame_id",
        "image_path",
        "warped_path",
        "debug_path",
        "homography_valid",
        "marker_count",
        "h00",
        "h01",
        "h02",
        "h10",
        "h11",
        "h12",
        "h20",
        "h21",
        "h22",
    ]

    valid_count = 0
    invalid_count = 0

    with homography_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        total = len(items)

        for idx, item in enumerate(items, start=1):
            frame_id = item["frame_id"]
            image_path = Path(item["image_path"])
            display_path = item["display_path"]

            image_bgr = cv2.imread(str(image_path))

            stem = frame_stem(frame_id, str(image_path))
            warped_name = f"{stem}_warped.jpg"
            debug_name = f"{stem}_markers.jpg"

            warped_path = out_dir / warped_name
            debug_path = debug_dir / debug_name

            row = {
                "session_id": session_id,
                "frame_id": frame_id,
                "image_path": display_path,
                "warped_path": str(warped_path),
                "debug_path": str(debug_path),
                "homography_valid": 0,
                "marker_count": 0,
                "h00": 0,
                "h01": 0,
                "h02": 0,
                "h10": 0,
                "h11": 0,
                "h12": 0,
                "h20": 0,
                "h21": 0,
                "h22": 0,
            }

            if image_bgr is None:
                print(f"[WARN] failed to read: {image_path}")
                invalid_count += 1
                writer.writerow(row)
                continue

            corners, ids = detect_aruco(image_bgr)
            centers = centers_from_markers(corners, ids)

            debug_img = draw_debug(image_bgr, corners, ids, centers)
            cv2.imwrite(str(debug_path), debug_img)

            row["marker_count"] = len(centers)

            H = compute_homography(centers, args.width, args.height)

            if H is None:
                invalid_count += 1
                writer.writerow(row)
            else:
                warped = cv2.warpPerspective(image_bgr, H, (args.width, args.height))
                cv2.imwrite(str(warped_path), warped)

                valid_count += 1

                h = H.flatten()
                row.update(
                    {
                        "homography_valid": 1,
                        "h00": h[0],
                        "h01": h[1],
                        "h02": h[2],
                        "h10": h[3],
                        "h11": h[4],
                        "h12": h[5],
                        "h20": h[6],
                        "h21": h[7],
                        "h22": h[8],
                    }
                )

                writer.writerow(row)

            if idx % 50 == 0 or idx == total:
                print(f"[PROGRESS] {idx}/{total}")

    print("")
    print(f"[DONE] total frames: {len(items)}")
    print(f"[DONE] valid homography: {valid_count}")
    print(f"[DONE] invalid homography: {invalid_count}")
    print(f"[DONE] warped dir: {out_dir}")
    print(f"[DONE] debug dir: {debug_dir}")
    print(f"[DONE] homography csv: {homography_csv}")


if __name__ == "__main__":
    main()