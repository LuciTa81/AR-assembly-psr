from pathlib import Path
from unittest.mock import patch
import json
import urllib.request

import numpy as np
import pytest

from server.realtime.overlay_http_server import OverlayHttpServer, SharedOverlayState


def test_frame_age_increases_without_a_new_frame():
    shared = SharedOverlayState()
    shared.update({"frame_id": 7, "timestamp_ms": 1000}, np.zeros((8, 8, 3), np.uint8))
    with patch("time.perf_counter", return_value=1.125):
        first = shared.snapshot_state()
    with patch("time.perf_counter", return_value=2.5):
        second = shared.snapshot_state()
    assert first["frame_age_ms"] == 125
    assert second["frame_age_ms"] == 1500
    assert first["frame_id"] == second["frame_id"] == 7


def test_startup_without_capture_time_has_no_valid_age():
    assert SharedOverlayState().snapshot_state()["frame_age_ms"] == -1


def test_jpeg_headers_describe_the_image_and_keep_aging_without_capture():
    server = OverlayHttpServer("127.0.0.1", 0, str(Path("web_overlay")))
    server.update(
        {"session_id": "photo-session", "source": "camera", "frame_id": 21, "timestamp_ms": 1000},
        np.zeros((8, 8, 3), np.uint8),
    )
    server.start()
    try:
        for now, age in [(1.2, "200"), (2.5, "1500")]:
            with patch("time.perf_counter", return_value=now):
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{server.server.server_port}/frame.jpg", timeout=2,
                ) as response:
                    assert response.headers["X-AR-Frame-Id"] == "21"
                    assert response.headers["X-AR-Session"] == "photo-session"
                    assert response.headers["X-AR-Source"] == "camera"
                    assert response.headers["X-AR-Timestamp-Ms"] == "1000"
                    assert response.headers["X-AR-Frame-Age-Ms"] == age
                    assert response.headers["Cache-Control"] == "no-store"
                    assert response.read().startswith(b"\xff\xd8")
    finally:
        server.stop()


def test_failed_jpeg_encoding_never_leaves_previous_image_as_current():
    shared = SharedOverlayState()
    shared.update({"frame_id": 1, "timestamp_ms": 1000}, np.zeros((8, 8, 3), np.uint8))
    assert shared.snapshot_jpeg() is not None
    with patch("cv2.imencode", return_value=(False, None)):
        shared.update({"frame_id": 2, "timestamp_ms": 1100}, np.zeros((8, 8, 3), np.uint8))
    assert shared.snapshot_jpeg() is None


def test_http_snapshot_reports_age_but_keeps_state_contract():
    server = OverlayHttpServer("127.0.0.1", 0, str(Path("web_overlay")))
    server.update(
        {"schema_version": "realtime_v1", "frame_id": 8, "timestamp_ms": 1000,
         "current_state": "S2", "next_action": "Fasten screw A"},
        np.zeros((8, 8, 3), np.uint8),
    )
    server.start()
    try:
        with patch("time.perf_counter", return_value=1.2):
            with urllib.request.urlopen(
                f"http://127.0.0.1:{server.server.server_port}/state.json", timeout=2,
            ) as response:
                body = json.load(response)
                assert response.headers["Cache-Control"] == "no-store"
        assert body["frame_age_ms"] == 200
        assert body["current_state"] == "S2"
        assert body["next_action"] == "Fasten screw A"
    finally:
        server.stop()


def spatial_snapshot():
    fixture = Path(__file__).resolve().parents[1] / "fixtures/spatial_guidance_v1.json"
    return json.loads(fixture.read_text(encoding="utf-8"))["expected"]


def test_spatial_pose_age_is_independent_of_state_age_and_expires_on_repeat_reads():
    shared = SharedOverlayState()
    message = spatial_snapshot()
    shared.update(message, np.zeros((8, 8, 3), np.uint8))
    with patch("time.perf_counter", return_value=1.125):
        first = shared.snapshot_state()
    assert first["frame_age_ms"] == 105
    assert first["spatial"]["pose_age_ms"] == 125
    assert first["spatial"]["target_visible"]
    # State advances; the same camera observation must not get a new lifetime.
    message["frame_id"] += 1
    message["timestamp_ms"] = 1150
    shared.update(message, np.zeros((8, 8, 3), np.uint8))
    with patch("time.perf_counter", return_value=1.151):
        second = shared.snapshot_state()
    assert second["frame_age_ms"] == 1
    assert second["spatial"]["pose_frame_id"] == 7
    assert second["spatial"]["pose_age_ms"] == 151
    assert second["spatial"]["reason"] == "stale_pose"
    assert not second["spatial"]["target_visible"]
    assert second["spatial"]["left_pixel"] is None and second["spatial"]["right_pixel"] is None
    assert first["spatial"]["target_visible"]


def test_nested_coordinates_cannot_be_mutated_by_producer_or_http_reader():
    shared = SharedOverlayState()
    message = spatial_snapshot()
    shared.update(message, np.zeros((8, 8, 3), np.uint8))
    message["spatial"]["left_pixel"][0] = -999
    with patch("time.perf_counter", return_value=1.025):
        first = shared.snapshot_state()
        assert first["spatial"]["left_pixel"][0] == 1008
        first["spatial"]["right_pixel"][0] = -999
        assert shared.snapshot_state()["spatial"]["right_pixel"][0] == 908.8


@pytest.mark.parametrize("timestamp", [None, -1, True, 2000])
def test_unknown_or_future_pose_time_hides_spatial_without_changing_step(timestamp):
    shared = SharedOverlayState()
    message = spatial_snapshot()
    message["spatial"]["pose_timestamp_ms"] = timestamp
    shared.update(message, np.zeros((8, 8, 3), np.uint8))
    with patch("time.perf_counter", return_value=1.025):
        result = shared.snapshot_state()
    assert not result["spatial"]["target_visible"]
    assert result["spatial"]["pose_age_ms"] == -1
    assert result["spatial"]["reason"] == "invalid_pose"
    assert result["spatial"]["left_pixel"] is None and result["spatial"]["right_pixel"] is None
    assert result["current_state"] == "S2"


def test_optional_spatial_payload_round_trips_over_existing_http_endpoint():
    server = OverlayHttpServer("127.0.0.1", 0, str(Path("web_overlay")))
    server.update(spatial_snapshot(), np.zeros((8, 8, 3), np.uint8))
    server.start()
    try:
        with patch("time.perf_counter", return_value=1.025):
            with urllib.request.urlopen(
                f"http://127.0.0.1:{server.server.server_port}/state.json", timeout=2,
            ) as response:
                body = json.load(response)
        assert body == spatial_snapshot()
        assert body["spatial"]["calibration_status"] == "synthetic"
        assert not body["spatial"]["display_alignment_verified"]
    finally:
        server.stop()
