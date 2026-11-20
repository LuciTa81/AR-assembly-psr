import json
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest


def api():
    from server.realtime import tracking_report
    return tracking_report


def row(frame, status='tracking', reason='', **diagnostic):
    return {'frame_id': frame, 'state': 'S2', 'marker_ok': True,
            'presentation_diagnostics': {
                'frame_id': frame, 'analysis_status': status, 'analysis_reason': reason,
                'analysis_ms': 20., 'publish_age_ms': 25., 'source_interval_ms': 100.,
                **diagnostic}}


def write_rows(tmp_path, rows):
    path = tmp_path / 'results.jsonl'
    path.write_text(''.join(json.dumps(item) + '\n' for item in rows), encoding='utf-8')
    return path


def test_report_separates_tracking_from_alignment_and_missing_evidence(tmp_path):
    path = write_rows(tmp_path, [
        row(1), row(2, 'pose_rejected', 'No physical workspace pose above the mat'),
        row(3, 'pose_rejected', 'At least four visible measured markers required for pose', marker_ids=[]),
        {'frame_id': 4, 'state': 'S2'},
    ])
    report = api().summarize(path)
    assert report['rows'] == 4
    assert report['pose_frames'] == 3
    assert report['pose_reason_counts'] == {'tracking': 1, 'pose_quality': 1, 'insufficient_markers': 1}
    assert report['raw_rejection_counts']['No physical workspace pose above the mat'] == 1
    assert report['pose_tracking_fraction'] == pytest.approx(1 / 3)
    assert report['marker_ids_missing_frames'] == 2
    assert report['numeric_replay_available_frames'] == 0
    assert report['timings_ms']['analysis_ms']['p95'] == 20.
    assert report['optical_alignment_verified'] is False


def test_report_range_and_missing_timing_are_not_zeros(tmp_path):
    path = write_rows(tmp_path, [row(1), row(2, analysis_ms=None), row(3)])
    report = api().summarize(path, first_frame=2, last_frame=2)
    assert report['rows'] == 1 and report['frame_range'] == [2, 2]
    assert report['timings_ms']['analysis_ms'] is None
    with pytest.raises(ValueError, match='No selected'):
        api().summarize(path, first_frame=9)


@pytest.mark.parametrize('rows', [
    [row(1), row(1)], [row(2), row(1)],
    [{'frame_id': 1, 'presentation_diagnostics': {'frame_id': 99}}],
])
def test_report_rejects_duplicate_reversed_or_mixed_frames(tmp_path, rows):
    with pytest.raises(ValueError, match='frame'):
        api().summarize(write_rows(tmp_path, rows))


def test_replay_numeric_pose_requires_exact_profile_binding():
    from .test_workspace_projection import models
    camera, workspace, detections, _, _ = models()
    d = row(1)['presentation_diagnostics']
    d.update(marker_ids=list(detections), detected_corners_px={str(k): v.tolist() for k, v in detections.items()},
             image_size=list(camera.image_size), camera_profile_sha256='a'*64, workspace_profile_sha256='b'*64)
    pose = api().replay_pose(d, camera, workspace, 'a'*64, 'b'*64)
    assert pose['reason_code'] == 'tracking' and pose['rms_px'] < .001
    with pytest.raises(ValueError, match='profile'):
        api().replay_pose(d, camera, workspace, 'c'*64, 'b'*64)
    d['marker_ids'] = [0, 0, 2, 3]
    assert api().replay_pose(d, camera, workspace, 'a'*64, 'b'*64)['reason_code'] == 'pose_unavailable'


def test_runtime_numeric_record_round_trip_without_camera_or_images(tmp_path):
    import numpy as np
    from .test_workspace_projection import models
    from .test_workspace_live_preview import profiles
    from server.realtime.presentation_bridge import PresentationBridge
    from server.realtime.realtime_logger import RealtimeLogger
    from server.realtime.workspace_live_preview import load_profiles

    cam_path, board_path = profiles(tmp_path)
    cam, board, meta = load_profiles(cam_path, board_path)
    config = tmp_path / 'presentation.json'
    config.write_text(json.dumps({'camera_profile': str(cam_path), 'workspace_profile': str(board_path)}))
    all_detections = models()[2]
    logger = RealtimeLogger(str(tmp_path / 'logs'), 'numeric-only', {}, save_frames=False)
    bridge = PresentationBridge(config, 'numeric-only', root=tmp_path / 'local')
    try:
        for frame_id, keys in enumerate([(0, 2, 3, 5), (0, 1, 2, 4)], 1):
            detections = {key: all_detections[key] for key in keys}
            ids = np.array(keys).reshape(-1, 1)
            packet = SimpleNamespace(frame_id=frame_id, frame=np.zeros((720, 1280, 3), np.uint8),
                                     timestamp_ms=int(time.perf_counter() * 1000))
            with patch('cv2.VideoCapture', side_effect=AssertionError('camera forbidden')), \
                 patch('server.realtime.workspace_live_preview.detect_markers', return_value=(detections, [], ids)):
                _, status = bridge.update(packet)
            d = status['diagnostics']
            logger.log_result(dict(frame_id=frame_id, state='S2', presentation_diagnostics=d))
            assert len(json.dumps(d).encode()) < 6000
    finally:
        bridge.close()
        logger.close()
    report = api().summarize(logger.session_dir / 'results.jsonl', profiles=(
        cam, board, meta['camera_profile_sha256'], meta['workspace_profile_sha256']))
    assert report['numeric_replay_available_frames'] == 2
    assert report['replay_reason_counts'] == {'tracking': 1, 'marker_geometry': 1}
    assert report['pose_reason_counts'] == report['replay_reason_counts']
    assert not (logger.session_dir / 'frames').exists()


