"""Compare numeric hypotheses and prepare an explicitly unverified A-only trial."""

import argparse
import copy
import hashlib
import json
from pathlib import Path

import numpy as np

from depth_shift_trial import fit, predict, shifted_matrices


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    folder = Path(__file__).parent
    audit = json.loads((folder / 'saved-pose-audit.json').read_text())
    path = args.root / 'outputs/display_retarget/fit-20261104T133307Z-3f75411a/candidate-probe.json'
    source_bytes = path.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    assert source_hash == audit['source_candidate_sha256']
    for name, expected in audit['input_hashes'].items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == expected
    candidate = json.loads(source_bytes)
    matrices = np.array([candidate[e+'_projection'] for e in ('left', 'right')]).reshape(2, 3, 4)
    xyz = np.array([g['camera_xyz_mm'] for g in audit['groups']])
    offsets = np.array([g['offset_px'] for g in audit['groups']])
    raw = predict(matrices, xyz)
    observed = raw + offsets
    report = dict(schema_version='beast_depth_shift_comparison_v1', candidate_only=True,
        calibration_valid=False, display_alignment_verified=False, activated=False,
        source_candidate_sha256=source_hash, input_hashes=audit['input_hashes'],
        model='shared_camera_z_translation_plus_four_eye_pixel_offsets',
        interpretation='Computational residual model, not a measured physical camera/eye translation',
        cautions=['Only three A pose clusters; no B/C/D optical evidence for this trial.',
                  'Bounds are computational assumptions, not measured hardware dimensions.',
                  'Leave-one-group-out is internal validation, not independent live validation.',
                  'Do not combine with existing A +17px or C/D residual corrections.'],
        folds=[])
    for held in range(3):
        train = [i for i in range(3) if i != held]
        result = fit(matrices, xyz[train], observed[train])
        prediction = predict(matrices, xyz[held:held+1], result['shift_mm'], result['bias_px'])[0]
        constant = raw[held] + offsets[train].mean(axis=0)
        report['folds'].append(dict(held_out=audit['groups'][held]['label'], fit=result,
            error_px=np.linalg.norm(prediction-observed[held], axis=1).tolist(),
            error_xy_px=(prediction-observed[held]).tolist(),
            constant_bias_error_px=np.linalg.norm(constant-observed[held], axis=1).tolist()))
    full = fit(matrices, xyz, observed)
    predicted = predict(matrices, xyz, full['shift_mm'], full['bias_px'])
    report['fit'] = full
    report['training_error_px'] = np.linalg.norm(predicted-observed, axis=2).tolist()
    rng = np.random.default_rng(64)
    shifts, changes = [], []
    for _ in range(32):
        # Synthetic perturbations measure sensitivity, not real capture uncertainty.
        perturbed = fit(matrices, xyz+rng.normal(0., 1., xyz.shape),
                        observed+rng.normal(0., 1., observed.shape))
        shifts.append(perturbed['shift_mm'])
        changes.append(np.linalg.norm(predict(matrices, xyz, perturbed['shift_mm'],
            perturbed['bias_px'])-predicted, axis=2))
    report['synthetic_sensitivity'] = dict(seed=64, trials=32, xyz_std_mm=1., pixel_std_px=1.,
        shift_p05_median_p95_mm=np.percentile(shifts, [5, 50, 95]).tolist(),
        predicted_change_p50_p95_max_px=np.percentile(changes, [50, 95, 100]).tolist(),
        measured_uncertainty=False)
    converted = shifted_matrices(matrices, full['shift_mm'], full['bias_px'])
    np.testing.assert_allclose(predict(converted, xyz), predicted, atol=1e-9, rtol=0)
    trial = copy.deepcopy(candidate)
    for eye, matrix in zip(('left', 'right'), converted):
        assert abs(np.linalg.det(matrix[:, :3])) > 1e-12
        trial[eye+'_projection'] = matrix.ravel().tolist()
    trial['depth_shift_review'] = dict(source_candidate_sha256=source_hash,
        setup_id='20261114-A-mid-near-1652', target_id='A', scope='A-only read-only trial, not active calibration',
        fit=full, source_camera_z_range_mm=[float(xyz[:, 2].min()), float(xyz[:, 2].max())],
        live_validation='pending', stage_offsets_allowed=False, cd_depth_config_allowed=False,
        runtime_range_enforced=False)
    trial_path = folder / 'candidate-A-depth-shift-unverified.json'
    trial_path.write_text(json.dumps(trial, indent=2, allow_nan=False), encoding='utf-8')
    report['trial_path'] = str(trial_path)
    report['trial_sha256'] = hashlib.sha256(trial_path.read_bytes()).hexdigest()
    report['next_live_check'] = 'A at an unadjusted intermediate pose, approximately camera Z 430-450mm; readiness required.'
    (folder / 'depth-shift-comparison.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    assert path.read_bytes() == source_bytes
    print(json.dumps({k: report[k] for k in ('fit', 'training_error_px', 'folds', 'synthetic_sensitivity', 'trial_sha256')}, indent=2))
    print('PASS: excluded-pose comparison, synthetic perturbations, exported-matrix equivalence, source preservation')


if __name__ == '__main__':
    main()
