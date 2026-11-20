"""Offline partial-marker replay; numerical acceptance never enables live tracking."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from .corner_tracking_report import metrics
from .display_observation_server import pose_reason_code
from .tracking_report import numeric_evidence, selected_rows
from .workspace_live_preview import load_profiles
from .workspace_projection import (
    _estimate_planar_pose, estimate_pose, finite_array, marker_center_px,
    require_ippe_support, require_spread,
)


def evaluate_pose(detections, workspace, camera, image_size):
    detail = dict(baseline_reason='tracking', candidate_reason='tracking',
                  fallback_attempted=False, solver='IPPE')
    try:
        baseline = estimate_pose(detections, workspace, camera, image_size)
        detail['baseline_rms_px'] = detail['candidate_rms_px'] = baseline.rms_px
        return baseline, baseline, detail
    except ValueError as exc:
        detail.update(baseline_reason=pose_reason_code('pose_rejected', str(exc)),
                      baseline_error=str(exc), solver=None)
        detail['candidate_reason'] = detail['baseline_reason']
    ids = sorted(detections)
    if (detail['baseline_reason'] != 'marker_geometry' or len(ids) != 4
            or set(ids) - set(workspace.markers)):
        return None, None, detail
    objects = np.array([workspace.markers[key] for key in ids], np.float64)
    try:
        require_spread(objects[:, :2], 'Visible metric markers')
    except ValueError:
        return None, None, detail
    try:
        require_ippe_support(objects[:, :2])
    except ValueError:
        pass
    else:
        return None, None, detail
    detail.update(fallback_attempted=True, solver='SQPNP')
    try:
        observed = np.array([marker_center_px(detections[key], camera) for key in ids])
        candidate = _estimate_planar_pose(objects, observed, ids, camera, 3., 5., .25,
                                          solver=cv2.SOLVEPNP_SQPNP)
        detail.update(candidate_reason='tracking', candidate_rms_px=candidate.rms_px)
        return None, candidate, detail
    except ValueError as exc:
        detail.update(candidate_reason=pose_reason_code('pose_rejected', str(exc)),
                      candidate_error=str(exc))
        return None, None, detail


def target_deltas(reference, candidate, workspace, camera):
    objects = np.array([workspace.targets[key] for key in 'ABCD'])
    xyz, pixels = [], []
    for pose in (reference, candidate):
        points = objects @ cv2.Rodrigues(pose.rvec)[0].T + pose.tvec.reshape(3)
        if not np.isfinite(points).all() or (points[:, 2] <= 0).any():
            raise ValueError('All A-D targets must have finite positive camera depth')
        xyz.append(points)
        # Include offscreen targets: clipping could hide the largest displacement.
        pixels.append(cv2.projectPoints(objects, pose.rvec, pose.tvec, camera.matrix,
                                        camera.distortion)[0].reshape(4, 2))
    px = np.linalg.norm(pixels[1] - pixels[0], axis=1)
    mm = np.linalg.norm(xyz[1] - xyz[0], axis=1)
    if not np.isfinite(px).all() or not np.isfinite(mm).all():
        raise ValueError('Nonfinite target comparison')
    return dict(targets={key: dict(camera_px=float(p), camera_xyz_mm=float(m))
                         for key, p, m in zip('ABCD', px, mm)},
                max_target_delta_px=float(px.max()), max_target_delta_mm=float(mm.max()))


def _summary(records):
    result = dict(cases=len(records),
        baseline_reason_counts=dict(Counter(r['baseline_reason'] for r in records)),
        candidate_reason_counts=dict(Counter(r['candidate_reason'] for r in records)),
        fallback_attempts=sum(r['fallback_attempted'] for r in records),
        fallback_accepted=sum(r['fallback_attempted'] and r['candidate_reason'] == 'tracking' for r in records))
    if records and 'preserved' in records[0]:
        result.update(preservation_pass=sum(r['preserved'] is True for r in records),
                      preservation_fail=sum(r['preserved'] is False for r in records),
                      not_compared=sum(r['preserved'] is None for r in records),
                      baseline_preservation_pass=sum(r['baseline_preserved'] is True for r in records),
                      baseline_preservation_fail=sum(r['baseline_preserved'] is False for r in records))
        for key in ('max_target_delta_px', 'max_target_delta_mm'):
            result[key] = metrics([r[key] for r in records if key in r])
    return result


def replay_trace(path, profiles, *, first_frame=None, last_frame=None,
                 max_target_px=5., max_target_mm=5.):
    limits = (max_target_px, max_target_mm)
    if any(type(v) not in (int, float) or not np.isfinite(v) or v <= 0 for v in limits):
        raise ValueError('Preservation limits must be finite and positive')
    path = Path(path)
    source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    camera, workspace, meta = profiles
    if set(workspace.targets) != set('ABCD'):
        raise ValueError('All A-D targets are required')
    observed, masked, references = [], [], 0
    for row in selected_rows(path, first_frame, last_frame):
        d = row.get('presentation_diagnostics')
        if not isinstance(d, dict) or any(d.get(key) != meta[key] for key in (
                'camera_profile_sha256', 'workspace_profile_sha256')):
            raise ValueError('Numeric evidence profile binding mismatch')
        if d.get('image_size') != list(camera.image_size):
            raise ValueError('Numeric evidence resolution mismatch')
        empty = d.get('marker_ids') == [] and d.get('detected_corners_px') == {}
        if not empty and not numeric_evidence(d):
            raise ValueError('Incomplete or duplicate numeric marker evidence')
        detections = {int(k): finite_array(v, (4, 2), 'detected corners')
                      for k, v in d['detected_corners_px'].items()}
        if set(detections) - set(workspace.markers):
            raise ValueError('Unregistered numeric marker')
        baseline, _, detail = evaluate_pose(detections, workspace, camera, d['image_size'])
        recorded = d.get('reason_code', pose_reason_code(d.get('analysis_status'), d.get('analysis_reason') or ''))
        detail.update(frame_id=row['frame_id'], state=row.get('state'), marker_ids=sorted(detections),
                      recorded_reason=recorded)
        observed.append(detail)
        if baseline is None or recorded != 'tracking' or len(detections) != 5:
            continue
        references += 1
        for removed in sorted(detections):
            subset = {k: v for k, v in detections.items() if k != removed}
            masked_baseline, candidate, case = evaluate_pose(subset, workspace, camera, d['image_size'])
            case.update(frame_id=row['frame_id'], removed_marker=removed, marker_ids=sorted(subset),
                        preserved=None, baseline_preserved=None)
            if candidate is not None:
                try:
                    case.update(target_deltas(baseline, candidate, workspace, camera))
                    case['preserved'] = (case['max_target_delta_px'] <= max_target_px
                                         and case['max_target_delta_mm'] <= max_target_mm)
                    # A successful masked IPPE pose is returned unchanged by the candidate path.
                    if masked_baseline is not None:
                        case['baseline_preserved'] = case['preserved']
                except ValueError as exc:
                    case['comparison_error'] = str(exc)
            masked.append(case)
    if not observed:
        raise ValueError('No selected frames')
    if hashlib.sha256(path.read_bytes()).hexdigest() != source_hash:
        raise ValueError('Trace changed during replay; use a stopped session')
    return dict(schema_version='beast_partial_marker_replay_v1', live_enabled=False,
        optical_alignment_verified=False, source_trace=str(path.resolve()), source_trace_sha256=source_hash,
        camera_profile_sha256=meta['camera_profile_sha256'], workspace_profile_sha256=meta['workspace_profile_sha256'],
        opencv_version=cv2.__version__, frame_range=[observed[0]['frame_id'], observed[-1]['frame_id']],
        scope='Saved numeric observations only; no detector occlusion simulation or live activation',
        preservation_scope='Both limits compare against full-five-marker IPPE, not physical or optical ground truth; report only, not a live gate',
        comparison_scope='All A-D distorted camera pixels, including offscreen targets; 3D target differences in camera coordinates, not camera-position differences',
        baseline_scope='Unmodified IPPE on the observed or masked marker set',
        candidate_scope='Same IPPE result, or SQPNP only for exactly four spread registered centers failing IPPE rank',
        preservation_criteria=dict(max_target_px=max_target_px, max_target_mm=max_target_mm, report_only=True),
        observed=dict(_summary(observed), ground_truth_available=False,
            recorded_reason_counts=dict(Counter(r['recorded_reason'] for r in observed)),
            baseline_recorded_mismatches=[r['frame_id'] for r in observed if r['baseline_reason'] != r['recorded_reason']],
            records=observed),
        leave_one_out=dict(_summary(masked), reference_frames=references,
            reference='Accepted full-five-marker IPPE pose from the same frame; not independent physical truth',
            by_removed_marker={str(k): _summary([r for r in masked if r['removed_marker'] == k])
                               for k in sorted({r['removed_marker'] for r in masked})}, records=masked))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', required=True, type=Path)
    parser.add_argument('--camera-profile', required=True, type=Path)
    parser.add_argument('--workspace-profile', required=True, type=Path)
    parser.add_argument('--first-frame', type=int)
    parser.add_argument('--last-frame', type=int)
    parser.add_argument('--max-target-px', type=float, default=5.)
    parser.add_argument('--max-target-mm', type=float, default=5.)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError('Output already exists; choose a new path')
        report = replay_trace(args.results, load_profiles(args.camera_profile, args.workspace_profile),
                              first_frame=args.first_frame, last_frame=args.last_frame,
                              max_target_px=args.max_target_px, max_target_mm=args.max_target_mm)
        text = json.dumps(report, indent=2, allow_nan=False)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(text + '\n')
        print(json.dumps(dict(output=str(args.output), frames=report['observed']['cases'],
            fallback_accepted=report['observed']['fallback_accepted'],
            leave_one_out_cases=report['leave_one_out']['cases'],
            preservation_pass=report['leave_one_out'].get('preservation_pass', 0), live_enabled=False)))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f'Partial marker replay failed: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
