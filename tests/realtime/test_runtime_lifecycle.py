import threading
from pathlib import Path

import pytest


def test_candidate_probe_uses_background_polling_only_for_read_only_candidates():
    # Wiring guard; the actual transport/parser is exercised by the Unity smoke test.
    source = (Path(__file__).resolve().parents[2]
              / 'client_unity/Assets/Scripts/StereoAlignmentProbe.cs').read_text(encoding='utf-8')
    compact = ''.join(source.split())
    assert 'recorder.Initialize(observationConfig,candidate,backgroundPolling:candidate!=null);' in compact
    assert 'recorder.Feedback.Diagnostic(now)' in source
    assert 'recorder.LastNetworkMs' in source


def test_four_corner_probe_is_opt_in_and_keeps_per_eye_clipping():
    root = Path(__file__).resolve().parents[2]
    source = (root / 'client_unity/Assets/Scripts/StereoAlignmentProbe.cs').read_text(encoding='utf-8')
    launcher = (root / 'scripts/run_beast_unity.ps1').read_text(encoding='utf-8')
    assert '--candidate-corners' in source and '--candidate-corners' in launcher
    assert 'TryProjectCorners' in source and 'CandidateProjection.LidPerimeter' in source
    assert 'GUI.BeginGroup' in source and 'GUI.EndGroup' in source
    assert '[switch]$CandidateCorners' in launcher


def test_overlay_can_close_after_bind_but_before_thread_start():
    from server.realtime.overlay_http_server import OverlayHttpServer
    server = OverlayHttpServer("127.0.0.1", 0, ".")
    stopper = threading.Thread(target=server.stop, daemon=True)
    stopper.start()
    stopper.join(1)
    stopped = not stopper.is_alive()
    if not stopped:
        server.start()
        stopper.join(2)
    assert stopped, "cleanup must not wait forever when startup has not called serve_forever"


def test_unreadable_recorded_image_is_not_silently_skipped(tmp_path):
    pytest.importorskip("cv2", exc_type=ImportError)
    from server.realtime.frame_source import FrameSourceConfig, SessionFrameSource
    (tmp_path / "broken.jpg").write_bytes(b"not an image")
    source = SessionFrameSource(FrameSourceConfig("session", session_path=str(tmp_path)))
    with pytest.raises(ValueError, match="Unreadable"):
        list(source)


@pytest.mark.parametrize('presentation,cpu_count,expected', [
    (True, 16, 4), (True, 2, 2), (True, 1, 1), (True, None, 1),
    (False, 16, 1),
])
def test_presentation_compute_threads_applied_after_yolo_before_capture(
        monkeypatch, tmp_path, presentation, cpu_count, expected):
    from contextlib import ExitStack
    from types import SimpleNamespace
    import os
    import cv2
    from server.realtime import frame_source, presentation_bridge, yolo_realtime
    from server.realtime.run_realtime_server import run_session

    original = cv2.getNumThreads()
    observed = []

    def initialize_yolo(**_kwargs):
        # Ultralytics import changes this process-wide setting, even for ArUco.
        cv2.setNumThreads(0)
        return SimpleNamespace(available=True, close=lambda: None)

    def before_capture(_config):
        observed.append(cv2.getNumThreads())
        raise RuntimeError('test stopped before camera capture')

    monkeypatch.setattr(os, 'cpu_count', lambda: cpu_count)
    monkeypatch.setattr(yolo_realtime, 'RealtimeYoloAnalyzer', initialize_yolo)
    monkeypatch.setattr(frame_source, 'create_frame_source', before_capture)
    monkeypatch.setattr(presentation_bridge, 'PresentationBridge',
        lambda *_args: SimpleNamespace(config_path=tmp_path/'client.json', close=lambda: None))
    config = {'source': {'type': 'camera'}, 'logging': {'output_root': str(tmp_path/'logs')}}
    args = SimpleNamespace(camera_index=None, camera_backend=None, host=None, port=None,
        presentation_config=tmp_path/'presentation.json' if presentation else None,
        save_frames=False, diagnostic_preview=False)
    try:
        with pytest.raises(RuntimeError, match='test stopped before camera capture'):
            with ExitStack() as resources:
                run_session(config, args, resources)
        assert observed == [expected]
    finally:
        cv2.setNumThreads(original)
