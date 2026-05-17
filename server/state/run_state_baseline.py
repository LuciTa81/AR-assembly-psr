from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


STATES = ["S0", "S1", "S2", "S3", "S4", "S5", "S6"]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run framewise, FSM, and simple left-to-right HMM baseline."
    )
    parser.add_argument("--input", type=str, required=True)
    parser.add_argument("--out-csv", type=str, required=True)
    parser.add_argument("--out-plot", type=str, required=True)
    parser.add_argument("--out-metrics", type=str, required=True)
    return parser.parse_args()


def safe_col(df, name, default=0.0):
    if name not in df.columns:
        return pd.Series([default] * len(df))
    return df[name].fillna(default).astype(float)


def build_observation_scores(df: pd.DataFrame) -> np.ndarray:
    """
    Handcrafted observation score.
    Higher = more likely.
    This is not final; it is a prototype baseline for session_13.
    """
    box = safe_col(df, "box_present_score", 1.0).to_numpy()
    lid = safe_col(df, "lid_closed_score", 0.0).to_numpy()

    a = safe_col(df, "screw_a_done_score", 0.0).to_numpy()
    b = safe_col(df, "screw_b_done_score", 0.0).to_numpy()
    c = safe_col(df, "screw_c_done_score", 0.0).to_numpy()
    d = safe_col(df, "screw_d_done_score", 0.0).to_numpy()

    tool = safe_col(df, "tool_visible", 0.0).to_numpy()
    hand = safe_col(df, "hand_visible", 0.0).to_numpy()

    n = len(df)
    scores = np.zeros((n, len(STATES)), dtype=np.float64)

    # S0: box missing or initial
    scores[:, 0] = (1.0 - box) + 0.05

    # S1: box placed, lid not closed
    scores[:, 1] = box * (1.0 - lid) + 0.05

    # S2: lid closed, before screw A done
    scores[:, 2] = lid * (1.0 - a) + 0.05

    # S3~S6: cumulative screw completion cues
    scores[:, 3] = 0.60 * a + 0.20 * lid + 0.05 * tool + 0.05 * hand
    scores[:, 4] = 0.45 * a + 0.55 * b + 0.10 * lid + 0.05 * tool
    scores[:, 5] = 0.30 * a + 0.35 * b + 0.55 * c + 0.05 * tool
    scores[:, 6] = 0.20 * a + 0.25 * b + 0.35 * c + 0.65 * d + 0.05 * tool

    # normalize per row
    scores = np.clip(scores, 1e-6, None)
    scores = scores / scores.sum(axis=1, keepdims=True)

    return scores


def framewise_predict(scores: np.ndarray) -> list[str]:
    idx = scores.argmax(axis=1)
    return [STATES[i] for i in idx]


def fsm_smooth(framewise: list[str]) -> list[str]:
    """
    Enforce left-to-right sequence.
    It can stay or move forward by 1.
    """
    current = 0
    out = []

    for pred in framewise:
        pred_idx = STATES.index(pred)

        if pred_idx > current:
            current = min(current + 1, pred_idx)

        out.append(STATES[current])

    return out


def hmm_viterbi(scores: np.ndarray) -> list[str]:
    n, k = scores.shape

    # Transition: left-to-right.
    # stay is high, next is allowed, skip/backward almost impossible.
    trans = np.full((k, k), 1e-8, dtype=np.float64)

    for i in range(k):
        trans[i, i] = 0.92
        if i + 1 < k:
            trans[i, i + 1] = 0.08

    # final state stays
    trans[k - 1, k - 1] = 1.0

    # normalize
    trans = trans / trans.sum(axis=1, keepdims=True)

    # initial state
    start = np.full(k, 1e-8, dtype=np.float64)
    start[0] = 0.90
    start[1] = 0.10
    start = start / start.sum()

    log_start = np.log(start)
    log_trans = np.log(trans)
    log_emit = np.log(np.clip(scores, 1e-8, None))

    dp = np.zeros((n, k), dtype=np.float64)
    back = np.zeros((n, k), dtype=np.int64)

    dp[0] = log_start + log_emit[0]

    for t in range(1, n):
        for j in range(k):
            prev_scores = dp[t - 1] + log_trans[:, j]
            best_prev = int(np.argmax(prev_scores))
            dp[t, j] = prev_scores[best_prev] + log_emit[t, j]
            back[t, j] = best_prev

    states_idx = np.zeros(n, dtype=np.int64)
    states_idx[-1] = int(np.argmax(dp[-1]))

    for t in range(n - 2, -1, -1):
        states_idx[t] = back[t + 1, states_idx[t + 1]]

    return [STATES[i] for i in states_idx]


