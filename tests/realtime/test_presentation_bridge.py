import json
import time
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

from .test_workspace_live_preview import profiles
from .test_display_observation_server import inputs


@pytest.mark.parametrize('state,target,phase,ok,want', [
    ('S2', 'screw_a', 'GUIDING', True, 'A'),
    ('S3', 'screw_b', 'OBSERVING', True, 'B'),
    ('S4', 'screw_c', 'OBSERVED', True, 'C'),
    ('S5', 'screw_d', 'GUIDING', True, 'D'),
    ('S1', 'lid', 'GUIDING', True, None),
    ('S6', 'complete', 'AWAITING_CONFIRMATION', True, None),
    ('S3', 'screw_a', 'GUIDING', True, None),
    ('S2', 'screw_a', 'PAUSED', True, None),
    ('S2', 'screw_a', 'GUIDING', False, None),
])
def test_stage_selects_only_the_current_valid_screw(state, target, phase, ok, want):
    from server.realtime.presentation_bridge import guided_target
    estimate = SimpleNamespace(state=state, target=target, guidance=SimpleNamespace(phase=phase))
    assert guided_target(estimate, ok) == want


def test_metric_tracking_uses_the_same_observation_without_renewing_age():
    from server.realtime.presentation_bridge import metric_marker
    observation = dict(received_at=10., analysis=dict(status="tracking", marker_ids=[0, 1, 4, 5]))
    assert metric_marker(observation, 10.10).marker_ok
    assert not metric_marker(observation, 10.151).marker_ok
    observation["analysis"]["status"] = "pose_rejected"
    assert not metric_marker(observation, 10.10).marker_ok


@pytest.mark.parametrize('reason', ['tool_not_visible', 'tool_position_unknown', 'invalid_observation', 'observation_gap'])
def test_tool_wait_keeps_current_spatial_target_but_marker_loss_does_not(reason):
    from server.realtime.presentation_bridge import guided_target
    estimate = SimpleNamespace(state='S2', target='screw_a', guidance=SimpleNamespace(phase='PAUSED', reason=reason))
    assert guided_target(estimate, True) == 'A'
    assert guided_target(estimate, False) is None


def test_bridge_updates_target_without_reusing_previous_arrow(tmp_path):
    from server.realtime.presentation_bridge import PresentationBridge
    from .test_workspace_overlay import scene_packet
    cam, board = profiles(tmp_path)
    config = tmp_path / 'presentation.json'
    config.write_text(json.dumps({'camera_profile': str(cam), 'workspace_profile': str(board)}))
    _, _, fixture = scene_packet()
    packet = SimpleNamespace(frame_id=7, frame=fixture['image'], timestamp_ms=10000)
    bridge = PresentationBridge(config, 'stage-test', root=tmp_path / 'local')
    try:
        with patch('server.realtime.presentation_bridge.analyze_frame', return_value=fixture['analysis']), \
             patch('server.realtime.presentation_bridge.time.perf_counter', return_value=10.01):
            images = []
            for target in ('A', 'B', 'C', 'D', None):
                image, status = bridge.update(packet, target_id=target)
                overlay = status['assembly_overlay']
                assert overlay['target_id'] == target
                assert overlay['selection_mode'] == 'stage'
                assert any(s['kind'] == 'arrow' for s in overlay['segments']) == (target is not None)
                images.append(image)
            assert not np.array_equal(images[0], images[1])
    finally:
        bridge.close()


