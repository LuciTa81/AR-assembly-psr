from argparse import Namespace

import cv2
import numpy as np
import pytest

from server.realtime.run_realtime_server import build_effective_config
from .test_workspace_projection import models


@pytest.mark.parametrize("shift", [0., 100.])
def test_tool_plane_uses_seated_height_distortion_and_current_pose(shift):
    from server.realtime.yolo_realtime import MetricToolPlane, transform_points
    camera, workspace, _, rvec, tvec = models()
    tvec = tvec + np.array([shift, 20., shift])
    plane = MetricToolPlane(camera, workspace)
    current = dict(received_at=1., analysis=dict(status="tracking", rvec=rvec.ravel().tolist(),
                                                tvec_mm=tvec.ravel().tolist()))
    matrix = plane.homography(current, 1.03)
    xyz = np.array([workspace.targets[name] for name in "ABCD"])
    pixels = cv2.projectPoints(xyz, rvec, tvec, camera.matrix, camera.distortion)[0].reshape(-1, 2)
    actual = transform_points(matrix, pixels, camera)
    expected = np.array([plane.centers[name] for name in "abcd"])
    assert np.allclose(actual, expected, atol=.01)
    assert np.linalg.norm(actual[0] - actual[1]) == pytest.approx(110., abs=.01)
    assert plane.homography(current, 1.151) is None
    assert plane.homography(current, .99) is None
    current["analysis"]["status"] = "rejected"
    assert plane.homography(current, 1.03) is None


def test_tool_plane_rejects_mixed_heights_and_nonfinite_pose():
    from server.realtime.yolo_realtime import MetricToolPlane
    camera, workspace, _, rvec, tvec = models()
    plane = MetricToolPlane(camera, workspace)
    rvec[0] = np.nan
    assert plane.homography(dict(received_at=1., analysis=dict(status="tracking",
        rvec=rvec.ravel().tolist(), tvec_mm=tvec.tolist())), 1.03) is None
    workspace.targets["D"][2] += 5
    with pytest.raises(ValueError, match="height"):
        MetricToolPlane(camera, workspace)


@pytest.mark.parametrize('with_handle', [True, False])
def test_metric_tip_is_image_endpoint_not_reboxed_after_perspective_warp(with_handle):
    from types import SimpleNamespace
    from server.realtime.yolo_realtime import MetricToolPlane, RealtimeYoloAnalyzer
    camera, workspace, _, rvec, tvec = models()
    plane = MetricToolPlane(camera, workspace)
    matrix = plane.homography(dict(received_at=1., analysis=dict(status='tracking',
        rvec=rvec.ravel().tolist(), tvec_mm=tvec.tolist())), 1.01)
    x, y = cv2.projectPoints(workspace.targets['A'], rvec, tvec, camera.matrix,
                             camera.distortion)[0].reshape(2)
    def box(xyxy, cls):
        return SimpleNamespace(cls=np.array([cls]), conf=np.array([.95]), xyxy=np.array([xyxy]))
    prediction = SimpleNamespace(names={0:'driver', 1:'handle'}, boxes=[
        box([x-7,y-120,x+7,y],0), box([x-9,y-120,x+9,y-95],1)])
    if not with_handle:
        prediction.boxes.pop()
    analyzer = RealtimeYoloAnalyzer(False,'','',metric_plane=plane)
    analyzer.centers = plane.centers
    analyzer.model = SimpleNamespace(predict=lambda **_kwargs: [prediction])
    result = analyzer._process(1, np.zeros((720,1280,3),np.uint8), matrix)
    assert result.features['tool_tip_source'] == (2 if with_handle else 1)
    assert result.features['tool_dist_a'] < .05


