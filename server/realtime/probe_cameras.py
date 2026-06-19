from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import cv2


BACKENDS = {
    "any": cv2.CAP_ANY,
    "dshow": cv2.CAP_DSHOW,
    "msmf": cv2.CAP_MSMF,
}


def parse_args():
    parser = argparse.ArgumentParser(description="Probe local camera indices for the realtime harness.")
    parser.add_argument("--max-index", type=int, default=8)
    parser.add_argument("--backend", choices=sorted(BACKENDS), default="dshow")
    parser.add_argument("--warmup-frames", type=int, default=8)
    parser.add_argument("--out-dir", default="outputs/realtime_camera_probe")
    parser.add_argument("--save-preview", action="store_true")
    return parser.parse_args()


def probe_index(index: int, backend: int, warmup_frames: int):
    cap = cv2.VideoCapture(index, backend)
    if not cap.isOpened():
        cap.release()
        return {
            "index": index,
            "opened": False,
            "read_ok": False,
            "width": 0,
            "height": 0,
            "fps": 0.0,
            "backend": "",
            "preview_path": "",
        }, None

    frame = None
    read_ok = False
    start = time.perf_counter()
    frames_read = 0
    for _ in range(max(1, warmup_frames)):
        read_ok, frame = cap.read()
        if read_ok and frame is not None:
            frames_read += 1
        time.sleep(0.02)
    elapsed = max(1e-6, time.perf_counter() - start)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    fps_prop = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    measured_fps = frames_read / elapsed
    try:
        backend_name = cap.getBackendName()
    except Exception:
        backend_name = ""
    cap.release()
    return {
        "index": index,
        "opened": True,
        "read_ok": bool(read_ok and frame is not None),
        "width": width,
        "height": height,
        "fps": round(fps_prop if fps_prop > 0 else measured_fps, 3),
        "backend": backend_name,
        "preview_path": "",
    }, frame


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    backend = BACKENDS[args.backend]

    print(f"[INFO] probing camera indices 0..{args.max_index} using backend={args.backend}")
    for index in range(args.max_index + 1):
        row, frame = probe_index(index, backend, args.warmup_frames)
        if args.save_preview and row["read_ok"] and frame is not None:
            preview_path = out_dir / f"camera_{index}_preview.jpg"
            cv2.imwrite(str(preview_path), frame)
            row["preview_path"] = str(preview_path)
        rows.append(row)
        status = "OK" if row["read_ok"] else "NO"
        print(
            f"[{status}] index={index} opened={row['opened']} "
            f"read={row['read_ok']} size={row['width']}x{row['height']} "
            f"fps={row['fps']} backend={row['backend']}"
        )

    csv_path = out_dir / f"camera_probe_{args.backend}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["index", "opened", "read_ok", "width", "height", "fps", "backend", "preview_path"],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"[DONE] probe csv: {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