def test_presentation_uses_given_frame_and_preserves_capture_age(tmp_path):
    from server.realtime.presentation_bridge import PresentationBridge
    cam, board = profiles(tmp_path)
    config = tmp_path / 'presentation.json'
    config.write_text(json.dumps({'camera_profile': str(cam), 'workspace_profile': str(board)}))
    analysis = inputs()[-1]['analysis']
    analysis['detected_corners_px'] = {'0': [[1., 1.], [2., 1.], [2., 2.], [1., 2.]]}
    frame = np.zeros((720, 1280, 3), np.uint8)
    packet = SimpleNamespace(frame_id=7, frame=frame, timestamp_ms=int(time.perf_counter()*1000)-50)
    with patch('server.realtime.presentation_bridge.analyze_frame', return_value=analysis) as analyze:
        bridge = PresentationBridge(config, 'live-test', root=tmp_path / 'local')
        try:
            image, status = bridge.update(packet)
            assert analyze.call_args.args[0] is frame
            assert not np.shares_memory(image, frame)
            assert not frame.any()
            assert status['status'] == 'tracking'
            diagnostic = status['diagnostics']
            assert diagnostic['analysis_status'] == 'tracking'
            assert diagnostic['reason_code'] == 'tracking'
            assert diagnostic['marker_count'] == len(analysis['marker_ids'])
            assert diagnostic['marker_ids'] == analysis['marker_ids']
            assert diagnostic['detected_corners_px'] == analysis['detected_corners_px']
            assert diagnostic['camera_profile_sha256'] == bridge.store.session['camera_profile_sha256']
            assert diagnostic['workspace_profile_sha256'] == bridge.store.session['workspace_profile_sha256']
            assert diagnostic['image_size'] == [1280, 720]
            assert diagnostic['source_interval_ms'] is None
            assert diagnostic['input_age_ms'] >= 50
            assert diagnostic['analysis_ms'] >= 0
            assert diagnostic['publish_age_ms'] >= diagnostic['input_age_ms']
            current = bridge.store.snapshot(time.perf_counter())
            assert current['frame_id'] == 7 and current['age_ms'] >= 50
            assert bridge.store.snapshot(time.perf_counter()+1)['status'] == 'stale'
            assert set(p.name for p in bridge.directory.iterdir()) == {'client-config.json'}
        finally:
            bridge.close()
        assert not bridge.thread.is_alive()
        assert bridge.store.snapshot(time.perf_counter())['status'] == 'camera_error'


@pytest.mark.parametrize('tracking', [True, False])
def test_console_preview_preserves_top_pixels_and_keeps_numeric_diagnostics(tmp_path, tracking):
    from server.realtime.presentation_bridge import PresentationBridge
    from .test_workspace_overlay import scene_packet
    cam, board = profiles(tmp_path)
    config = tmp_path / 'presentation.json'
    config.write_text(json.dumps({'camera_profile': str(cam), 'workspace_profile': str(board)}))
    _, _, fixture = scene_packet()
    fixture['image'][:] = (60, 80, 100)
    if not tracking:
        fixture['analysis'].update(status='pose_rejected', reason='missing markers', targets={})
    packet = SimpleNamespace(frame_id=7, frame=fixture['image'], timestamp_ms=10000)
    bridge = PresentationBridge(config, 'clean-preview-test', root=tmp_path / 'local')
    try:
        with patch('server.realtime.presentation_bridge.analyze_frame', return_value=fixture['analysis']), \
             patch('server.realtime.presentation_bridge.time.perf_counter', return_value=10.01):
            image, status = bridge.update(packet, target_id='B')
        assert image.shape == packet.frame.shape
        assert np.array_equal(image[:41], packet.frame[:41])
        assert status['diagnostics']['analysis_status'] == fixture['analysis']['status']
        assert status['diagnostics']['marker_ids'] == fixture['analysis']['marker_ids']
        assert bool(status['assembly_overlay']['segments']) == tracking
        assert np.all(packet.frame == (60, 80, 100))
    finally:
        bridge.close()


