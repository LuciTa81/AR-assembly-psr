"""Synthetic truth is constructed independently of the joint fitter."""
from importlib import import_module, util
import json
from unittest.mock import patch

import cv2
import numpy as np
import pytest

from .test_display_fit import dataset, paired_dataset


def module():
    assert util.find_spec('server.realtime.display_joint_fit') is not None, 'Joint comparison module is not implemented'
    return import_module('server.realtime.display_joint_fit')


def truth(baseline=64.):
    rotation = cv2.Rodrigues(np.array([.06, -.09, .025]))[0]
    translation = np.array([12., -8., 30.])
    result = []
    for sign, cx, cy in ((1, 950., 470.), (-1, 970., 474.)):
        intrinsic = np.array([[1650., 0, cx], [0, 1580., cy], [0, 0, 1.]])
        offset = translation + [sign * baseline / 2, 0, 0]
        result.append(intrinsic @ np.column_stack([rotation, offset]))
    return result


def positions():
    return np.array([[x, y, z] for z in (400., 550., 700.)
                     for x, y in ((-90., -60.), (80., -60.), (-90., 90.), (80., 90.))])


def predict(matrices, xyz):
    homogeneous = np.column_stack([xyz, np.ones(len(xyz))])
    views = [homogeneous @ p.T for p in matrices]
    return np.stack([q[:, :2] / q[:, 2:] for q in views], axis=1)


def fitted_matrices(result):
    return [np.array(result['projections'][eye]) for eye in ('left', 'right')]


def test_joint_recovers_tilted_synthetic_truth_at_unseen_positions():
    xyz = positions()
    pixels = predict(truth(), xyz)
    result = module().fit_joint(xyz, pixels, pd_mm=64.)
    checks = np.array([[-20., 30., 480.], [40., -20., 610.]])
    np.testing.assert_allclose(predict(fitted_matrices(result), checks), predict(truth(), checks), atol=.01)
    assert not result['calibration_valid'] and not result['display_alignment_verified']
    assert result['pd_prior']['source'] == 'user_supplied_reference'
    assert result['pd_prior']['is_measured_uncertainty'] is False


def test_pd_is_soft_prior_not_a_rewritten_output_baseline():
    xyz = positions()
    result = module().fit_joint(xyz, predict(truth(72.), xyz), pd_mm=64., prior_scale_mm=100.)
    assert result['parameters']['baseline_mm'] > 68.
    assert result['pd_prior']['reference_mm'] == 64.
    assert result['fit_error_px']['max'] < .2


@pytest.mark.parametrize('bad', ['few', 'nan', 'plane', 'pixel_shape', 'behind', 'pd', 'prior'])
def test_invalid_or_degenerate_inputs_do_not_produce_joint_candidate(bad):
    xyz = positions()
    uv = predict(truth(), xyz)
    kwargs = dict(pd_mm=64., prior_scale_mm=5.)
    if bad == 'few': xyz, uv = xyz[:4], uv[:4]
    elif bad == 'nan': uv[0, 0, 0] = np.nan
    elif bad == 'plane': xyz[:, 2] = 500
    elif bad == 'pixel_shape': uv = uv[:, 0]
    elif bad == 'behind': xyz[0, 2] = -1
    elif bad == 'pd': kwargs['pd_mm'] = -64
    else: kwargs['prior_scale_mm'] = 0
    with pytest.raises(ValueError):
        module().fit_joint(xyz, uv, **kwargs)


def test_incompatible_eye_scales_are_visible_in_residuals_not_silently_dropped():
    xyz = positions()
    uv = predict(truth(), xyz)
    uv[:, 1, 1] = 474 + (uv[:, 1, 1] - 474) * 1.2
    result = module().fit_joint(xyz, uv, pd_mm=64.)
    assert result['fit_error_px']['max'] > 10
    assert 'large_fit_error' in result['warnings']
    assert len(result['fit_error_px']['per_pose']) == len(xyz)
    assert not result['display_alignment_verified']


