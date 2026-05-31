from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import yaml

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def parse_args():
    p = argparse.ArgumentParser(description="Warp session frames using 6 ArUco marker corners + RANSAC homography.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--session", type=str)
    g.add_argument("--image-dir", type=str)
    p.add_argument("--layout", type=str, required=True)
    p.add_argument("--out-dir", type=str, required=True)
    p.add_argument("--debug-dir", type=str, required=True)
    p.add_argument("--homography-csv", type=str, required=True)
    p.add_argument("--session-id", type=str, default=None)
    p.add_argument("--width", type=int, default=800)
    p.add_argument("--height", type=int, default=600)
    p.add_argument("--detect-scale", type=float, default=1.5)
    return p.parse_args()


def collect_images_from_dir(root: Path) -> List[Dict[str, str]]:
    paths = sorted(p for p in root.rglob("*") if p.suffix.lower() in IMAGE_EXTS)
    return [{"frame_id": str(i), "image_path": str(p), "display_path": p.name} for i, p in enumerate(paths, 1)]


def collect_images_from_session(session_dir: Path) -> List[Dict[str, str]]:
    frames_csv = session_dir / "frames.csv"
    if frames_csv.exists():
        rows = []
        with frames_csv.open("r", encoding="utf-8-sig", newline="") as f:
            for i, row in enumerate(csv.DictReader(f), 1):
                fid = str(row.get("frame_id", i))
                rel = row.get("image_path", "")
                path = session_dir / rel if rel else session_dir / "frames" / f"{int(fid):06d}.jpg"
                rows.append({"frame_id": fid, "image_path": str(path), "display_path": rel or path.name})
        return rows
    frames_dir = session_dir / "frames"
    return collect_images_from_dir(frames_dir if frames_dir.exists() else session_dir)


def frame_stem(fid: str, image_path: str) -> str:
    try: return f"{int(fid):06d}"
    except Exception: return Path(image_path).stem


def load_layout(path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not data or "markers" not in data:
        raise ValueError(f"Invalid marker layout: {path}")
    return data


def aruco_dictionary(name: str):
    return cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, name))


def detect_aruco(image_bgr, dictionary_name: str, scale: float):
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    if scale != 1.0:
        gray_d = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    else:
        gray_d = gray
    params = cv2.aruco.DetectorParameters() if hasattr(cv2.aruco, "DetectorParameters") else cv2.aruco.DetectorParameters_create()
    params.adaptiveThreshWinSizeMin = 3
    params.adaptiveThreshWinSizeMax = 53
    params.adaptiveThreshWinSizeStep = 4
    params.minMarkerPerimeterRate = 0.015
    params.maxMarkerPerimeterRate = 4.0
    params.polygonalApproxAccuracyRate = 0.03
    if hasattr(cv2.aruco, "CORNER_REFINE_SUBPIX"):
        params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    d = aruco_dictionary(dictionary_name)
    if hasattr(cv2.aruco, "ArucoDetector"):
        detector = cv2.aruco.ArucoDetector(d, params)
        corners, ids, _ = detector.detectMarkers(gray_d)
    else:
        corners, ids, _ = cv2.aruco.detectMarkers(gray_d, d, parameters=params)
    corners = corners or []
    if scale != 1.0 and corners:
        corners = [c / scale for c in corners]
    return corners, ids


def normalize_markers(layout):
    out = {}
    for mid_raw, info in layout["markers"].items():
        mid = int(mid_raw)
        out[mid] = {"name": info.get("name", f"marker_{mid}"),
                    "row": info.get("row", "unknown"), "col": info.get("col", "unknown"),
                    "corners": np.array(info["corners"], dtype=np.float32)}
    return out


def build_correspondences(corners, ids, markers):
    src, dst, known = [], [], []
    if ids is None:
        return np.empty((0, 2), np.float32), np.empty((0, 2), np.float32), []
    for corner, mid_raw in zip(corners, ids.flatten()):
        mid = int(mid_raw)
        if mid not in markers: continue
        src.append(corner.reshape(4, 2).astype(np.float32))
        dst.append(markers[mid]["corners"].astype(np.float32))
        known.append(mid)
    if not src:
        return np.empty((0, 2), np.float32), np.empty((0, 2), np.float32), []
    return np.concatenate(src, axis=0), np.concatenate(dst, axis=0), sorted(known)