def accuracy(y_true, y_pred):
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    return float((y_true == y_pred).mean())


def state_f1_table(df: pd.DataFrame, pred_col: str) -> pd.DataFrame:
    rows = []

    for s in STATES:
        true_s = df["gt_state"] == s
        pred_s = df[pred_col] == s

        tp = int((true_s & pred_s).sum())
        fp = int((~true_s & pred_s).sum())
        fn = int((true_s & ~pred_s).sum())

        precision = tp / (tp + fp) if tp + fp > 0 else 0.0
        recall = tp / (tp + fn) if tp + fn > 0 else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall > 0
            else 0.0
        )

        rows.append(
            {
                "pred_col": pred_col,
                "state": s,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "tp": tp,
                "fp": fp,
                "fn": fn,
            }
        )

    return pd.DataFrame(rows)


def plot_timeline(df: pd.DataFrame, out_plot: Path):
    state_to_y = {s: i for i, s in enumerate(STATES)}

    x = df["frame_id"].astype(int)

    plt.figure(figsize=(12, 5))

    plt.plot(x, df["gt_state"].map(state_to_y), label="GT", linewidth=3)
    plt.plot(x, df["pred_framewise"].map(state_to_y), label="Framewise", alpha=0.7)
    plt.plot(x, df["pred_fsm"].map(state_to_y), label="FSM", alpha=0.8)
    plt.plot(x, df["pred_hmm"].map(state_to_y), label="HMM", linewidth=2)

    plt.yticks(range(len(STATES)), STATES)
    plt.xlabel("frame_id")
    plt.ylabel("state")
    plt.title("State Timeline")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    out_plot.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_plot)
    plt.close()


def main():
    args = parse_args()

    input_path = Path(args.input)
    out_csv = Path(args.out_csv)
    out_plot = Path(args.out_plot)
    out_metrics = Path(args.out_metrics)

    df = pd.read_csv(input_path)

    df["frame_id"] = df["frame_id"].astype(int)
    df = df.sort_values("frame_id").reset_index(drop=True)

    scores = build_observation_scores(df)

    df["pred_framewise"] = framewise_predict(scores)
    df["pred_fsm"] = fsm_smooth(df["pred_framewise"].tolist())
    df["pred_hmm"] = hmm_viterbi(scores)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False, encoding="utf-8-sig")

    metrics_rows = []

    for col in ["pred_framewise", "pred_fsm", "pred_hmm"]:
        metrics_rows.append(
            {
                "metric": "accuracy",
                "model": col,
                "value": accuracy(df["gt_state"], df[col]),
            }
        )

    metrics = pd.DataFrame(metrics_rows)

    f1_tables = [
        state_f1_table(df, "pred_framewise"),
        state_f1_table(df, "pred_fsm"),
        state_f1_table(df, "pred_hmm"),
    ]

    full_metrics = pd.concat(
        [
            metrics,
            pd.concat(f1_tables, ignore_index=True),
        ],
        ignore_index=True,
        sort=False,
    )

    out_metrics.parent.mkdir(parents=True, exist_ok=True)
    full_metrics.to_csv(out_metrics, index=False, encoding="utf-8-sig")

    plot_timeline(df, out_plot)

    print(f"[DONE] predictions: {out_csv}")
    print(f"[DONE] metrics: {out_metrics}")
    print(f"[DONE] plot: {out_plot}")
    print("")
    print(metrics)


if __name__ == "__main__":
    main()