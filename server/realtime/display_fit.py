"""Offline eye-projection candidate fitting; never opens a camera or activates Unity."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import cv2
import numpy as np

from .camera_calibration import stamp, write_json
from .display_calibration import BINDING_FIELDS
from .workspace_live_preview import load_profiles
from .workspace_projection import finite_array


def _require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _normalize(points):
    center = points.mean(axis=0)
    scale = np.sqrt(points.shape[1]) / np.sqrt(np.mean(np.sum((points - center) ** 2, axis=1)))
    transform = np.eye(points.shape[1] + 1)
    transform[:-1, :-1] *= scale
    transform[:-1, -1] = -scale * center
    homogeneous = np.column_stack([points, np.ones(len(points))])
    return homogeneous @ transform.T, transform


def fit_projection(xyz, pixels) -> np.ndarray:
    """Normalized DLT using NumPy SVD. This estimates a pinhole candidate, not optical validity."""
    xyz = np.asarray(xyz, dtype=np.float64)
    pixels = np.asarray(pixels, dtype=np.float64)
    _require(xyz.ndim == 2 and xyz.shape[1:] == (3,) and len(xyz) >= 6, 'At least six 3D points per eye required')
    _require(pixels.shape == (len(xyz), 2) and np.isfinite(xyz).all() and np.isfinite(pixels).all(), 'Invalid point arrays')
    for values, dimension in ((xyz, 3), (pixels, 2)):
        spread = np.linalg.svd(values - values.mean(axis=0), compute_uv=False)
        _require(len(spread) == dimension and spread[0] > 1e-9 and spread[-1] / spread[0] > 1e-3,
                 'Degenerate or near-planar/collinear calibration geometry')
    objects, world_normalization = _normalize(xyz)
    images, image_normalization = _normalize(pixels)
    rows = []
    for point, pixel in zip(objects, images):
        rows.extend([np.r_[point, np.zeros(4), -pixel[0] * point],
                     np.r_[np.zeros(4), point, -pixel[1] * point]])
    _, singular, vectors = np.linalg.svd(np.asarray(rows), full_matrices=False)
    _require(singular[-2] / singular[0] > 1e-6, 'Insufficient independent projection constraints')
    matrix = np.linalg.solve(image_normalization, vectors[-1].reshape(3, 4)) @ world_normalization
    scale = np.linalg.norm(matrix[2, :3])
    _require(np.isfinite(matrix).all() and scale > 1e-12, 'Invalid projection matrix')
    matrix /= scale
    homogeneous = np.column_stack([xyz, np.ones(len(xyz))]) @ matrix.T
    if np.median(homogeneous[:, 2]) < 0:
        matrix *= -1
    _require(np.linalg.matrix_rank(matrix[:, :3]) == 3, 'Singular camera block')
    _errors(matrix, xyz, pixels)
    return matrix


def _errors(matrix, xyz, pixels):
    q = np.column_stack([xyz, np.ones(len(xyz))]) @ matrix.T
    _require(np.isfinite(q).all() and (q[:, 2] > 1e-9).all(), 'Points behind fitted eye or invalid projection')
    residual = np.linalg.norm(q[:, :2] / q[:, 2:] - pixels, axis=1)
    _require(np.isfinite(residual).all(), 'Non-finite reprojection error')
    return dict(rms=float(np.sqrt(np.mean(residual ** 2))), max=float(residual.max()), per_point=residual.tolist())


def _read_points(path, camera, workspace, binding):
    content = path.read_bytes()
    data = json.loads(content)
    paired = data.get('schema_version') == 'beast_display_correspondence_pair_v2'
    _require((paired or data.get('schema_version') == 'beast_display_correspondence_candidate_v1')
             and data.get('candidate_only') is True and data.get('calibration_valid') is False
             and data.get('display_alignment_verified') is False, 'Expected unverified correspondence candidate')
    eye = data.get('eye')
    _require(eye == 'both' if paired else eye in ('left', 'right'), 'Invalid eye for correspondence schema')
    display, observation = data['display'], data['observation']
    _require(display.get('selected_view') == eye.title() and display.get('channels_confirmed_by_user') is True,
             'Selected eye/channel confirmation mismatch')
    if paired or data.get('stability') is not None:
        _require(isinstance(data.get('setup_id'), str) and data['setup_id'].strip()
                 and len(data['setup_id']) <= 128, 'Missing or invalid capture setup_id')
    if paired:
        _require(data.get('binocular_confirmed_by_user') is True
                 and display.get('left_marked') is True and display.get('right_marked') is True,
                 'Pair needs explicit binocular confirmation')
    if paired or data.get('stability') is not None:
        stability = data.get('stability')
        _require(isinstance(stability, dict), 'Missing pair stability evidence')
        count, first, last = (stability.get(name) for name in ('distinct_frames', 'first_frame_id', 'last_frame_id'))
        _require(all(type(v) is int for v in (count, first, last))
                 and 3 <= count <= 256 and 0 < first < last and count <= last - first + 1
                 and last == observation.get('frame_id'), 'Invalid stability frames')
        span, delta = finite_array([stability.get('span_ms'), stability.get('max_target_delta_mm')], (2,), 'stability')
        _require(180 <= span <= 600.001 and 0 <= delta <= 2, 'Unstable paired observation')
    _require(display.get('coordinate_convention') == 'eye_local_pixels_top_left'
             and display.get('channel_order') == 'left_half_left_eye_right_half_right_eye'
             and display.get('framebuffer_width') == data.get('output_width') == 3840
             and display.get('height') == data.get('output_height') == 1080
             and display.get('eye_width') == 1920, 'Expected unchanged Full SBS output geometry')
    _require(observation.get('schema_version') == 'beast_display_observation_v1'
             and observation.get('status') == 'tracking' and observation.get('target_id') == 'A'
             and observation.get('image_size') == list(camera.image_size), 'Invalid observation geometry/status')
    _require(all(observation.get(name) == value for name, value in binding.items()), 'Profile binding mismatch')
    frame, session = observation.get('frame_id'), observation.get('session_id')
    _require(type(frame) is int and frame > 0 and isinstance(session, str) and session.strip(), 'Invalid observation identity')
    ids = observation.get('marker_ids')
    _require(isinstance(ids, list) and len(ids) >= 4 and all(type(i) is int and i in workspace.markers for i in ids)
             and len(set(ids)) == len(ids), 'Invalid marker IDs')
    _require(type(observation.get('marker_count')) is int and observation['marker_count'] == len(ids),
             'Marker count does not match marker IDs')
    clocks = finite_array([data.get('request_started_seconds'), data.get('response_received_seconds'),
                           data.get('request_rtt_ms'), observation.get('age_ms'), data.get('conservative_age_ms')], (5,), 'clocks')
    start, finish, rtt, age, conservative = clocks
    _require(0 <= start <= finish and rtt >= 0 and age >= 0 and 0 <= conservative <= 150
             and np.isclose(rtt, (finish - start) * 1000, atol=1e-3)
             and np.isclose(conservative, age + rtt, atol=1e-3), 'Stale or inconsistent observation age')
    rms, maximum = finite_array([observation.get('rms_px'), observation.get('max_error_px')], (2,), 'quality')
    _require(0 <= rms <= 3 and rms <= maximum <= 5, 'Invalid observation quality')
    xyz = finite_array(observation.get('camera_xyz_mm'), (3,), 'camera_xyz_mm')
    world = finite_array(observation.get('world_xyz_mm'), (3,), 'world_xyz_mm')
    rotation = cv2.Rodrigues(finite_array(observation.get('rvec'), (3,), 'rvec'))[0]
    translation = finite_array(observation.get('tvec_mm'), (3,), 'tvec_mm')
    _require(xyz[2] > 0 and np.allclose(world, workspace.targets['A'], atol=1e-5)
             and np.allclose(xyz, rotation @ world + translation, atol=1e-5), 'Inconsistent 3D target coordinates')
    target_pixel = finite_array(observation.get('target_pixel'), (2,), 'target_pixel')
    expected_pixel = cv2.projectPoints(xyz.reshape(1, 3), np.zeros(3), np.zeros(3),
                                      camera.matrix, camera.distortion)[0].reshape(2)
    _require((target_pixel >= 0).all() and (target_pixel < camera.image_size).all()
             and np.allclose(target_pixel, expected_pixel, rtol=0, atol=1e-4), 'Inconsistent camera target pixel')
    points = []
    for selected in ('left', 'right') if paired else (eye,):
        pixels = finite_array([display.get(selected + '_x'), display.get(selected + '_y')], (2,), 'eye pixels')
        _require((pixels >= 0).all() and (pixels < [1920, 1080]).all(), 'Eye coordinates outside display')
        points.append(dict(eye=selected, camera_xyz_mm=xyz.tolist(), eye_pixel=pixels.tolist(),
                           source_path=str(path.resolve()), source_sha256=hashlib.sha256(content).hexdigest(),
                           session_id=session, frame_id=frame, setup_id=data.get('setup_id'),
                           capture_mode='paired' if paired else 'single_eye'))
    return points


def analyze_dataset(dataset_path: Path, camera_path: Path, workspace_path: Path) -> dict:
    camera, workspace, metadata = load_profiles(camera_path, workspace_path)
    binding = {key: metadata[key] for key in BINDING_FIELDS if key.endswith('_sha256')}
    binding.update(camera_profile_id=camera.profile_id, workspace_profile_id=workspace.profile_id)
    dataset_path = Path(dataset_path)
    raw = dataset_path.read_bytes()
    manifest = json.loads(raw)
    _require(manifest.get('schema_version') == 'beast_display_fit_dataset_v1'
             and isinstance(manifest.get('points'), list), 'Invalid fit dataset schema')
    samples, identities, group_eyes, group_splits, pair_sessions = [], set(), set(), {}, {}
    for entry in manifest['points']:
        group, split = entry.get('pose_id'), entry.get('split')
        _require(isinstance(group, str) and group.strip() and split in ('fit', 'check'), 'Each point needs pose_id and fit/check split')
        source = entry.get('path')
        _require(isinstance(source, str) and source.strip(), 'Point path required')
        _require(group not in group_splits or group_splits[group] == split, 'Pose group leakage between fit and check')
        group_splits[group] = split
        for point in _read_points((dataset_path.parent / source).resolve(), camera, workspace, binding):
            if point['capture_mode'] == 'paired':
                previous = pair_sessions.setdefault(point['session_id'], (group, split))
                _require(previous == (group, split), 'Pair session must stay in one pose group and split')
            identity = (point['session_id'], point['frame_id'], point['eye'])
            _require(identity not in identities and (group, point['eye']) not in group_eyes, 'Duplicate observation or pose/eye')
            identities.add(identity)
            group_eyes.add((group, point['eye']))
            samples.append(dict(point, pose_id=group, split=split))
    setups = {s['setup_id'] for s in samples}
    _require(len(setups) <= 1, 'Cannot mix changed wearing/display setup_id values')
    report = dict(schema_version='beast_display_fit_review_v1', model='normalized_dlt_pinhole_candidate',
                  activation_status='not_activated', calibration_valid=False, display_alignment_verified=False,
                  eye_size=[1920, 1080], display_mode='full_sbs', coordinate_convention='eye_local_pixels_top_left',
                  camera_axes='x_right_y_down_z_forward', units='mm', **binding,
                  dataset_path=str(dataset_path.resolve()), dataset_sha256=hashlib.sha256(raw).hexdigest(),
                  samples=samples, eyes={}, limitations=[
                      'Mathematical fitting is not an optical alignment or depth-comfort pass.',
                      'Legacy single-eye records do not establish simultaneous binocular alignment.',
                      'Stable glasses fit, 0DoF and display-distance settings require user confirmation.',
                      'Six fit points is only the algebraic minimum; geometry and held-out errors still matter.'])
    return _fit_report(report)


def _fit_report(report):
    samples = report['samples']
    report['eyes'] = {}
    for eye in ('left', 'right'):
        fit = [s for s in samples if s['eye'] == eye and s['split'] == 'fit']
        check = [s for s in samples if s['eye'] == eye and s['split'] == 'check']
        result = dict(fit_count=len(fit), check_count=len(check), projection=None,
                      additional_fit_points_minimum=max(0, 6 - len(fit)),
                      additional_check_points_minimum=max(0, 2 - len(check)),
                      fit_error_px=None, check_error_px=None, status='needs_fit_points', reason='')
        if fit:
            xy = np.array([s['eye_pixel'] for s in fit])
            result['fit_pixel_span'] = np.ptp(xy, axis=0).tolist()
        if len(fit) >= 6:
            try:
                xyz, pixels = np.array([s['camera_xyz_mm'] for s in fit]), np.array([s['eye_pixel'] for s in fit])
                matrix = fit_projection(xyz, pixels)
                result.update(projection=matrix.tolist(), fit_error_px=_errors(matrix, xyz, pixels),
                              status='candidate_fitted' if len(check) >= 2 else 'needs_check_points')
                if check:
                    result['check_error_px'] = _errors(matrix, np.array([s['camera_xyz_mm'] for s in check]),
                                                      np.array([s['eye_pixel'] for s in check]))
            except (ValueError, np.linalg.LinAlgError) as exc:
                result.update(status='rejected_geometry', projection=None, reason=str(exc))
        report['eyes'][eye] = result
    statuses = [eye['status'] for eye in report['eyes'].values()]
    report['status'] = next((status for status in ('rejected_geometry', 'needs_fit_points', 'needs_check_points')
                             if status in statuses), 'candidate_fitted')
    _add_review(report)
    return report


def analyze_retargeted_dataset(dataset_path, camera_path, source_workspace_path, workspace_path):
    """Refit a documented A measurement correction, without rewriting source captures."""
    report = analyze_dataset(dataset_path, camera_path, source_workspace_path)
    _, old, old_metadata = load_profiles(camera_path, source_workspace_path)
    _, new, metadata = load_profiles(camera_path, workspace_path)
    raw = Path(workspace_path).read_bytes()
    adjustment = json.loads(raw).get('target_adjustment', {})
    source_hash = report['workspace_profile_sha256']
    _require(old_metadata['workspace_profile_sha256'] == source_hash
             and metadata['camera_profile_sha256'] == report['camera_profile_sha256']
             and hashlib.sha256(raw).hexdigest() == metadata['workspace_profile_sha256'],
             'Profiles changed during candidate calculation')
    _require(new.profile_id != old.profile_id and adjustment.get('target') == 'A'
             and adjustment.get('parent_profile_sha256') == source_hash
             and np.array_equal(adjustment.get('original_A_mm'), old.targets['A']),
             'Expected a new workspace with documented parent and original A coordinates')
    _require(old.markers.keys() == new.markers.keys()
             and all(np.array_equal(old.markers[k], new.markers[k]) for k in old.markers),
             'Retarget requires unchanged marker anchors')
    _require(old.targets.keys() == new.targets.keys()
             and all(np.array_equal(old.targets[k], new.targets[k]) for k in old.targets if k != 'A'),
             'Only the A measurement may change')
    for sample in report['samples']:
        source = Path(sample['source_path']).read_bytes()
        _require(hashlib.sha256(source).hexdigest() == sample['source_sha256'], 'Source capture changed')
        observation = json.loads(source)['observation']
        rotation = cv2.Rodrigues(finite_array(observation['rvec'], (3,), 'rvec'))[0]
        xyz = rotation @ new.targets['A'] + finite_array(observation['tvec_mm'], (3,), 'tvec_mm')
        _require(xyz[2] > 0, 'Corrected target is behind the camera')
        sample['source_camera_xyz_mm'] = sample['camera_xyz_mm']
        sample['camera_xyz_mm'] = xyz.tolist()
    report.update(workspace_profile_id=new.profile_id,
                  workspace_profile_sha256=metadata['workspace_profile_sha256'],
                  retarget_review=dict(source_workspace_id=old.profile_id,
                      source_workspace_sha256=source_hash,
                      old_A_mm=old.targets['A'].tolist(), new_A_mm=new.targets['A'].tolist(),
                      method='Refit unchanged eye pixels with R @ corrected_A + t for each source observation',
                      assumption='Same physical target; registration correction only, not moved object',
                      source_captures_preserved=True, new_wearing_validated=False))
    report['limitations'].append('Retargeted historical observations do not validate current wearing or optical alignment.')
    return _fit_report(report)


def _add_review(report):
    """Diagnostic thresholds are collection targets, not optical acceptance criteria."""
    samples, warnings = report['samples'], []
    if any(s['capture_mode'] != 'paired' for s in samples):
        warnings.append('legacy_single_eye_samples')
    for name in ('left', 'right'):
        eye = report['eyes'][name]
        fit = [s for s in samples if s['eye'] == name and s['split'] == 'fit']
        check = [s for s in samples if s['eye'] == name and s['split'] == 'check']
        if len(fit) < 12: warnings.append('limited_fit_count')
        if len(check) < 4: warnings.append('limited_check_count')
        eye['fit_depth_range_mm'] = None
        eye['check_errors_by_depth'] = []
        if fit:
            xyz = np.array([s['camera_xyz_mm'] for s in fit])
            eye['fit_depth_range_mm'] = [float(xyz[:, 2].min()), float(xyz[:, 2].max())]
            eye['fit_xyz_span_mm'] = np.ptp(xyz, axis=0).tolist()
            if np.ptp(xyz[:, 2]) < 100: warnings.append('limited_depth_span')
        if eye['projection'] is None: warnings.append('missing_projection')
        for split in ('fit', 'check'):
            error = eye[split + '_error_px']
            if error and error['max'] > 10: warnings.append('large_' + split + '_error')
        if eye['check_error_px']:
            eye['check_errors_by_depth'] = sorted([
                dict(pose_id=s['pose_id'], camera_z_mm=s['camera_xyz_mm'][2], error_px=error)
                for s, error in zip(check, eye['check_error_px']['per_point'])],
                key=lambda value: value['camera_z_mm'])
            lo, hi = eye['fit_depth_range_mm']
            if any(not lo <= s['camera_xyz_mm'][2] <= hi for s in check):
                warnings.append('check_outside_fit_depth')
    report['stereo_geometry'] = None
    report['stereo_check'] = dict(pair_count=0)
    if all(eye['projection'] is not None for eye in report['eyes'].values()):
        matrices = [np.array(report['eyes'][eye]['projection']) for eye in ('left', 'right')]
        centers = [-np.linalg.solve(p[:, :3], p[:, 3]) for p in matrices]
        delta = centers[1] - centers[0]
        separation = float(np.linalg.norm(delta))
        report['stereo_geometry'] = dict(left_center_camera_mm=centers[0].tolist(),
            right_center_camera_mm=centers[1].tolist(), right_minus_left_mm=delta.tolist(),
            center_separation_mm=separation, interpretation='fitted_pinhole_centers_not_measured_ipd')
        if not 40 <= separation <= 90 or delta[0] <= 0 or abs(delta[1]) > 15 or abs(delta[2]) > 30:
            warnings.append('implausible_stereo_geometry')
        pairs = {}
        for s in samples:
            if s['split'] == 'check' and s['capture_mode'] == 'paired':
                pairs.setdefault(s['pose_id'], {})[s['eye']] = s
        residuals = []
        for pair in pairs.values():
            if set(pair) != {'left', 'right'}: continue
            predicted, observed = [], []
            for p, name in zip(matrices, ('left', 'right')):
                q = p @ np.r_[pair[name]['camera_xyz_mm'], 1.]
                predicted.append(q[:2] / q[2])
                observed.append(np.array(pair[name]['eye_pixel']))
            residuals.append((predicted[0] - predicted[1]) - (observed[0] - observed[1]))
        report['stereo_check']['pair_count'] = len(residuals)
        if residuals:
            residuals = np.abs(np.array(residuals))
            for axis, label in enumerate(('horizontal', 'vertical')):
                report['stereo_check'][label + '_disparity_error_px'] = dict(
                    rms=float(np.sqrt(np.mean(residuals[:, axis] ** 2))),
                    max=float(residuals[:, axis].max()))
        else:
            warnings.append('no_paired_check_points')
    warnings = sorted(set(warnings))
    report['collection_review'] = dict(status='needs_review' if warnings else 'ready_for_optical_check',
        warnings=warnings, recommended_fit_per_eye=12, recommended_check_per_eye=4,
        paired_pose_count=len({s['pose_id'] for s in samples if s['capture_mode'] == 'paired'}),
        threshold_note='Heuristic numeric checks only; no measured IPD, millimetre accuracy or comfort pass.')


def probe_profile(report: dict) -> dict:
    """Explicit, unverified experimental export; not accepted by normal guidance."""
    _require(report.get('schema_version') == 'beast_display_fit_review_v1'
             and report.get('status') in ('needs_check_points', 'candidate_fitted')
             and report.get('activation_status') == 'not_activated'
             and report.get('calibration_valid') is False
             and report.get('display_alignment_verified') is False, 'No usable unverified candidate')
    result = dict(schema_version='beast_candidate_projection_probe_v1', candidate_only=True,
                  calibration_valid=False, display_alignment_verified=False,
                  coordinate_convention='eye_local_pixels_top_left', display_mode='full_sbs',
                  channel_order='left_half_left_eye_right_half_right_eye', eye_width=1920, eye_height=1080,
                  **{name: report[name] for name in BINDING_FIELDS})
    for eye in ('left', 'right'):
        data = report['eyes'][eye]
        _require(data['fit_count'] >= 6 and data['status'] in ('needs_check_points', 'candidate_fitted'),
                 'Both eyes need valid candidate fits')
        matrix = finite_array(data['projection'], (3, 4), 'candidate projection')
        _require(np.linalg.matrix_rank(matrix[:, :3]) == 3, 'Singular candidate projection')
        samples = [s for s in report['samples'] if s['eye'] == eye and s['split'] == 'fit']
        _errors(matrix, np.array([s['camera_xyz_mm'] for s in samples]),
                np.array([s['eye_pixel'] for s in samples]))
        result[eye + '_projection'] = matrix.reshape(-1).tolist()
    if 'retarget_review' in report:
        result['retarget_review'] = report['retarget_review']
    return result


def create_pair_dataset(destination: Path, fit_paths, check_paths) -> Path:
    """Select one final pair per collection session; never infer or reshuffle holdouts."""
    _require(len(fit_paths) > 0, 'Select fit pairs explicitly')
    entries, groups = [], set()
    for split, paths in (('fit', fit_paths), ('check', check_paths)):
        for source in paths:
            path = Path(source).resolve()
            data = json.loads(path.read_bytes())
            _require(data.get('schema_version') == 'beast_display_correspondence_pair_v2',
                     'Dataset assembly accepts paired records only')
            group = data.get('observation', {}).get('session_id')
            _require(isinstance(group, str) and group.strip() and group not in groups,
                     'Choose one final pair per pose session; never share a pose between fit and check')
            groups.add(group)
            entries.append(dict(path=str(path), pose_id=group, split=split))
    destination = Path(destination)
    write_json(destination, dict(schema_version='beast_display_fit_dataset_v1', points=entries))
    return destination


def run_fit(dataset_path: Path, camera_path: Path, workspace_path: Path, *, output_root: Path | None = None,
            export_probe: bool = False, retarget_from_workspace: Path | None = None) -> Path:
    report = (analyze_dataset(dataset_path, camera_path, workspace_path) if retarget_from_workspace is None
              else analyze_retargeted_dataset(dataset_path, camera_path, retarget_from_workspace, workspace_path))
    root = output_root or Path(os.environ['LOCALAPPDATA']) / 'ARAssembly/beast-mvp/display_fits'
    directory = Path(root) / ('fit-' + stamp())
    directory.mkdir(parents=True, exist_ok=False)
    write_json(directory / 'report.json', report)
    if export_probe:
        write_json(directory / 'candidate-probe.json', probe_profile(report))
    return directory


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--camera-profile', type=Path, required=True)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--retarget-from-workspace', type=Path,
                        help='Explicit A measurement correction from this unchanged-marker source workspace')
    parser.add_argument('--output-root', type=Path)
    parser.add_argument('--export-probe', action='store_true', help='Export an explicitly unverified optical test profile')
    parser.add_argument('--fit-pairs', type=Path, nargs='+', help='Create a NEW dataset from these final paired records')
    parser.add_argument('--check-pairs', type=Path, nargs='+', help='Independent paired checks; never used for fitting')
    args = parser.parse_args(argv)
    try:
        if args.fit_pairs is not None:
            create_pair_dataset(args.dataset, args.fit_pairs, args.check_pairs or [])
        elif args.check_pairs is not None:
            raise ValueError('--check-pairs requires --fit-pairs when creating a new dataset')
        directory = run_fit(args.dataset, args.camera_profile, args.workspace, export_probe=args.export_probe,
                            output_root=args.output_root, retarget_from_workspace=args.retarget_from_workspace)
        report = json.loads((directory / 'report.json').read_text(encoding='utf-8'))
        print(json.dumps(dict(directory=str(directory.resolve()), status=report['status'],
                              eyes=report['eyes'], collection_review=report['collection_review'],
                              stereo_geometry=report['stereo_geometry'], stereo_check=report['stereo_check'],
                              activation_status='not_activated'), allow_nan=False))
        return 0 if report['status'] == 'candidate_fitted' else 1
    except (OSError, ValueError, TypeError, KeyError, cv2.error) as exc:
        print(f'[ERROR] {exc}')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