def test_report_replays_saved_numeric_fixture_with_no_alignment_claim():
    from pathlib import Path
    from server.realtime.workspace_projection import CameraModel, MetricWorkspace
    fixture = json.loads((Path(__file__).parent / 'fixtures/workspace_pose_comfort.json').read_text())
    cam = CameraModel.from_profile(fixture['camera'])
    board = MetricWorkspace.from_dict(fixture['workspace'])
    for keys, expected in [([0, 1, 2, 4, 5], 'tracking'), ([0, 1, 2, 4], 'marker_geometry'),
                           ([0, 1, 2, 5], 'marker_geometry'), ([0, 2, 4, 5], 'tracking')]:
        d = dict(marker_ids=keys, detected_corners_px={str(key): fixture['detected_corners_px'][str(key)] for key in keys},
                 camera_profile_sha256='a'*64, workspace_profile_sha256='b'*64, image_size=list(cam.image_size))
        assert api().replay_pose(d, cam, board, 'a'*64, 'b'*64)['reason_code'] == expected


def trace_row(frame):
    return dict(schema_version='beast_display_pose_trace_v1', session_id='test-session',
                camera_profile_id='test-camera', workspace_profile_id='test-workspace',
                camera_profile_sha256='a'*64, workspace_profile_sha256='b'*64,
                frame_id=frame, status='stale', reason='No fresh observation',
                marker_ids=None, marker_count=-1, age_ms=200.,
                analysis_status='tracking', analysis_reason='', analysis_marker_ids=[0, 2, 4, 5],
                detected_corners_px={}, image_size=[1280, 720])


def test_pose_trace_keeps_analysis_distinct_from_observation_freshness(tmp_path):
    trace = trace_row(1)
    report = api().summarize(write_rows(tmp_path, [trace]), pose_trace=True)
    assert report['pose_frames'] == 1
    assert report['pose_reason_counts'] == {'tracking': 1}
    assert report['observation_reason_counts'] == {'stale': 1}
    assert report['marker_combinations'] == {'0,2,4,5': 1}
    assert report['marker_count_frames'] == {'4': 1}
    assert report['marker_presence_frames'] == {'0': 1, '2': 1, '4': 1, '5': 1}
    assert report['state_counts'] == {'unknown': 1}
    assert report['timings_ms']['publish_age_ms']['mean'] == 200.
    assert report['optical_alignment_verified'] is False


@pytest.mark.parametrize('field,value', [
    ('schema_version', 'unknown'), ('session_id', 'other-session'),
    ('camera_profile_id', 'other-camera'), ('workspace_profile_id', 'other-workspace'),
    ('camera_profile_sha256', 'c'*64), ('workspace_profile_sha256', 'c'*64),
    ('session_id', None),
])
def test_pose_trace_rejects_mixed_or_missing_provenance(tmp_path, field, value):
    changed = trace_row(2)
    changed[field] = value
    with pytest.raises(ValueError, match='trace'):
        api().summarize(write_rows(tmp_path, [trace_row(1), changed]), pose_trace=True)


def test_pose_trace_checks_profile_binding_even_without_replayable_corners(tmp_path):
    with pytest.raises(ValueError, match='profile binding'):
        api().summarize(write_rows(tmp_path, [trace_row(1)]), pose_trace=True,
                        profiles=(None, None, 'c'*64, 'b'*64))


def test_pose_trace_replays_real_fixture_and_preserves_rejections(tmp_path):
    from pathlib import Path
    from server.realtime.workspace_projection import CameraModel, MetricWorkspace
    fixture = json.loads((Path(__file__).parent / 'fixtures/workspace_pose_comfort.json').read_text())
    cam = CameraModel.from_profile(fixture['camera'])
    board = MetricWorkspace.from_dict(fixture['workspace'])
    rows = []
    for index, ids in enumerate([[0, 1, 2, 4, 5], [0, 1, 2, 5], [0, 1, 2], []], 1):
        item = trace_row(index)
        item.update(analysis_marker_ids=ids, detected_corners_px={
            str(key): fixture['detected_corners_px'][str(key)] for key in ids})
        rows.append(item)
    with patch('cv2.VideoCapture', side_effect=AssertionError('camera forbidden')):
        report = api().summarize(write_rows(tmp_path, rows), pose_trace=True,
                                profiles=(cam, board, 'a'*64, 'b'*64))
    assert report['replay_reason_counts'] == {
        'tracking': 1, 'marker_geometry': 1, 'insufficient_markers': 1}
    assert report['numeric_replay_available_frames'] == 3
    assert report['marker_count_frames'] == {'5': 1, '4': 1, '3': 1, '0': 1}
    assert report['marker_presence_frames'] == {'0': 3, '1': 3, '2': 3, '4': 1, '5': 2}
    assert report['optical_alignment_verified'] is False


def test_pose_trace_cli_writes_report_without_replacing_an_existing_output(tmp_path, capsys):
    source = write_rows(tmp_path, [trace_row(1)])
    output = tmp_path / 'report.json'
    argv = ['tracking_report', '--pose-trace', str(source), '--output', str(output)]
    with patch('sys.argv', argv), patch('cv2.VideoCapture', side_effect=AssertionError('camera forbidden')):
        assert api().main() == 0
        report = json.loads(output.read_text(encoding='utf-8'))
        assert report['pose_frames'] == 1
        assert report['observation_reason_counts'] == {'stale': 1}
        with pytest.raises(SystemExit) as exc:
            api().main()
        assert exc.value.code == 2
    assert json.loads(output.read_text(encoding='utf-8')) == report
