"""Offline shared-rig comparison only; no device access or profile export."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import cv2
import numpy as np
from scipy.optimize import least_squares

from .camera_calibration import stamp, write_json
from .display_fit import _require, analyze_dataset, fit_projection

EYES = ('left', 'right')
PARAMETERS = ('rx', 'ry', 'rz', 'tx_mm', 'ty_mm', 'tz_mm', 'fx_px', 'fy_px',
              'cx_left_px', 'cy_left_px', 'cx_right_px', 'cy_right_px', 'baseline_mm')
LOWER = np.array([-.6] * 3 + [-300.] * 3 + [200., 200., -1920., -1080., -1920., -1080., 20.])
UPPER = np.array([.6] * 3 + [300.] * 3 + [10000., 10000., 3840., 2160., 3840., 2160., 120.])
SCALES = np.array([.2] * 3 + [100.] * 3 + [2000., 2000., 1000., 1000., 1000., 1000., 64.])
FIT_ERRORS = (ValueError, np.linalg.LinAlgError, cv2.error)


def _matrices(parameters):
    rotation = cv2.Rodrigues(parameters[:3])[0]
    result = {}
    for eye, sign, start in (('left', 1., 8), ('right', -1., 10)):
        intrinsic = np.array([[parameters[6], 0., parameters[start]],
                              [0., parameters[7], parameters[start + 1]], [0., 0., 1.]])
        translation = parameters[3:6].copy()
        translation[0] += sign * parameters[12] / 2.
        result[eye] = intrinsic @ np.column_stack([rotation, translation])
    return result


def _predict(matrices, xyz):
    homogeneous = np.column_stack([xyz, np.ones(len(xyz))])
    result = []
    for eye in EYES:
        q = homogeneous @ matrices[eye].T
        _require(np.isfinite(q).all() and (q[:, 2] > 1e-6).all(), 'Invalid joint projection depth')
        result.append(q[:, :2] / q[:, 2:])
    return np.stack(result, axis=1)


def _error(predicted, observed):
    delta = predicted - observed
    residual = np.linalg.norm(delta, axis=2)
    return dict(rms=float(np.sqrt(np.mean(residual ** 2))), max=float(residual.max()),
                per_pose=residual.tolist(),
                residual_convention='predicted_minus_observed_x_right_y_down',
                predicted_px=predicted.tolist(), observed_px=observed.tolist(),
                residual_xy_px=delta.tolist(),
                common_shift_xy_px=delta.mean(axis=1).tolist(),
                disparity_residual_xy_px=(delta[:, 0] - delta[:, 1]).tolist(),
                per_eye={eye: dict(rms=float(np.sqrt(np.mean(residual[:, i] ** 2))),
                                   max=float(residual[:, i].max()))
                         for i, eye in enumerate(EYES)})


def fit_joint(xyz, pixels, *, pd_mm: float, prior_scale_mm: float = 5.) -> dict:
    """Shared rotation/focal lengths, separate image offsets, and a soft baseline prior."""
    xyz, pixels = np.asarray(xyz, float), np.asarray(pixels, float)
    _require(xyz.ndim == 2 and xyz.shape[1:] == (3,) and len(xyz) >= 5,
             'At least five paired 3D points required')
    _require(pixels.shape == (len(xyz), 2, 2) and np.isfinite(xyz).all()
             and np.isfinite(pixels).all() and (xyz[:, 2] > 0).all(), 'Invalid paired coordinates')
    _require(np.isfinite([pd_mm, prior_scale_mm]).all() and 20 < pd_mm < 120
             and prior_scale_mm > 0, 'Invalid PD reference or prior scale')
    singular = np.linalg.svd(xyz - xyz.mean(axis=0), compute_uv=False)
    _require(singular[0] > 1e-9 and singular[-1] / singular[0] > 1e-3,
             'Degenerate joint fit geometry')

    # Explicit solver weights are assumptions, not measured optical uncertainties.
    pixel_scale = 2.
    def residual(parameters):
        rotation = cv2.Rodrigues(parameters[:3])[0]
        q = xyz @ rotation.T + parameters[3:6]
        depth = np.maximum(q[:, 2], 1.)
        predicted = np.empty_like(pixels)
        for i, sign, start in ((0, 1., 8), (1, -1., 10)):
            predicted[:, i, 0] = parameters[6] * (q[:, 0] + sign * parameters[12] / 2) / depth + parameters[start]
            predicted[:, i, 1] = parameters[7] * q[:, 1] / depth + parameters[start + 1]
        return np.r_[(predicted - pixels).ravel() / pixel_scale,
                     (parameters[12] - pd_mm) / prior_scale_mm,
                     np.maximum(1. - q[:, 2], 0.) * 100.]

    normalized = np.column_stack([xyz[:, :2] / xyz[:, 2:], np.ones(len(xyz))])
    slopes = np.linalg.lstsq(normalized, pixels.mean(axis=1), rcond=None)[0]
    focal = np.clip([slopes[0, 0], slopes[1, 1]], 500., 6000.)
    seed = np.r_[np.zeros(6), focal, slopes[2], slopes[2], pd_mm]
    disparity = (pixels[:, 0] - pixels[:, 1]).mean(axis=0)
    seed[8] += (disparity[0] - focal[0] * pd_mm / xyz[:, 2].mean()) / 2
    seed[10] -= (disparity[0] - focal[0] * pd_mm / xyz[:, 2].mean()) / 2
    seed[9] += disparity[1] / 2
    seed[11] -= disparity[1] / 2
    fits = []
    for z_start in (0., -50., 50.):
        start = np.clip(seed, LOWER + .001, UPPER - .001)
        start[5] = z_start
        fitted = least_squares(residual, start, bounds=(LOWER, UPPER), x_scale=SCALES,
                               loss='linear', max_nfev=600, ftol=1e-9, xtol=1e-9, gtol=1e-9)
        if fitted.success and np.isfinite(fitted.x).all():
            try:
                _predict(_matrices(fitted.x), xyz)
            except ValueError:
                continue
            fits.append(fitted)
    _require(bool(fits), 'Joint optimizer did not converge to a positive-depth candidate')
    best = min(fits, key=lambda value: value.cost)
    matrices = _matrices(best.x)
    error = _error(_predict(matrices, xyz), pixels)
    data_singular = np.linalg.svd(best.jac[:pixels.size] * SCALES, compute_uv=False)
    ratio = float(data_singular[-1] / data_singular[0])
    bounds_hit = [name for name, hit in zip(PARAMETERS, best.active_mask) if hit]
    warnings = []
    if ratio < 1e-6: warnings.append('weak_data_identifiability')
    if bounds_hit: warnings.append('solver_bound_hit')
    if error['max'] > 10: warnings.append('large_fit_error')
    rotation = cv2.Rodrigues(best.x[:3])[0]
    midpoint = -rotation.T @ best.x[3:6]
    half_baseline = rotation.T @ np.array([best.x[12] / 2., 0., 0.])
    return dict(model='shared_parallel_rig_soft_pd_v1', candidate_only=True,
                calibration_valid=False, display_alignment_verified=False, activation_status='not_activated',
                parameters=dict(zip(PARAMETERS, best.x.tolist())),
                projections={eye: matrix.tolist() for eye, matrix in matrices.items()},
                fit_error_px=error, warnings=warnings,
                pd_prior=dict(reference_mm=float(pd_mm), scale_mm=float(prior_scale_mm),
                              source='user_supplied_reference', distance_type='unspecified',
                              is_measured_uncertainty=False, hard_fixed=False),
                geometry=dict(left_center_camera_mm=(midpoint - half_baseline).tolist(),
                              right_center_camera_mm=(midpoint + half_baseline).tolist(),
                              separation_mm=float(best.x[12]),
                              interpretation='Prior-constrained model geometry, not independently measured IPD'),
                assumptions=['Shared eye orientation and fx/fy, zero skew, horizontal baseline in the eye frame.',
                             'Independent left/right image offsets; not assumed symmetric about the camera.',
                             'No prescription-lens distortion model; optical compatibility is unverified.',
                             'PD prior and solver bounds do not establish optical validity.'],
                solver=dict(method='scipy_least_squares_trf', loss='linear', start_count=3,
                            successful_starts=len(fits), nfev=int(best.nfev), cost=float(best.cost),
                            pixel_residual_scale_px=pixel_scale, bounds_hit=bounds_hit,
                            bounds={name: [float(lo), float(hi)] for name, lo, hi in zip(PARAMETERS, LOWER, UPPER)},
                            data_scaled_singular_values=data_singular.tolist(),
                            data_scaled_min_max_ratio=ratio))


def _fit_matrices(model, xyz, pixels, pd_mm, prior_scale_mm):
    if model == 'dlt':
        return {eye: fit_projection(xyz, pixels[:, i]) for i, eye in enumerate(EYES)}
    result = fit_joint(xyz, pixels, pd_mm=pd_mm, prior_scale_mm=prior_scale_mm)
    return {eye: np.array(result['projections'][eye]) for eye in EYES}


def _summary(values):
    return (dict(median=float(np.median(values)), p95=float(np.percentile(values, 95)),
                 max=float(np.max(values))) if values else None)


def _leave_one_out(xyz, pixels, ids, pd_mm, prior_scale_mm):
    review = dict(is_independent_optical_validation=False,
                  note='Diagnostic refits of fit poses only; not new observations or a comfort test.')
    for model in ('joint', 'dlt'):
        folds = []
        for index, pose_id in enumerate(ids):
            mask = np.arange(len(ids)) != index
            fold = dict(held_out_pose_id=pose_id, training_pose_ids=[p for j, p in enumerate(ids) if mask[j]])
            try:
                matrices = _fit_matrices(model, xyz[mask], pixels[mask], pd_mm, prior_scale_mm)
                fold.update(status='evaluated', error_px=_error(_predict(matrices, xyz[~mask]), pixels[~mask]))
            except FIT_ERRORS as exc:
                fold.update(status='unavailable', reason=str(exc), error_px=None)
            folds.append(fold)
        errors = [f['error_px']['rms'] for f in folds if f['error_px'] is not None]
        review[model] = dict(folds=folds, success_count=len(errors), failure_count=len(folds) - len(errors),
                             held_out_rms_px=_summary(errors))
    return review


def perturbation_review(xyz, pixels, *, pd_mm, prior_scale_mm=5., trials=16, seed=64):
    """Same artificial noise for both models; evaluate at the unchanged fit centroid."""
    _require(type(trials) is int and 0 <= trials <= 128, 'Perturbation trials must be between 0 and 128')
    xyz, pixels = np.asarray(xyz, float), np.asarray(pixels, float)
    probe = xyz.mean(axis=0, keepdims=True)
    report = dict(seed=seed, trials_per_noise=trials, probe_camera_xyz_mm=probe[0].tolist(),
                  is_optical_accuracy=False,
                  note='Gaussian independent coordinate noise; not measured noise or confidence intervals. '
                       'Shifts are relative to each unperturbed fit at its fit centroid, not ground truth.')
    if trials == 0:
        return dict(report, status='not_requested')
    rng, reference = np.random.default_rng(seed), {}
    for model in ('joint', 'dlt'):
        try:
            reference[model] = _predict(_fit_matrices(model, xyz, pixels, pd_mm, prior_scale_mm), probe)
        except FIT_ERRORS as exc:
            reference[model] = str(exc)
    for noise in ('screen_1px', 'camera_1mm'):
        outcomes = {model: [] for model in reference}
        for trial in range(trials):
            noisy_xyz, noisy_pixels = xyz.copy(), pixels.copy()
            if noise == 'screen_1px':
                noisy_pixels += rng.normal(0., 1., pixels.shape)
            else:
                # A paired save shares one 3D observation; do not perturb eyes separately.
                noisy_xyz += rng.normal(0., 1., xyz.shape)
            for model, baseline in reference.items():
                result = dict(trial=trial)
                try:
                    _require(not isinstance(baseline, str), f'Unperturbed fit unavailable: {baseline}')
                    matrices = _fit_matrices(model, noisy_xyz, noisy_pixels, pd_mm, prior_scale_mm)
                    predicted = _predict(matrices, probe)
                    centers = [-np.linalg.solve(matrices[e][:, :3], matrices[e][:, 3]) for e in EYES]
                    result.update(status='evaluated', prediction_shift_px=_error(predicted, baseline)['rms'],
                                  separation_mm=float(np.linalg.norm(centers[1] - centers[0])))
                except FIT_ERRORS as exc:
                    result.update(status='unavailable', reason=str(exc))
                outcomes[model].append(result)
        report[noise] = {}
        for model, results in outcomes.items():
            successful = [r for r in results if r['status'] == 'evaluated']
            report[noise][model] = dict(trials=results, success_count=len(successful),
                failure_count=trials - len(successful),
                prediction_shift_px=_summary([r['prediction_shift_px'] for r in successful]),
                separation_mm=_summary([r['separation_mm'] for r in successful]))
    return report


def compare_dataset(dataset_path, camera_path, workspace_path, *, pd_mm, prior_scale_mm=5.,
                    perturbations=16, seed=64):
    """Reuse the original strict reader; fit/check membership is never inferred or changed."""
    dlt = analyze_dataset(dataset_path, camera_path, workspace_path)
    _require(all(s['capture_mode'] == 'paired' for s in dlt['samples']), 'Joint comparison requires paired records')
    groups = {}
    for sample in dlt['samples']:
        groups.setdefault(sample['pose_id'], {})[sample['eye']] = sample
    poses = []
    for pose_id, pair in groups.items():
        _require(set(pair) == set(EYES), 'Incomplete eye pair')
        left, right = pair['left'], pair['right']
        _require(left['camera_xyz_mm'] == right['camera_xyz_mm']
                 and left['source_sha256'] == right['source_sha256'], 'Pair must share one saved observation')
        poses.append(dict(pose_id=pose_id, split=left['split'], xyz=left['camera_xyz_mm'],
                          pixels=[pair[eye]['eye_pixel'] for eye in EYES]))
    fit, check = ([p for p in poses if p['split'] == split] for split in ('fit', 'check'))
    _require(len(fit) >= 5, 'At least five fit poses required')
    xyz = np.array([p['xyz'] for p in fit])
    pixels = np.array([p['pixels'] for p in fit])
    joint = fit_joint(xyz, pixels, pd_mm=pd_mm, prior_scale_mm=prior_scale_mm)
    joint['check_error_px'] = None
    if check:
        try:
            matrices = {eye: np.array(joint['projections'][eye]) for eye in EYES}
            joint['check_error_px'] = _error(_predict(matrices, np.array([p['xyz'] for p in check])),
                                            np.array([p['pixels'] for p in check]))
            if joint['check_error_px']['max'] > 10:
                joint['warnings'].append('large_check_error')
        except FIT_ERRORS as exc:
            joint['check_failure_reason'] = str(exc)
            joint['warnings'].append('invalid_check_projection')
    else:
        joint['warnings'].append('no_independent_check_poses')
    ids = [p['pose_id'] for p in fit]
    leave_one_out = _leave_one_out(xyz, pixels, ids, pd_mm, prior_scale_mm)
    sensitivity = perturbation_review(xyz, pixels, pd_mm=pd_mm, prior_scale_mm=prior_scale_mm,
                                      trials=perturbations, seed=seed)
    warnings = list(joint['warnings'])
    for model in ('joint', 'dlt'):
        if leave_one_out[model]['failure_count']:
            warnings.append(model + '_leave_one_out_unavailable')
        if any(f['error_px'] and f['error_px']['max'] > 10 for f in leave_one_out[model]['folds']):
            warnings.append('large_leave_one_out_error')
        if any(sensitivity.get(noise, {}).get(model, {}).get('failure_count', 0)
               for noise in ('screen_1px', 'camera_1mm')):
            warnings.append(model + '_perturbation_failures')
    return dict(schema_version='beast_joint_fit_comparison_v1', candidate_only=True,
                status='offline_comparison_only', calibration_valid=False, display_alignment_verified=False,
                activation_status='not_activated', fit_pose_ids=ids,
                check_pose_ids=[p['pose_id'] for p in check], baseline_dlt=dlt, joint=joint,
                leave_one_pose_out=leave_one_out, perturbation=sensitivity, warnings=sorted(set(warnings)),
                threshold_note='10px warning is a diagnostic heuristic, not an optical acceptance criterion.',
                limitations=['This report cannot be exported as a runtime display profile.',
                             'Lower sensitivity can result from model constraints and does not establish accuracy.',
                             'Prescription insert effects and wearing changes are not estimated.'])


def run_comparison(dataset_path, camera_path, workspace_path, *, output_root=None, **options):
    report = compare_dataset(dataset_path, camera_path, workspace_path, **options)
    root = output_root or Path(os.environ['LOCALAPPDATA']) / 'ARAssembly/beast-mvp/display_fits'
    directory = Path(root) / ('joint-' + stamp())
    directory.mkdir(parents=True, exist_ok=False)
    write_json(directory / 'report.json', report)
    return directory


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--camera-profile', type=Path, required=True)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--pd-mm', type=float, required=True, help='User-supplied reference, not a fixed baseline')
    parser.add_argument('--pd-prior-scale-mm', type=float, default=5., help='Solver weight, NOT measurement uncertainty')
    parser.add_argument('--perturbations', type=int, default=16)
    parser.add_argument('--seed', type=int, default=64)
    parser.add_argument('--output-root', type=Path)
    args = parser.parse_args(argv)
    try:
        directory = run_comparison(args.dataset, args.camera_profile, args.workspace, pd_mm=args.pd_mm,
                                   prior_scale_mm=args.pd_prior_scale_mm, perturbations=args.perturbations,
                                   seed=args.seed, output_root=args.output_root)
        print(json.dumps(dict(directory=str(directory.resolve()), status='offline_comparison_only',
                              activation_status='not_activated'), allow_nan=False))
        return 0
    except (OSError, TypeError, KeyError, *FIT_ERRORS) as exc:
        print(f'[ERROR] {exc}')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