def test_comparison_keeps_explicit_checks_out_of_fitting(tmp_path):
    paths = paired_dataset(tmp_path)
    before = module().compare_dataset(*paths, pd_mm=60., perturbations=0)
    filename = tmp_path / 'point-7-left.json'
    raw = json.loads(filename.read_text())
    raw['display']['right_x'] += 30
    filename.write_text(json.dumps(raw))
    after = module().compare_dataset(*paths, pd_mm=60., perturbations=0)
    assert before['joint']['check_error_px']['max'] < .01
    assert after['joint']['check_error_px']['max'] == pytest.approx(30., abs=.01)
    assert before['joint']['projections'] == after['joint']['projections']
    assert before['joint']['fit_error_px'] == after['joint']['fit_error_px']
    assert 'large_check_error' in after['joint']['warnings']
    assert after['check_pose_ids'] == ['pose-6', 'pose-7']
    assert not after['calibration_valid'] and not after['display_alignment_verified']
    json.dumps(after, allow_nan=False)


def test_leave_one_pose_out_removes_both_eyes_and_excludes_explicit_checks(tmp_path):
    paths = paired_dataset(tmp_path)
    original = module().fit_joint
    with patch.object(module(), 'fit_joint', wraps=original) as fit:
        report = module().compare_dataset(*paths, pd_mm=60., perturbations=0)
    calls = fit.call_args_list
    assert len(calls) == 7  # One main fit and six refits, never the two explicit checks.
    full = np.asarray(calls[0].args[0])
    assert len(full) == 6
    folds = report['leave_one_pose_out']['joint']['folds']
    for index, (fold, call) in enumerate(zip(folds, calls[1:])):
        np.testing.assert_array_equal(call.args[0], np.delete(full, index, axis=0))
        assert np.asarray(call.args[1]).shape == (5, 2, 2)
        assert fold['held_out_pose_id'] not in fold['training_pose_ids']
        assert fold['error_px']['max'] < .01
    dlt = report['leave_one_pose_out']['dlt']
    assert dlt['failure_count'] == 6 and dlt['success_count'] == 0
    assert all('six' in f['reason'] for f in dlt['folds'])


@pytest.mark.parametrize('bad', ['legacy', 'setup', 'binding'])
def test_comparison_uses_original_binding_and_paired_validation(tmp_path, bad):
    paths = dataset(tmp_path) if bad == 'legacy' else paired_dataset(tmp_path)
    if bad != 'legacy':
        filename = tmp_path / 'point-0-left.json'
        raw = json.loads(filename.read_text())
        if bad == 'setup': raw['setup_id'] = 'different-wearing'
        else: raw['observation']['workspace_profile_sha256'] = 'a' * 64
        filename.write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        module().compare_dataset(*paths, pd_mm=60., perturbations=0)


def test_perturbation_is_reproducible_and_does_not_mutate_observations():
    xyz = positions()
    uv = predict(truth(), xyz)
    original_xyz, original_uv = xyz.copy(), uv.copy()
    first = module().perturbation_review(xyz, uv, pd_mm=64., trials=2, seed=17)
    second = module().perturbation_review(xyz, uv, pd_mm=64., trials=2, seed=17)
    assert first == second
    np.testing.assert_array_equal(xyz, original_xyz)
    np.testing.assert_array_equal(uv, original_uv)
    for noise in ('screen_1px', 'camera_1mm'):
        for model in ('dlt', 'joint'):
            result = first[noise][model]
            assert result['success_count'] == 2 and result['failure_count'] == 0
            assert result['prediction_shift_px']['median'] >= 0
    assert first['is_optical_accuracy'] is False


def test_failed_refits_are_counted_not_hidden():
    xyz = positions()
    uv = predict(truth(), xyz)
    with patch.object(module(), 'fit_joint', side_effect=ValueError('diagnostic failure')):
        report = module().perturbation_review(xyz, uv, pd_mm=64., trials=2)
    assert report['screen_1px']['joint']['failure_count'] == 2
    assert report['screen_1px']['joint']['prediction_shift_px'] is None
    assert 'diagnostic failure' in report['screen_1px']['joint']['trials'][0]['reason']


