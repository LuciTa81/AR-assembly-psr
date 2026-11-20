from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
import pytest

from .test_workspace_live_preview import profiles


def module():
    from server.realtime import display_fit
    return display_fit


def test_tracked_diagnostic_is_not_accepted_as_calibration_input(tmp_path):
    path = tmp_path / 'diagnostic-frame-1.json'
    path.write_text(json.dumps(dict(schema_version='beast_tracked_alignment_diagnostic_v1',
                                   candidate_only=True, calibration_valid=False,
                                   display_alignment_verified=False)))
    with pytest.raises(ValueError, match='Expected unverified correspondence'):
        module()._read_points(path, None, None, {})


@pytest.mark.parametrize('change', ['valid', 'motion', 'frame', 'setup'])
def test_single_eye_stability_evidence_is_checked_when_present(tmp_path, change):
    paths = dataset(tmp_path)
    filename = tmp_path / 'point-0-left.json'
    raw = json.loads(filename.read_text())
    raw['setup_id'] = 'unchanged-fit'
    raw['observation']['frame_id'] = 101
    raw['stability'] = dict(distinct_frames=4, first_frame_id=98, last_frame_id=101,
                            span_ms=300., max_target_delta_mm=0.)
    if change == 'motion': raw['stability']['max_target_delta_mm'] = 3.
    elif change == 'frame': raw['stability']['last_frame_id'] = 100
    elif change == 'setup': raw['setup_id'] = None
    filename.write_text(json.dumps(raw))
    from server.realtime.workspace_live_preview import load_profiles
    camera, workspace, metadata = load_profiles(paths[1], paths[2])
    binding = {key: metadata[key] for key in ('camera_profile_sha256', 'workspace_profile_sha256')}
    binding.update(camera_profile_id=camera.profile_id, workspace_profile_id=workspace.profile_id)
    if change == 'valid':
        sample = module()._read_points(filename, camera, workspace, binding)[0]
        assert sample['capture_mode'] == 'single_eye' and sample['frame_id'] == 101
    else:
        with pytest.raises(ValueError):
            module()._read_points(filename, camera, workspace, binding)


@pytest.mark.parametrize('other_setup', ['changed-fit', None])
def test_independent_eyes_do_not_mix_wearing_setups(tmp_path, other_setup):
    paths = dataset(tmp_path)
    for filename in tmp_path.glob('point-*.json'):
        raw = json.loads(filename.read_text())
        raw['setup_id'] = 'unchanged-fit' if raw['eye'] == 'left' else other_setup
        filename.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match='setup'):
        module().analyze_dataset(*paths)


def test_independent_eye_poses_predict_one_common_target_without_claiming_alignment(tmp_path):
    paths = dataset(tmp_path)
    from server.realtime.workspace_live_preview import load_profiles
    camera, _, _ = load_profiles(paths[1], paths[2])
    for filename in tmp_path.glob('point-*.json'):
        raw = json.loads(filename.read_text())
        raw['setup_id'] = 'unchanged-fit'
        if raw['eye'] == 'right':
            obs = raw['observation']
            xyz = np.array(obs['camera_xyz_mm']) + [12., -8., 30.]
            obs['camera_xyz_mm'] = xyz.tolist()
            obs['tvec_mm'] = (np.array(obs['tvec_mm']) + [12., -8., 30.]).tolist()
            obs['target_pixel'] = cv2.projectPoints(xyz.reshape(1, 3), np.zeros(3), np.zeros(3),
                camera.matrix, camera.distortion)[0].reshape(2).tolist()
            uv = project(projection('right'), [xyz])[0]
            raw['display']['right_x'], raw['display']['right_y'] = uv.tolist()
        filename.write_text(json.dumps(raw))
    report = module().analyze_dataset(*paths)
    for eye in ('left', 'right'):
        fitted = np.array(report['eyes'][eye]['projection'])
        np.testing.assert_allclose(project(fitted, [[10., 20., 520.]]),
                                   project(projection(eye), [[10., 20., 520.]]), atol=1e-7)
    assert not report['calibration_valid'] and not report['display_alignment_verified']


