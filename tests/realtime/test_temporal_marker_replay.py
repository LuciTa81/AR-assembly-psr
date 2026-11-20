import copy
import json
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
import pytest

from .test_workspace_projection import corner_scene


def api():
    from server.realtime.temporal_marker_replay import ShortOcclusionCandidate
    return ShortOcclusionCandidate


def scene(shift=(13., 5., 7.)):
    camera, board, _, detections, _, _ = corner_scene((0, 1, 2, 4, 5), camera_shift=shift)
    return camera, board, detections


def test_full_path_is_unchanged_and_partial_uses_current_observation():
    camera, board, full = scene()
    before = copy.deepcopy(board.markers)
    tracker = api()(camera, board)
    _, anchor, meta = tracker.update(1, 1000, full, camera.image_size)
    assert meta['method'] == 'baseline' and meta['anchor_frame'] == 1
    moved = scene((16., 5., 7.))[2]
    del moved[5]
    with patch('cv2.VideoCapture', side_effect=AssertionError('no camera')):
        baseline, pose, meta = tracker.update(2, 1100, moved, camera.image_size)
    assert baseline is None and pose is not None
    assert meta['method'] == 'temporal_centers' and meta['anchor_frame'] == 1
    assert meta['anchor_age_ms'] == 100
    assert pose is not anchor
    np.testing.assert_allclose(pose.camera_position_mm, [216., -175., 507.], atol=.05)
    for key in before:
        np.testing.assert_array_equal(board.markers[key], before[key])


def test_partial_results_never_renew_reference_or_extend_deadline():
    camera, board, full = scene()
    tracker = api()(camera, board)
    tracker.update(1, 1000, full, camera.image_size)
    partial = {k:v for k,v in full.items() if k != 5}
    for frame, now in ((2,1100), (3,1200), (4,1300)):
        _, pose, meta = tracker.update(frame, now, partial, camera.image_size)
        assert pose is not None and meta['anchor_frame'] == 1
    _, pose, meta = tracker.update(5, 1301, partial, camera.image_size)
    assert pose is None and meta['candidate_reason'] == 'anchor_expired'
    _, pose, meta = tracker.update(6, 1400, partial, camera.image_size)
    assert pose is None


def test_no_reference_no_rescue_and_reappearance_restores_original_pose():
    camera, board, full = scene()
    tracker = api()(camera, board)
    partial = {k:v for k,v in full.items() if k != 4}
    _, pose, _ = tracker.update(1, 1000, partial, camera.image_size)
    assert pose is None
    base, pose, meta = tracker.update(2, 1100, full, camera.image_size)
    assert base is pose and meta['anchor_frame'] == 2


@pytest.mark.parametrize('fault', ['few', 'quality', 'unknown', 'resolution', 'nan'])
def test_other_failure_types_are_not_rescued(fault):
    camera, board, full = scene()
    tracker = api()(camera, board)
    tracker.update(1, 1000, full, camera.image_size)
    partial = copy.deepcopy(full)
    del partial[5]
    size = camera.image_size
    if fault == 'few': del partial[4]
    if fault == 'quality':
        partial = copy.deepcopy(full)
        partial[4] += [40, 0]
    if fault == 'unknown': partial[49] = partial.pop(4)
    if fault == 'resolution': size = (640, 480)
    if fault == 'nan': partial[0][0,0] = np.nan
    _, pose, meta = tracker.update(2, 1100, partial, size)
    assert pose is None
    assert meta['method'] != 'temporal_centers'


@pytest.mark.parametrize('frame,now', [(1,1100), (2,1000), (True,1100), (2,999)])
def test_reversed_or_duplicate_inputs_clear_reference(frame, now):
    camera, board, full = scene()
    tracker = api()(camera, board)
    tracker.update(1, 1000, full, camera.image_size)
    partial = {k:v for k,v in full.items() if k != 5}
    with pytest.raises(ValueError): tracker.update(frame, now, partial, camera.image_size)
    _, pose, _ = tracker.update(3, 1200, partial, camera.image_size)
    assert pose is None


def test_large_camera_motion_is_not_hidden_by_temporal_candidate():
    camera, board, full = scene()
    tracker = api()(camera, board)
    tracker.update(1, 1000, full, camera.image_size)
    moved = scene((55., 5., 7.))[2]
    del moved[5]
    _, pose, meta = tracker.update(2, 1100, moved, camera.image_size)
    assert pose is None and meta['candidate_reason'] == 'motion_limit'


def test_normal_four_marker_path_is_not_overridden():
    camera, board, full = scene()
    tracker = api()(camera, board)
    tracker.update(1, 1000, full, camera.image_size)
    partial = {k:v for k,v in full.items() if k != 1}
    baseline, pose, meta = tracker.update(2, 1100, partial, camera.image_size)
    assert baseline is pose and pose is not None and meta['method'] == 'baseline'
    assert meta['anchor_frame'] == 1


def test_reference_creation_failure_does_not_break_accepted_baseline():
    camera, board, full = scene()
    tracker = api()(camera, board)
    tracker.update(1, 1000, full, camera.image_size)
    with patch('server.realtime.temporal_marker_replay.pixel_to_plane', side_effect=ValueError('outside image')):
        baseline, candidate, detail = tracker.update(2, 1100, full, camera.image_size)
    assert baseline is candidate and baseline is not None
    assert detail['method'] == 'baseline' and detail['anchor_frame'] is None
    assert detail['anchor_error'] == 'outside image'
    partial = {k:v for k,v in full.items() if k != 5}
    _, candidate, detail = tracker.update(3, 1200, partial, camera.image_size)
    assert candidate is None and detail['candidate_reason'] == 'no_anchor'


