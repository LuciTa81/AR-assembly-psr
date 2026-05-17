from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Dict, Optional, Tuple

import cv2
import numpy as np


ROI_NAMES = [
    "enclosure",
    "lid",
    "base_front",
    "inner_area",
    "screw_a",
    "screw_b",
    "screw_c",
    "screw_d",
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build ROI features from ROI crop folders using reference templates."
    )

    parser.add_argument(
        "--crops-dir",
        type=str,
        required=True,
        help="ROI crops root, e.g. outputs/roi_crops/session_13",
    )
    parser.add_argument(
        "--refs",
        type=str,
        required=True,
        help="Reference template directory, e.g. refs/roi_templates",
    )
    parser.add_argument(
        "--out",
        type=str,
        required=True,
        help="Output CSV path, e.g. outputs/features/session_13_roi_features.csv",
    )
    parser.add_argument(
        "--session-id",
        type=str,
        default=None,
        help="Session id. Defaults to crops-dir folder name.",
    )
    parser.add_argument(
        "--debug-out",
        type=str,
        default=None,
        help="Optional debug CSV path with template distances.",
    )

    return parser.parse_args()


def collect_frame_dirs(crops_dir: Path):
    dirs = [p for p in crops_dir.iterdir() if p.is_dir()]
    return sorted(dirs, key=lambda p: frame_id_to_int(frame_id_from_name(p.name)))


def frame_id_from_name(name: str) -> str:
    """
    Examples:
    - 000092_warped -> 92
    - 000092 -> 92
    - frame_000092 -> 92
    """
    stem = name.replace("_warped", "")
    m = re.search(r"(\d+)", stem)
    if m:
        return str(int(m.group(1)))
    return stem


def frame_id_to_int(frame_id: str) -> int:
    try:
        return int(frame_id)
    except Exception:
        return 10**9


def read_image(path: Path):
    img = cv2.imread(str(path))
    if img is None:
        return None
    return img


def load_ref(ref_dir: Path, name: str):
    for ext in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]:
        p = ref_dir / f"{name}{ext}"
        if p.exists():
            img = cv2.imread(str(p))
            if img is None:
                raise FileNotFoundError(f"Failed to read reference: {p}")
            return img
    return None