def test_probe_export_remains_explicit_unverified_and_flat(tmp_path):
    report = module().analyze_dataset(*dataset(tmp_path, 6, 0))
    assert callable(getattr(module(), 'probe_profile', None))
    profile = module().probe_profile(report)
    assert profile['schema_version'] == 'beast_candidate_projection_probe_v1'
    assert profile['candidate_only'] is True
    assert not profile['calibration_valid'] and not profile['display_alignment_verified']
    for eye in ('left', 'right'):
        assert len(profile[eye + '_projection']) == 12
        np.testing.assert_allclose(np.array(profile[eye + '_projection']).reshape(3, 4),
                                   report['eyes'][eye]['projection'])


@pytest.mark.parametrize('change', ['rejected', 'missing', 'activated'])
def test_probe_export_refuses_invalid_candidates(tmp_path, change):
    report = module().analyze_dataset(*dataset(tmp_path))
    if change == 'rejected': report['status'] = 'rejected_geometry'
    elif change == 'missing': report['eyes']['right']['projection'] = None
    else: report['calibration_valid'] = True
    assert callable(getattr(module(), 'probe_profile', None))
    with pytest.raises(ValueError):
        module().probe_profile(report)


def projection(eye='left'):
    return np.array([[1500., 0, 960, 45000 if eye == 'left' else -45000],
                     [0, 1510, 540, 0], [0, 0, 1, 0]])


def project(matrix, xyz):
    q = np.column_stack([xyz, np.ones(len(xyz))]) @ matrix.T
    return q[:, :2] / q[:, 2:]


def corrected_workspace(paths):
    import hashlib
    original = paths[2].read_bytes()
    data = json.loads(original)
    before = data['targets_mm']['A'][:]
    data['profile_id'] += '-A-correction'
    data['targets_mm']['A'] = (np.array(before) + [-2., -.45, 0.]).tolist()
    data['target_adjustment'] = dict(target='A', original_A_mm=before,
        parent_profile_sha256=hashlib.sha256(original).hexdigest())
    destination = paths[2].with_name('corrected-workspace.json')
    destination.write_text(json.dumps(data), encoding='utf-8')
    return destination


def test_retarget_refits_coordinates_preserves_sources_and_remains_unverified(tmp_path):
    paths = dataset(tmp_path)
    target = corrected_workspace(paths)
    original = module().analyze_dataset(*paths)
    before = {p: p.read_bytes() for p in tmp_path.glob('*.json')}
    assert callable(getattr(module(), 'analyze_retargeted_dataset', None))
    with patch('cv2.VideoCapture', side_effect=AssertionError('Camera must stay closed')):
        report = module().analyze_retargeted_dataset(*paths, target)
    assert all(p.read_bytes() == content for p, content in before.items())
    assert report['workspace_profile_id'].endswith('-A-correction')
    assert report['workspace_profile_sha256'] != original['workspace_profile_sha256']
    assert report['retarget_review']['source_workspace_sha256'] == original['workspace_profile_sha256']
    assert report['retarget_review']['new_wearing_validated'] is False
    for old, new in zip(original['samples'], report['samples']):
        raw = json.loads(before[Path(new['source_path'])])
        rotation = cv2.Rodrigues(np.array(raw['observation']['rvec']))[0]
        np.testing.assert_allclose(new['camera_xyz_mm'],
            np.array(old['camera_xyz_mm']) + rotation @ [-2., -.45, 0.])
        assert new['source_camera_xyz_mm'] == old['camera_xyz_mm']
        for key in ('eye_pixel', 'source_sha256', 'session_id', 'frame_id', 'pose_id', 'split'):
            assert new[key] == old[key]
    for eye in ('left', 'right'):
        assert report['eyes'][eye]['check_count'] == 2
        assert report['eyes'][eye]['fit_error_px']['rms'] < 1e-7
        assert report['eyes'][eye]['check_error_px']['rms'] < 1e-7
        assert not np.allclose(report['eyes'][eye]['projection'], original['eyes'][eye]['projection'])
    probe = module().probe_profile(report)
    assert probe['workspace_profile_sha256'] == report['workspace_profile_sha256']
    assert probe['candidate_only'] and not probe['calibration_valid'] and not probe['display_alignment_verified']


@pytest.mark.parametrize('change', ['marker', 'other_target', 'parent_hash', 'original_A', 'same_id'])
def test_retarget_rejects_changes_beyond_documented_A_correction(tmp_path, change):
    paths = dataset(tmp_path)
    target = corrected_workspace(paths)
    data = json.loads(target.read_text())
    if change == 'marker': data['marker_centers_mm']['0'][0] += 1
    elif change == 'other_target': data['targets_mm']['B'] = [99, 99, 60]
    elif change == 'parent_hash': data['target_adjustment']['parent_profile_sha256'] = '0' * 64
    elif change == 'original_A': data['target_adjustment']['original_A_mm'][0] += 1
    else: data['profile_id'] = json.loads(paths[2].read_text())['profile_id']
    target.write_text(json.dumps(data))
    assert callable(getattr(module(), 'analyze_retargeted_dataset', None))
    with pytest.raises(ValueError):
        module().analyze_retargeted_dataset(*paths, target)


