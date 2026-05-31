from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List

import cv2
import numpy as np
import yaml

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
REQUIRED_IDS = [0, 1, 2, 3, 4, 5]
MARKER_META = {
    0: {"name": "top_left", "row": "top", "col": "left"},
    1: {"name": "top_center", "row": "top", "col": "center"},
    2: {"name": "top_right", "row": "top", "col": "right"},
    3: {"name": "bottom_left", "row": "bottom", "col": "left"},
    4: {"name": "bottom_center", "row": "bottom", "col": "center"},
    5: {"name": "bottom_right", "row": "bottom", "col": "right"},
}


def parse_args():
    p = argparse.ArgumentParser(description="Create a calibrated 6-marker layout from one reference frame.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--session", type=str)
    g.add_argument("--image", type=str)
    p.add_argument("--frame-id", type=str, default=None)
    p.add_argument("--out", type=str, required=True)
    p.add_argument("--preview-dir", type=str, default="outputs/calibration")
    p.add_argument("--width", type=int, default=800)
    p.add_argument("--height", type=int, default=600)
    p.add_argument("--margin-x", type=float, default=45.0)
    p.add_argument("--margin-y", type=float, default=45.0)
    p.add_argument("--detect-scale", type=float, default=1.5)
    return p.parse_args()


def collect_images_from_session(session_dir: Path) -> List[Dict[str, str]]:
    frames_csv = session_dir / "frames.csv"
    if frames_csv.exists():
        rows = []
        with frames_csv.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader, start=1):
                frame_id = str(row.get("frame_id", i))
                image_rel = row.get("image_path", "")
                image_path = session_dir / image_rel if image_rel else session_dir / "frames" / f"{int(frame_id):06d}.jpg"
                rows.append({"frame_id": frame_id, "image_path": str(image_path), "display_path": image_rel or image_path.name})
        return rows
    frames_dir = session_dir / "frames"
    root = frames_dir if frames_dir.exists() else session_dir
    return [{"frame_id": str(i), "image_path": str(p), "display_path": p.name}
            for i, p in enumerate(sorted(q for q in root.rglob("*") if q.suffix.lower() in IMAGE_EXTS), start=1)]


def detect_markers(image_bgr, detect_scale: float):
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    if detect_scale != 1.0:
        gray_detect = cv2.resize(gray, None, fx=detect_scale, fy=detect_scale, interpolation=cv2.INTER_CUBIC)
    else:
        gray_detect = gray
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    params = cv2.aruco.DetectorParameters() if hasattr(cv2.aruco, "DetectorParameters") else cv2.aruco.DetectorParameters_create()
    params.adaptiveThreshWinSizeMin = 3
    params.adaptiveThreshWinSizeMax = 53
    params.adaptiveThreshWinSizeStep = 4
    params.minMarkerPerimeterRate = 0.015
    params.maxMarkerPerimeterRate = 4.0
    params.polygonalApproxAccuracyRate = 0.03
    if hasattr(cv2.aruco, "CORNER_REFINE_SUBPIX"):
        params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    if hasattr(cv2.aruco, "ArucoDetector"):
        detector = cv2.aruco.ArucoDetector(aruco_dict, params)
        corners, ids, _ = detector.detectMarkers(gray_detect)
    else:
        corners, ids, _ = cv2.aruco.detectMarkers(gray_detect, aruco_dict, parameters=params)
    corners = corners or []
    if detect_scale != 1.0 and corners:
        corners = [c / detect_scale for c in corners]
    marker_corners = {}
    if ids is not None:
        for marker_id, corner in zip(ids.flatten(), corners):
            marker_corners[int(marker_id)] = corner.reshape(4, 2).astype(np.float32)
    return marker_corners, corners, ids


def select_outer_corner(corners: np.ndarray, position: str) -> np.ndarray:
    x, y = corners[:, 0], corners[:, 1]
    if position == "tl": idx = int(np.argmin(x + y))
    elif position == "tr": idx = int(np.argmax(x - y))
    elif position == "br": idx = int(np.argmax(x + y))
    elif position == "bl": idx = int(np.argmax(y - x))
    else: raise ValueError(position)
    return corners[idx]


def transform_points(H: np.ndarray, pts: np.ndarray) -> np.ndarray:
    return cv2.perspectiveTransform(pts.reshape(-1, 1, 2).astype(np.float32), H).reshape(-1, 2)


def round_point(p):
    return [float(round(float(p[0]), 2)), float(round(float(p[1]), 2))]


