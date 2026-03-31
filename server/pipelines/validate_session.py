from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


EXPECTED_COLUMNS = [
    "frame_id",
    "timestamp_iso",
    "timestamp_unix_ms",
    "image_path",
    "width",
    "height",
]


def validate_session(session_dir: str) -> int:
    session_path = Path(session_dir)

    print(f"[INFO] Validating session: {session_path}")

    if not session_path.exists():
        print(f"[ERROR] Session path does not exist: {session_path}")
        return 1

    if not session_path.is_dir():
        print(f"[ERROR] Session path is not a directory: {session_path}")
        return 1

    meta_path = session_path / "meta.json"
    frames_csv_path = session_path / "frames.csv"
    frames_dir = session_path / "frames"

    has_error = False

    if not meta_path.exists():
        print("[ERROR] meta.json not found")
        has_error = True
    else:
        print("[OK] meta.json found")

    if not frames_csv_path.exists():
        print("[ERROR] frames.csv not found")
        has_error = True
    else:
        print("[OK] frames.csv found")

    if not frames_dir.exists():
        print("[ERROR] frames/ directory not found")
        has_error = True
    else:
        print("[OK] frames/ directory found")

    if has_error:
        return 1

    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        print("[OK] meta.json parsed")
    except Exception as e:
        print(f"[ERROR] Failed to parse meta.json: {e}")
        return 1

    session_id = meta.get("session_id")
    if session_id != session_path.name:
        print(
            f"[WARN] session_id in meta.json ({session_id}) "
            f"does not match folder name ({session_path.name})"
        )
    else:
        print("[OK] session_id matches folder name")

    try:
        df = pd.read_csv(frames_csv_path)
        print("[OK] frames.csv parsed")
    except Exception as e:
        print(f"[ERROR] Failed to parse frames.csv: {e}")
        return 1

    if list(df.columns) != EXPECTED_COLUMNS:
        print("[ERROR] frames.csv columns do not match expected schema")
        print(f"       expected: {EXPECTED_COLUMNS}")
        print(f"       actual:   {list(df.columns)}")
        return 1
    else:
        print("[OK] frames.csv columns match expected schema")

    if len(df) == 0:
        print("[ERROR] frames.csv contains no rows")
        return 1

    expected_ids = list(range(1, len(df) + 1))
    actual_ids = df["frame_id"].tolist()
    if actual_ids != expected_ids:
        print("[WARN] frame_id sequence is not strictly 1..N")
    else:
        print("[OK] frame_id sequence is contiguous")

    invalid_sizes = df[(df["width"] <= 0) | (df["height"] <= 0)]
    if len(invalid_sizes) > 0:
        print(f"[ERROR] Found {len(invalid_sizes)} rows with invalid width/height")
        has_error = True
    else:
        print("[OK] width/height values are valid")

    missing_files = []
    for _, row in df.iterrows():
        image_rel = str(row["image_path"])
        image_path = session_path / image_rel
        if not image_path.exists():
            missing_files.append(image_rel)

    if missing_files:
        print(f"[ERROR] Missing image files: {len(missing_files)}")
        for p in missing_files[:10]:
            print(f"       - {p}")
        if len(missing_files) > 10:
            print(f"       ... and {len(missing_files) - 10} more")
        has_error = True
    else:
        print("[OK] All image files referenced by frames.csv exist")

    jpg_files = sorted(frames_dir.glob("*.jpg"))
    if len(jpg_files) != len(df):
        print(
            f"[WARN] Image count ({len(jpg_files)}) "
            f"differs from frames.csv row count ({len(df)})"
        )
    else:
        print("[OK] Image count matches frames.csv row count")

    if has_error:
        print("[RESULT] Validation finished with errors")
        return 1

    print("[RESULT] Validation successful")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python server/pipelines/validate_session.py <session_dir>")
        sys.exit(1)

    sys.exit(validate_session(sys.argv[1]))