def coverage(ids, markers):
    rows, cols = set(), set()
    for mid in ids:
        rows.add(markers[mid].get("row", "unknown"))
        cols.add(markers[mid].get("col", "unknown"))
    return {"rows": rows, "cols": cols,
            "top_count": sum(1 for mid in ids if markers[mid].get("row") == "top"),
            "bottom_count": sum(1 for mid in ids if markers[mid].get("row") == "bottom"),
            "column_span": len(cols)}


def basic_ok(ids, src, layout, markers):
    r = layout.get("quality_rules", {})
    cov = coverage(ids, markers)
    if len(ids) < int(r.get("min_markers", 3)): return False, f"marker_count<{int(r.get('min_markers', 3))}", cov
    if len(src) < int(r.get("min_points", 12)): return False, f"point_count<{int(r.get('min_points', 12))}", cov
    if bool(r.get("require_both_rows", True)) and not ("top" in cov["rows"] and "bottom" in cov["rows"]):
        return False, "missing_top_or_bottom_row", cov
    if cov["column_span"] < int(r.get("min_column_span", 2)):
        return False, f"column_span<{int(r.get('min_column_span', 2))}", cov
    return True, "ok", cov


def reproj_error(H, src, dst, mask):
    if H is None or len(src) == 0: return float("inf")
    src_h = cv2.convertPointsToHomogeneous(src).reshape(-1, 3)
    proj = (H @ src_h.T).T
    pts = proj[:, :2] / proj[:, 2:3]
    errors = np.linalg.norm(pts - dst, axis=1)
    if mask is not None:
        m = mask.reshape(-1).astype(bool)
        if m.sum() > 0: errors = errors[m]
    return float(np.mean(errors)) if len(errors) else float("inf")


def estimate_H(src, dst, layout):
    r = layout.get("quality_rules", {})
    th = float(r.get("ransac_reproj_threshold", 8.0))
    min_in = float(r.get("min_inlier_ratio", 0.55))
    max_err = float(r.get("max_reprojection_error", 12.0))
    H, mask = cv2.findHomography(src, dst, cv2.RANSAC, th)
    if H is None or mask is None:
        return None, 0, len(src), 0.0, float("inf"), 0.0, "findHomography_failed"
    total = int(len(src)); inliers = int(mask.sum()); ratio = inliers / max(1, total)
    err = reproj_error(H, src, dst, mask)
    q = float(max(0.0, min(1.0, ratio * np.exp(-err / max(1e-6, max_err)))))
    if ratio < min_in: return H, inliers, total, ratio, err, q, "low_inlier_ratio"
    if err > max_err: return H, inliers, total, ratio, err, q, "high_reprojection_error"
    return H, inliers, total, ratio, err, q, "ok"


