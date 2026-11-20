from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest

from server.realtime.schemas import FramePacket
from server.realtime.yolo_realtime import YoloRealtimeResult


def inputs(frame=10, reason="ok", marker_ok=True):
    packet = FramePacket(frame, 2000, "fixture", np.full((720, 1280, 3), 90, np.uint8))
    marker = SimpleNamespace(marker_ok=marker_ok, marker_count=6 if marker_ok else 3,
                             marker_status="OK" if marker_ok else "LOST",
                             homography=np.eye(3), warp_quality=1.0)
    result = YoloRealtimeResult(True, available=True, frame_id=8, timestamp_ms=1800,
        reason=reason, source_marker_ok=True,
        features={"driver_visible": 1., "driver_count": 1., "tool_tip_source": 2.,
                  "tool_tip_x": 440., "tool_tip_y": 460., "tool_score_a": .8},
        detections=[dict(x1=200., y1=200., x2=300., y2=400.,
                         **{"class": "driver", "confidence": .9})])
    estimate = SimpleNamespace(state="S2", target="screw_a", next_action="Tool at screw A",
        guidance=SimpleNamespace(phase="OBSERVING", reason=""))
    gate = SimpleNamespace(started_at=1600, release_at=None, armed=False,
                           timing=SimpleNamespace(engage_ms=800, release_ms=400))
    return packet, marker, result, estimate, gate


def test_delayed_detection_uses_its_source_image_and_homography_without_mutation():
    from server.realtime.tool_diagnostic_preview import ToolDiagnosticPreview
    preview = ToolDiagnosticPreview({"a": (420., 440.)})
    source = np.full((720, 1280, 3), 30, np.uint8)
    h = np.array([[2., 0., 20.], [0., 2., 40.], [0., 0., 1.]])
    preview.remember(FramePacket(8, 1800, "fixture", source), h)
    source[:] = 200
    h[:] = 0
    args = inputs()
    before = args[0].frame.copy()
    features = deepcopy(args[2].features)
    image, info = preview.render(*args)
    assert info["observation_frame"] == 8
    assert info["targets"]["a"] == [200., 200.]
    assert info["tip"] == [210., 210.]
    assert info["engage_ms"] == 200
    assert info["detections"] == 1
    assert image.shape == (544, 1280, 3)
    assert image[400, 500].tolist() == [90, 90, 90]
    assert image[400, 1140].tolist() == [30, 30, 30]
    assert np.any((image[:, :, 1] > 180) & (image[:, :, 0] < 80))
    assert np.array_equal(args[0].frame, before)
    assert args[2].features == features
    assert args[4].started_at == 1600


@pytest.mark.parametrize("reason,marker_ok", [("stale", True), ("ok", False),
    ("before_tracking_recovery", True), ("warming_up", True)])
def test_invalid_evidence_never_leaves_old_boxes_or_tip_visible(reason, marker_ok):
    from server.realtime.tool_diagnostic_preview import ToolDiagnosticPreview
    preview = ToolDiagnosticPreview({"a": (420., 440.)})
    args = inputs(reason=reason, marker_ok=marker_ok)
    preview.remember(FramePacket(8, 1800, "fixture", np.ones((720, 1280, 3), np.uint8)), np.eye(3))
    image, info = preview.render(*args)
    assert info["observation_frame"] is None
    assert info["targets"] == {} and info["tip"] is None
    assert info["detections"] == 0
    assert not image[300:400, 800:1200].any()


def test_evicted_source_is_not_replaced_with_current_frame():
    from server.realtime.tool_diagnostic_preview import ToolDiagnosticPreview
    preview = ToolDiagnosticPreview({"a": (420., 440.)}, buffer_size=2)
    for i in (8, 9, 10):
        preview.remember(FramePacket(i, 1000+i, "fixture", np.zeros((720, 1280, 3), np.uint8)), np.eye(3))
    _, info = preview.render(*inputs())
    assert info["observation_frame"] is None
    assert info["preview_reason"] == "source_frame_missing"


def test_singular_projection_and_invalid_tip_do_not_crash_preview():
    from server.realtime.tool_diagnostic_preview import ToolDiagnosticPreview
    preview = ToolDiagnosticPreview({"a": (420., 440.)})
    args = inputs()
    args[2].features["tool_tip_x"] = float("nan")
    preview.remember(FramePacket(8, 1800, "fixture", args[0].frame), np.zeros((3, 3)))
    _, info = preview.render(*args)
    assert info["targets"] == {} and info["tip"] is None
    assert info["detections"] == 1


@pytest.mark.parametrize("saved_in_config,saved_on_cli", [(True, False), (False, True)])
def test_no_image_saving_diagnostic_rejects_capture_saving(saved_in_config, saved_on_cli):
    from server.realtime.run_realtime_server import build_effective_config
    config = {"logging": {"save_frames": saved_in_config}}
    with pytest.raises(ValueError, match="diagnostic.*save_frames"):
        build_effective_config(config, SimpleNamespace(diagnostic_preview=True, save_frames=saved_on_cli))
