from __future__ import annotations

import csv
import json
import hashlib
import os
import subprocess
import time
from contextlib import ExitStack
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


class RealtimeLogger:
    def __init__(self, output_root: str, session_id: str, config: Dict[str, Any], save_frames: bool = False, save_frame_every: int = 10):
        self.output_root = Path(output_root)
        self.session_id = session_id
        self.session_dir = self.output_root / session_id
        if not session_id or Path(session_id).name != session_id or session_id in {".", ".."}:
            raise ValueError("session_id must be a single directory name")
        self.session_dir.mkdir(parents=True, exist_ok=False)
        self.save_frames = bool(save_frames)
        self.save_frame_every = max(1, int(save_frame_every))
        self.frames_dir = self.session_dir / "frames"
        if self.save_frames:
            self.frames_dir.mkdir(exist_ok=True)

        (self.session_dir / "config_used.yaml").write_text(
            yaml.safe_dump(config, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        meta = {
            "session_id": session_id,
            "created_at_unix": time.time(),
            "output_files": [
                "frames.csv",
                "latency.csv",
                "events.csv",
                "results.jsonl",
                "overlay_messages.jsonl",
            ],
        }
        weights = config.get("yolo", {}).get("weights")
        meta["model_sha256"] = None
        if config.get("yolo", {}).get("enabled") and weights and Path(weights).is_file():
            with Path(weights).open("rb") as f:
                meta["model_sha256"] = hashlib.file_digest(f, "sha256").hexdigest()
        try:
            revision = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[2],
                capture_output=True, text=True, check=True, timeout=5,
            )
            meta["code_revision"] = revision.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            meta["code_revision"] = None
        (self.session_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

        self._files = ExitStack()
        try:
            for name, filename in (
                ("frames_file", "frames.csv"), ("latency_file", "latency.csv"),
                ("events_file", "events.csv"), ("results_file", "results.jsonl"),
                ("overlay_file", "overlay_messages.jsonl"),
            ):
                setattr(self, name, self._files.enter_context(
                    (self.session_dir / filename).open("x", encoding="utf-8", newline="")))
        except BaseException:
            self._files.close()
            raise

        self.frames_writer = csv.DictWriter(self.frames_file, fieldnames=[
            "frame_id", "timestamp_ms", "source", "source_path", "saved_frame",
            "source_frame_id", "source_timestamp_ms",
        ])
        self.latency_writer = csv.DictWriter(
            self.latency_file,
            fieldnames=[
                "frame_id",
                "fps",
                "queue_lag_ms",
                "latency_capture_ms",
                "latency_aruco_ms",
                "latency_roi_ms",
                "latency_filter_ms",
                "latency_overlay_ms",
                "total_latency_ms",
            ],
        )
        self.events_writer = csv.DictWriter(self.events_file, fieldnames=["timestamp_ms", "event", "from_state", "to_state", "reason", "confidence"])
        self.frames_writer.writeheader()
        self.latency_writer.writeheader()
        self.events_writer.writeheader()

    def log_frame(self, frame_packet, frame_bgr) -> str:
        saved = ""
        if self.save_frames and frame_packet.frame_id % self.save_frame_every == 0:
            import cv2
            saved = f"frames/{frame_packet.frame_id:06d}.jpg"
            ok, encoded = cv2.imencode(".jpg", frame_bgr)
            if not ok:
                raise OSError("Frame JPEG encoding failed")
            (self.session_dir / saved).write_bytes(encoded.tobytes())
        self.frames_writer.writerow(
            {
                "frame_id": frame_packet.frame_id,
                "timestamp_ms": frame_packet.timestamp_ms,
                "source": frame_packet.source,
                "source_path": frame_packet.source_path,
                "saved_frame": saved,
                "source_frame_id": frame_packet.source_frame_id,
                "source_timestamp_ms": frame_packet.source_timestamp_ms,
            }
        )
        return saved

    def log_latency(self, row: Dict[str, Any]) -> None:
        self.latency_writer.writerow(row)

    def log_result(self, row: Dict[str, Any]) -> None:
        self.results_file.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")

    def log_overlay(self, message: Dict[str, Any]) -> None:
        self.overlay_file.write(json.dumps(message, ensure_ascii=False) + "\n")

    def log_event(self, timestamp_ms: int, event: str, from_state: str = "", to_state: str = "", reason: str = "", confidence: float = 0.0) -> None:
        self.events_writer.writerow(
            {
                "timestamp_ms": timestamp_ms,
                "event": event,
                "from_state": from_state,
                "to_state": to_state,
                "reason": reason,
                "confidence": round(float(confidence), 6),
            }
        )

    def flush_transition(self) -> None:
        for f in (self.results_file, self.events_file):
            f.flush()
            os.fsync(f.fileno())

    def close(self) -> None:
        self._files.close()