def draw_debug(img, corners, ids, known_ids, status, cov):
    dbg = img.copy()
    if ids is not None and len(ids) > 0:
        cv2.aruco.drawDetectedMarkers(dbg, corners, ids)
    y = 30
    for line in [status, f"known IDs: {known_ids}", f"top={cov.get('top_count',0)} bottom={cov.get('bottom_count',0)} cols={cov.get('column_span',0)}"]:
        cv2.putText(dbg, line, (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
        y += 30
    return dbg


def main():
    args = parse_args()
    layout = load_layout(Path(args.layout))
    markers = normalize_markers(layout)
    dictionary_name = layout.get("dictionary", "DICT_4X4_50")
    if args.session:
        root = Path(args.session); items = collect_images_from_session(root); session_id = args.session_id or root.name
    else:
        root = Path(args.image_dir); items = collect_images_from_dir(root); session_id = args.session_id or root.name
    out_dir, dbg_dir, csv_path = Path(args.out_dir), Path(args.debug_dir), Path(args.homography_csv)
    out_dir.mkdir(parents=True, exist_ok=True); dbg_dir.mkdir(parents=True, exist_ok=True); csv_path.parent.mkdir(parents=True, exist_ok=True)
    fb = layout.get("fallback", {}); use_prev = bool(fb.get("use_previous_h", True)); max_gap = int(fb.get("max_fallback_gap", 2))
    fields = ["session_id","frame_id","image_path","warped_path","debug_path","homography_valid","homography_usable","homography_source","failure_reason","marker_count","detected_ids","top_count","bottom_count","column_span","inlier_count","total_points","inlier_ratio","reprojection_error","warp_quality","h00","h01","h02","h10","h11","h12","h20","h21","h22"]
    last_H, last_idx = None, -10**9
    counts = {"detected":0,"fallback":0,"invalid":0}
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for idx, item in enumerate(items, 1):
            fid, img_path = item["frame_id"], Path(item["image_path"])
            stem = frame_stem(fid, str(img_path)); wp = out_dir / f"{stem}_warped.jpg"; dp = dbg_dir / f"{stem}_markers_v2.jpg"
            row = {k: 0 for k in fields}
            row.update({"session_id": session_id, "frame_id": fid, "image_path": item["display_path"], "warped_path": str(wp), "debug_path": str(dp),
                        "homography_valid":0,"homography_usable":0,"homography_source":"invalid","failure_reason":""})
            img = cv2.imread(str(img_path))
            if img is None:
                row["failure_reason"] = "failed_to_read_image"; w.writerow(row); counts["invalid"] += 1; continue
            corners, ids = detect_aruco(img, dictionary_name, args.detect_scale)
            src, dst, known_ids = build_correspondences(corners, ids, markers)
            cov = coverage(known_ids, markers)
            row.update({"marker_count":len(known_ids), "detected_ids":";".join(map(str, known_ids)), "top_count":cov["top_count"], "bottom_count":cov["bottom_count"], "column_span":cov["column_span"], "total_points":len(src)})
            ok, reason, cov = basic_ok(known_ids, src, layout, markers)
            H = None; source = "invalid"; q = 0.0; inl = 0; total = len(src); ratio = 0.0; err = float("inf")
            if ok:
                Hc, inl, total, ratio, err, q, hreason = estimate_H(src, dst, layout)
                if Hc is not None and hreason == "ok": H, source, reason = Hc, "detected_ransac", "ok"
                else: reason = hreason
            if H is None and use_prev and last_H is not None:
                gap = idx - last_idx
                if gap <= max_gap:
                    H = last_H.copy(); source = "previous_h_fallback"; reason = f"fallback_gap_{gap}"; q = 0.35
            if H is not None:
                cv2.imwrite(str(wp), cv2.warpPerspective(img, H, (args.width, args.height)))
                vals = H.flatten()
                row.update({"homography_usable":1,"homography_source":source,"failure_reason":reason,"inlier_count":inl,"total_points":total,"inlier_ratio":round(ratio,6),"reprojection_error":round(err,6) if np.isfinite(err) else "","warp_quality":round(q,6),
                            "h00":vals[0],"h01":vals[1],"h02":vals[2],"h10":vals[3],"h11":vals[4],"h12":vals[5],"h20":vals[6],"h21":vals[7],"h22":vals[8]})
                if source == "detected_ransac":
                    row["homography_valid"] = 1; last_H = H.copy(); last_idx = idx; counts["detected"] += 1
                else: counts["fallback"] += 1
            else:
                row["failure_reason"] = reason; counts["invalid"] += 1
            status = f"{row['homography_source']} valid={row['homography_valid']} usable={row['homography_usable']} q={row['warp_quality']}"
            cv2.imwrite(str(dp), draw_debug(img, corners, ids, known_ids, status, cov))
            w.writerow(row)
            if idx % 50 == 0 or idx == len(items): print(f"[PROGRESS] {idx}/{len(items)}")
    print(f"\n[DONE] total frames: {len(items)}")
    print(f"[DONE] detected valid homography: {counts['detected']}")
    print(f"[DONE] previous-H fallback: {counts['fallback']}")
    print(f"[DONE] invalid frames: {counts['invalid']}")
    print(f"[DONE] warped dir: {out_dir}")
    print(f"[DONE] debug dir: {dbg_dir}")
    print(f"[DONE] homography csv: {csv_path}")

if __name__ == "__main__":
    main()
