"""Offline failure attribution and omission stress test. No live integration."""

import argparse
from collections import Counter
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from .corner_tracking_report import metrics
from .display_observation_server import pose_reason_code
from .partial_marker_replay import target_deltas
from .tracking_report import numeric_evidence, selected_rows
from .workspace_live_preview import load_profiles
from .workspace_projection import (
    _physical_pose, estimate_pose, finite_array, marker_center_px, pixel_to_plane, require_spread,
)


def three_center_solutions(ids, centers, workspace, camera):
    result = dict(physical_solutions=0, solutions=[])
    objects = np.array([workspace.markers[k] for k in ids])
    observed = np.array([centers[k] for k in ids])
    try:
        require_spread(objects[:, :2], 'Three metric centers')
        require_spread(observed, 'Three image centers')
        _, rotations, translations, _ = cv2.solvePnPGeneric(
            objects, observed, camera.matrix, None, flags=cv2.SOLVEPNP_SQPNP)
        for rvec, tvec in zip(rotations, translations):
            pose = _physical_pose(rvec, tvec, objects, observed, ids, camera)
            if pose is not None:
                result['solutions'].append(dict(rms_px=pose.rms_px,
                    camera_position_mm=pose.camera_position_mm.tolist()))
        result['physical_solutions'] = len(result['solutions'])
    except (ValueError, cv2.error) as exc:
        result['error'] = str(exc)
    return result


def evaluate(detections, workspace, camera):
    """Normal results are unchanged; discarded evidence is explicit and offline only."""
    if any(type(k) is not int or k not in workspace.markers for k in detections):
        raise ValueError('Only registered integer marker IDs are allowed')
    centers = {k: marker_center_px(v, camera) for k,v in detections.items()}
    detail = dict(method='unavailable', baseline_reason='tracking', marker_ids=sorted(detections))
    try:
        baseline = estimate_pose(detections, workspace, camera, camera.image_size)
    except ValueError as exc:
        detail.update(baseline_reason=pose_reason_code('pose_rejected', str(exc)), baseline_error=str(exc))
    else:
        detail['method'] = 'baseline'
        return baseline, baseline, detail
    if len(detections) == 3:
        detail['three_center'] = three_center_solutions(sorted(detections), centers, workspace, camera)
    if detail['baseline_reason'] != 'pose_quality':
        return None, None, detail
    try:
        # Inspect a rejected fit, never emit this relaxed fit as an accepted pose.
        fit = estimate_pose(detections, workspace, camera, camera.image_size,
                            max_rms_px=1e6, max_point_error_px=1e6)
    except ValueError as exc:
        detail['diagnostic_error'] = str(exc)
        return None, None, detail
    residuals = fit.observed_centers_px - fit.projected_centers_px
    norms = np.linalg.norm(residuals, axis=1)
    detail.update(rejected_rms_px=fit.rms_px, rejected_max_px=fit.max_error_px,
        residuals_px={str(k):v.tolist() for k,v in zip(fit.marker_ids, residuals)},
        worst_marker=fit.marker_ids[int(np.argmax(norms))],
        over_limit_ids=[k for k,e in zip(fit.marker_ids,norms) if e > 5.])
    if len(detections) != 5 or len(detail['over_limit_ids']) != 1:
        return None, None, detail
    omitted = detail['over_limit_ids'][0]
    try:
        candidate = estimate_pose({k:v for k,v in detections.items() if k != omitted},
                                  workspace, camera, camera.image_size)
    except ValueError as exc:
        detail['subset_error'] = str(exc)
        return None, None, detail
    detail.update(method='single_center_omission', omitted_marker=omitted,
                  candidate_rms_px=candidate.rms_px,
                  rejected_fit_delta=target_deltas(fit, candidate, workspace, camera))
    return None, candidate, detail