@pytest.mark.parametrize('metric,inside', [(True,0), (True,1), (True,2), (False,1)])
def test_metric_driver_count_and_selection_ignore_only_outside_workspace(metric, inside):
    from types import SimpleNamespace
    from server.realtime.yolo_realtime import (MetricToolPlane, RealtimeYoloAnalyzer,
        transform_points, make_bbox_points, polygon_intersects_workspace)
    camera, workspace, _, rvec, tvec = models()
    plane = MetricToolPlane(camera, workspace)
    matrix = plane.homography(dict(received_at=1., analysis=dict(status='tracking',
        rvec=rvec.ravel().tolist(), tvec_mm=tvec.tolist())), 1.)
    outside = dict(x1=20., y1=50., x2=45., y2=200.)
    poly = transform_points(matrix, make_bbox_points(outside), camera)
    assert not polygon_intersects_workspace(poly, plane.width_mm, plane.depth_mm)
    def box(xyxy, confidence):
        return SimpleNamespace(cls=np.array([0]), conf=np.array([confidence]), xyxy=np.array([xyxy]))
    boxes = [box(list(outside.values()), .99)]
    for name in 'AB'[:inside]:
        x,y = cv2.projectPoints(workspace.targets[name],rvec,tvec,camera.matrix,camera.distortion)[0].reshape(2)
        boxes.append(box([x-5,y-70,x+5,y], .90))
    analyzer = RealtimeYoloAnalyzer(False,'','',metric_plane=plane if metric else None)
    analyzer.centers = plane.centers
    analyzer.model = SimpleNamespace(predict=lambda **_: [SimpleNamespace(names={0:'driver'}, boxes=boxes)])
    result = analyzer._process(1,np.zeros((720,1280,3),np.uint8),matrix)
    assert len(result.detections) == inside+1  # Full detections remain available for diagnosis.
    assert result.features['driver_count'] == (inside if metric else inside+1)
    if metric:
        assert result.features['driver_count_raw'] == inside+1
        assert result.features['driver_visible'] == bool(inside)
        if inside == 1:
            assert result.features['tool_dist_a'] < .05
        if inside == 0:
            assert result.features['tool_tip_x'] == -1


@pytest.mark.parametrize('metric', [True, False])
def test_metric_duplicate_shaft_boxes_do_not_count_as_two_tools(metric):
    from types import SimpleNamespace
    from server.realtime.yolo_realtime import MetricToolPlane, RealtimeYoloAnalyzer
    camera, workspace, _, rvec, tvec = models()
    plane = MetricToolPlane(camera, workspace)
    h = plane.homography(dict(received_at=1.,analysis=dict(status='tracking',
        rvec=rvec.ravel().tolist(),tvec_mm=tvec.tolist())),1.)
    x,y = cv2.projectPoints(workspace.targets['D'],rvec,tvec,camera.matrix,camera.distortion)[0].reshape(2)
    def box(coords, confidence):
        return SimpleNamespace(cls=np.array([0]),conf=np.array([confidence]),xyxy=np.array([coords]))
    boxes = [box([x-10,y-150,x+10,y],.8), box([x-7,y-148,x+13,y],.6)]
    analyzer = RealtimeYoloAnalyzer(False,'','',metric_plane=plane if metric else None)
    analyzer.centers = plane.centers
    analyzer.model = SimpleNamespace(predict=lambda **_: [SimpleNamespace(names={0:'driver'},boxes=boxes)])
    result = analyzer._process(1,np.zeros((720,1280,3),np.uint8),h)
    assert result.features['driver_count'] == (1 if metric else 2)
    assert len(result.detections) == 2
    if metric:
        assert result.features['driver_count_raw'] == result.features['driver_count_in_workspace'] == 2
        assert result.features['tool_dist_d'] < .05


