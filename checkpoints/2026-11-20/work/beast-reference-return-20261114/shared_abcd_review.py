"""Extend the frozen six-pose review with confirmed C/D; never export calibration."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

import cv2
import numpy as np

from shared_ab_review import check_groups, require, validate_record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.root))
    from server.realtime.display_joint_fit import fit_joint, _predict, _error
    from server.realtime.workspace_live_preview import load_profiles
    from server.realtime.workspace_projection import estimate_pose

    folder = Path(__file__).parent
    hashes = {}

    def read(path, expected=None):
        path = Path(path)
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        require(expected is None or digest == expected, f'Changed source: {path.name}')
        hashes[str(path)] = digest
        return json.loads(raw.decode('utf-8-sig'))

    frozen = read(folder/'shared-AB-review.json')
    require(frozen['independent_pose_count'] == 6 and not frozen['activated'], 'Unexpected frozen review')
    for path, digest in frozen['input_hashes'].items():
        require(hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest, f'Changed frozen source: {path}')
        hashes[path] = digest
    implementation = Path(frozen['joint_implementation']['path'])
    require(hashlib.sha256(implementation.read_bytes()).hexdigest() == frozen['joint_implementation']['sha256'],
            'Joint solver changed since AB review')
    hashes[str(implementation)] = frozen['joint_implementation']['sha256']
    presentation = read(args.root/'outputs/demo/presentation.json')
    camera, workspace, meta = load_profiles(presentation['camera_profile'], presentation['workspace_profile'])
    frozen_hashes = {Path(path): digest for path, digest in frozen['input_hashes'].items()}
    selections = [dict(g, selected_record_sha256=frozen_hashes[Path(g['selected_record'])])
                  for g in frozen['groups']]
    for target in ('C', 'D'):
        selection = read(folder/f'accepted-{target}-free-pose.json')
        require(selection['setup_id'] == frozen['setup_id'] and selection['independent_pose_count'] == 1
                and selection['activation_allowed'] is False, 'Invalid C/D selection')
        selections.append(dict(selection, label=f'{target}_free'))
    require([s['label'] for s in selections] ==
            ['A_middle', 'A_near_1', 'A_near_2', 'B_middle', 'B_near_1', 'B_near_2', 'C_free', 'D_free'],
            'Unexpected independent group selection')
    candidates = {
        'A': read(args.root/'outputs/display_retarget/fit-20261104T133307Z-3f75411a/candidate-probe.json'),
        'B': read(folder/'candidate-B-depth-shift-unverified.json'),
        **{s['target_id']: read(s['candidate_path'], s['candidate_sha256']) for s in selections[6:]}}
    records, xyz, pixels, groups, traces = [], [], [], [], {}
    for selected in selections:
        record = read(selected['selected_record'], selected['selected_record_sha256'])
        target = selected['label'][0]
        candidate = candidates[target]
        candidate_path = (args.root/'outputs/display_retarget/fit-20261104T133307Z-3f75411a/candidate-probe.json'
                          if target == 'A' else folder/(f'candidate-{target}-collection-only.json' if target in 'CD'
                                                                       else 'candidate-B-depth-shift-unverified.json'))
        point, pair = validate_record(record, setup=frozen['setup_id'], target=target,
            camera_hash=meta['camera_profile_sha256'], workspace_hash=meta['workspace_profile_sha256'],
            candidate_hash=hashes[str(candidate_path)])
        matrices = {e: np.array(candidate[e+'_projection']).reshape(3, 4) for e in ('left', 'right')}
        base = np.array([record[e+'_base_px'] for e in ('left', 'right')])
        np.testing.assert_allclose(_predict(matrices, point[None])[0], base, atol=1e-6, rtol=0)
        trace_path = Path(selected['selected_record']).parent/'pose-trace.jsonl'
        if trace_path not in traces:
            raw = trace_path.read_bytes()
            hashes[str(trace_path)] = hashlib.sha256(raw).hexdigest()
            traces[trace_path] = {r['frame_id']: r for r in map(json.loads, raw.splitlines())}
        obs = record['observation']
        row = traces[trace_path][obs['frame_id']]
        pose = estimate_pose({int(k): np.array(v) for k, v in row['detected_corners_px'].items()},
                             workspace, camera, camera.image_size)
        replay = cv2.Rodrigues(pose.rvec)[0] @ workspace.targets[target] + pose.tvec.reshape(3)
        np.testing.assert_allclose(replay, point, atol=1e-6, rtol=0)
        records.append(record)
        xyz.append(point)
        pixels.append(pair)
        groups.append(dict(label=selected['label'], selected_record=selected['selected_record'],
                           camera_xyz_mm=point.tolist(), final_pixels=pair.tolist(),
                           marker_rms_px=obs['rms_px'], exact_candidate_pixel_and_pose_replay=True))
    labels = [g['label'] for g in groups]
    check_groups(labels, records)
    xyz, pixels = np.array(xyz), np.array(pixels)
    rays = xyz[:, :2]/xyz[:, 2:]
    frozen_matrices = {e: np.array(frozen['shared_joint']['projections'][e]) for e in ('left', 'right')}
    report = dict(schema_version='beast_shared_ABCD_review_v1', activated=False, live_enabled=False,
        calibration_valid=False, display_alignment_verified=False, setup_id=frozen['setup_id'],
        independent_pose_count=8, groups=groups,
        validity='Internal saved-coordinate comparison only; not new optical validation.',
        caveats=['Repeated saves count once. Same wearing is user-reported.',
                 'C/D each have one pose; this does not validate distance or angle generalization.',
                 'Camera Z is not eye distance. Absolute final pixels, not relative offsets, are fitted.',
                 'PD 64mm is a soft reference; effective fitted baseline is not measured user PD.'],
        coverage=dict(ray_xy_min=rays.min(axis=0).tolist(), ray_xy_max=rays.max(axis=0).tolist(),
                      xyz_min_mm=xyz.min(axis=0).tolist(), xyz_max_mm=xyz.max(axis=0).tolist()),
        frozen_AB_predictions_on_new_CD=_error(_predict(frozen_matrices, xyz[6:]), pixels[6:]),
        shared_joint=fit_joint(xyz, pixels, pd_mm=64), folds=[])
    for held, label in enumerate(labels):
        mask = np.arange(len(labels)) != held
        fitted = fit_joint(xyz[mask], pixels[mask], pd_mm=64)
        matrices = {e: np.array(fitted['projections'][e]) for e in ('left', 'right')}
        report['folds'].append(dict(held_out=label, train_labels=[p for i, p in enumerate(labels) if mask[i]],
            error_px=_error(_predict(matrices, xyz[~mask]), pixels[~mask]),
            train_fit_max_px=fitted['fit_error_px']['max'], warnings=fitted['warnings'],
            parameters=fitted['parameters'], solver=fitted['solver']))
        print(json.dumps(dict(held_out=label, error_px=report['folds'][-1]['error_px']['per_pose'])), flush=True)
    report['input_hashes'] = hashes
    report['joint_implementation'] = frozen['joint_implementation']
    require(all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in hashes.items()),
            'Source changed during computation')
    (folder/'shared-ABCD-review.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(dict(fit_error=report['shared_joint']['fit_error_px'],
                         parameters=report['shared_joint']['parameters'], warnings=report['shared_joint']['warnings'])))
    print('PASS: eight unique accepted groups, exact replay and unchanged sources; no runtime activation')


if __name__ == '__main__':
    main()
