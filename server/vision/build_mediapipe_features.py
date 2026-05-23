from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np
import pandas as pd
import yaml


SCREW_NAMES = ["a", "b", "c", "d"]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build MediaPipe index-near features by projecting index finger coordinates into warped workspace."
    )

    parser.add_argument("--mediapipe-raw", type=str, required=True)
    parser.add_argument("--homography", type=str, required=True)
    parser.add_argument("--layout", type=str, required=True)
    parser.add_argument("--out", type=str, required=True)
    parser.add_argument("--session-id", type=str, required=True)

    parser.add_argument("--near-threshold", type=float, default=140.0)
    parser.add_argument("--workspace-width", type=int, default=800)
    parser.add_argument("--workspace-height", type=int, default=600)

    parser.add_argument("--warped-dir", type=str, default=None)
    parser.add_argument("--debug-dir", type=str, default=None)
    parser.add_argument("--debug-limit", type=int, default=0)

    return parser.parse_args()


def norm_frame_id(value) -> int:
    if pd.isna(value):
        return -1

    s = str(value)
    m = re.search(r"(\d+)", s)

    if m:
        return int(m.group(1))

    return -1


def load_layout(layout_path: Path) -> Dict[str, Any]:
    with layout_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if data is None or "rois" not in data:
        raise ValueError(f"Invalid ROI layout: {layout_path}")

    return data


def parse_rect(value: Any) -> Tuple[float, float, float, float]:
    """
    Returns x, y, w, h.
    Supports:
    - {x,y,w,h}
    - {x1,y1,x2,y2}
    - [x,y,w,h]
    """
    if isinstance(value, dict):
        if all(k in value for k in ["x", "y", "w", "h"]):
            return float(value["x"]), float(value["y"]), float(value["w"]), float(value["h"])

        if all(k in value for k in ["x1", "y1", "x2", "y2"]):
            x1 = float(value["x1"])
            y1 = float(value["y1"])
            x2 = float(value["x2"])
            y2 = float(value["y2"])
            return x1, y1, x2 - x1, y2 - y1

    if isinstance(value, (list, tuple)) and len(value) == 4:
        return float(value[0]), float(value[1]), float(value[2]), float(value[3])

    raise ValueError(f"Invalid ROI rect: {value}")


def load_screw_centers(layout_path: Path) -> Dict[str, Tuple[float, float]]:
    layout = load_layout(layout_path)
    rois = layout["rois"]

    centers = {}

    for name in ["screw_a", "screw_b", "screw_c", "screw_d"]:
        if name not in rois:
            raise ValueError(f"Missing ROI in layout: {name}")

        x, y, w, h = parse_rect(rois[name])
        key = name.replace("screw_", "")
        centers[key] = (x + w / 2.0, y + h / 2.0)

    return centers


