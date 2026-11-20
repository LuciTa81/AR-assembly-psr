import copy
import importlib
import json
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

from server.realtime.workspace_live_preview import load_profiles
from .test_tracking_report import write_rows
from .test_workspace_live_preview import profiles as write_profiles
from .test_workspace_projection import corner_scene


def api():
    name = 'server.realtime.partial_marker_replay'
    assert importlib.util.find_spec(name) is not None, 'partial marker replay not implemented'
    return importlib.import_module(name)


@pytest.fixture
def sample(tmp_path):
    paths = write_profiles(tmp_path)
    profiles = load_profiles(*paths)
    detected = corner_scene((0, 1, 2, 4, 5))[3]
    return profiles, detected, paths


def record(frame, sample, ids=(0, 1, 2, 4, 5), reason='tracking'):
    (camera, _, meta), detected, _ = sample
    return dict(frame_id=frame, state='S4', presentation_diagnostics=dict(
        frame_id=frame, marker_ids=list(ids), marker_count=len(ids),
        detected_corners_px={str(k): detected[k].tolist() for k in ids},
        image_size=list(camera.image_size), reason_code=reason,
        camera_profile_sha256=meta['camera_profile_sha256'],
        workspace_profile_sha256=meta['workspace_profile_sha256']))


def test_normal_center_pose_is_returned_unchanged_without_fallback(sample):
    (camera, board, _), detected, _ = sample
    original = copy.deepcopy(detected)
    with patch('cv2.VideoCapture', side_effect=AssertionError('camera forbidden')):
        baseline, candidate, detail = api().evaluate_pose(detected, board, camera, camera.image_size)
    assert baseline is candidate
    assert detail['candidate_reason'] == 'tracking'
    assert detail['solver'] == 'IPPE' and not detail['fallback_attempted']
    np.testing.assert_allclose(candidate.camera_position_mm, [213, -175, 507], atol=.01)
    for key in detected:
        np.testing.assert_array_equal(detected[key], original[key])


@pytest.mark.parametrize('missing', [4, 5])
def test_only_four_spread_rank_deficient_centers_use_sqpnp(sample, missing):
    (camera, board, _), detected, _ = sample
    detected = {k: v for k, v in detected.items() if k != missing}
    baseline, candidate, detail = api().evaluate_pose(detected, board, camera, camera.image_size)
    assert baseline is None and detail['baseline_reason'] == 'marker_geometry'
    assert detail['fallback_attempted'] and detail['solver'] == 'SQPNP'
    assert detail['candidate_reason'] == 'tracking'
    np.testing.assert_allclose(candidate.camera_position_mm, [213, -175, 507], atol=.01)


@pytest.mark.parametrize('fault', ['under4', 'quality', 'collinear', 'invalid_corner', 'resolution'])
def test_fallback_cannot_rescue_other_failures(sample, fault):
    (camera, board, _), detected, _ = sample
    size = camera.image_size
    if fault == 'under4':
        detected = {k: detected[k] for k in (0, 1, 2)}
    elif fault == 'quality':
        detected[4] += [40, 0]
    else:
        detected = {k: detected[k] for k in (0, 1, 2, 4)}
        if fault == 'collinear':
            board.markers[4] = np.array([600., 240., 0.])
        elif fault == 'invalid_corner':
            detected[0][0, 0] = np.nan
        else:
            size = (640, 480)
    module = api()
    with patch.object(module, '_estimate_planar_pose', side_effect=AssertionError('fallback forbidden')):
        baseline, candidate, detail = module.evaluate_pose(detected, board, camera, size)
    assert baseline is None and candidate is None
    assert not detail['fallback_attempted']
    assert detail['candidate_reason'] == detail['baseline_reason']


def test_target_comparison_includes_all_four_even_outside_the_image():
    camera = SimpleNamespace(matrix=np.diag([1000., 1000., 1.]), distortion=np.zeros(5))
    board = SimpleNamespace(targets=dict(A=np.array([0., 0., 0.]), B=np.array([10., 0., 0.]),
                                        C=np.array([0., 10., 0.]), D=np.array([1000., 1000., 0.])))
    a = SimpleNamespace(rvec=np.zeros(3), tvec=np.array([0., 0., 500.]))
    b = SimpleNamespace(rvec=np.zeros(3), tvec=np.array([0., 0., 1000.]))
    delta = api().target_deltas(a, b, board, camera)
    assert set(delta['targets']) == set('ABCD')
    assert delta['targets']['A']['camera_px'] == 0
    assert delta['max_target_delta_px'] == pytest.approx(1000 * np.sqrt(2))
    assert delta['max_target_delta_mm'] == pytest.approx(500)
    assert all(v['camera_xyz_mm'] == pytest.approx(500) for v in delta['targets'].values())


