"""Offline, unmeasured corner hypothesis versus center pose on a saved numeric trace."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np

from .display_observation_server import pose_reason_code
from .tracking_report import numeric_evidence, selected_rows
from .workspace_projection import (
    CameraModel, MetricWorkspace, estimate_pose, estimate_corner_pose,
    finite_array, pixel_to_plane, project_targets,
)


def reference_candidate(reference, profiles, *, side_mm):
    """Estimate orientation only; keep measured centers and an explicit assumed side."""
    camera, workspace, camera_hash, workspace_hash = profiles
    if type(side_mm) not in (int, float) or not math.isfinite(side_mm) or side_mm <= 0:
        raise ValueError('Assumed side must be finite and positive')
    try:
        ref_cam = CameraModel.from_profile(reference['camera'])
        ref_board = MetricWorkspace.from_dict(reference['workspace'])
        same = (ref_cam.profile_id == camera.profile_id and ref_cam.image_size == camera.image_size
                and np.array_equal(ref_cam.matrix, camera.matrix)
                and np.array_equal(ref_cam.distortion, camera.distortion)
                and ref_board.profile_id == workspace.profile_id)
        for first, second in ((ref_board.markers, workspace.markers), (ref_board.targets, workspace.targets)):
            same = same and set(first) == set(second) and all(np.array_equal(first[k], second[k]) for k in first)
        if not same:
            raise ValueError('geometry differs')
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError('Reference geometry must match supplied profiles') from exc
    image_hash = reference.get('source_image_sha256', '')
    if (not isinstance(image_hash, str) or len(image_hash) != 64
            or any(char not in '0123456789abcdef' for char in image_hash)):
        raise ValueError('Reference source image SHA256 required')
    source = reference.get('detected_corners_px')
    if (not isinstance(source, dict) or not source
            or any(key not in {str(k) for k in workspace.markers} for key in source)):
        raise ValueError('Reference requires registered marker IDs')
    detections = {int(key): finite_array(value, (4, 2), 'reference corners') for key, value in source.items()}
    for corners in detections.values():
        if cv2.contourArea(corners.astype(np.float32), oriented=True) <= 0:
            raise ValueError('Reference image winding must match decoded front face')
    pose = estimate_pose(detections, workspace, camera, camera.image_size)
    square = np.array([[-.5, .5], [.5, .5], [.5, -.5], [-.5, -.5]])
    world, diagnostics = {}, {}
    for key in sorted(detections):
        backprojected = np.array([pixel_to_plane(pixel, 0., pose, camera) for pixel in detections[key]])
        xy = backprojected[:, :2] - backprojected[:, :2].mean(axis=0)
        # Least-squares planar rotation of a fixed-size square, preserving decoded order.
        angle = math.atan2(float(np.sum(square[:, 0] * xy[:, 1] - square[:, 1] * xy[:, 0])),
                           float(np.sum(square * xy)))
        rotation = np.array([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])
        offsets = np.column_stack([side_mm * square @ rotation.T, np.zeros(4)])
        world[str(key)] = (offsets + workspace.markers[key]).tolist()
        diagnostics[str(key)] = {
            'rotation_degrees': math.degrees(angle),
            'edge_lengths_mm': np.linalg.norm(np.roll(backprojected, -1, axis=0) - backprojected, axis=1).tolist(),
            'backprojected_center_delta_mm': float(np.linalg.norm(backprojected.mean(axis=0) - workspace.markers[key])),
        }
    return dict(schema_version='beast_offline_corner_hypothesis_v1', offline_only=True,
                geometry_measured=False, optical_alignment_verified=False,
                scope='orientation derived from center pose, not independent ground truth or live calibration',
                source_image_sha256=image_hash, camera_profile_sha256=camera_hash,
                workspace_profile_sha256=workspace_hash, assumed_black_side_mm=side_mm,
                missing_marker_ids=sorted(set(workspace.markers) - set(detections)),
                marker_corners_mm=world, orientation_diagnostics=diagnostics,
                reference_center_rms_px=pose.rms_px)


def metrics(values):
    if not values:
        return None
    values = sorted(values)
    return dict(n=len(values), mean=float(np.mean(values)),
                p95=values[math.ceil(.95 * len(values)) - 1], max=values[-1])


def compare_trace(path, profiles, candidate, *, first_frame=None, last_frame=None):
    camera, workspace, camera_hash, workspace_hash = profiles
    if (candidate.get('camera_profile_sha256'), candidate.get('workspace_profile_sha256')) != profiles[2:]:
        raise ValueError('Candidate profile binding mismatch')
    world = {int(key): value for key, value in candidate['marker_corners_mm'].items()}
    if not world or set(world) - set(workspace.markers):
        raise ValueError('Candidate contains unregistered geometry')
    names = ('baseline', 'corner_candidate')
    counts = {name: Counter() for name in names}
    errors = {name: {} for name in names}
    residuals, steps = {name: [] for name in names}, {name: [] for name in names}
    previous = {name: None for name in names}
    run, longest = dict.fromkeys(names, 0), dict.fromkeys(names, 0)
    groups, observations, unmodeled = {}, Counter(), Counter()
    paired = dict.fromkeys(('both', 'baseline_only', 'candidate_only', 'neither'), 0)
    camera_deltas, target_deltas = [], []
    rows = numeric = 0
    first = last = None
    for row in selected_rows(path, first_frame, last_frame, pose_trace=True):
        rows += 1
        last = row['frame_id']
        if first is None:
            first = last
        d = row['presentation_diagnostics']
        if ((d['camera_profile_sha256'], d['workspace_profile_sha256']) != (camera_hash, workspace_hash)
                or row['camera_profile_id'] != camera.profile_id or row['workspace_profile_id'] != workspace.profile_id):
            raise ValueError('Trace profile binding mismatch')
        observations[pose_reason_code(row.get('status'), row.get('reason') or '')] += 1
        available = numeric_evidence(d)
        numeric += int(available)
        ids = d.get('marker_ids')
        valid_ids = isinstance(ids, list) and all(type(key) is int for key in ids) and len(ids) == len(set(ids))
        combo = (','.join(map(str, sorted(ids))) or '(none)') if valid_ids else '(missing_or_invalid)'
        group = groups.setdefault(combo, {'rows': 0, **{name: Counter() for name in names}})
        group['rows'] += 1
        if valid_ids:
            unmodeled.update(str(key) for key in ids if key in workspace.markers and key not in world)
        detections = {int(k): v for k, v in d['detected_corners_px'].items()} if available else {}
        poses = {}
        for name in names:
            pose = None
            if not available:
                code = 'no_numeric_evidence'
            elif set(detections) - set(workspace.markers):
                code = 'unregistered_markers'
            elif name == 'corner_candidate' and len(set(detections) & set(world)) < 3:
                code = 'insufficient_markers'
            else:
                try:
                    pose = (estimate_pose(detections, workspace, camera, d.get('image_size', ()))
                            if name == 'baseline' else
                            estimate_corner_pose(detections, world, camera, d.get('image_size', ())))
                    code = 'tracking'
                except (ValueError, TypeError) as exc:
                    code = pose_reason_code('pose_rejected', str(exc))
                    errors[name].setdefault(code, str(exc))
            counts[name][code] += 1
            group[name][code] += 1
            if pose is not None:
                residuals[name].append(pose.rms_px)
                prev = previous[name]
                consecutive = prev is not None and last == prev[0] + 1
                if consecutive:
                    steps[name].append(float(np.linalg.norm(pose.camera_position_mm - prev[1])))
                run[name] = run[name] + 1 if consecutive else 1
                longest[name] = max(longest[name], run[name])
                previous[name] = (last, pose.camera_position_mm)
                poses[name] = pose
            else:
                previous[name], run[name] = None, 0
        pair_code = ('both' if len(poses) == 2 else 'baseline_only' if 'baseline' in poses
                     else 'candidate_only' if poses else 'neither')
        paired[pair_code] += 1
        if len(poses) == 2:
            a, b = poses['baseline'], poses['corner_candidate']
            camera_deltas.append(float(np.linalg.norm(a.camera_position_mm - b.camera_position_mm)))
            aa, bb = project_targets(a, workspace, camera).get('A'), project_targets(b, workspace, camera).get('A')
            if aa and bb and aa['visible'] and bb['visible']:
                target_deltas.append(float(np.linalg.norm(np.array(aa['pixel']) - bb['pixel'])))
    if not rows:
        raise ValueError('No selected frames')
    result = dict(schema_version='beast_offline_corner_comparison_v1', optical_alignment_verified=False,
                  scope='conditional numeric replay; acceptance is not accuracy or display availability',
                  motion_metric_scope='consecutive source-frame pose change includes user motion, not measured jitter',
                  residual_scope='baseline uses centers, candidate uses corners; residuals are not identical metrics',
                  rows=rows, numeric_frames=numeric, frame_range=[first, last],
                  observation_reason_counts=dict(observations), unmodeled_marker_presence_frames=dict(unmodeled),
                  paired_acceptance_all_frames=paired,
                  by_marker_combination=groups, paired_camera_delta_mm=metrics(camera_deltas),
                  paired_target_a_delta_px=metrics(target_deltas), candidate=candidate)
    for name in names:
        result[name] = dict(reason_counts=dict(counts[name]), rejection_examples=errors[name],
                            accepted_fraction_all_frames=counts[name]['tracking'] / rows,
                            accepted_fraction_numeric_frames=counts[name]['tracking'] / numeric if numeric else None,
                            accepted_rms_px=metrics(residuals[name]),
                            consecutive_camera_step_mm=metrics(steps[name]), longest_accepted_run_frames=longest[name])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pose-trace', required=True, type=Path)
    parser.add_argument('--reference-fixture', required=True, type=Path, help='Existing saved-image numeric fixture')
    parser.add_argument('--side-mm', required=True, type=float, help='Assumed black outer side, NOT a measured value')
    parser.add_argument('--camera-profile', required=True, type=Path)
    parser.add_argument('--workspace-profile', required=True, type=Path)
    parser.add_argument('--first-frame', type=int)
    parser.add_argument('--last-frame', type=int)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError('Output already exists; choose a new path')
        from .workspace_live_preview import load_profiles
        camera, workspace, meta = load_profiles(args.camera_profile, args.workspace_profile)
        profiles = (camera, workspace, meta['camera_profile_sha256'], meta['workspace_profile_sha256'])
        reference_bytes = args.reference_fixture.read_bytes()
        trace_hash = hashlib.sha256(args.pose_trace.read_bytes()).hexdigest()
        candidate = reference_candidate(json.loads(reference_bytes), profiles, side_mm=args.side_mm)
        report = compare_trace(args.pose_trace, profiles, candidate, first_frame=args.first_frame, last_frame=args.last_frame)
        if hashlib.sha256(args.pose_trace.read_bytes()).hexdigest() != trace_hash:
            raise ValueError('Trace changed during replay; use a stopped session')
        report.update(source_trace_sha256=trace_hash, source_fixture_sha256=hashlib.sha256(reference_bytes).hexdigest(),
                      opencv_version=cv2.__version__)
        text = json.dumps(report, indent=2, allow_nan=False)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(text + '\n')
        print(text)
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f'Offline corner comparison failed: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