def test_auto_trial_is_opt_in_bounded_and_does_not_reuse_old_roi():
    base = dict(source=dict(type="camera"), aruco=dict(enabled=True), roi=dict(enabled=True),
                yolo=dict(enabled=True), logging=dict(save_frames=False))
    args = Namespace(screw_auto_trial=True, guidance_mode="auto", presentation_config="profiles.json")
    config = build_effective_config(base, args)
    assert config["screw_auto_trial"] is True
    assert not config["aruco"]["enabled"] and not config["roi"]["enabled"]
    assert config["yolo"]["enabled"]
    assert config["state_filter"]["initial_state"] == "S2"
    assert config["state_filter"]["max_state"] == "S3"
    assert config["state_filter"]["guidance_policy"] == "timed_v1"
    assert base["aruco"]["enabled"] and base["roi"]["enabled"]
    assert not build_effective_config(base, Namespace()).get("screw_auto_trial", False)


def test_full_screw_trial_explicitly_ends_at_final_confirmation():
    config = build_effective_config(dict(source=dict(type='camera'), yolo=dict(enabled=True)),
        Namespace(screw_auto_trial=True, screw_auto_end_state='S6', guidance_mode='auto',
                  presentation_config='profiles.json'))
    assert config['state_filter']['initial_state'] == 'S2'
    assert config['state_filter']['max_state'] == 'S6'


@pytest.mark.parametrize('trial,end', [(False,'S6'), (True,'S4'), (True,'complete')])
def test_screw_trial_end_state_cannot_silently_change_other_modes(trial, end):
    with pytest.raises(ValueError, match='end state'):
        build_effective_config(dict(source=dict(type='camera'), yolo=dict(enabled=True)),
            Namespace(screw_auto_trial=trial, screw_auto_end_state=end, guidance_mode='auto',
                      presentation_config='profiles.json'))


@pytest.mark.parametrize("changes", [dict(presentation_config=None), dict(guidance_mode="operator"),
                                      dict(save_frames=True), dict(host="0.0.0.0")])
def test_auto_trial_rejects_unsafe_or_ambiguous_configuration(changes):
    args = dict(screw_auto_trial=True, guidance_mode="auto", presentation_config="profiles.json")
    args.update(changes)
    with pytest.raises(ValueError):
        build_effective_config(dict(source=dict(type="camera"), yolo=dict(enabled=True)), Namespace(**args))


