from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build minimal HMM input CSV by merging ROI, YOLO, MediaPipe, and labels."
    )

    parser.add_argument("--session-id", type=str, required=True)
    parser.add_argument("--roi", type=str, required=True)
    parser.add_argument("--yolo", type=str, required=True)
    parser.add_argument("--mediapipe", type=str, required=True)
    parser.add_argument("--labels", type=str, required=True)
    parser.add_argument("--out", type=str, required=True)

    return parser.parse_args()


def norm_frame_id(value) -> int:
    """
    Robust frame id parser.
    Handles:
    - 92
    - 000092
    - 000092_warped
    - 000092_jpg
    """
    if pd.isna(value):
        return -1

    s = str(value)

    match = re.search(r"(\d+)", s)
    if match:
        return int(match.group(1))

    return -1


def load_roi(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["frame_id"] = df["frame_id"].apply(norm_frame_id)

    keep_cols = [
        "frame_id",
        "box_present_score",
        "lid_closed_score",
        "screw_a_done_score",
        "screw_b_done_score",
        "screw_c_done_score",
        "screw_d_done_score",
    ]

    for c in keep_cols:
        if c not in df.columns:
            if c == "frame_id":
                continue
            df[c] = -1.0

    return df[keep_cols].copy()


def load_yolo(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(
            columns=[
                "frame_id",
                "tool_visible",
                "tool_confidence",
                "tool_detection_count",
            ]
        )

    df = pd.read_csv(path)

    if df.empty:
        return pd.DataFrame(
            columns=[
                "frame_id",
                "tool_visible",
                "tool_confidence",
                "tool_detection_count",
            ]
        )

    df["frame_id"] = df["frame_id"].apply(norm_frame_id)

    if "confidence" not in df.columns:
        df["confidence"] = 0.0

    grouped = (
        df.groupby("frame_id")
        .agg(
            tool_confidence=("confidence", "max"),
            tool_detection_count=("confidence", "count"),
        )
        .reset_index()
    )

    grouped["tool_visible"] = 1

    return grouped[
        [
            "frame_id",
            "tool_visible",
            "tool_confidence",
            "tool_detection_count",
        ]
    ]


def load_mediapipe(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(
            columns=[
                "frame_id",
                "hand_visible",
                "hand_score",
            ]
        )

    df = pd.read_csv(path)

    if df.empty:
        return pd.DataFrame(
            columns=[
                "frame_id",
                "hand_visible",
                "hand_score",
            ]
        )

    df["frame_id"] = df["frame_id"].apply(norm_frame_id)

    if "hand_visible" not in df.columns:
        df["hand_visible"] = 0

    if "hand_score" not in df.columns:
        df["hand_score"] = 0.0

    grouped = (
        df.groupby("frame_id")
        .agg(
            hand_visible=("hand_visible", "max"),
            hand_score=("hand_score", "max"),
        )
        .reset_index()
    )

    return grouped[
        [
            "frame_id",
            "hand_visible",
            "hand_score",
        ]
    ]


def load_labels(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)

    required = ["session_id", "start_frame", "end_frame", "state"]
    for c in required:
        if c not in df.columns:
            raise ValueError(f"labels file missing column: {c}")

    df["start_frame"] = df["start_frame"].apply(norm_frame_id)
    df["end_frame"] = df["end_frame"].apply(norm_frame_id)

    return df


def assign_gt_state(frame_id: int, labels: pd.DataFrame) -> str:
    match = labels[
        (labels["start_frame"] <= frame_id)
        & (labels["end_frame"] >= frame_id)
    ]

    if len(match) == 0:
        return "UNKNOWN"

    return str(match.iloc[0]["state"])


def main():
    args = parse_args()

    roi_path = Path(args.roi)
    yolo_path = Path(args.yolo)
    mp_path = Path(args.mediapipe)
    labels_path = Path(args.labels)
    out_path = Path(args.out)

    roi = load_roi(roi_path)
    yolo = load_yolo(yolo_path)
    mp = load_mediapipe(mp_path)
    labels = load_labels(labels_path)

    # ROI 기준으로 전체 frame 생성
    base = roi.copy()

    base["session_id"] = args.session_id

    base = base.merge(yolo, on="frame_id", how="left")
    base = base.merge(mp, on="frame_id", how="left")

    # missing fill
    base["tool_visible"] = base["tool_visible"].fillna(0).astype(int)
    base["tool_confidence"] = base["tool_confidence"].fillna(0.0).astype(float)
    base["tool_detection_count"] = base["tool_detection_count"].fillna(0).astype(int)

    base["hand_visible"] = base["hand_visible"].fillna(0).astype(int)
    base["hand_score"] = base["hand_score"].fillna(0.0).astype(float)

    base["gt_state"] = base["frame_id"].apply(lambda x: assign_gt_state(x, labels))

    # column order
    cols = [
        "session_id",
        "frame_id",
        "gt_state",
        "box_present_score",
        "lid_closed_score",
        "screw_a_done_score",
        "screw_b_done_score",
        "screw_c_done_score",
        "screw_d_done_score",
        "tool_visible",
        "tool_confidence",
        "tool_detection_count",
        "hand_visible",
        "hand_score",
    ]

    base = base[cols].sort_values("frame_id")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    base.to_csv(out_path, index=False, encoding="utf-8-sig")

    print(f"[DONE] saved: {out_path}")
    print(f"[DONE] rows: {len(base)}")
    print("[STATE COUNTS]")
    print(base["gt_state"].value_counts())


if __name__ == "__main__":
    main()