def test_retarget_does_not_use_checks_to_improve_fit(tmp_path):
    paths = dataset(tmp_path)
    target = corrected_workspace(paths)
    assert callable(getattr(module(), 'analyze_retargeted_dataset', None))
    before = module().analyze_retargeted_dataset(*paths, target)
    point = tmp_path / 'point-7-left.json'
    raw = json.loads(point.read_text())
    raw['display']['left_x'] += 100
    point.write_text(json.dumps(raw))
    after = module().analyze_retargeted_dataset(*paths, target)
    np.testing.assert_array_equal(after['eyes']['left']['projection'], before['eyes']['left']['projection'])
    assert after['eyes']['left']['check_error_px']['max'] > 99


def points():
    return np.array([[-90, -60, 400], [70, -50, 440], [-80, 100, 480],
                     [90, 110, 550], [-50, 40, 650], [60, -60, 610],
                     [20, 70, 510], [-20, -30, 570]], dtype=float)


def dataset(tmp_path, fit_count=6, check_count=2):
    from server.realtime.workspace_live_preview import load_profiles
    cam_path, workspace_path = profiles(tmp_path)
    camera, workspace, metadata = load_profiles(cam_path, workspace_path)
    binding = {key: metadata[key] for key in ('camera_profile_sha256', 'workspace_profile_sha256')}
    binding.update(camera_profile_id=camera.profile_id, workspace_profile_id=workspace.profile_id)
    entries = []
    for index, xyz in enumerate(points()[:fit_count + check_count]):
        world = workspace.targets['A']
        rvec = np.array([np.pi, 0, 0])
        tvec = xyz - cv2.Rodrigues(rvec)[0] @ world
        camera_pixel = cv2.projectPoints(np.array([world]), rvec, tvec, camera.matrix, camera.distortion)[0].reshape(2)
        for eye_index, eye in enumerate(('left', 'right')):
            pixels = {name: project(projection(name), [xyz])[0] for name in ('left', 'right')}
            raw = dict(schema_version='beast_display_correspondence_candidate_v1', candidate_only=True,
                calibration_valid=False, display_alignment_verified=False, eye=eye,
                output_width=3840, output_height=1080, request_started_seconds=10.,
                response_received_seconds=10.025, request_rtt_ms=25., conservative_age_ms=65.,
                display=dict(coordinate_convention='eye_local_pixels_top_left',
                    channel_order='left_half_left_eye_right_half_right_eye', channels_confirmed_by_user=True,
                    selected_view=eye.title(), framebuffer_width=3840, eye_width=1920, height=1080,
                    left_x=pixels['left'][0], left_y=pixels['left'][1],
                    right_x=pixels['right'][0], right_y=pixels['right'][1]),
                observation=dict(binding, schema_version='beast_display_observation_v1', session_id='fixture',
                    target_id='A', status='tracking', frame_id=index * 2 + eye_index + 1,
                    age_ms=40., rms_px=.1, max_error_px=.2, image_size=[1280, 720],
                    marker_ids=list(workspace.markers), marker_count=len(workspace.markers),
                    rvec=rvec.tolist(), tvec_mm=tvec.tolist(), world_xyz_mm=world.tolist(),
                    camera_xyz_mm=xyz.tolist(), target_pixel=camera_pixel.tolist()))
            filename = f'point-{index}-{eye}.json'
            (tmp_path / filename).write_text(json.dumps(raw), encoding='utf-8')
            entries.append(dict(path=filename, pose_id=f'pose-{index}', split='fit' if index < fit_count else 'check'))
    manifest = tmp_path / 'dataset.json'
    manifest.write_text(json.dumps(dict(schema_version='beast_display_fit_dataset_v1', points=entries)), encoding='utf-8')
    return manifest, cam_path, workspace_path