@pytest.mark.parametrize('end_state,hybrid,resume_ms,completed_ms,nested,linked', [
    ('S3', False, None, None, False, False), ('S6', False, None, None, False, False),
    ('S6', True, None, None, False, False), ('S6', True, 600, None, False, False),
    ('S6', True, 600, 2000, False, False), ('S6', True, 600, 2000, True, False),
    ('S6', True, 600, 2000, True, True),
])
def test_real_tool_scoring_and_runtime_transition_share_one_metric_frame(monkeypatch, tmp_path, end_state, hybrid, resume_ms, completed_ms, nested, linked):
    import json
    import time
    from contextlib import ExitStack
    from types import SimpleNamespace
    from server.realtime import frame_source, presentation_bridge, yolo_realtime
    from server.realtime.run_realtime_server import run_session
    from server.realtime.schemas import FramePacket
    from server.realtime.workspace_projection import project_targets
    from .test_workspace_live_preview import profiles

    camera, workspace, _, _, _ = models()
    rvec = np.array([np.pi, 0., 0.])
    tvec = np.array([-200., 120., 560.])
    pose = SimpleNamespace(rvec=rvec, tvec=tvec)
    targets = project_targets(pose, workspace, camera)
    screw_frames = 39 if end_state == 'S3' else 161
    setup_frames = 3 if hybrid else 0
    total_frames = screw_frames + setup_frames + int(hybrid)
    controls = []
    if hybrid:
        from server.realtime import assembly_session
        original_control = assembly_session.AssemblySession
        def create_control(*args):
            control = original_control(*args)
            controls.append(control)
            return control
        monkeypatch.setattr(assembly_session, 'AssemblySession', create_control)
    boxes = []

    def box(xyxy, cls, confidence=.95):
        return SimpleNamespace(cls=np.array([cls]), conf=np.array([confidence]), xyxy=np.array([xyxy]))

    class Detector:
        def predict(self, **_kwargs):
            return [SimpleNamespace(boxes=boxes, names={0:'driver', 1:'handle'})]

    class SynchronousYolo(yolo_realtime.RealtimeYoloAnalyzer):
        # Replace only scheduling and the neural detector, not geometry/evidence validation.
        def __init__(self, **kwargs):
            kwargs['enabled'] = False
            super().__init__(**kwargs)
            self.enabled = self.available = True
            self.model = Detector()
            self.centers = dict(self.metric_plane.centers)
        def submit(self, frame_id, frame, homography, *, timestamp_ms, marker_ok):
            if not marker_ok or homography is None:
                return
            self._result = self._process(frame_id, frame, homography)
            self._result.session_id = self.session_id
            self._result.timestamp_ms = timestamp_ms
            self._result.source_marker_ok = marker_ok

    clock = [10.]
    monkeypatch.setattr(time, 'perf_counter', lambda: clock[0])
    observed = []
    def analyze(image, *_args):
        observed.append(int(image[0,0,0]))
        return dict(status='tracking', reason='', marker_ids=[0,1,2,3,4,5],
                    rms_px=0., rvec=rvec.tolist(), tvec_mm=tvec.tolist(), targets=targets)
    monkeypatch.setattr(presentation_bridge, 'analyze_frame', analyze)
    monkeypatch.setattr(yolo_realtime, 'RealtimeYoloAnalyzer', SynchronousYolo)
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    class Frames:
        closed = False
        def __iter__(self):
            for i in range(1, total_frames + 1):
                clock[0] = 10. + i / 10.
                if hybrid and i in (2, 3, total_frames):
                    control = controls[0]
                    control.request(control.session_id, control.metadata()['revision'])
                boxes.clear()
                screw_frame = max(1, i - setup_frames)
                cycle = (screw_frame - 1) % 39 + 1
                target = 'ABCD'[min(3, (screw_frame - 1) // 39)]
                # Recovery trials lose mid-HOLD input, then completed HOLD during withdrawal.
                missing = (resume_ms and cycle == 12) or (completed_ms and cycle in (18, 19))
                if cycle >= 6 and i > setup_frames and not missing:
                    # Each screw needs its own sustained engagement then visible withdrawal.
                    x, y = np.array(targets[target]['pixel']) + ([0., 0.] if cycle < 20 else [74., 0.])
                    boxes.extend([box([x-7, y-100, x+7, y], 0), box([x-9, y-100, x+9, y-75], 1)])
                    if nested:
                        boxes.append(box([x-6, y-40, x+8, y+1], 0, .3))
                    if linked:
                        boxes.append(box([x+35, y-60, x+45, y-10], 0, .99))
                yield FramePacket(i, round(clock[0]*1000), 'synthetic-camera',
                                  np.full((720,1280,3), i, np.uint8))
        def close(self):
            self.closed = True
    frames = Frames()
    def source(config):
        assert (config.width, config.height) == camera.image_size
        return frames
    monkeypatch.setattr(frame_source, 'create_frame_source', source)
    cam, board = profiles(tmp_path)
    config_path = tmp_path/'presentation.json'
    config_path.write_text(json.dumps(dict(camera_profile=str(cam), workspace_profile=str(board))))
    args = Namespace(screw_auto_trial=not hybrid, screw_auto_end_state=None if hybrid else end_state,
        guidance_mode='hybrid' if hybrid else 'auto', presentation_config=config_path,
        camera_index=None, camera_backend=None, host=None, port=0, save_frames=False,
        diagnostic_preview=False, max_frames=total_frames, screw_resume_ms=resume_ms,
        completed_hold_resume_ms=completed_ms, nested_driver_dedup=nested)
    config = build_effective_config(dict(source=dict(type='camera',width=640,height=480),
        yolo=dict(enabled=True,interval_frames=1,handle_linked_driver=linked), state_filter=dict(min_confidence=.55),
        logging=dict(output_root=str(tmp_path/'logs'))), args)
    with ExitStack() as resources:
        assert run_session(config, args, resources) == 0
    rows = [json.loads(line) for line in next((tmp_path/'logs').glob('*/results.jsonl')).read_text().splitlines()]
    assert frames.closed and observed == list(range(1,total_frames + 1))
    if hybrid:
        assert [row['state'] for row in rows[:3]] == ['S0', 'S1', 'S2']
        assert rows[-1]['guidance']['phase'] == 'COMPLETED'
        confirmations = [row for row in rows if row['assembly_input']['confirmation_revision'] is not None]
        assert [row['state'] for row in confirmations] == ['S1', 'S2', 'S6']
        assert all(row['transition_event'] == 'operator_confirmation' for row in confirmations)
        rows = rows[setup_frames:-1]
    assert all(row['state'] == 'S2' for row in rows[:19])
    assert any(row['guidance']['phase'] == 'OBSERVED' for row in rows[:19])
    if resume_ms:
        assert rows[11]['guidance']['phase'] == 'PAUSED'
        assert rows[12]['guidance']['phase'] == 'OBSERVING'
    if completed_ms:
        assert all(row['guidance']['phase'] == 'PAUSED' for row in rows[17:19])
        assert rows[19]['state'] == 'S2' and rows[19]['guidance']['phase'] == 'OBSERVED'
    expected = ['S2->S3'] if end_state == 'S3' else ['S2->S3', 'S3->S4', 'S4->S5', 'S5->S6']
    assert [row['transition_event'] for row in rows if row['transition_event']] == expected
    assert rows[-1]['state'] == end_state
    if end_state == 'S3':
        assert rows[-1]['target'] == 'screw_b'
    else:
        assert all(row['guidance']['phase'] == 'AWAITING_CONFIRMATION' for row in rows if row['state']=='S6')
        for cycle_index in range(4):
            engagement = rows[cycle_index*39:cycle_index*39+19]
            assert all(row['state'] == f'S{cycle_index+2}' for row in engagement)
            assert any(row['guidance']['phase']=='OBSERVED' for row in engagement)
    assert rows[0]['yolo_detections'] == []
    assert {d['class'] for d in rows[10]['yolo_detections']} == {'driver', 'handle'}
    if nested:
        assert rows[10]['driver_count'] == 1
        assert rows[10]['driver_nested_duplicates'] == 1
        assert rows[10]['filter_input']['features']['nested_driver_dedup'] == 1
    if linked:
        assert rows[10]['filter_input']['features']['handle_linked_driver'] == 1
        assert rows[10]['filter_input']['features']['driver_unlinked_candidates'] == 1
        assert rows[10]['driver_count_raw'] == 3
    assert rows[10]['yolo_frame_id'] == rows[10]['frame_id']
    messages = [json.loads(line) for line in next((tmp_path/'logs').glob('*/overlay_messages.jsonl')).read_text().splitlines()]
    target_map = dict(S0=None, S1=None, S2='A', S3='B', S4='C', S5='D', S6=None)
    assert all(row['extra']['presentation_target'] == target_map[row['current_state']] for row in messages)
    assert all(row['extra']['screw_auto_end_state']==end_state for row in messages)
    assert all(row['extra']['tool_distance_unit']=='mm' and row['extra']['screw_auto_trial'] == (not hybrid) for row in messages)
    assert all(row['extra']['roi_reason']=='disabled' and ('operator' in row['extra']) == hybrid for row in messages)
    if hybrid:
        assert all(row['extra']['operator']['mode'] == 'hybrid' for row in messages)
        assert all(not row['extra']['operator']['can_confirm'] for row in messages if row['current_state'] in ('S2','S3','S4','S5'))
    assert not list(tmp_path.rglob('*.jpg')) and not list(tmp_path.rglob('*.png'))
    from server.realtime.realtime_replay import validate_session
    assert validate_session(next((tmp_path/'logs').iterdir()))['matched']
