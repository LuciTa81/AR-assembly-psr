from __future__ import annotations

import numpy as np

from server.realtime import probe_cameras


class FakeCapture:
    def __init__(self, index: int, backend: int, opened: bool = True) -> None:
        self.index = index
        self.backend = backend
        self.opened = opened
        self.released = False
        self.properties = {
            probe_cameras.cv2.CAP_PROP_FRAME_WIDTH: 640.0,
            probe_cameras.cv2.CAP_PROP_FRAME_HEIGHT: 480.0,
            probe_cameras.cv2.CAP_PROP_FPS: 30.0,
        }

    def isOpened(self) -> bool:
        return self.opened

    def set(self, property_id: int, value: float) -> bool:
        self.properties[property_id] = value
        return True

    def get(self, property_id: int) -> float:
        return self.properties.get(property_id, 0.0)

    def read(self):
        if not self.opened:
            return False, None
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        return True, frame

    def getBackendName(self) -> str:
        return "FAKE"

    def release(self) -> None:
        self.released = True


def test_probe_mode_reports_requested_and_actual_mode(monkeypatch):
    fake = FakeCapture(index=1, backend=700)
    monkeypatch.setattr(probe_cameras.cv2, "VideoCapture", lambda index, backend: fake)

    row, frame = probe_cameras.probe_mode(
        index=1,
        backend=700,
        width=1280,
        height=720,
        requested_fps=30.0,
        sample_seconds=0.05,
    )

    assert row["index"] == 1
    assert row["requested_width"] == 1280
    assert row["requested_height"] == 720
    assert row["requested_fps"] == 30.0
    assert row["actual_width"] == 1280
    assert row["actual_height"] == 720
    assert row["frames_read"] > 0
    assert row["measured_fps"] > 0
    assert frame is not None


def test_probe_mode_closes_failed_capture(monkeypatch):
    fake = FakeCapture(index=7, backend=700, opened=False)
    monkeypatch.setattr(probe_cameras.cv2, "VideoCapture", lambda index, backend: fake)

    row, frame = probe_cameras.probe_mode(7, 700, 640, 480, 30.0, 0.01)

    assert row["opened"] is False
    assert row["read_ok"] is False
    assert frame is None
    assert fake.released is True


def test_probe_mode_returns_last_successful_frame_after_a_read_failure(monkeypatch):
    fake = FakeCapture(index=1, backend=700)
    successful_frame = np.ones((720, 1280, 3), dtype=np.uint8)
    responses = iter([(True, successful_frame), (False, None)])
    monkeypatch.setattr(probe_cameras.cv2, "VideoCapture", lambda index, backend: fake)
    monkeypatch.setattr(fake, "read", lambda: next(responses, (False, None)))

    row, frame = probe_cameras.probe_mode(1, 700, 1280, 720, 30.0, 0.01)

    assert row["read_ok"] is True
    assert row["read_failures"] > 0
    assert frame is successful_frame
