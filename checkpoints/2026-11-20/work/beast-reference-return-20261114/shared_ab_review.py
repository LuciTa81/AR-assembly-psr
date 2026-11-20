"""Review same-wearing tracked pairs with the existing shared binocular solver.

Reads numeric records only. No devices, runtime writes, or calibration export.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys

import cv2
import numpy as np


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_record(record, *, setup, target, camera_hash, workspace_hash, candidate_hash):
    expected = dict(schema_version='beast_tracked_alignment_diagnostic_v1',
        setup_id=setup, candidate_sha256=candidate_hash, rendered_view='Both',
        coordinate_convention='eye_local_pixels_top_left',
        channel_order='left_half_left_eye_right_half_right_eye',
        output_width=3840, output_height=1080)
    require(all(record.get(k) == v for k, v in expected.items()), 'Record context mismatch')
    require(record.get('binocular_confirmed_by_user') is True
            and record.get('candidate_only') is True
            and record.get('calibration_valid') is False
            and record.get('display_alignment_verified') is False, 'Invalid pair confirmation or flags')
    age = record.get('conservative_age_ms', float('nan'))
    require(np.isfinite(age) and 0 <= age <= 150, 'Stale or invalid observation age')
    obs = record['observation']
    require(obs.get('status') == 'tracking' and obs.get('target_id') == target
            and obs.get('camera_profile_sha256') == camera_hash
            and obs.get('workspace_profile_sha256') == workspace_hash, 'Observation context mismatch')
    xyz = np.asarray(obs['camera_xyz_mm'], float)
    require(xyz.shape == (3,) and np.isfinite(xyz).all() and xyz[2] > 0, 'Invalid camera XYZ')
    pixels = np.array([record[e+'_final_px'] for e in ('left', 'right')], float)
    base = np.array([record[e+'_base_px'] for e in ('left', 'right')], float)
    offset = np.array([record[e+'_offset_px'] for e in ('left', 'right')], float)
    require(all(a.shape == (2, 2) and np.isfinite(a).all() for a in (pixels, base, offset)),
            'Incomplete or nonfinite eye pair')
    require(np.allclose(base + offset, pixels, atol=1e-6, rtol=0), 'Saved pixel reconstruction mismatch')
    require((pixels >= 0).all() and (pixels < [1920, 1080]).all(), 'Pixels outside eye viewport')
    return xyz, pixels


def check_groups(labels, records):
    keys = [(r['observation']['session_id'], r['observation']['frame_id']) for r in records]
    require(len(labels) == len(records) and len(labels) == len(set(labels))
            and len(keys) == len(set(keys)), 'Duplicate pose group or saved frame')


def unobserved_target_coverage(records, xyz):
    xyz = np.asarray(xyz, float)
    ymin, ymax = np.min(xyz[:, 1]/xyz[:, 2]), np.max(xyz[:, 1]/xyz[:, 2])
    points = []
    for record in records:
        for target in record['observation']['camera_targets']:
            if target['target_id'] not in ('C', 'D'):
                continue
            point = np.asarray(target['camera_xyz_mm'], float)
            require(point.shape == (3,) and np.isfinite(point).all() and point[2] > 0,
                    'Invalid unobserved target XYZ')
            ray = point[:2]/point[2]
            points.append(dict(target_id=target['target_id'], ray_xy=ray.tolist(),
                outside_observed_y=bool(not ymin <= ray[1] <= ymax)))
    return dict(these_are_calibration_observations=False,
        note='C/D coordinates projected from the saved poses; no user-adjusted C/D labels in this session.',
        points=points, outside_observed_vertical_range=sum(p['outside_observed_y'] for p in points))


def plot_coverage(report, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 6), dpi=160)
    for target, color in (('A', '#12785d'), ('B', '#1566ac')):
        groups = [g for g in report['groups'] if g['label'].startswith(target)]
        rays = np.array([np.array(g['camera_xyz_mm'])[:2]/g['camera_xyz_mm'][2] for g in groups])
        ax.scatter(rays[:, 0], rays[:, 1], color=color, s=65, label=f'{target}: accepted eye alignment')
        for g, ray in zip(groups, rays):
            ax.annotate(g['label'], ray, xytext=(6, -12 if g['label'] == 'B_near_2' else 7),
                        textcoords='offset points', fontsize=9)
    for target, marker in (('C', 's'), ('D', '^')):
        rays = np.array([p['ray_xy'] for p in report['unobserved_CD_coverage']['points'] if p['target_id'] == target])
        ax.scatter(rays[:, 0], rays[:, 1], facecolors='none', edgecolors='#8b939b', s=55,
                   marker=marker, label=f'{target}: calculated position only')
    for y in (report['coverage']['ray_xy_min'][1], report['coverage']['ray_xy_max'][1]):
        ax.axhline(y, color='#507d72', linewidth=.8, linestyle='--')
    ax.set(xlabel='Camera ray X/Z (right positive)', ylabel='Camera ray Y/Z (down positive)',
           title='Current same-wearing data: 6 accepted A/B pose groups')
    ax.invert_yaxis()
    ax.grid(alpha=.15)
    ax.legend(loc='center left', fontsize=8, framealpha=.95)
    fig.text(.5, .015, 'Dashed lines: observed A/B vertical span. C/D markers are NOT additional calibration samples.',
             ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .05, 1, 1))
    fig.savefig(path)
    plt.close(fig)


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

    def read(path, expected_hash=None):
        path = Path(path)
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        require(expected_hash is None or digest == expected_hash, f'Changed source: {path.name}')
        hashes[str(path)] = digest
        return json.loads(raw.decode('utf-8-sig'))

    presentation = read(args.root/'outputs/demo/presentation.json')
    camera, workspace, meta = load_profiles(presentation['camera_profile'], presentation['workspace_profile'])
    read(presentation['camera_profile'], meta['camera_profile_sha256'])
    read(presentation['workspace_profile'], meta['workspace_profile_sha256'])
    audit = read(folder/'saved-pose-audit.json')
    middle = read(folder/'accepted-B-middle.json')
    near = read(folder/'accepted-B-near-groups.json')
    a_paths = [p for p in audit['input_hashes'] if Path(p).name.startswith('diagnostic-frame-')]
    require(len(a_paths) == 3, 'Expected three accepted A groups')
    a_records = [read(p, audit['input_hashes'][p]) for p in a_paths]
    selected_b = [dict(middle, label='B_middle'), *near['groups']]
    b_records = [read(s['selected_record'], s['selected_record_sha256']) for s in selected_b]
    records = a_records + b_records
    labels = ['A_middle', 'A_near_1', 'A_near_2'] + [s['label'] for s in selected_b]
    check_groups(labels, records)
    require([r['observation']['frame_id'] for r in a_records] == [1277, 1392, 1899],
            'A selection order changed')
    setup = middle['setup_id']
    require(near['setup_id'] == setup, 'Mixed wearing setup')
    a_candidate_path = args.root/'outputs/display_retarget/fit-20261104T133307Z-3f75411a/candidate-probe.json'
    a_candidate = read(a_candidate_path, audit['source_candidate_sha256'])
    b_candidate = read(folder/'candidate-B-depth-shift-unverified.json', middle['candidate_sha256'])
    require(middle['candidate_sha256'] == near['candidate_sha256'], 'B candidate mismatch')

    xyz, pixels, traces, groups = [], [], {}, []
    paths = a_paths + [s['selected_record'] for s in selected_b]
    for label, record, path in zip(labels, records, paths):
        target = label[0]
        candidate = a_candidate if target == 'A' else b_candidate
        candidate_hash = audit['source_candidate_sha256'] if target == 'A' else middle['candidate_sha256']
        point, pair = validate_record(record, setup=setup, target=target,
            camera_hash=meta['camera_profile_sha256'], workspace_hash=meta['workspace_profile_sha256'],
            candidate_hash=candidate_hash)
        matrices = {e: np.array(candidate[e+'_projection']).reshape(3, 4) for e in ('left', 'right')}
        base = np.array([record[e+'_base_px'] for e in ('left', 'right')])
        np.testing.assert_allclose(_predict(matrices, point[None])[0], base, rtol=0, atol=1e-6)
        trace_path = Path(path).parent/'pose-trace.jsonl'
        if trace_path not in traces:
            raw = trace_path.read_bytes()
            hashes[str(trace_path)] = hashlib.sha256(raw).hexdigest()
            traces[trace_path] = {r['frame_id']: r for r in map(json.loads, raw.splitlines())}
        obs = record['observation']
        row = traces[trace_path][obs['frame_id']]
        corners = {int(k): np.array(v) for k, v in row['detected_corners_px'].items()}
        pose = estimate_pose(corners, workspace, camera, camera.image_size)
        replay = cv2.Rodrigues(pose.rvec)[0] @ workspace.targets[target] + pose.tvec.reshape(3)
        np.testing.assert_allclose(replay, point, atol=1e-6, rtol=0)
        xyz.append(point)
        pixels.append(pair)
        groups.append(dict(label=label, selected_record=path, camera_xyz_mm=point.tolist(),
            final_pixels=pair.tolist(), marker_rms_px=obs['rms_px'],
            exact_candidate_pixel_and_pose_replay=True))
    xyz, pixels = np.array(xyz), np.array(pixels)
    directions = xyz[:, :2] / xyz[:, 2:]
    singular = np.linalg.svd(xyz - xyz.mean(axis=0), compute_uv=False)
    report = dict(schema_version='beast_shared_AB_review_v1', activated=False,
        live_enabled=False, setup_id=setup, independent_pose_count=len(records), groups=groups,
        validity='Internal saved-coordinate comparison, not independent optical validation',
        caveats=['Final absolute screen pixels are combined, not candidate-relative offsets.',
                 'Same-wearing context is user-reported, not measured by an eye tracker.',
                 'No prior wearing sessions or unconfirmed adjustments included.',
                 'Six pose groups; repeat saves do not increase the independent sample count.',
                 'Camera Z is not eye-to-screw distance; no required physical head position.',
                 'A/B results cannot certify unobserved C/D or arbitrary side views.'],
        coverage=dict(xyz_min_mm=xyz.min(axis=0).tolist(), xyz_max_mm=xyz.max(axis=0).tolist(),
            ray_xy_min=directions.min(axis=0).tolist(), ray_xy_max=directions.max(axis=0).tolist(),
            centered_xyz_singular_values_mm=singular.tolist(),
            xyz_min_max_singular_ratio=float(singular[-1]/singular[0]),
            z_y_correlation=float(np.corrcoef(xyz[:, 2], xyz[:, 1])[0, 1])),
        shared_joint=fit_joint(xyz, pixels, pd_mm=64), folds=[])
    report['unobserved_CD_coverage'] = unobserved_target_coverage(records, xyz)
    for held, label in enumerate(labels):
        mask = np.arange(len(labels)) != held
        result = dict(held_out=label, train_labels=[p for i, p in enumerate(labels) if mask[i]])
        try:
            fitted = fit_joint(xyz[mask], pixels[mask], pd_mm=64)
            matrices = {e: np.array(fitted['projections'][e]) for e in ('left', 'right')}
            result.update(status='evaluated', error_px=_error(_predict(matrices, xyz[~mask]), pixels[~mask]),
                train_fit_max_px=fitted['fit_error_px']['max'], warnings=fitted['warnings'],
                parameters=fitted['parameters'], solver=fitted['solver'])
        except (ValueError, np.linalg.LinAlgError, cv2.error) as exc:
            result.update(status='unavailable', reason=str(exc))
        report['folds'].append(result)
    report['pd_prior_sensitivity'] = []
    for scale in (2., 10.):
        fitted = fit_joint(xyz, pixels, pd_mm=64, prior_scale_mm=scale)
        report['pd_prior_sensitivity'].append(dict(scale_mm=scale, parameters=fitted['parameters'],
            fit_error_px=fitted['fit_error_px'], warnings=fitted['warnings']))
    bmatrices = {e: np.array(b_candidate[e+'_projection']).reshape(3, 4) for e in ('left', 'right')}
    report['unchanged_A_derived_comparator'] = _error(_predict(bmatrices, xyz), pixels)
    report['joint_implementation'] = dict(path=str(args.root/'server/realtime/display_joint_fit.py'),
        sha256=hashlib.sha256((args.root/'server/realtime/display_joint_fit.py').read_bytes()).hexdigest())
    report['input_hashes'] = hashes
    require(all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in hashes.items()),
            'Source changed during offline computation')
    (folder/'shared-AB-review.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    plot_coverage(report, folder/'shared-AB-coverage.png')
    print(json.dumps(dict(coverage=report['coverage'],
        fit_error=report['shared_joint']['fit_error_px']['per_pose'],
        parameters=report['shared_joint']['parameters'], warnings=report['shared_joint']['warnings'],
        folds=[dict(held_out=f['held_out'], status=f['status'],
            error=f.get('error_px', {}).get('per_pose'), warnings=f.get('warnings')) for f in report['folds']]),
        separators=(',', ':')))
    print('PASS: six accepted groups, exact replay and source hashes; no runtime activation')


if __name__ == '__main__':
    main()
