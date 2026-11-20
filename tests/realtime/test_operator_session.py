import json
import time
import urllib.error
import urllib.request
from argparse import Namespace

import numpy as np
import pytest

from server.realtime.operator_session import OperatorSession
from server.realtime.overlay_http_server import OverlayHttpServer
from server.realtime.run_realtime_server import build_effective_config


def test_operator_mode_disables_legacy_recognition_without_changing_base():
    base = {"source": {"type": "dummy"}, "aruco": {"enabled": True},
            "roi": {"enabled": True}, "yolo": {"enabled": True}, "logging": {"save_frames": True}}
    result = build_effective_config(base, Namespace(guidance_mode="operator"))
    assert result["guidance_mode"] == "operator"
    assert all(not result[key]["enabled"] for key in ("aruco", "roi", "yolo"))
    assert base["yolo"]["enabled"]
    assert result["logging"]["save_frames"] is False


def test_live_operator_mode_requires_current_metric_profiles_before_capture():
    with pytest.raises(ValueError, match="presentation"):
        build_effective_config({"source": {"type": "camera"}}, Namespace(guidance_mode="operator"))


def test_confirmation_advances_on_next_frame_once_and_finishes_explicitly():
    session = OperatorSession("test")
    for revision in range(7):
        before = session.update(True)
        assert before.state == "S" + str(min(revision, 6))
        session.request("test", revision)
        with pytest.raises(ValueError):
            session.request("test", revision)
        after = session.update(True)
        assert after.transition_event == "operator_confirmation"
        assert session.metadata()["revision"] == revision + 1
        assert session.update(True).transition_event == ""
    assert after.guidance.phase == "COMPLETED"
    assert after.guidance.reason == "operator_confirmation"
    with pytest.raises(ValueError):
        session.request("test", 7)


def test_old_session_revision_and_lost_tracking_never_advance():
    session = OperatorSession("new")
    for sid, revision in [("old", 0), ("new", -1), ("new", True), ("new", 1)]:
        with pytest.raises(ValueError):
            session.request(sid, revision)
    session.request("new", 0)
    assert session.update(False).state == "S0"
    assert session.metadata()["last_result"] == "rejected_tracking"
    assert session.update(True).state == "S0"


def test_http_confirm_is_local_fresh_and_revision_checked():
    control = OperatorSession("test")
    server = OverlayHttpServer("127.0.0.1", 0, "web_overlay", operator=control)
    server.start()
    try:
        state = dict(session_id="test", frame_id=1, timestamp_ms=int(time.perf_counter()*1000),
                     system_status="RUNNING", marker_status="OK")
        server.update(state, np.zeros((8, 8, 3), np.uint8))
        def post(origin=None, revision=0):
            request = urllib.request.Request(server.url + "/operator/confirm",
                json.dumps(dict(session_id="test", revision=revision)).encode(),
                headers={"Content-Type": "application/json", "X-AR-Operator": "confirm",
                         "Origin": origin or server.url})
            try:
                with urllib.request.urlopen(request, timeout=2) as response:
                    return response.status
            except urllib.error.HTTPError as error:
                return error.code
        assert post("https://example.com") == 403
        assert post() == 202
        assert post() == 409
        control.update(True)
        state["timestamp_ms"] -= 1000
        server.update(state, np.zeros((8, 8, 3), np.uint8))
        assert post(revision=1) == 409
    finally:
        server.stop()


def test_operator_server_refuses_non_loopback_binding():
    with pytest.raises(ValueError):
        OverlayHttpServer("0.0.0.0", 0, "web_overlay", operator=OperatorSession("test"))


@pytest.mark.parametrize("stop_early", [False, True])
def test_runtime_uses_one_metric_observation_for_stage_and_overlay(monkeypatch, tmp_path, stop_early):
    from contextlib import ExitStack
    from server.realtime import frame_source, operator_session, workspace_live_preview
    from server.realtime.run_realtime_server import run_session
    from server.realtime.schemas import FramePacket
    from .test_workspace_live_preview import profiles
    from .test_workspace_projection import models

    cam, board = profiles(tmp_path)
    presentation = tmp_path / "presentation.json"
    presentation.write_text(json.dumps(dict(camera_profile=str(cam), workspace_profile=str(board))))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    control = OperatorSession("placeholder")
    def create_control(session_id):
        control.session_id = session_id
        return control
    monkeypatch.setattr(operator_session, "OperatorSession", create_control)
    detections = models()[2]
    observed = []
    def detect(*_args, **_kwargs):
        observed.append(1)
        return detections, [], np.array(list(detections)).reshape(-1, 1)
    monkeypatch.setattr(workspace_live_preview, "detect_markers", detect)
    class Frames:
        closed = False
        def __iter__(self):
            for i in range(8):
                if i:
                    control.request(control.session_id, i - 1)
                yield FramePacket(i + 1, int(time.perf_counter() * 1000), "synthetic-camera",
                                  np.zeros((720, 1280, 3), np.uint8))
        def close(self):
            self.closed = True
    frames = Frames()
    monkeypatch.setattr(frame_source, "create_frame_source", lambda _config: frames)
    args = Namespace(guidance_mode="operator", presentation_config=presentation, camera_index=None,
                     camera_backend=None, host=None, port=0, save_frames=False, max_frames=8,
                     diagnostic_preview=False)
    if stop_early:
        args.stop_file = tmp_path / "stop"
        args.stop_file.touch()
    config = build_effective_config(dict(source=dict(type="camera"),
        logging=dict(output_root=str(tmp_path / "logs"))), args)
    with ExitStack() as resources:
        assert run_session(config, args, resources) == 0
    count = 1 if stop_early else 8
    assert frames.closed and len(observed) == count
    messages = next((tmp_path / "logs").glob("*/overlay_messages.jsonl"))
    rows = [json.loads(line) for line in messages.read_text().splitlines()]
    assert [r["extra"]["presentation_target"] for r in rows] == [None, None, "A", "B", "C", "D", None, None][:count]
    assert all(r["marker_status"] == "OK" for r in rows)
    assert rows[-1]["guidance"]["phase"] == ("GUIDING" if stop_early else "COMPLETED")
    assert all(r["extra"]["yolo_reason"] == "disabled" for r in rows)