@pytest.mark.parametrize('eye', ['left', 'right'])
def test_normalized_projection_recovers_unseen_positions(eye):
    xyz = points()
    matrix = module().fit_projection(xyz[:6], project(projection(eye), xyz[:6]))
    np.testing.assert_allclose(project(matrix, xyz[6:]), project(projection(eye), xyz[6:]), atol=1e-7)


def test_projection_is_invariant_to_world_units_and_translation():
    xyz = points()
    uv = project(projection(), xyz)
    transformed = xyz * 1000 + [2e6, -3e6, 1e6]
    matrix = module().fit_projection(transformed[:6], uv[:6])
    np.testing.assert_allclose(project(matrix, transformed[6:]), uv[6:], atol=1e-6)


@pytest.mark.parametrize('kind', ['few', 'coplanar', 'repeats', 'nan', 'line_pixels'])
def test_degenerate_data_does_not_produce_projection(kind):
    xyz = points()[:6].copy()
    uv = project(projection(), xyz)
    if kind == 'few': xyz, uv = xyz[:3], uv[:3]
    elif kind == 'coplanar': xyz[:, 2] = 500
    elif kind == 'repeats': xyz, uv = np.tile(xyz[:3], (2, 1)), np.tile(uv[:3], (2, 1))
    elif kind == 'nan': xyz[0, 0] = np.nan
    else: uv[:, 1] = 600
    with pytest.raises(ValueError):
        module().fit_projection(xyz, uv)


def test_insufficient_data_reports_counts_without_fabricating_matrices(tmp_path):
    paths = dataset(tmp_path, fit_count=3, check_count=0)
    report = module().analyze_dataset(*paths)
    assert report['status'] == 'needs_fit_points'
    for eye in ('left', 'right'):
        assert report['eyes'][eye]['fit_count'] == 3
        assert report['eyes'][eye]['additional_fit_points_minimum'] == 3
        assert report['eyes'][eye]['additional_check_points_minimum'] == 2
        assert report['eyes'][eye]['projection'] is None
    assert not report['calibration_valid'] and not report['display_alignment_verified']


def test_candidate_is_not_activated_and_holdouts_are_separate(tmp_path):
    paths = dataset(tmp_path)
    report = module().analyze_dataset(*paths)
    assert report['status'] == 'candidate_fitted'
    assert report['activation_status'] == 'not_activated'
    assert not report['calibration_valid'] and not report['display_alignment_verified']
    for eye in ('left', 'right'):
        result = report['eyes'][eye]
        assert result['fit_count'] == 6 and result['check_count'] == 2
        assert result['fit_error_px']['rms'] < 1e-7
        assert result['check_error_px']['rms'] < 1e-7
    from server.realtime.display_calibration import SyntheticDisplayProfile
    with pytest.raises(ValueError):
        SyntheticDisplayProfile.from_dict(report)
    json.dumps(report, allow_nan=False)


def test_large_holdout_errors_are_reported_not_refitted(tmp_path):
    paths = dataset(tmp_path)
    filename = tmp_path / 'point-7-left.json'
    raw = json.loads(filename.read_text())
    raw['display']['left_x'] += 100
    filename.write_text(json.dumps(raw))
    report = module().analyze_dataset(*paths)
    assert report['eyes']['left']['check_error_px']['max'] == pytest.approx(100)
    assert report['eyes']['left']['fit_error_px']['max'] < 1e-7
    assert not report['calibration_valid']


@pytest.mark.parametrize('bad', ['eye', 'binding', 'stale', 'selected_view', 'xyz', 'size',
                                'target_outside', 'target_nonfinite', 'target_mismatch', 'marker_count'])
def test_invalid_correspondence_rejected_before_fitting(tmp_path, bad):
    paths = dataset(tmp_path)
    filename = tmp_path / 'point-0-left.json'
    raw = json.loads(filename.read_text())
    if bad == 'eye': raw['eye'] = 'both'
    elif bad == 'binding': raw['observation']['workspace_profile_sha256'] = 'a' * 64
    elif bad == 'stale': raw['conservative_age_ms'] = 151
    elif bad == 'selected_view': raw['display']['selected_view'] = 'Right'
    elif bad == 'xyz': raw['observation']['camera_xyz_mm'][0] += 10
    elif bad == 'size': raw['output_width'] = 1920
    elif bad == 'target_outside': raw['observation']['target_pixel'] = [-9999, 9999]
    elif bad == 'target_nonfinite': raw['observation']['target_pixel'] = [float('nan'), float('inf')]
    elif bad == 'target_mismatch': raw['observation']['target_pixel'][0] += 10
    else: raw['observation']['marker_count'] = 0
    filename.write_text(json.dumps(raw))
    with pytest.raises(ValueError): module().analyze_dataset(*paths)


