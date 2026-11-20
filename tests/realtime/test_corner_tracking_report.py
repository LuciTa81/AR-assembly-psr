import copy
import importlib
import json
from unittest.mock import patch

import numpy as np
import pytest

from .test_workspace_projection import camera_data, corner_scene, workspace_data
from .test_tracking_report import trace_row, write_rows


def api():
    name = 'server.realtime.corner_tracking_report'
    assert importlib.util.find_spec(name) is not None, 'offline comparison API not implemented'
    return importlib.import_module(name)


def reference():
    cam, board, world, detected, _, _ = corner_scene((0, 1, 2, 4, 5))
    fixture = dict(camera=camera_data(), workspace=workspace_data(), source_image_sha256='e'*64,
                   detected_corners_px={str(k): v.tolist() for k, v in detected.items()})
    return fixture, (cam, board, 'a'*64, 'b'*64), world


def candidate():
    fixture, profiles, world = reference()
    return api().reference_candidate(fixture, profiles, side_mm=70.), profiles, world


def trace(frame, ids=(0, 1, 2, 4, 5)):
    fixture, profiles, _ = reference()
    row = trace_row(frame)
    row.update(camera_profile_id=profiles[0].profile_id, workspace_profile_id=profiles[1].profile_id,
               analysis_marker_ids=list(ids), detected_corners_px={
                   str(key): fixture['detected_corners_px'][str(key)] for key in ids})
    return row


def test_reference_candidate_recovers_orientation_without_inventing_missing_marker():
    fixture, profiles, world = reference()
    before = copy.deepcopy(fixture)
    with patch('cv2.VideoCapture', side_effect=AssertionError('camera forbidden')):
        result = api().reference_candidate(fixture, profiles, side_mm=70.)
    assert result['optical_alignment_verified'] is False
    assert result['geometry_measured'] is False and result['offline_only'] is True
    assert result['missing_marker_ids'] == [3]
    assert set(result['marker_corners_mm']) == {'0', '1', '2', '4', '5'}
    for key in world:
        np.testing.assert_allclose(result['marker_corners_mm'][str(key)], world[key], atol=.001)
        assert result['orientation_diagnostics'][str(key)]['edge_lengths_mm'] == pytest.approx([70]*4, abs=.001)
    assert fixture == before


@pytest.mark.parametrize('side', [0, -1, float('nan'), float('inf'), True])
def test_reference_rejects_invalid_assumed_side(side):
    fixture, profiles, _ = reference()
    with pytest.raises(ValueError, match='side'):
        api().reference_candidate(fixture, profiles, side_mm=side)


@pytest.mark.parametrize('part,field,value', [
    ('camera', 'distortion_coefficients', [0]*5),
    ('camera', 'profile_id', 'different-camera'),
    ('workspace', 'marker_centers_mm', {'3': [0, 0, 0]}),
    ('workspace', 'targets_mm', {'A': [1, 2, 3]}),
])
def test_reference_requires_matching_geometry(part, field, value):
    fixture, profiles, _ = reference()
    fixture[part][field] = value
    with pytest.raises(ValueError, match='reference|Reference'):
        api().reference_candidate(fixture, profiles, side_mm=70.)


def test_reference_rejects_unknown_ids_and_reversed_image_corners():
    fixture, profiles, _ = reference()
    fixture['detected_corners_px']['17'] = fixture['detected_corners_px']['0']
    with pytest.raises(ValueError, match='registered'):
        api().reference_candidate(fixture, profiles, side_mm=70.)
    del fixture['detected_corners_px']['17']
    fixture['detected_corners_px']['0'].reverse()
    with pytest.raises(ValueError, match='winding'):
        api().reference_candidate(fixture, profiles, side_mm=70.)


def test_compare_keeps_all_frames_and_stale_observations_distinct(tmp_path):
    cand, profiles, _ = candidate()
    rows = [trace(1), trace(2, (0, 1, 2)), trace(3, ()), trace(4, (0, 1))]
    path = write_rows(tmp_path, rows)
    with patch('cv2.VideoCapture', side_effect=AssertionError('camera forbidden')):
        result = api().compare_trace(path, profiles, cand)
    assert result['rows'] == 4 and result['numeric_frames'] == 3
    assert result['baseline']['reason_counts'] == {'tracking': 1, 'insufficient_markers': 2, 'no_numeric_evidence': 1}
    assert result['corner_candidate']['reason_counts'] == {'tracking': 2, 'no_numeric_evidence': 1, 'insufficient_markers': 1}
    assert result['corner_candidate']['accepted_fraction_all_frames'] == .5
    assert result['observation_reason_counts'] == {'stale': 4}
    assert result['paired_camera_delta_mm']['n'] == 1
    assert result['paired_camera_delta_mm']['max'] < .001
    assert result['paired_target_a_delta_px']['n'] == 1
    assert result['paired_acceptance_all_frames'] == {'both': 1, 'baseline_only': 0, 'candidate_only': 1, 'neither': 2}
    assert result['optical_alignment_verified'] is False
    assert result['by_marker_combination']['0,1,2']['corner_candidate']['tracking'] == 1


