from __future__ import annotations

import csv
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional

import cv2
import numpy as np

from server.realtime.schemas import FramePacket

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


@dataclass
class FrameSourceConfig:
    source_type: str
    camera_index: int = 0
    camera_backend: str = "dshow"
    session_path: str = ""
    width: int = 1280
    height: int = 720
    replay_fps: float = 5.0
    dummy_fps: float = 10.0


class BaseFrameSource:
    def __iter__(self) -> Iterator[FramePacket]:
        raise NotImplementedError

    def close(self) -> None:
        return


class DummyFrameSource(BaseFrameSource):
    def __init__(self, config: FrameSourceConfig):
        self.config = config
        self.interval = 1.0 / max(1e-6, float(config.dummy_fps))

    def __iter__(self) -> Iterator[FramePacket]:
        frame_id = 0
        while True:
            frame_id += 1
            started = time.perf_counter()
            frame = np.full((self.config.height, self.config.width, 3), 245, dtype=np.uint8)
            x = 80 + (frame_id * 7) % max(1, self.config.width - 220)
            y = 160 + (frame_id * 3) % max(1, self.config.height - 260)
            cv2.rectangle(frame, (x, y), (x + 180, y + 120), (70, 130, 200), 3)
            cv2.circle(frame, (x + 90, y + 60), 18, (60, 180, 90), -1)
            cv2.putText(frame, "AR PSR realtime harness", (40, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (30, 30, 30), 2)
            cv2.putText(frame, f"dummy frame {frame_id}", (40, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (80, 80, 80), 2)
            yield FramePacket(
                frame_id=frame_id,
                timestamp_ms=int(time.perf_counter() * 1000),
                source="dummy",
                frame=frame,
            )
            elapsed = time.perf_counter() - started
            if elapsed < self.interval:
                time.sleep(self.interval - elapsed)


class CameraFrameSource(BaseFrameSource):
    def __init__(self, config: FrameSourceConfig):
        self.config = config
        backend_map = {
            "any": cv2.CAP_ANY,
            "dshow": cv2.CAP_DSHOW,
            "msmf": cv2.CAP_MSMF,
        }
        backend = backend_map.get(config.camera_backend.lower(), cv2.CAP_DSHOW)
        self.cap = cv2.VideoCapture(config.camera_index, backend)
        if config.width > 0:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.width)
        if config.height > 0:
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.height)
        if not self.cap.isOpened():
            raise RuntimeError(f"Failed to open camera index {config.camera_index} with backend {config.camera_backend}")

    def __iter__(self) -> Iterator[FramePacket]:
        frame_id = 0
        while True:
            ok, frame = self.cap.read()
            if not ok or frame is None:
                time.sleep(0.02)
                continue
            frame_id += 1
            yield FramePacket(
                frame_id=frame_id,
                timestamp_ms=int(time.perf_counter() * 1000),
                source="camera",
                frame=frame,
            )

    def close(self) -> None:
        self.cap.release()


class SessionFrameSource(BaseFrameSource):
    def __init__(self, config: FrameSourceConfig):
        self.config = config
        self.session_path = Path(config.session_path)
        if not self.session_path.exists():
            raise FileNotFoundError(f"session path not found: {self.session_path}")
        self.items = self._collect_items()
        self.interval = 1.0 / max(1e-6, float(config.replay_fps))

    def _collect_items(self) -> List[Path]:
        frames_csv = self.session_path / "frames.csv"
        if frames_csv.exists():
            paths: List[Path] = []
            with frames_csv.open("r", encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    rel = row.get("image_path") or row.get("path") or ""
                    frame_id = row.get("frame_id") or ""
                    if rel:
                        paths.append((self.session_path / rel).resolve())
                    elif frame_id:
                        paths.append((self.session_path / "frames" / f"{int(frame_id):06d}.jpg").resolve())
            if paths:
                return paths
        root = self.session_path / "frames" if (self.session_path / "frames").exists() else self.session_path
        return sorted(p for p in root.rglob("*") if p.suffix.lower() in IMAGE_EXTS)

    def __iter__(self) -> Iterator[FramePacket]:
        frame_id = 0
        while True:
            for path in self.items:
                started = time.perf_counter()
                frame = cv2.imread(str(path))
                if frame is None:
                    continue
                frame_id += 1
                yield FramePacket(
                    frame_id=frame_id,
                    timestamp_ms=int(time.perf_counter() * 1000),
                    source="session",
                    frame=frame,
                    source_path=str(path),
                )
                elapsed = time.perf_counter() - started
                if elapsed < self.interval:
                    time.sleep(self.interval - elapsed)


def create_frame_source(config: FrameSourceConfig) -> BaseFrameSource:
    source_type = config.source_type.lower()
    if source_type == "camera":
        return CameraFrameSource(config)
    if source_type == "session":
        return SessionFrameSource(config)
    if source_type == "dummy":
        return DummyFrameSource(config)
    raise ValueError(f"unknown source type: {config.source_type}")