def test_replay_separates_real_gaps_from_leave_one_out_preservation(tmp_path, sample):
    rows = [record(722, sample), record(723, sample, (0, 1, 2, 4), 'marker_geometry'),
            record(724, sample, (0, 1, 2), 'insufficient_markers'),
            record(725, sample, (), 'insufficient_markers')]
    report = api().replay_trace(write_rows(tmp_path, rows), sample[0], first_frame=722, last_frame=725)
    assert report['live_enabled'] is False and report['optical_alignment_verified'] is False
    assert report['observed']['baseline_reason_counts'] == {
        'tracking': 1, 'marker_geometry': 1, 'insufficient_markers': 2}
    assert report['observed']['candidate_reason_counts'] == {'tracking': 2, 'insufficient_markers': 2}
    assert report['observed']['baseline_recorded_mismatches'] == []
    assert report['observed']['ground_truth_available'] is False
    assert 'preservation_pass' not in report['observed']
    loo = report['leave_one_out']
    assert loo['reference_frames'] == 1 and loo['cases'] == 5
    assert set(loo['by_removed_marker']) == {'0', '1', '2', '4', '5'}
    assert loo['fallback_attempts'] == 2
    assert loo['preservation_pass'] == 5 and loo['preservation_fail'] == 0
    assert loo['baseline_preservation_pass'] == 3
    assert loo['by_removed_marker']['0']['baseline_preservation_pass'] == 1
    assert loo['by_removed_marker']['4']['baseline_preservation_pass'] == 0
    assert report['preservation_criteria'] == dict(max_target_px=5., max_target_mm=5., report_only=True)


@pytest.mark.parametrize('px,mm', [(1e-9, 1e9), (1e9, 1e-9)])
def test_report_requires_both_limits_without_changing_pose_acceptance(tmp_path, sample, px, mm):
    rows = [record(1, sample)]
    rows[0]['presentation_diagnostics']['detected_corners_px']['4'] = (sample[1][4] + [.5, 0]).tolist()
    path = write_rows(tmp_path, rows)
    loose = api().replay_trace(path, sample[0])
    strict = api().replay_trace(path, sample[0], max_target_px=px, max_target_mm=mm)
    assert strict['leave_one_out']['candidate_reason_counts'] == loose['leave_one_out']['candidate_reason_counts']
    assert strict['leave_one_out']['preservation_fail'] > loose['leave_one_out']['preservation_fail']


@pytest.mark.parametrize('fault', ['hash', 'empty_hash', 'duplicate_ids', 'missing_corner',
                                    'unknown_id', 'nonfinite', 'resolution', 'frame'])
def test_invalid_numeric_evidence_or_binding_is_rejected(tmp_path, sample, fault):
    row = record(1, sample, () if fault == 'empty_hash' else (0, 1, 2, 4, 5))
    d = row['presentation_diagnostics']
    if fault in ('hash', 'empty_hash'):
        d['workspace_profile_sha256'] = 'f' * 64
    elif fault == 'duplicate_ids':
        d['marker_ids'].append(0)
    elif fault == 'missing_corner':
        del d['detected_corners_px']['0']
    elif fault == 'unknown_id':
        d['marker_ids'].append(17)
        d['detected_corners_px']['17'] = d['detected_corners_px']['0']
    elif fault == 'nonfinite':
        d['detected_corners_px']['0'][0][0] = float('nan')
    elif fault == 'resolution':
        d['image_size'] = [640, 480]
    else:
        d['frame_id'] = 2
    with pytest.raises(ValueError):
        api().replay_trace(write_rows(tmp_path, [row]), sample[0])


@pytest.mark.parametrize('kwargs', [dict(max_target_px=0), dict(max_target_mm=float('nan')),
                                   dict(first_frame=3, last_frame=2), dict(first_frame=9)])
def test_invalid_limits_or_empty_selection_are_rejected(tmp_path, sample, kwargs):
    with pytest.raises(ValueError):
        api().replay_trace(write_rows(tmp_path, [record(1, sample)]), sample[0], **kwargs)


def test_trace_mutation_during_replay_is_rejected(tmp_path, sample):
    path = write_rows(tmp_path, [record(1, sample)])
    module = api()
    original = module.selected_rows
    def changing(*args, **kwargs):
        yield from original(*args, **kwargs)
        with path.open('a', encoding='utf-8') as stream:
            stream.write('\n')
    with patch.object(module, 'selected_rows', changing), pytest.raises(ValueError, match='changed'):
        module.replay_trace(path, sample[0])


def test_cli_is_camera_free_create_exclusive_and_prints_only_summary(tmp_path, sample, capsys):
    path = write_rows(tmp_path, [record(722, sample)])
    output = tmp_path / 'report.json'
    camera, board = sample[2]
    argv = ['partial_marker_replay', '--results', str(path), '--camera-profile', str(camera),
            '--workspace-profile', str(board), '--first-frame', '722', '--last-frame', '1661',
            '--output', str(output)]
    with patch('sys.argv', argv), patch('cv2.VideoCapture', side_effect=AssertionError('camera forbidden')):
        assert api().main() == 0
        before = output.read_bytes()
        report = json.loads(before)
        assert len(report['source_trace_sha256']) == 64
        assert report['live_enabled'] is False
        summary = json.loads(capsys.readouterr().out)
        assert summary['output'] == str(output)
        assert 'records' not in summary
        with pytest.raises(SystemExit) as exc:
            api().main()
        assert exc.value.code == 2
    assert output.read_bytes() == before