def failure_runs(records):
    runs, group = [], []
    for row in [*records, None]:
        if group and (row is None or row['state'] != group[0]['state']
                      or row['baseline_reason'] == 'tracking'):
            runs.append(dict(state=group[0]['state'], first=group[0]['frame_id'], last=group[-1]['frame_id'],
                frames=len(group), sample_span_ms=group[-1]['timestamp_ms']-group[0]['timestamp_ms'],
                reasons=dict(Counter(r['baseline_reason'] for r in group))))
            group = []
        if row is not None and row['baseline_reason'] != 'tracking':
            group.append(row)
    return runs


def fault_sweep(references, workspace, camera):
    records = []
    for frame, detections in references:
        reference = estimate_pose(detections, workspace, camera, camera.image_size)
        for marker in sorted(detections):
            for shift in ([15.,0.], [-15.,0.], [0.,15.], [0.,-15.]):
                changed = {k:v.copy() for k,v in detections.items()}
                changed[marker] += shift
                record = dict(frame_id=frame, perturbed_marker=marker, shift_px=shift)
                try:
                    baseline, candidate, detail = evaluate(changed, workspace, camera)
                    record.update(method=detail['method'], omitted_marker=detail.get('omitted_marker'))
                    if candidate is not None:
                        delta = target_deltas(reference, candidate, workspace, camera)
                        record.update(px=delta['max_target_delta_px'], mm=delta['max_target_delta_mm'],
                            preserved=delta['max_target_delta_px'] <= 5. and delta['max_target_delta_mm'] <= 5.)
                except ValueError as exc:
                    record.update(method='invalid_perturbation', error=str(exc))
                records.append(record)
    fallback = [r for r in records if r['method'] == 'single_center_omission']
    return dict(cases=len(records), fallback_accepted=len(fallback),
        fallback_preserved=sum(r.get('preserved') is True for r in fallback),
        wrong_omission=sum(r['omitted_marker'] != r['perturbed_marker'] for r in fallback),
        fallback_px=metrics([r['px'] for r in fallback]), fallback_mm=metrics([r['mm'] for r in fallback]),
        baseline_accepted=sum(r['method']=='baseline' for r in records),
        reference='same-frame unmodified five-marker fit; not physical truth', records=records)