def test_offline_run_writes_report_only_without_touching_inputs_or_opening_camera(tmp_path):
    paths = paired_dataset(tmp_path)
    originals = {p: p.read_bytes() for p in tmp_path.glob('*.json')}
    with patch.object(cv2, 'VideoCapture', side_effect=AssertionError('No camera')):
        directory = module().run_comparison(*paths, pd_mm=60., perturbations=0,
                                            output_root=tmp_path / 'results')
    report = json.loads((directory / 'report.json').read_text())
    assert report['schema_version'] == 'beast_joint_fit_comparison_v1'
    assert report['activation_status'] == 'not_activated'
    assert set(p.name for p in directory.iterdir()) == {'report.json'}
    assert all(p.read_bytes() == value for p, value in originals.items())
    from server.realtime.display_fit import probe_profile
    with pytest.raises(ValueError): probe_profile(report)


def test_held_out_prediction_risk_is_visible_in_comparison_summary(tmp_path):
    paths = paired_dataset(tmp_path)
    filename = tmp_path / 'point-0-left.json'
    raw = json.loads(filename.read_text())
    raw['display']['left_x'] += 40
    filename.write_text(json.dumps(raw))
    report = module().compare_dataset(*paths, pd_mm=60., perturbations=0)
    assert report['leave_one_pose_out']['joint']['held_out_rms_px']['max'] > 10
    assert 'large_leave_one_out_error' in report['warnings']
    assert 'dlt_leave_one_out_unavailable' in report['warnings']


def test_cli_cannot_export_or_activate_an_offline_candidate():
    with pytest.raises(SystemExit) as error:
        module().main(['--dataset', 'unused', '--camera-profile', 'unused', '--workspace', 'unused',
                       '--pd-mm', '64', '--export-probe'])
    assert error.value.code == 2


def test_residual_components_distinguish_shared_shift_from_eye_disparity():
    observed = np.array([[[800., 500.], [600., 500.]], [[900., 400.], [700., 400.]]])
    shift = np.array([[[1., 12.], [1., 12.]], [[3., 4.], [-3., -4.]]])
    predicted = observed + shift
    result = module()._error(predicted, observed)
    np.testing.assert_array_equal(result['predicted_px'], predicted)
    np.testing.assert_array_equal(result['observed_px'], observed)
    np.testing.assert_array_equal(result['residual_xy_px'], shift)
    np.testing.assert_array_equal(result['common_shift_xy_px'], [[1., 12.], [0., 0.]])
    np.testing.assert_array_equal(result['disparity_residual_xy_px'], [[0., 0.], [6., 8.]])
    assert result['residual_convention'] == 'predicted_minus_observed_x_right_y_down'
    assert result['rms'] == pytest.approx(np.sqrt(85.))


def test_residual_report_is_a_snapshot_without_mutating_inputs():
    observed = np.zeros((1, 2, 2))
    predicted = np.array([[[1., 2.], [3., 4.]]])
    before = predicted.copy()
    result = module()._error(predicted, observed)
    np.testing.assert_array_equal(predicted, before)
    np.testing.assert_array_equal(observed, np.zeros((1, 2, 2)))
    predicted[:] = 99
    observed[:] = 88
    np.testing.assert_array_equal(result['predicted_px'], before)
    np.testing.assert_array_equal(result['observed_px'], np.zeros((1, 2, 2)))


def test_report_predictions_can_be_replayed_by_pose_without_refitting_checks(tmp_path):
    report = module().compare_dataset(*paired_dataset(tmp_path), pd_mm=60., perturbations=0)
    for split in ('fit', 'check'):
        ids = report[split + '_pose_ids']
        xyz = [next(s['camera_xyz_mm'] for s in report['baseline_dlt']['samples']
                    if s['pose_id'] == pose_id and s['eye'] == 'left') for pose_id in ids]
        detail = report['joint'][split + '_error_px']
        np.testing.assert_allclose(detail['predicted_px'], predict(fitted_matrices(report['joint']), xyz))
        for i, pose_id in enumerate(ids):
            for j, eye in enumerate(('left', 'right')):
                sample = next(s for s in report['baseline_dlt']['samples']
                              if s['pose_id'] == pose_id and s['eye'] == eye)
                np.testing.assert_array_equal(detail['observed_px'][i][j], sample['eye_pixel'])
    assert report['activation_status'] == 'not_activated'