@pytest.mark.parametrize('bad', ['duplicate_file', 'duplicate_pose_eye', 'split_leakage'])
def test_repeated_samples_cannot_masquerade_as_independent_fit_or_check_points(tmp_path, bad):
    paths = dataset(tmp_path)
    raw = json.loads(paths[0].read_text())
    if bad == 'duplicate_file': raw['points'].append(copy.deepcopy(raw['points'][0]))
    elif bad == 'duplicate_pose_eye': raw['points'][2]['pose_id'] = raw['points'][0]['pose_id']
    else: raw['points'][1]['split'] = 'check'
    paths[0].write_text(json.dumps(raw))
    with pytest.raises(ValueError): module().analyze_dataset(*paths)


def test_command_writes_only_review_and_never_opens_camera(tmp_path):
    paths = dataset(tmp_path, fit_count=3, check_count=0)
    originals = {p: p.read_bytes() for p in tmp_path.glob('*.json')}
    with patch.object(cv2, 'VideoCapture', side_effect=AssertionError('No camera')):
        output = module().run_fit(*paths, output_root=tmp_path / 'results')
    report = json.loads((output / 'report.json').read_text())
    assert report['status'] == 'needs_fit_points'
    assert set(p.name for p in output.iterdir()) == {'report.json'}
    assert all(p.read_bytes() == value for p, value in originals.items())


def paired_dataset(tmp_path):
    paths = dataset(tmp_path)
    manifest = json.loads(paths[0].read_text())
    entries = []
    for entry in manifest['points'][::2]:
        source = tmp_path / entry['path']
        raw = json.loads(source.read_text())
        raw.update(schema_version='beast_display_correspondence_pair_v2', eye='both',
                   binocular_confirmed_by_user=True, setup_id='fixed-fit-and-osd',
                   stability=dict(distinct_frames=4, first_frame_id=1,
                                  last_frame_id=raw['observation']['frame_id'] + 100,
                                  span_ms=300., max_target_delta_mm=.5))
        raw['observation']['frame_id'] += 100
        raw['observation']['session_id'] = entry['pose_id']
        raw['display'].update(selected_view='Both', left_marked=True, right_marked=True)
        source.write_text(json.dumps(raw))
        entries.append(entry)
    manifest['points'] = entries
    paths[0].write_text(json.dumps(manifest))
    return paths


def test_pair_reader_expands_both_eyes_from_one_observation(tmp_path):
    report = module().analyze_dataset(*paired_dataset(tmp_path))
    assert len(report['samples']) == 16
    for a, b in zip(report['samples'][::2], report['samples'][1::2]):
        assert (a['eye'], b['eye']) == ('left', 'right')
        assert a['camera_xyz_mm'] == b['camera_xyz_mm']
        assert a['source_sha256'] == b['source_sha256']
        assert a['capture_mode'] == b['capture_mode'] == 'paired'
    assert report['collection_review']['paired_pose_count'] == 8
    assert not report['display_alignment_verified']


@pytest.mark.parametrize('change', ['confirmation', 'mark', 'stable_count', 'stable_span',
                                  'stable_delta', 'stable_frame', 'eye', 'legacy_both'])
def test_pair_requires_explicit_confirmation_and_stable_evidence(tmp_path, change):
    paths = paired_dataset(tmp_path)
    source = tmp_path / 'point-0-left.json'
    raw = json.loads(source.read_text())
    if change == 'confirmation': raw['binocular_confirmed_by_user'] = False
    elif change == 'mark': raw['display']['right_marked'] = False
    elif change == 'stable_count': raw['stability']['distinct_frames'] = 2
    elif change == 'stable_span': raw['stability']['span_ms'] = 30
    elif change == 'stable_delta': raw['stability']['max_target_delta_mm'] = 2.1
    elif change == 'stable_frame': raw['stability']['last_frame_id'] += 1
    elif change == 'eye': raw['eye'] = 'left'
    else: raw['schema_version'] = 'beast_display_correspondence_candidate_v1'
    source.write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        module().analyze_dataset(*paths)