def preprocess(img_bgr, size: Tuple[int, int] = (64, 64)) -> np.ndarray:
    """
    Return combined gray + edge feature vector.
    This is simple but works for a controlled ROI baseline.
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, size, interpolation=cv2.INTER_AREA)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    # brightness normalization
    gray_eq = cv2.equalizeHist(gray)

    edges = cv2.Canny(gray_eq, 50, 150)

    gray_f = gray_eq.astype(np.float32) / 255.0
    edge_f = edges.astype(np.float32) / 255.0

    # gray + edge를 같이 비교
    feat = np.concatenate(
        [
            gray_f.reshape(-1),
            0.7 * edge_f.reshape(-1),
        ]
    )

    return feat


def distance(crop_bgr, ref_bgr) -> float:
    if crop_bgr is None or ref_bgr is None:
        return float("nan")

    crop_feat = preprocess(crop_bgr)
    ref_feat = preprocess(ref_bgr)

    return float(np.mean(np.abs(crop_feat - ref_feat)))


def positive_score(crop_bgr, negative_ref, positive_ref) -> Tuple[float, float, float]:
    """
    Returns:
      score, d_negative, d_positive

    score는 0~1.
    positive_ref에 가까우면 score가 커진다.
    """
    if crop_bgr is None or negative_ref is None or positive_ref is None:
        return -1.0, float("nan"), float("nan")

    d_neg = distance(crop_bgr, negative_ref)
    d_pos = distance(crop_bgr, positive_ref)

    if not np.isfinite(d_neg) or not np.isfinite(d_pos):
        return -1.0, d_neg, d_pos

    score = d_neg / (d_neg + d_pos + 1e-8)
    score = max(0.0, min(1.0, float(score)))

    return score, d_neg, d_pos


def load_crop(frame_dir: Path, roi_name: str):
    for ext in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]:
        p = frame_dir / f"{roi_name}{ext}"
        if p.exists():
            return read_image(p)
    return None


def main():
    args = parse_args()

    crops_dir = Path(args.crops_dir)
    ref_dir = Path(args.refs)
    out_path = Path(args.out)
    debug_out_path = Path(args.debug_out) if args.debug_out else None

    session_id = args.session_id or crops_dir.name

    if not crops_dir.exists():
        raise FileNotFoundError(f"crops-dir not found: {crops_dir}")

    if not ref_dir.exists():
        raise FileNotFoundError(f"refs dir not found: {ref_dir}")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    if debug_out_path:
        debug_out_path.parent.mkdir(parents=True, exist_ok=True)

    refs = {
        "box_absent": load_ref(ref_dir, "box_absent"),
        "box_present": load_ref(ref_dir, "box_present"),

        "lid_open": load_ref(ref_dir, "lid_open"),
        "lid_closed": load_ref(ref_dir, "lid_closed"),

        "screw_a_empty": load_ref(ref_dir, "screw_a_empty"),
        "screw_a_done": load_ref(ref_dir, "screw_a_done"),

        "screw_b_empty": load_ref(ref_dir, "screw_b_empty"),
        "screw_b_done": load_ref(ref_dir, "screw_b_done"),

        "screw_c_empty": load_ref(ref_dir, "screw_c_empty"),
        "screw_c_done": load_ref(ref_dir, "screw_c_done"),

        "screw_d_empty": load_ref(ref_dir, "screw_d_empty"),
        "screw_d_done": load_ref(ref_dir, "screw_d_done"),
    }

    print("[INFO] reference status")
    for k, v in refs.items():
        print(f"  {k}: {'OK' if v is not None else 'MISSING'}")

    frame_dirs = collect_frame_dirs(crops_dir)

    if not frame_dirs:
        raise FileNotFoundError(f"No frame crop directories found: {crops_dir}")

    fieldnames = [
        "session_id",
        "frame_id",
        "crop_dir",
        "box_present_score",
        "lid_closed_score",
        "screw_a_done_score",
        "screw_b_done_score",
        "screw_c_done_score",
        "screw_d_done_score",
    ]

    debug_fieldnames = [
        "session_id",
        "frame_id",
        "roi_name",
        "score",
        "d_negative",
        "d_positive",
        "negative_ref",
        "positive_ref",
    ]

    debug_writer = None
    debug_file = None

    if debug_out_path:
        debug_file = debug_out_path.open("w", encoding="utf-8", newline="")
        debug_writer = csv.DictWriter(debug_file, fieldnames=debug_fieldnames)
        debug_writer.writeheader()

    def write_debug(frame_id, roi_name, score, d_neg, d_pos, neg_ref, pos_ref):
        if debug_writer is None:
            return
        debug_writer.writerow(
            {
                "session_id": session_id,
                "frame_id": frame_id,
                "roi_name": roi_name,
                "score": round(score, 6) if score >= 0 else score,
                "d_negative": round(d_neg, 6) if np.isfinite(d_neg) else "",
                "d_positive": round(d_pos, 6) if np.isfinite(d_pos) else "",
                "negative_ref": neg_ref,
                "positive_ref": pos_ref,
            }
        )

    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        total = len(frame_dirs)

        for idx, frame_dir in enumerate(frame_dirs, start=1):
            frame_id = frame_id_from_name(frame_dir.name)

            enclosure = load_crop(frame_dir, "enclosure")
            lid = load_crop(frame_dir, "lid")
            screw_a = load_crop(frame_dir, "screw_a")
            screw_b = load_crop(frame_dir, "screw_b")
            screw_c = load_crop(frame_dir, "screw_c")
            screw_d = load_crop(frame_dir, "screw_d")

            # box refs가 없으면 session_13에서는 box가 있다고 가정
            if refs["box_absent"] is not None and refs["box_present"] is not None:
                box_score, d0, d1 = positive_score(
                    enclosure,
                    refs["box_absent"],
                    refs["box_present"],
                )
                write_debug(frame_id, "enclosure", box_score, d0, d1, "box_absent", "box_present")
            else:
                box_score = 1.0

            lid_score, d0, d1 = positive_score(
                lid,
                refs["lid_open"],
                refs["lid_closed"],
            )
            write_debug(frame_id, "lid", lid_score, d0, d1, "lid_open", "lid_closed")

            screw_a_score, d0, d1 = positive_score(
                screw_a,
                refs["screw_a_empty"],
                refs["screw_a_done"],
            )
            write_debug(frame_id, "screw_a", screw_a_score, d0, d1, "screw_a_empty", "screw_a_done")

            screw_b_score, d0, d1 = positive_score(
                screw_b,
                refs["screw_b_empty"],
                refs["screw_b_done"],
            )
            write_debug(frame_id, "screw_b", screw_b_score, d0, d1, "screw_b_empty", "screw_b_done")

            screw_c_score, d0, d1 = positive_score(
                screw_c,
                refs["screw_c_empty"],
                refs["screw_c_done"],
            )
            write_debug(frame_id, "screw_c", screw_c_score, d0, d1, "screw_c_empty", "screw_c_done")

            screw_d_score, d0, d1 = positive_score(
                screw_d,
                refs["screw_d_empty"],
                refs["screw_d_done"],
            )
            write_debug(frame_id, "screw_d", screw_d_score, d0, d1, "screw_d_empty", "screw_d_done")

            writer.writerow(
                {
                    "session_id": session_id,
                    "frame_id": frame_id,
                    "crop_dir": frame_dir.name,
                    "box_present_score": round(box_score, 6),
                    "lid_closed_score": round(lid_score, 6),
                    "screw_a_done_score": round(screw_a_score, 6),
                    "screw_b_done_score": round(screw_b_score, 6),
                    "screw_c_done_score": round(screw_c_score, 6),
                    "screw_d_done_score": round(screw_d_score, 6),
                }
            )

            if idx % 50 == 0 or idx == total:
                print(f"[PROGRESS] {idx}/{total}")

    if debug_file:
        debug_file.close()

    print("")
    print(f"[DONE] roi features saved: {out_path}")
    print(f"[DONE] total frames: {len(frame_dirs)}")

    if debug_out_path:
        print(f"[DONE] debug distances saved: {debug_out_path}")


if __name__ == "__main__":
    main()