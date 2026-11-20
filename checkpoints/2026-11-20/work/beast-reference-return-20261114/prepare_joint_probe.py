"""Prepare a separate read-only trial from the frozen eight-pose analysis."""

import hashlib
import json
from pathlib import Path

import numpy as np


folder = Path(__file__).parent
report_path = folder/'shared-ABCD-review.json'
report = json.loads(report_path.read_text())
assert report['independent_pose_count'] == 8
assert not any(report[k] for k in ('activated', 'live_enabled', 'calibration_valid', 'display_alignment_verified'))
for path, digest in report['input_hashes'].items():
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest, path
base = json.loads((folder/'candidate-D-collection-only.json').read_text())
keys = ('schema_version', 'candidate_only', 'calibration_valid', 'display_alignment_verified',
        'coordinate_convention', 'display_mode', 'channel_order', 'eye_width', 'eye_height',
        'camera_profile_id', 'workspace_profile_id', 'camera_profile_sha256', 'workspace_profile_sha256')
candidate = {k: base[k] for k in keys}
points = np.array([g['camera_xyz_mm'] for g in report['groups']])
expected = np.array(report['shared_joint']['fit_error_px']['predicted_px'])
for eye_index, eye in enumerate(('left', 'right')):
    matrix = np.array(report['shared_joint']['projections'][eye])
    assert matrix.shape == (3, 4) and np.isfinite(matrix).all()
    assert abs(np.linalg.det(matrix[:, :3])) > 1e-12
    camera = np.column_stack((points, np.ones(len(points)))) @ matrix.T
    assert (camera[:, 2] > 1e-9).all()
    pixels = camera[:, :2]/camera[:, 2:]
    np.testing.assert_allclose(pixels, expected[:, eye_index], atol=1e-8, rtol=0)
    assert (pixels >= 0).all() and (pixels < [1920, 1080]).all()
    candidate[eye+'_projection'] = matrix.reshape(-1).tolist()
candidate['joint_probe_review'] = dict(
    source_report=str(report_path), source_sha256=hashlib.sha256(report_path.read_bytes()).hexdigest(),
    setup_id=report['setup_id'], pd_reference_mm=64, independent_pose_count=8,
    scope='Read-only bounded optical trial; not installed calibration',
    live_validation='pending', stage_offsets_allowed=False, cd_depth_config_allowed=False,
    fit_rms_px=report['shared_joint']['fit_error_px']['rms'],
    leave_one_out_max_px=max(f['error_px']['max'] for f in report['folds']))
# Adapter for the existing device-free C# parity test; no new observations.
fixture = dict(schema_version='beast_joint_fit_comparison_v1', activation_status='not_activated',
    adapter_note='Derived from shared-ABCD-review.json for projection-code parity only.',
    fit_pose_ids=[g['label'] for g in report['groups']], check_pose_ids=[],
    baseline_dlt=dict(samples=[dict(pose_id=g['label'], eye='left', camera_xyz_mm=g['camera_xyz_mm'])
                               for g in report['groups']]),
    joint=dict(projections=report['shared_joint']['projections'],
               fit_error_px=dict(predicted_px=expected.tolist())))
for name, value in [('candidate-ABCD-joint-unverified.json', candidate), ('joint-ABCD-csharp-replay.json', fixture)]:
    path = folder/name
    data = json.dumps(value, indent=2, allow_nan=False).encode('utf-8')
    assert not path.exists() or path.read_bytes() == data, f'Refuse to replace different trial: {path}'
    path.write_bytes(data)
    print(name, hashlib.sha256(data).hexdigest())
print('PASS: unchanged source hashes, eight projection checks, no baseline replacement or stage corrections')
