"""Offline B pose comparison. Never opens devices or exports active calibration."""

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import sys

import cv2
import numpy as np

from depth_shift_trial import fit, predict


def inverse_depth(depths, offsets, query):
    depths, offsets = np.asarray(depths, float), np.asarray(offsets, float)
    if (depths.shape != (2,) or offsets.shape != (2, 2, 2)
            or not np.isfinite(depths).all() or not np.isfinite(offsets).all()
            or not np.isfinite(query) or query <= 0 or (depths <= 0).any()
            or abs(depths[0] - depths[1]) < 1e-6):
        raise ValueError('Two distinct positive depths and finite paired offsets required')
    weight = (1/query - 1/depths[0]) / (1/depths[1] - 1/depths[0])
    return offsets[0] + weight * (offsets[1] - offsets[0]), bool(not 0 <= weight <= 1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.root))
    from server.realtime.workspace_live_preview import load_profiles
    from server.realtime.workspace_projection import estimate_pose

    folder = Path(__file__).parent
    hashes = {}

    def read(path):
        path = Path(path)
        data = path.read_bytes()
        hashes[str(path)] = hashlib.sha256(data).hexdigest()
        return json.loads(data.decode('utf-8-sig'))

    middle = read(folder/'accepted-B-middle.json')
    near = read(folder/'accepted-B-near-groups.json')
    selections = [dict(middle, label='B_middle', cluster_frames=middle['final_cluster_frames']), *near['groups']]
    candidate_path = folder/'candidate-B-depth-shift-unverified.json'
    candidate = read(candidate_path)
    candidate_hash = hashes[str(candidate_path)]
    matrices = np.array([candidate[e+'_projection'] for e in ('left', 'right')]).reshape(2, 3, 4)
    presentation = read(args.root/'outputs/demo/presentation.json')
    camera, workspace, meta = load_profiles(presentation['camera_profile'], presentation['workspace_profile'])
    assert all(meta[k] == candidate[k] for k in ('camera_profile_sha256', 'workspace_profile_sha256'))
    report = dict(schema_version='beast_B_offline_comparison_v1', activated=False,
        independent_pose_count=3, target_id='B', candidate_sha256=candidate_hash,
        scope='Offline diagnostics only; no measured optical error or clinical fusion assessment',
        caveats=['Three user-adjusted pose groups, not repeated-save count.',
                 'Depth and orientation covary; causal effects cannot be separated.',
                 'Leave-one-group-out is internal validation, not an independent live test.',
                 'Extrapolation is diagnostic only; never approved for rendering.',
                 'Camera Z is not eye-to-target distance.'], groups=[], folds=[])
    records, traces, repeated = [], {}, []
    for selected in selections:
        path = Path(selected['selected_record'])
        record = read(path)
        assert hashes[str(path)] == selected['selected_record_sha256']
        obs = record['observation']
        assert record['candidate_sha256'] == candidate_hash == middle['candidate_sha256'] == near['candidate_sha256']
        assert record['setup_id'] == middle['setup_id'] == near['setup_id']
        assert record['rendered_view'] == 'Both' and record['binocular_confirmed_by_user'] is True
        assert obs['target_id'] == 'B' and obs['status'] == 'tracking'
        assert 0 <= record['conservative_age_ms'] <= 150
        assert record['candidate_only'] and not record['calibration_valid'] and not record['display_alignment_verified']
        assert (record['output_width'], record['output_height']) == (3840, 1080)
        assert all(obs[k] == meta[k] for k in ('camera_profile_sha256', 'workspace_profile_sha256'))
        trace_path = path.parent/'pose-trace.jsonl'
        if trace_path not in traces:
            raw = trace_path.read_bytes()
            hashes[str(trace_path)] = hashlib.sha256(raw).hexdigest()
            traces[trace_path] = {r['frame_id']: r for r in map(json.loads, raw.splitlines())}
        row = traces[trace_path][obs['frame_id']]
        detections = {int(k): np.array(v) for k, v in row['detected_corners_px'].items()}
        pose = estimate_pose(detections, workspace, camera, camera.image_size)
        xyz = cv2.Rodrigues(pose.rvec)[0] @ workspace.targets['B'] + pose.tvec.reshape(3)
        np.testing.assert_allclose(xyz, obs['camera_xyz_mm'], atol=1e-6, rtol=0)
        offsets = np.array([record[e+'_offset_px'] for e in ('left', 'right')])
        pixels = np.array([record[e+'_final_px'] for e in ('left', 'right')])
        np.testing.assert_allclose(predict(matrices, xyz[None])[0] + offsets, pixels, atol=1e-6, rtol=0)
        records.append(record)
        group_rows = [read(path.parent/f'diagnostic-frame-{frame}.json') for frame in selected['cluster_frames']]
        for r in group_rows:
            assert r['candidate_sha256'] == candidate_hash and r['setup_id'] == record['setup_id']
            assert r['observation']['target_id'] == 'B' and r['binocular_confirmed_by_user']
            np.testing.assert_array_equal([r[e+'_offset_px'] for e in ('left', 'right')], offsets)
        repeated.append(group_rows)
        local = [r for r in traces[trace_path].values()
                 if abs(r['received_at_monotonic']-row['received_at_monotonic']) <= .5]
        report['groups'].append(dict(label=selected['label'], record=str(path), camera_xyz_mm=xyz.tolist(),
            offset_px=offsets.tolist(), marker_ids=obs['marker_ids'], rms_px=obs['rms_px'],
            conservative_age_ms=record['conservative_age_ms'], repeated_saves=len(group_rows),
            exact_pose_and_pixel_replay=True,
            half_second_window=dict(frames=len(local), tracking=sum(r['status']=='tracking' for r in local))))

    xyz = np.array([r['observation']['camera_xyz_mm'] for r in records])
    pixels = np.array([[r[e+'_final_px'] for e in ('left', 'right')] for r in records])
    residual = pixels-predict(matrices, xyz)
    z = xyz[:, 2]
    report['unchanged_A_derived_B_error_px'] = np.linalg.norm(residual, axis=2).tolist()
    for held in range(3):
        train = [i for i in range(3) if i != held]
        depth_prediction, extra = inverse_depth(z[train], residual[train], z[held])
        shifted = fit(matrices, xyz[train], pixels[train])
        prediction = predict(matrices, xyz[held:held+1], shifted['shift_mm'], shifted['bias_px'])[0]
        report['folds'].append(dict(held_out=selections[held]['label'],
            constant_bias_error_px=np.linalg.norm(residual[train].mean(axis=0)-residual[held], axis=1).tolist(),
            inverse_depth_error_px=np.linalg.norm(depth_prediction-residual[held], axis=1).tolist(),
            inverse_depth_xy_error_px=(depth_prediction-residual[held]).tolist(),
            inverse_depth_extrapolation=extra, shifted_fit=shifted,
            shifted_error_px=np.linalg.norm(prediction-pixels[held], axis=1).tolist()))

    full = fit(matrices, xyz, pixels)
    report['B_only_shift_fit'] = full
    report['B_only_shift_training_error_px'] = np.linalg.norm(
        predict(matrices, xyz, full['shift_mm'], full['bias_px'])-pixels, axis=2).tolist()
    a_review = read(folder/'saved-pose-audit.json')
    a_paths = [Path(p) for p in a_review['input_hashes'] if Path(p).name.startswith('diagnostic-frame-')]
    a_records = [read(p) for p in a_paths]
    assert len(a_records) == 3
    for p, r in zip(a_paths, a_records):
        assert hashes[str(p)] == a_review['input_hashes'][str(p)]
        assert r['setup_id'] == middle['setup_id'] and r['observation']['target_id'] == 'A'
    a_xyz = np.array([r['observation']['camera_xyz_mm'] for r in a_records])
    a_pixels = np.array([[r[e+'_final_px'] for e in ('left', 'right')] for r in a_records])
    report['A_regression_if_B_fit_replaces_global'] = dict(
        record_paths=[str(p) for p in a_paths],
        before_error_px=np.linalg.norm(predict(matrices, a_xyz)-a_pixels, axis=2).tolist(),
        after_error_px=np.linalg.norm(predict(matrices, a_xyz, full['shift_mm'], full['bias_px'])-a_pixels, axis=2).tolist())
    joint_xyz, joint_pixels = np.concatenate([a_xyz, xyz]), np.concatenate([a_pixels, pixels])
    joint = fit(matrices, joint_xyz, joint_pixels)
    report['shared_AB_same_five_parameter_family'] = dict(fit=joint,
        per_pose_error_px=np.linalg.norm(predict(matrices, joint_xyz, joint['shift_mm'], joint['bias_px'])-joint_pixels, axis=2).tolist(),
        pose_order=['A_0', 'A_1', 'A_2']+[s['label'] for s in selections],
        interpretation='Training comparison only; no higher-DOF fit or activation')

    # Vary representatives without turning repeats into additional training poses.
    alternatives = []
    for choice in itertools.product(*repeated):
        depths = np.array([r['observation']['camera_xyz_mm'][2] for r in choice])
        values = np.array([[r[e+'_offset_px'] for e in ('left', 'right')] for r in choice])
        middle_index = int(np.argsort(depths)[1])
        endpoints = [i for i in range(3) if i != middle_index]
        predicted, extra = inverse_depth(depths[endpoints], values[endpoints], depths[middle_index])
        assert not extra
        alternatives.append(np.linalg.norm(predicted-values[middle_index], axis=1))
    report['representative_choice_sensitivity'] = dict(combinations=len(alternatives),
        interpolated_held_pose_error_min_median_max_px=np.percentile(alternatives, [0,50,100], axis=0).tolist(),
        independent_validation=False)
    report['pairwise_pose_change'] = []
    for i,j in itertools.combinations(range(3),2):
        rotations = [cv2.Rodrigues(np.array(records[k]['observation']['rvec']))[0] for k in (i,j)]
        angle = np.degrees(np.arccos(np.clip((np.trace(rotations[1]@rotations[0].T)-1)/2,-1,1)))
        report['pairwise_pose_change'].append(dict(labels=[selections[i]['label'],selections[j]['label']],
            xyz_delta_mm=(xyz[j]-xyz[i]).tolist(), rotation_deg=float(angle)))
    report['source_camera_z_range_mm'] = [float(z.min()),float(z.max())]
    report['runtime_compatibility'] = 'Existing TargetDepthTrial only accepts C/D; B residuals cannot be passed as C/D records.'
    report['input_hashes'] = hashes
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
    output = folder/'B-offline-comparison.json'
    output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('folds','B_only_shift_fit','B_only_shift_training_error_px',
        'A_regression_if_B_fit_replaces_global','shared_AB_same_five_parameter_family','representative_choice_sensitivity')}, separators=(',',':')))
    print('PASS: selected groups, exact replay, excluded-pose comparison, input preservation; no activation')


if __name__ == '__main__':
    main()