def test_missing_geometry_is_counted_and_not_invented(tmp_path):
    cand, profiles, _ = candidate()
    del cand['marker_corners_mm']['5']
    result = api().compare_trace(write_rows(tmp_path, [trace(1, (0, 2, 5))]), profiles, cand)
    assert result['unmodeled_marker_presence_frames'] == {'5': 1}
    assert result['corner_candidate']['reason_counts'] == {'insufficient_markers': 1}


@pytest.mark.parametrize('which', ['trace', 'candidate'])
def test_comparison_rejects_profile_mismatch_even_on_empty_rows(tmp_path, which):
    cand, profiles, _ = candidate()
    row = trace(1, ())
    if which == 'trace':
        row['camera_profile_sha256'] = 'c'*64
    else:
        cand['workspace_profile_sha256'] = 'c'*64
    with pytest.raises(ValueError, match='binding'):
        api().compare_trace(write_rows(tmp_path, [row]), profiles, cand)


def test_comparison_requires_matching_trace_profile_ids(tmp_path):
    cand, profiles, _ = candidate()
    row = trace(1)
    row['camera_profile_id'] = 'wrong-id'
    with pytest.raises(ValueError, match='binding'):
        api().compare_trace(write_rows(tmp_path, [row]), profiles, cand)


def test_unknown_and_incomplete_numeric_markers_are_not_replayed(tmp_path):
    cand, profiles, _ = candidate()
    unknown, incomplete = trace(1), trace(2)
    unknown['analysis_marker_ids'].append(17)
    unknown['detected_corners_px']['17'] = unknown['detected_corners_px']['0']
    del incomplete['detected_corners_px']['0']
    result = api().compare_trace(write_rows(tmp_path, [unknown, incomplete]), profiles, cand)
    for key in ('baseline', 'corner_candidate'):
        assert result[key]['reason_counts'] == {'unregistered_markers': 1, 'no_numeric_evidence': 1}


def test_frame_change_metrics_do_not_bridge_missing_or_rejected_frames(tmp_path):
    cand, profiles, _ = candidate()
    rows = [trace(1), trace(2), trace(3, ()), trace(4), trace(6)]
    result = api().compare_trace(write_rows(tmp_path, rows), profiles, cand)
    assert result['corner_candidate']['consecutive_camera_step_mm']['n'] == 1
    assert result['baseline']['consecutive_camera_step_mm']['n'] == 1
    assert result['corner_candidate']['longest_accepted_run_frames'] == 2
    subset = api().compare_trace(write_rows(tmp_path, rows), profiles, cand, first_frame=3, last_frame=4)
    assert subset['rows'] == 2 and subset['frame_range'] == [3, 4]
    with pytest.raises(ValueError, match='No selected'):
        api().compare_trace(write_rows(tmp_path, rows), profiles, cand, first_frame=7)


def test_cli_writes_reproducible_offline_report_without_overwriting(tmp_path, capsys):
    from .test_workspace_live_preview import profiles as write_profiles
    from server.realtime.workspace_live_preview import load_profiles
    fixture, _, _ = reference()
    camera_path, workspace_path = write_profiles(tmp_path)
    cam, board, meta = load_profiles(camera_path, workspace_path)
    row = trace(1)
    row.update(camera_profile_sha256=meta['camera_profile_sha256'], workspace_profile_sha256=meta['workspace_profile_sha256'])
    trace_path = write_rows(tmp_path, [row])
    ref_path = tmp_path / 'reference.json'
    ref_path.write_text(json.dumps(fixture), encoding='utf-8')
    output = tmp_path / 'report.json'
    argv = ['corner_tracking_report', '--pose-trace', str(trace_path), '--reference-fixture', str(ref_path),
            '--side-mm', '70', '--camera-profile', str(camera_path), '--workspace-profile', str(workspace_path),
            '--output', str(output)]
    with patch('sys.argv', argv), patch('cv2.VideoCapture', side_effect=AssertionError('camera forbidden')):
        assert api().main() == 0
        report = json.loads(output.read_text())
        assert report['source_trace_sha256'] and report['source_fixture_sha256']
        assert report['candidate']['source_image_sha256'] == 'e'*64
        with pytest.raises(SystemExit) as exc:
            api().main()
        assert exc.value.code == 2
    assert json.loads(output.read_text()) == report