def load_homography(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["frame_id"] = df["frame_id"].apply(norm_frame_id)

    required = ["h00", "h01", "h02", "h10", "h11", "h12", "h20", "h21", "h22"]

    for c in required:
        if c not in df.columns:
            raise ValueError(f"homography CSV missing column: {c}")

    if "homography_usable" not in df.columns:
        if "homography_valid" in df.columns:
            df["homography_usable"] = df["homography_valid"]
        else:
            df["homography_usable"] = 0

    if "homography_valid" not in df.columns:
        df["homography_valid"] = df["homography_usable"]

    if "warp_quality" not in df.columns:
        df["warp_quality"] = df["homography_usable"].astype(float)

    if "marker_count" not in df.columns:
        df["marker_count"] = 0

    if "homography_source" not in df.columns:
        df["homography_source"] = ""

    return df


def h_from_row(row) -> np.ndarray:
    vals = [
        float(row["h00"]), float(row["h01"]), float(row["h02"]),
        float(row["h10"]), float(row["h11"]), float(row["h12"]),
        float(row["h20"]), float(row["h21"]), float(row["h22"]),
    ]
    return np.array(vals, dtype=np.float64).reshape(3, 3)


def load_mediapipe_raw(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(
            columns=[
                "frame_id",
                "hand_visible",
                "hand_score",
                "index_x",
                "index_y",
            ]
        )

    df = pd.read_csv(path)

    if df.empty:
        return pd.DataFrame(
            columns=[
                "frame_id",
                "hand_visible",
                "hand_score",
                "index_x",
                "index_y",
            ]
        )

    df["frame_id"] = df["frame_id"].apply(norm_frame_id)

    if "hand_visible" not in df.columns:
        if "num_hands" in df.columns:
            df["hand_visible"] = (df["num_hands"].astype(float) > 0).astype(int)
        else:
            df["hand_visible"] = 0

    if "hand_score" not in df.columns:
        df["hand_score"] = 0.0

    if "index_x" not in df.columns or "index_y" not in df.columns:
        raise ValueError("MediaPipe raw CSV must contain index_x and index_y")

    for c in ["hand_visible", "hand_score", "index_x", "index_y"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    return df


def pick_best_hand(rows: pd.DataFrame) -> Optional[pd.Series]:
    if rows is None or rows.empty:
        return None

    valid = rows[
        (rows["hand_visible"] > 0)
        & (rows["index_x"] >= 0)
        & (rows["index_y"] >= 0)
    ].copy()

    if valid.empty:
        return None

    valid = valid.sort_values("hand_score", ascending=False)
    return valid.iloc[0]


def transform_point(H: np.ndarray, x: float, y: float) -> Tuple[float, float]:
    pts = np.array([[[x, y]]], dtype=np.float32)
    warped = cv2.perspectiveTransform(pts, H)
    return float(warped[0, 0, 0]), float(warped[0, 0, 1])


def point_inside_workspace(x: float, y: float, width: int, height: int) -> bool:
    return 0 <= x < width and 0 <= y < height


def euclidean(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return float(np.linalg.norm(np.array(p1, dtype=np.float32) - np.array(p2, dtype=np.float32)))


def warped_image_path(warped_dir: Optional[Path], frame_id: int) -> Optional[Path]:
    if warped_dir is None:
        return None

    p = warped_dir / f"{frame_id:06d}_warped.jpg"

    if p.exists():
        return p

    return None


def draw_debug(
    warped_path: Path,
    out_path: Path,
    index_point: Optional[Tuple[float, float]],
    screw_centers: Dict[str, Tuple[float, float]],
    row: Dict[str, Any],
):
    img = cv2.imread(str(warped_path))

    if img is None:
        return

    for key, center in screw_centers.items():
        x, y = int(round(center[0])), int(round(center[1]))

        cv2.circle(img, (x, y), 8, (0, 255, 255), 2)
        cv2.putText(
            img,
            key.upper(),
            (x + 8, y - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )

    if index_point is not None:
        ix, iy = int(round(index_point[0])), int(round(index_point[1]))

        cv2.circle(img, (ix, iy), 10, (0, 0, 255), -1)
        cv2.putText(
            img,
            "index",
            (ix + 10, iy),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 255),
            2,
            cv2.LINE_AA,
        )

    text = f"near={row.get('chosen_screw','none')} score={row.get('hand_score',0)}"

    cv2.putText(
        img,
        text,
        (20, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 0, 255),
        2,
        cv2.LINE_AA,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), img)


def main():
    args = parse_args()

    mp_raw_path = Path(args.mediapipe_raw)
    homography_path = Path(args.homography)
    layout_path = Path(args.layout)
    out_path = Path(args.out)

    warped_dir = Path(args.warped_dir) if args.warped_dir else None
    debug_dir = Path(args.debug_dir) if args.debug_dir else None

    screw_centers = load_screw_centers(layout_path)
    h_df = load_homography(homography_path)
    mp_df = load_mediapipe_raw(mp_raw_path)

    mp_group = {
        int(fid): group.copy()
        for fid, group in mp_df.groupby("frame_id")
    }

    rows = []
    debug_count = 0

    for _, h_row in h_df.sort_values("frame_id").iterrows():
        frame_id = int(h_row["frame_id"])
        hands = mp_group.get(frame_id, pd.DataFrame())

        hand_visible_any = 0

        if hands is not None and not hands.empty:
            hand_visible_any = int((hands["hand_visible"] > 0).any())

        best_hand = pick_best_hand(hands)

        homography_usable = int(str(h_row.get("homography_usable", "0")) == "1")
        homography_valid = int(str(h_row.get("homography_valid", "0")) == "1")
        warp_quality = float(h_row.get("warp_quality", 0.0) or 0.0)

        out = {
            "session_id": args.session_id,
            "frame_id": frame_id,
            "hand_visible": hand_visible_any,
            "hand_score": 0.0,
            "homography_valid": homography_valid,
            "homography_usable": homography_usable,
            "homography_source": h_row.get("homography_source", ""),
            "marker_count": h_row.get("marker_count", 0),
            "warp_quality": round(warp_quality, 6),
            "index_inside_workspace": 0,
            "index_x_warped": -1.0,
            "index_y_warped": -1.0,
            "index_dist_a": -1.0,
            "index_dist_b": -1.0,
            "index_dist_c": -1.0,
            "index_dist_d": -1.0,
            "index_near_a": 0,
            "index_near_b": 0,
            "index_near_c": 0,
            "index_near_d": 0,
            "chosen_screw": "none",
        }

        index_point = None

        if best_hand is not None:
            out["hand_score"] = round(float(best_hand["hand_score"]), 6)

        if best_hand is not None and homography_usable == 1:
            H = h_from_row(h_row)

            ix_raw = float(best_hand["index_x"])
            iy_raw = float(best_hand["index_y"])

            ix_w, iy_w = transform_point(H, ix_raw, iy_raw)

            out["index_x_warped"] = round(ix_w, 3)
            out["index_y_warped"] = round(iy_w, 3)

            index_point = (ix_w, iy_w)

            inside = point_inside_workspace(
                ix_w,
                iy_w,
                width=args.workspace_width,
                height=args.workspace_height,
            )

            out["index_inside_workspace"] = 1 if inside else 0

            if inside:
                dists = {}

                for key in SCREW_NAMES:
                    d = euclidean((ix_w, iy_w), screw_centers[key])
                    dists[key] = d
                    out[f"index_dist_{key}"] = round(d, 3)

                chosen = min(dists, key=dists.get)
                chosen_dist = dists[chosen]

                if chosen_dist <= args.near_threshold:
                    out[f"index_near_{chosen}"] = 1
                    out["chosen_screw"] = chosen

        rows.append(out)

        if debug_dir is not None and debug_count < args.debug_limit:
            wp = warped_image_path(warped_dir, frame_id) if warped_dir else None

            if wp is not None and wp.exists():
                draw_debug(
                    warped_path=wp,
                    out_path=debug_dir / f"{frame_id:06d}_mediapipe_feature_debug.jpg",
                    index_point=index_point,
                    screw_centers=screw_centers,
                    row=out,
                )
                debug_count += 1

    out_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "session_id",
        "frame_id",
        "hand_visible",
        "hand_score",
        "homography_valid",
        "homography_usable",
        "homography_source",
        "marker_count",
        "warp_quality",
        "index_inside_workspace",
        "index_x_warped",
        "index_y_warped",
        "index_dist_a",
        "index_dist_b",
        "index_dist_c",
        "index_dist_d",
        "index_near_a",
        "index_near_b",
        "index_near_c",
        "index_near_d",
        "chosen_screw",
    ]

    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[DONE] saved: {out_path}")
    print(f"[DONE] rows: {len(rows)}")
    print(f"[DONE] hand visible frames: {sum(r['hand_visible'] for r in rows)}")
    print(f"[DONE] index inside workspace frames: {sum(r['index_inside_workspace'] for r in rows)}")
    print(f"[DONE] index near A: {sum(r['index_near_a'] for r in rows)}")
    print(f"[DONE] index near B: {sum(r['index_near_b'] for r in rows)}")
    print(f"[DONE] index near C: {sum(r['index_near_c'] for r in rows)}")
    print(f"[DONE] index near D: {sum(r['index_near_d'] for r in rows)}")

    if debug_dir is not None:
        print(f"[DONE] debug dir: {debug_dir}")


if __name__ == "__main__":
    main()