@pytest.mark.parametrize('budget', [True, 0, -1, 301, 1.5])
def test_reference_lifetime_cannot_be_silently_relaxed(budget):
    camera, board, _ = scene()
    with pytest.raises(ValueError): api()(camera, board, max_anchor_ms=budget)


def test_sequence_masks_never_refresh_from_the_hidden_reference():
    from server.realtime.temporal_marker_replay import compare_windows
    camera, board, full = scene()
    rows = [dict(frame_id=i+1, timestamp_ms=1000+i*100, detections=copy.deepcopy(full))
            for i in range(8)]
    report = compare_windows(rows, camera, board, lengths=(5,), removed_ids=(5,))
    cases = report['records']
    assert len(cases) == 5
    assert [c['candidate_method'] for c in cases[:3]] == ['temporal_centers'] * 3
    assert cases[3]['candidate_reason'] == 'anchor_expired'
    assert cases[4]['candidate_reason'] == 'no_anchor'
    assert report['groups']['5:5']['candidate_accepted'] == 3
    assert report['groups']['5:5']['candidate_preserved'] == 3


def test_windows_with_missing_ground_truth_are_counted_not_filled_in():
    from server.realtime.temporal_marker_replay import compare_windows
    camera, board, full = scene()
    rows = [dict(frame_id=i+1, timestamp_ms=1000+i*100, detections=copy.deepcopy(full))
            for i in range(8)]
    del rows[2]['detections'][5]
    report = compare_windows(rows, camera, board, lengths=(3,), removed_ids=(5,))
    assert report['records'] == []
    assert report['skipped_windows'] == 1


@pytest.fixture
def saved_trace(tmp_path):
    from .test_workspace_live_preview import profiles
    from .test_partial_marker_replay import record
    from .test_tracking_report import write_rows
    from server.realtime.workspace_live_preview import load_profiles
    paths = profiles(tmp_path)
    models = load_profiles(*paths)
    sample = (models, scene()[2], paths)
    rows = [record(i+1, sample) for i in range(8)]
    for i, row in enumerate(rows):
        row['filter_input'] = dict(frame_id=i+1, timestamp_ms=1000+i*100)
    return write_rows(tmp_path, rows), models, paths, rows


@pytest.mark.parametrize('fault', ['binding', 'capture_frame', 'capture_time', 'duplicate_ids', 'nan'])
def test_replay_rejects_mismatched_or_malformed_evidence(saved_trace, fault):
    from server.realtime.temporal_marker_replay import replay
    path, models, _, rows = saved_trace
    if fault == 'binding': rows[0]['presentation_diagnostics']['camera_profile_sha256'] = 'bad'
    if fault == 'capture_frame': rows[0]['filter_input']['frame_id'] = 99
    if fault == 'capture_time': rows[1]['filter_input']['timestamp_ms'] = 1000
    if fault == 'duplicate_ids': rows[0]['presentation_diagnostics']['marker_ids'].append(5)
    if fault == 'nan': rows[0]['presentation_diagnostics']['detected_corners_px']['0'][0][0] = float('nan')
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows), encoding='utf-8')
    with pytest.raises(ValueError): replay(path, models)


def test_replay_detects_trace_mutation_and_never_overwrites_output(saved_trace, tmp_path, capsys):
    from server.realtime import temporal_marker_replay as m
    path, models, paths, _ = saved_trace
    original = m.compare_windows
    def change(*args, **kwargs):
        result = original(*args, **kwargs)
        with path.open('a', encoding='utf-8') as stream: stream.write('\n')
        return result
    with patch.object(m, 'compare_windows', change), pytest.raises(ValueError, match='changed'):
        m.replay(path, models)
    output = tmp_path / 'report.json'
    argv = ['replay', '--results', str(path), '--camera-profile', str(paths[0]),
            '--workspace-profile', str(paths[1]), '--output', str(output)]
    with patch('sys.argv', argv), patch('cv2.VideoCapture', side_effect=AssertionError('no camera')):
        m.main()
        before = output.read_bytes()
        report = json.loads(before)
        assert report['offline_only'] and not report['live_enabled']
        assert report['actual']['baseline_mismatches'] == []
        with pytest.raises(SystemExit): m.main()
        assert output.read_bytes() == before


def test_saved_c_occlusion_keeps_normal_path_and_never_counts_old_pose_as_new():
    from server.realtime.workspace_projection import CameraModel, MetricWorkspace
    data = json.loads((Path(__file__).parents[1]/'fixtures/short_occlusion_20261108.json').read_text(encoding='utf-8'))
    camera = CameraModel.from_profile(data['camera'])
    workspace = MetricWorkspace.from_dict(data['workspace'])
    tracker = api()(camera, workspace)
    temporal_frames = []
    for row in data['frames']:
        detections = {int(k):v for k,v in row['detected_corners_px'].items()}
        baseline, pose, detail = tracker.update(row['frame_id'], row['timestamp_ms'], detections, camera.image_size)
        assert detail['baseline_reason'] == row['recorded_reason']
        if baseline is not None:
            assert pose is baseline
        elif detail['method'] == 'temporal_centers':
            assert 0 < detail['anchor_age_ms'] <= 300
            assert detail['anchor_frame'] < row['frame_id']
            assert pose is not None and pose.rms_px <= 3 and pose.max_error_px <= 5
            temporal_frames.append(row['frame_id'])
        else:
            assert pose is None
    assert temporal_frames == [737]