def find_reference_item(args):
    if args.image:
        p = Path(args.image)
        return {"frame_id": p.stem, "image_path": str(p), "display_path": p.name}
    items = collect_images_from_session(Path(args.session))
    if args.frame_id is not None:
        target = str(int(args.frame_id)) if str(args.frame_id).isdigit() else str(args.frame_id)
        for item in items:
            fid = str(int(item["frame_id"])) if str(item["frame_id"]).isdigit() else str(item["frame_id"])
            if fid == target:
                return item
        raise FileNotFoundError(f"frame_id not found: {args.frame_id}")
    for item in items:
        img = cv2.imread(item["image_path"])
        if img is None:
            continue
        marker_corners, _, _ = detect_markers(img, args.detect_scale)
        if all(i in marker_corners for i in REQUIRED_IDS):
            return item
    raise RuntimeError("No frame found with all 6 markers visible.")


def main():
    args = parse_args()
    out_path = Path(args.out)
    preview_dir = Path(args.preview_dir)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)
    item = find_reference_item(args)
    img = cv2.imread(item["image_path"])
    if img is None:
        raise FileNotFoundError(item["image_path"])
    marker_corners, raw_corners, raw_ids = detect_markers(img, args.detect_scale)
    missing = [i for i in REQUIRED_IDS if i not in marker_corners]
    print(f"[INFO] reference frame_id: {item['frame_id']}")
    print(f"[INFO] reference image: {item['image_path']}")
    print(f"[INFO] detected ids: {sorted(marker_corners.keys())}")
    if missing:
        raise RuntimeError(f"Reference frame must contain all 6 markers. Missing: {missing}")
    src_outer = np.array([
        select_outer_corner(marker_corners[0], "tl"),
        select_outer_corner(marker_corners[2], "tr"),
        select_outer_corner(marker_corners[5], "br"),
        select_outer_corner(marker_corners[3], "bl"),
    ], dtype=np.float32)
    dst_outer = np.array([
        [args.margin_x, args.margin_y],
        [args.width - args.margin_x, args.margin_y],
        [args.width - args.margin_x, args.height - args.margin_y],
        [args.margin_x, args.height - args.margin_y],
    ], dtype=np.float32)
    H = cv2.getPerspectiveTransform(src_outer, dst_outer)
    warped = cv2.warpPerspective(img, H, (args.width, args.height))
    calibrated = {}
    for mid in REQUIRED_IDS:
        warped_corners = transform_points(H, marker_corners[mid])
        calibrated[mid] = {**MARKER_META[mid], "corners": [round_point(p) for p in warped_corners]}
    layout = {
        "layout_version": "marker_layout_v2_calibrated",
        "dictionary": "DICT_4X4_50",
        "image": {"width": args.width, "height": args.height},
        "calibration": {"frame_id": str(item["frame_id"]), "image_path": str(item["image_path"]),
                        "outer_anchor_rule": "ID0_outer_TL, ID2_outer_TR, ID5_outer_BR, ID3_outer_BL",
                        "dst_outer": [round_point(p) for p in dst_outer]},
        "markers": calibrated,
        "quality_rules": {"min_markers": 3, "min_points": 12, "require_both_rows": True,
                          "min_column_span": 2, "ransac_reproj_threshold": 8.0,
                          "min_inlier_ratio": 0.55, "max_reprojection_error": 12.0},
        "fallback": {"use_previous_h": True, "max_fallback_gap": 2},
    }
    with out_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(layout, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    debug = img.copy()
    if raw_ids is not None:
        cv2.aruco.drawDetectedMarkers(debug, raw_corners, raw_ids)
    for p, label in zip(src_outer, ["ID0 outer TL", "ID2 outer TR", "ID5 outer BR", "ID3 outer BL"]):
        x, y = int(round(p[0])), int(round(p[1]))
        cv2.circle(debug, (x, y), 10, (0, 255, 255), -1)
        cv2.putText(debug, label, (x + 10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    cv2.imwrite(str(preview_dir / "calibration_reference_debug.jpg"), debug)
    preview = warped.copy()
    for mid, info in calibrated.items():
        pts = np.array(info["corners"], dtype=np.float32)
        cv2.polylines(preview, [np.round(pts).astype(np.int32)], True, (0, 255, 255), 2)
        cx, cy = np.mean(pts, axis=0).astype(int)
        cv2.putText(preview, f"ID {mid}", (cx - 25, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    cv2.imwrite(str(preview_dir / "calibration_warped_preview.jpg"), preview)
    print(f"[DONE] calibrated layout saved: {out_path}")
    print(f"[DONE] preview dir: {preview_dir}")


if __name__ == "__main__":
    main()
