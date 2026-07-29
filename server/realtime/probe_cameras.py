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
    parser.add_argument("--modes", default="640x480@30,1280x720@30,1920x1080@30")
    parser.add_argument("--sample-seconds", type=float, default=3.0)
    parser.add_argument("--out-dir", default="outputs/realtime_camera_probe")
    parser.add_argument("--save-preview", action="store_true")
    return parser.parse_args()


CSV_FIELDS = [
    "index",
    "backend",
    "opened",
    "read_ok",
    "requested_width",
    "requested_height",
    "requested_fps",
    "actual_width",
    "actual_height",
    "fps_property",
    "frames_read",
    "measured_fps",
    "read_failures",
    "mean_read_ms",
    "p95_read_ms",
    "preview_path",
]


def probe_mode(
    index: int,
    backend: int,
    width: int,
    height: int,
    requested_fps: float,
    sample_seconds: float,
):
    cap = cv2.VideoCapture(index, backend)
    if not cap.isOpened():
        cap.release()
        return {
            "index": index,
            "backend": "",
            "opened": False,
            "read_ok": False,
            "requested_width": width,
            "requested_height": height,
            "requested_fps": requested_fps,
            "actual_width": 0,
            "actual_height": 0,
            "fps_property": 0.0,
            "frames_read": 0,
            "measured_fps": 0.0,
            "read_failures": 0,
            "mean_read_ms": 0.0,
            "p95_read_ms": 0.0,
            "preview_path": "",
        }, None

    if width > 0:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    if height > 0:
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    if requested_fps > 0:
        cap.set(cv2.CAP_PROP_FPS, requested_fps)

    frame = None
    start = time.perf_counter()
    frames_read = 0
    read_failures = 0
    read_durations_ms = []
    while time.perf_counter() - start < max(0.0, sample_seconds):
        read_start = time.perf_counter()
        read_ok, candidate_frame = cap.read()
        read_durations_ms.append((time.perf_counter() - read_start) * 1000.0)
        if read_ok and candidate_frame is not None:
            frames_read += 1
            frame = candidate_frame
        else:
            read_failures += 1
    elapsed = max(1e-6, time.perf_counter() - start)
    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    fps_prop = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    measured_fps = frames_read / elapsed
    try:
        backend_name = cap.getBackendName()
    except Exception:
        backend_name = ""
    cap.release()
    return {
        "index": index,
        "backend": backend_name,
        "opened": True,
        "read_ok": frames_read > 0,
        "requested_width": width,
        "requested_height": height,
        "requested_fps": requested_fps,
        "actual_width": actual_width,
        "actual_height": actual_height,
        "fps_property": round(fps_prop, 3),
        "frames_read": frames_read,
        "measured_fps": round(measured_fps, 3),
        "read_failures": read_failures,
        "mean_read_ms": round(sum(read_durations_ms) / len(read_durations_ms), 3)
        if read_durations_ms
        else 0.0,
        "p95_read_ms": round(sorted(read_durations_ms)[int(0.95 * (len(read_durations_ms) - 1))], 3)
        if read_durations_ms
        else 0.0,
        "preview_path": "",
    }, frame


def probe_index(index: int, backend: int, warmup_frames: int):
    return probe_mode(index, backend, 0, 0, 0.0, max(1, warmup_frames) * 0.02)


def parse_modes(value: str):
    modes = []
    for mode in value.split(","):
        try:
            dimensions, fps = mode.strip().split("@", maxsplit=1)
            width, height = dimensions.split("x", maxsplit=1)
            modes.append((int(width), int(height), float(fps)))
        except ValueError as exc:
            raise ValueError(f"invalid mode {mode!r}; expected WIDTHxHEIGHT@FPS") from exc
    return modes


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    backend = BACKENDS[args.backend]

    try:
        modes = parse_modes(args.modes)
    except ValueError as exc:
        raise SystemExit(f"[ERROR] {exc}") from exc

    print(f"[INFO] probing camera indices 0..{args.max_index} using backend={args.backend}")
    for index in range(args.max_index + 1):
        for width, height, requested_fps in modes:
            row, frame = probe_mode(index, backend, width, height, requested_fps, args.sample_seconds)
            if args.save_preview and row["read_ok"] and frame is not None:
                preview_path = out_dir / f"camera_{index}_{width}x{height}_{requested_fps:g}fps_preview.jpg"
                cv2.imwrite(str(preview_path), frame)
                row["preview_path"] = str(preview_path)
            rows.append(row)
            status = "OK" if row["read_ok"] else "NO"
            print(
                f"[{status}] index={index} opened={row['opened']} read={row['read_ok']} "
                f"requested={row['requested_width']}x{row['requested_height']}@{row['requested_fps']:g} "
                f"actual={row['actual_width']}x{row['actual_height']} "
                f"measured_fps={row['measured_fps']:.3f} backend={row['backend']}"
            )

    csv_path = out_dir / f"camera_probe_{args.backend}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=CSV_FIELDS,
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"[DONE] probe csv: {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