@pytest.mark.parametrize('ids,reason', [
    ([], 'lost'), ([0, 1, 2, 4], 'Visible marker geometry is degenerate for IPPE'),
])
def test_rejected_pose_clears_current_targets(tmp_path, ids, reason):
    from server.realtime.presentation_bridge import PresentationBridge
    cam, board = profiles(tmp_path)
    config = tmp_path / 'presentation.json'
    config.write_text(json.dumps({'camera_profile': str(cam), 'workspace_profile': str(board)}))
    packet = SimpleNamespace(frame_id=8, frame=np.zeros((720,1280,3),np.uint8), timestamp_ms=int(time.perf_counter()*1000))
    bridge = PresentationBridge(config, 'live-test', root=tmp_path / 'local')
    try:
        with patch('server.realtime.presentation_bridge.analyze_frame', return_value={'status':'pose_rejected','reason':reason,'marker_ids':ids, 'targets':{}}):
            _, status = bridge.update(packet)
        assert status['status'] == 'pose_rejected'
        assert 'camera_xyz_mm' not in bridge.store.snapshot(time.perf_counter())
        assert status['diagnostics']['analysis_reason'] == reason
        assert status['diagnostics']['marker_count'] == len(ids)
        assert status['diagnostics']['marker_ids'] == ids
        assert status['diagnostics']['reason_code'] == ('marker_geometry' if ids else 'pose_unavailable')
        assert bridge.store.snapshot(time.perf_counter())['reason_code'] == status['diagnostics']['reason_code']
    finally:
        bridge.close()


def test_diagnostics_keep_rejection_reason_when_observation_expires(tmp_path):
    from server.realtime.presentation_bridge import PresentationBridge
    cam, board = profiles(tmp_path)
    config = tmp_path / 'presentation.json'
    config.write_text(json.dumps({'camera_profile': str(cam), 'workspace_profile': str(board)}))
    packet = SimpleNamespace(frame_id=1, frame=np.zeros((720,1280,3),np.uint8),
                             timestamp_ms=int(time.perf_counter()*1000)-1000)
    bridge = PresentationBridge(config, 'diagnostic-test', root=tmp_path / 'local')
    try:
        with patch('server.realtime.presentation_bridge.analyze_frame', return_value={
            'status':'pose_rejected', 'reason':'need four markers', 'marker_ids':[], 'targets':{}}):
            _, status = bridge.update(packet)
            assert status['status'] == 'stale'
            assert status['diagnostics']['analysis_reason'] == 'need four markers'
            packet.timestamp_ms += 100
            packet.frame_id += 1
            _, status = bridge.update(packet)
            assert status['diagnostics']['source_interval_ms'] == 100
            assert status['diagnostics']['publish_age_ms'] >= 900
            assert 'camera_xyz_mm' not in bridge.store.snapshot(time.perf_counter())
        assert set(p.name for p in bridge.directory.iterdir()) == {'client-config.json'}
    finally:
        bridge.close()


def test_bridge_preserves_source_counter_without_coarse_clock_conversion(tmp_path):
    from server.realtime.presentation_bridge import PresentationBridge
    cam, board = profiles(tmp_path)
    config = tmp_path / 'presentation.json'
    config.write_text(json.dumps({'camera_profile': str(cam), 'workspace_profile': str(board)}))
    bridge = PresentationBridge(config, 'clock-test', root=tmp_path / 'local')
    packet = SimpleNamespace(frame_id=1, frame=np.zeros((720, 1280, 3), np.uint8), timestamp_ms=100000)
    try:
        with patch('server.realtime.presentation_bridge.analyze_frame', return_value=inputs()[-1]['analysis']), \
             patch('server.realtime.presentation_bridge.time.perf_counter', return_value=100.146), \
             patch('server.realtime.presentation_bridge.time.monotonic', return_value=42.156):
            _, status = bridge.update(packet)
        assert bridge.store.packet['received_at'] == 100.
        assert status['status'] == 'tracking' and status['age_ms'] == pytest.approx(146.)
        assert bridge.store.snapshot(100.146)['status'] == 'tracking'
        assert bridge.store.snapshot(100.151)['status'] == 'stale'
    finally:
        bridge.close()
