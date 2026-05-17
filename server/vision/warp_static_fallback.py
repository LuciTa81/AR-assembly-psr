from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List

import cv2
import numpy as np


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Apply detected homography when available, otherwise use a static fallback homography."
    )

    parser.add_argument("--session", type=str, required=True)
    parser.add_argument("--homography-csv", type=str, required=True)
    parser.add_argument("--out-dir", type=str, required=True)
    parser.add_argument("--out-csv", type=str, required=True)
    parser.add_argument("--reference-frame-id", type=str, default=None)
    parser.add_argument("--width", type=int, default=800)
    parser.add_argument("--height", type=int, default=600)

    return parser.parse_args()


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
        paths = sorted(p for p in frames_dir.rglob("*") if p.suffix.lower() in IMAGE_EXTS)
    else:
        paths = sorted(p for p in session_dir.rglob("*") if p.suffix.lower() in IMAGE_EXTS)

    rows = []
    for i, path in enumerate(paths, start=1):
        rows.append(
            {
                "frame_id": str(i),
                "image_path": str(path),
                "display_path": path.name,
            }
        )
    return rows


def load_homography_rows(homography_csv: Path) -> Dict[str, Dict[str, str]]:
    rows: Dict[str, Dict[str, str]] = {}

    with homography_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows[str(row["frame_id"])] = row

    return rows


def row_to_h(row: Dict[str, str]) -> np.ndarray:
    values = [
        float(row["h00"]), float(row["h01"]), float(row["h02"]),
        float(row["h10"]), float(row["h11"]), float(row["h12"]),
        float(row["h20"]), float(row["h21"]), float(row["h22"]),
    ]
    return np.array(values, dtype=np.float64).reshape(3, 3)


def choose_reference_h(
    h_rows: Dict[str, Dict[str, str]],
    reference_frame_id: str | None,
) -> tuple[str, np.ndarray]:
    if reference_frame_id is not None:
        row = h_rows.get(str(reference_frame_id))
        if row is None:
            raise ValueError(f"reference_frame_id not found: {reference_frame_id}")
        if row.get("homography_valid") != "1":
            raise ValueError(f"reference_frame_id is not valid: {reference_frame_id}")

        return str(reference_frame_id), row_to_h(row)

    for frame_id, row in h_rows.items():
        if row.get("homography_valid") == "1":
            return str(frame_id), row_to_h(row)

    raise ValueError("No valid homography row found.")


def frame_stem(frame_id: str, image_path: str) -> str:
    try:
        return f"{int(frame_id):06d}"
    except Exception:
        return Path(image_path).stem


def main():
    args = parse_args()

    session_dir = Path(args.session)
    homography_csv = Path(args.homography_csv)
    out_dir = Path(args.out_dir)
    out_csv = Path(args.out_csv)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    items = collect_images_from_session(session_dir)
    h_rows = load_homography_rows(homography_csv)

    ref_frame_id, h_ref = choose_reference_h(h_rows, args.reference_frame_id)

    print(f"[INFO] reference frame_id: {ref_frame_id}")
    print(f"[INFO] total frames: {len(items)}")

    fieldnames = [
        "session_id",
        "frame_id",
        "image_path",
        "warped_path",
        "homography_valid",
        "homography_source",
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

    detected_count = 0
    fallback_count = 0
    failed_count = 0

    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for idx, item in enumerate(items, start=1):
            frame_id = str(item["frame_id"])
            image_path = Path(item["image_path"])
            display_path = item["display_path"]

            image_bgr = cv2.imread(str(image_path))
            if image_bgr is None:
                failed_count += 1
                print(f"[WARN] failed to read: {image_path}")
                continue

            original_row = h_rows.get(frame_id)

            if original_row is not None and original_row.get("homography_valid") == "1":
                H = row_to_h(original_row)
                source = "detected_4marker"
                homography_valid = 1
                marker_count = original_row.get("marker_count", "4")
                detected_count += 1
            else:
                H = h_ref
                source = "static_fallback"
                homography_valid = 0
                marker_count = original_row.get("marker_count", "0") if original_row else "0"
                fallback_count += 1

            stem = frame_stem(frame_id, str(image_path))
            warped_name = f"{stem}_warped.jpg"
            warped_path = out_dir / warped_name

            warped = cv2.warpPerspective(image_bgr, H, (args.width, args.height))
            cv2.imwrite(str(warped_path), warped)

            h = H.flatten()

            writer.writerow(
                {
                    "session_id": session_dir.name,
                    "frame_id": frame_id,
                    "image_path": display_path,
                    "warped_path": str(warped_path),
                    "homography_valid": homography_valid,
                    "homography_source": source,
                    "marker_count": marker_count,
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

            if idx % 50 == 0 or idx == len(items):
                print(f"[PROGRESS] {idx}/{len(items)}")

    print("")
    print(f"[DONE] warped dir: {out_dir}")
    print(f"[DONE] out csv: {out_csv}")
    print(f"[DONE] detected H frames: {detected_count}")
    print(f"[DONE] static fallback frames: {fallback_count}")
    print(f"[DONE] failed frames: {failed_count}")


if __name__ == "__main__":
    main()