def read_observations(path, profiles):
    path = Path(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    camera, workspace, meta = profiles
    records, last_time = [], -1
    for row in selected_rows(path, None, None):
        d = row.get('presentation_diagnostics', {})
        if any(d.get(k) != meta[k] for k in ('camera_profile_sha256','workspace_profile_sha256')):
            raise ValueError('Profile binding mismatch')
        if d.get('image_size') != list(camera.image_size):
            raise ValueError('Resolution mismatch')
        if not numeric_evidence(d) and not (d.get('marker_ids') == [] and d.get('detected_corners_px') == {}):
            raise ValueError('Incomplete numeric evidence')
        capture = row.get('filter_input', {})
        now = capture.get('timestamp_ms')
        if (type(capture.get('frame_id')) is not int or capture['frame_id'] != row['frame_id']
                or type(now) is not int or now <= last_time):
            raise ValueError('Invalid capture identity or ordering')
        last_time = now
        detected = {int(k):finite_array(v,(4,2),'stored corners') for k,v in d['detected_corners_px'].items()}
        if set(detected)-set(workspace.markers):
            raise ValueError('Unregistered marker ID')
        records.append(dict(frame_id=row['frame_id'], timestamp_ms=now, state=row['state'],
                            detected=detected, recorded_reason=d['reason_code']))
    if not records:
        raise ValueError('No numeric observations')
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError('Trace changed while reading')
    return digest, records


def audit(path, profiles):
    path = Path(path)
    digest, rows = read_observations(path, profiles)
    camera, workspace, meta = profiles
    records, references = [], []
    for row in rows:
        detected = row['detected']
        baseline, candidate, detail = evaluate(detected, workspace, camera)
        if detail['baseline_reason'] != row['recorded_reason']:
            raise ValueError(f"Recorded reason mismatch at frame {row['frame_id']}")
        records.append(dict(frame_id=row['frame_id'], timestamp_ms=row['timestamp_ms'], state=row['state'], **detail))
        # Fixed sampling independent of residual size; reuse each reference for all faults.
        if baseline is not None and len(detected)==5 and row['frame_id'] % 30 == 0:
            references.append((row['frame_id'], detected))
    if not records:
        raise ValueError('No numeric observations')
    stress = fault_sweep(references, workspace, camera)
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError('Trace changed during audit')
    states = {}
    for state in sorted({r['state'] for r in records}):
        rs = [r for r in records if r['state']==state]
        states[state] = dict(frames=len(rs), reasons=dict(Counter(r['baseline_reason'] for r in rs)),
            methods=dict(Counter(r['method'] for r in rs)),
            quality_worst_marker=dict(Counter(str(r['worst_marker']) for r in rs if 'worst_marker' in r)),
            three_center_ambiguous=sum(r.get('three_center',{}).get('physical_solutions',0)>1 for r in rs))
    return dict(schema_version='beast_pose_failure_audit_v1', live_enabled=False,
        optical_alignment_verified=False, source_trace=str(path.resolve()), source_sha256=digest,
        camera_profile_sha256=meta['camera_profile_sha256'], workspace_profile_sha256=meta['workspace_profile_sha256'],
        opencv_version=cv2.__version__, states=states, records=records, failure_runs=failure_runs(records),
        fault_sweep=stress, policy=dict(full_marker_count=5, unique_residual_above_px=5.,
            subset_solver='unchanged IPPE', three_center_pose_emission=False),
        scope='Rejected-fit residuals do not prove which marker is wrong. Omission discards evidence; offline only.')


def fit_top_row(samples, workspace, camera):
    """Hypothesize marker 1 along the existing 0-2 row; never fit targets or optics."""
    frames = [frame for frame,_ in samples]
    if len(frames)<3 or len(set(frames))!=len(frames) or any(type(n) is not int or n<1 for n in frames):
        raise ValueError('At least three unique positive frame IDs required')
    start, end = workspace.markers[0], workspace.markers[2]
    direction = end-start
    length2 = float(direction @ direction)
    if length2 < 1 or np.linalg.norm(np.cross(direction,workspace.markers[1]-start)) > 1e-6:
        raise ValueError('Existing top row must already be collinear')
    undistorted = replace(camera, distortion=np.zeros(5))
    positions, used = [], []
    for frame,detected in samples:
        if set(detected)!={0,1,2,4,5}:
            continue
        try:
            pose = estimate_pose({k:v for k,v in detected.items() if k!=1},workspace,camera,camera.image_size)
            point = pixel_to_plane(marker_center_px(detected[1],camera),0.,pose,undistorted)
        except ValueError:
            continue
        positions.append(point)
        used.append(frame)
    if len(positions)<3:
        raise ValueError('At least three usable four-marker reference poses required')
    fractions = [(point-start) @ direction / length2 for point in positions]
    alpha = float(np.median(fractions))
    if not 0 < alpha < 1:
        raise ValueError('Fitted middle center is not between row endpoints')
    markers = {k:v.copy() for k,v in workspace.markers.items()}
    markers[1] = start + alpha*direction
    return replace(workspace,markers=markers), dict(marker_id=1,sample_count=len(used),frames=used,
        physical_measurement=False,registered_mm=workspace.markers[1].tolist(),hypothesis_mm=markers[1].tolist(),
        unconstrained_median_mm=np.median(positions,axis=0).tolist(),
        unconstrained_p05_mm=np.percentile(positions,5,axis=0).tolist(),
        unconstrained_p95_mm=np.percentile(positions,95,axis=0).tolist(),
        scope='Relative to the other registered centers and existing intrinsics; not independent measurement')


def compare_top_row(training_path, evaluation_paths, profiles, cutoff):
    if type(cutoff) is not int or cutoff < 1:
        raise ValueError('Positive training cutoff required')
    camera, workspace, meta = profiles
    training_path = Path(training_path)
    train_hash, rows = read_observations(training_path,profiles)
    samples = [(r['frame_id'],r['detected']) for r in rows if r['frame_id']<=cutoff
               and r['state'] in ('S2','S3','S4','S5')]
    candidate, fit = fit_top_row(samples,workspace,camera)
    reports = []
    for path in evaluation_paths:
        path = Path(path)
        digest, rows = read_observations(path,profiles)
        records = []
        same_trace = path.resolve()==training_path.resolve() or digest==train_hash
        for row in rows:
            if row['state'] not in ('S2','S3','S4','S5') or (same_trace and row['frame_id']<=cutoff):
                continue
            poses, reasons = [], []
            for profile in (workspace,candidate):
                try:
                    poses.append(estimate_pose(row['detected'],profile,camera,camera.image_size))
                    reasons.append('tracking')
                except ValueError as exc:
                    poses.append(None)
                    reasons.append(pose_reason_code('pose_rejected',str(exc)))
            if reasons[0]!=row['recorded_reason']:
                raise ValueError('Recorded baseline mismatch')
            a,b = poses
            status = 'both' if a is not None and b is not None else ('lost' if a is not None else ('extra' if b is not None else 'neither'))
            record = dict(frame_id=row['frame_id'],state=row['state'],status=status,
                          baseline_reason=reasons[0],hypothesis_reason=reasons[1])
            if status=='both': record.update(target_deltas(a,b,workspace,camera))
            records.append(record)
        if not records:
            raise ValueError('No held-out active-stage observations')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise ValueError('Evaluation trace changed during comparison')
        reports.append(dict(source=str(path.resolve()),sha256=digest,frames=len(records),records=records,
            states={state:dict(Counter(r['status'] for r in records if r['state']==state)) for state in ('S2','S3','S4','S5')},
            counts=dict(Counter(r['status'] for r in records)),
            both_px=metrics([r['max_target_delta_px'] for r in records if r['status']=='both']),
            both_mm=metrics([r['max_target_delta_mm'] for r in records if r['status']=='both'])))
    if hashlib.sha256(training_path.read_bytes()).hexdigest()!=train_hash:
        raise ValueError('Training trace changed during comparison')
    return dict(schema_version='beast_top_row_hypothesis_v1',live_enabled=False,calibration_valid=False,
        training_source=str(training_path.resolve()),training_sha256=train_hash,cutoff=cutoff,fit=fit,
        camera_profile_sha256=meta['camera_profile_sha256'],workspace_profile_sha256=meta['workspace_profile_sha256'],
        evaluations=reports,scope='Coordinate hypothesis only; no deployable profile, no optical ground truth, no task timing claims')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('results','camera-profile','workspace-profile','output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--fit-top-row-through',type=int)
    parser.add_argument('--evaluation-results',type=Path,action='append')
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError('Output exists; choose a new path')
        profiles = load_profiles(args.camera_profile,args.workspace_profile)
        if (args.fit_top_row_through is None) != (args.evaluation_results is None):
            raise ValueError('Row hypothesis requires both a training cutoff and evaluation traces')
        report = (audit(args.results,profiles) if args.fit_top_row_through is None else
            compare_top_row(args.results,args.evaluation_results,profiles,args.fit_top_row_through))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x',encoding='utf-8') as stream:
            json.dump(report,stream,indent=2,allow_nan=False)
        print(json.dumps(dict(output=str(args.output),schema=report['schema_version'],live_enabled=False)))
    except (ValueError,OSError,TypeError,KeyError) as exc:
        parser.exit(2,f'Offline audit failed: {exc}\n')


if __name__ == '__main__':
    main()