def test_report_separates_geometric_fit_from_collection_readiness(tmp_path):
    report = module().analyze_dataset(*dataset(tmp_path))
    assert report['status'] == 'candidate_fitted'
    assert report['collection_review']['status'] == 'needs_review'
    assert 'legacy_single_eye_samples' in report['collection_review']['warnings']
    assert 'limited_fit_count' in report['collection_review']['warnings']
    assert 'limited_check_count' in report['collection_review']['warnings']
    geometry = report['stereo_geometry']
    assert geometry['center_separation_mm'] == pytest.approx(60.)
    assert geometry['right_minus_left_mm'] == pytest.approx([60., 0., 0.])
    assert geometry['interpretation'] == 'fitted_pinhole_centers_not_measured_ipd'
    for result in report['eyes'].values():
        assert result['fit_depth_range_mm'] == [400., 650.]
        assert len(result['check_errors_by_depth']) == 2


def test_implausible_fitted_geometry_is_a_warning_not_a_measured_ipd(tmp_path):
    paths = dataset(tmp_path)
    for source in tmp_path.glob('point-*-right.json'):
        raw = json.loads(source.read_text())
        xyz = raw['observation']['camera_xyz_mm']
        matrix = projection('right')
        matrix[0, 3] = -210000
        uv = project(matrix, [xyz])[0]
        raw['display'].update(right_x=float(uv[0]), right_y=float(uv[1]))
        source.write_text(json.dumps(raw))
    report = module().analyze_dataset(*paths)
    assert 'implausible_stereo_geometry' in report['collection_review']['warnings']
    assert not report['calibration_valid']


def test_pair_check_disparity_errors_are_not_hidden_by_training_fit(tmp_path):
    paths = paired_dataset(tmp_path)
    source = tmp_path / 'point-7-left.json'
    raw = json.loads(source.read_text())
    raw['display']['right_x'] += 30
    source.write_text(json.dumps(raw))
    report = module().analyze_dataset(*paths)
    assert report['stereo_check']['pair_count'] == 2
    assert report['stereo_check']['horizontal_disparity_error_px']['max'] == pytest.approx(30.)
    assert 'large_check_error' in report['collection_review']['warnings']
    assert report['eyes']['right']['fit_error_px']['max'] < 1e-7


@pytest.mark.parametrize('setup', [None, '', 'changed-screen-distance'])
def test_pair_datasets_cannot_mix_missing_or_changed_setup(tmp_path, setup):
    paths = paired_dataset(tmp_path)
    source = tmp_path / 'point-7-left.json'
    raw = json.loads(source.read_text())
    raw['setup_id'] = setup
    source.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match='setup'):
        module().analyze_dataset(*paths)


def test_pair_manifest_builder_preserves_sources_and_explicit_splits(tmp_path):
    paired_dataset(tmp_path)
    sources = []
    for i in range(8):
        source = tmp_path / f'point-{i}-left.json'
        raw = json.loads(source.read_text())
        raw['observation']['session_id'] = f'pose-{i}'
        source.write_text(json.dumps(raw))
        sources.append(source)
    output = tmp_path / 'selected.json'
    assert callable(getattr(module(), 'create_pair_dataset', None))
    originals = [s.read_bytes() for s in sources]
    module().create_pair_dataset(output, sources[:6], sources[6:])
    manifest = json.loads(output.read_text())
    assert [p['split'] for p in manifest['points']] == ['fit'] * 6 + ['check'] * 2
    assert all(s.read_bytes() == raw for s, raw in zip(sources, originals))
    with pytest.raises(FileExistsError):
        module().create_pair_dataset(output, sources[:6], sources[6:])


def test_pair_manifest_rejects_same_pose_across_splits_before_writing(tmp_path):
    paired_dataset(tmp_path)
    source = tmp_path / 'point-1-left.json'
    raw = json.loads(source.read_text())
    raw['observation']['session_id'] = 'pose-0'
    source.write_text(json.dumps(raw))
    assert callable(getattr(module(), 'create_pair_dataset', None))
    output = tmp_path / 'selected.json'
    with pytest.raises(ValueError, match='pose'):
        module().create_pair_dataset(output, [tmp_path / 'point-0-left.json'], [tmp_path / 'point-1-left.json'])
    assert not output.exists()


def test_renaming_pose_groups_does_not_leak_one_pair_session_into_checks(tmp_path):
    paths = paired_dataset(tmp_path)
    source = tmp_path / 'point-7-left.json'
    raw = json.loads(source.read_text())
    raw['observation']['session_id'] = 'pose-0'
    source.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match='session'):
        module().analyze_dataset(*paths)
