"""Offline short-occlusion hypothesis. Never imported by the live presentation path."""

from dataclasses import replace
from collections import Counter
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from .display_observation_server import pose_reason_code
from .corner_tracking_report import metrics
from .partial_marker_replay import evaluate_pose, target_deltas
from .tracking_report import numeric_evidence, selected_rows
from .workspace_live_preview import load_profiles
from .workspace_projection import (
    _estimate_planar_pose, estimate_pose, finite_array, marker_center_px, pixel_to_plane,
)


class ShortOcclusionCandidate:
    """Use a past full pose as a temporary local reference, never as current pose.

    Backprojected centers are an unmeasured, disposable hypothesis. The measured
    workspace and targets are never changed. Only a normal five-marker result
    can refresh the reference; partial results cannot extend its lifetime.
    """

    def __init__(self, camera, workspace, *, max_anchor_ms=300):
        if type(max_anchor_ms) is not int or not 0 < max_anchor_ms <= 300:
            raise ValueError('Reference lifetime must be an integer in 1..300 ms')
        self.camera, self.workspace = camera, workspace
        self.undistorted_camera = replace(camera, distortion=np.zeros(5))
        self.max_anchor_ms = max_anchor_ms
        self.anchor = None
        self.last_frame = self.last_time = -1

    def update(self, frame_id, timestamp_ms, detections, image_size):
        if (type(frame_id) is not int or frame_id <= self.last_frame or frame_id < 1
                or type(timestamp_ms) is not int or timestamp_ms <= self.last_time or timestamp_ms < 1):
            self.anchor = None
            raise ValueError('Strictly increasing frame IDs and capture times required')
        self.last_frame, self.last_time = frame_id, timestamp_ms
        detail = dict(method='unavailable', baseline_reason='tracking', candidate_reason='tracking',
                      anchor_frame=self.anchor[0] if self.anchor else None,
                      anchor_age_ms=timestamp_ms-self.anchor[1] if self.anchor else None)
        if (tuple(image_size) != self.camera.image_size
                or any(type(key) is not int for key in detections)
                or set(detections) - set(self.workspace.markers)):
            self.anchor = None
            detail.update(baseline_reason='invalid_input', candidate_reason='invalid_input')
            return None, None, detail
        try:
            baseline = estimate_pose(detections, self.workspace, self.camera, image_size)
        except ValueError as exc:
            detail['baseline_reason'] = pose_reason_code('pose_rejected', str(exc))
            detail['candidate_reason'] = detail['baseline_reason']
            detail['baseline_error'] = str(exc)
        else:
            if len(detections) == 5:
                # marker_center_px is already undistorted; do not undistort it twice.
                try:
                    centers = {key: pixel_to_plane(marker_center_px(quad, self.camera), 0.,
                               baseline, self.undistorted_camera) for key, quad in detections.items()}
                    for point in centers.values():
                        point[2] = 0.
                except ValueError as exc:
                    self.anchor = None
                    detail.update(anchor_frame=None, anchor_age_ms=None, anchor_error=str(exc))
                else:
                    self.anchor = (frame_id, timestamp_ms, centers, baseline)
                    detail.update(anchor_frame=frame_id, anchor_age_ms=0,
                        anchor_max_adjustment_mm=max(float(np.linalg.norm(centers[k]-self.workspace.markers[k])) for k in centers))
            detail['method'] = 'baseline'
            return baseline, baseline, detail
        if detail['baseline_reason'] != 'marker_geometry' or len(detections) != 4:
            return None, None, detail
        if self.anchor is None:
            detail['candidate_reason'] = 'no_anchor'
            return None, None, detail
        _, anchor_time, centers, anchor_pose = self.anchor
        if timestamp_ms-anchor_time > self.max_anchor_ms:
            self.anchor = None
            detail['candidate_reason'] = 'anchor_expired'
            return None, None, detail
        if not set(detections) < set(centers):
            detail['candidate_reason'] = 'anchor_ids_mismatch'
            return None, None, detail
        ids = sorted(detections)
        try:
            objects = np.array([centers[key] for key in ids])
            observed = np.array([marker_center_px(detections[key], self.camera) for key in ids])
            candidate = _estimate_planar_pose(objects, observed, ids, self.camera, 3., 5., .25,
                                              solver=cv2.SOLVEPNP_SQPNP)
        except ValueError as exc:
            detail.update(candidate_reason='candidate_quality', candidate_error=str(exc))
            return None, None, detail
        relative = cv2.Rodrigues(candidate.rvec)[0] @ cv2.Rodrigues(anchor_pose.rvec)[0].T
        angle = float(np.degrees(np.arccos(np.clip((np.trace(relative)-1)/2, -1, 1))))
        distance = float(np.linalg.norm(candidate.camera_position_mm-anchor_pose.camera_position_mm))
        detail.update(anchor_rotation_deg=angle, anchor_translation_mm=distance)
        if angle > 5. or distance > 30.:
            detail['candidate_reason'] = 'motion_limit'
            return None, None, detail
        detail.update(method='temporal_centers', candidate_reason='tracking', rms_px=candidate.rms_px)
        return None, candidate, detail


def _preservation(reference, candidate, workspace, camera):
    if candidate is None:
        return None
    delta = target_deltas(reference, candidate, workspace, camera)
    return dict(px=delta['max_target_delta_px'], mm=delta['max_target_delta_mm'],
                preserved=delta['max_target_delta_px'] <= 5. and delta['max_target_delta_mm'] <= 5.)


def compare_windows(rows, camera, workspace, *, lengths=(1, 3, 5), removed_ids=(0, 1, 2, 4, 5)):
    """Each nonoverlapping eight-frame block has a past anchor and future evaluation.

    Full poses of hidden frames are evaluation references ONLY, never tracker inputs.
    Five-frame masks deliberately exceed the fixed reference deadline at 10 fps.
    """
    records, restoration, skipped = [], [], 0
    for start in range(0, len(rows)-7, 8):
        for length in lengths:
            block = rows[start:start+length+2]
            if (len(block) != length+2 or any(len(r['detections']) != 5 for r in block)
                    or any(set(r['detections']) != set(block[0]['detections']) for r in block)):
                skipped += 1
                continue
            try:
                references = [estimate_pose(r['detections'], workspace, camera, camera.image_size) for r in block]
            except ValueError:
                skipped += 1
                continue
            for missing in removed_ids:
                if missing not in block[0]['detections']:
                    continue
                tracker = ShortOcclusionCandidate(camera, workspace)
                anchor = block[0]
                tracker.update(anchor['frame_id'], anchor['timestamp_ms'], anchor['detections'], camera.image_size)
                previous = None
                for row, reference in zip(block[1:-1], references[1:-1]):
                    subset = {k:v for k,v in row['detections'].items() if k != missing}
                    baseline, stateless, _ = evaluate_pose(subset, workspace, camera, camera.image_size)
                    _, candidate, detail = tracker.update(row['frame_id'], row['timestamp_ms'], subset, camera.image_size)
                    comparisons = {name: _preservation(reference, pose, workspace, camera)
                                   for name, pose in (('baseline', baseline), ('stateless', stateless), ('candidate', candidate))}
                    records.append(dict(frame_id=row['frame_id'], anchor_frame=anchor['frame_id'],
                        length=length, removed_marker=missing, age_ms=row['timestamp_ms']-anchor['timestamp_ms'],
                        candidate_method=detail['method'], candidate_reason=detail['candidate_reason'], **comparisons))
                    previous = candidate
                row = block[-1]
                baseline, restored, detail = tracker.update(row['frame_id'], row['timestamp_ms'], row['detections'], camera.image_size)
                restoration.append(dict(frame_id=row['frame_id'], length=length, removed_marker=missing,
                    returned_to_baseline=restored is baseline and baseline is not None,
                    raw_step=target_deltas(previous, restored, workspace, camera) if previous is not None else None))
    groups = {}
    for length in lengths:
        for missing in removed_ids:
            selected = [r for r in records if r['length'] == length and r['removed_marker'] == missing]
            group = dict(cases=len(selected), candidate_reasons=dict(Counter(r['candidate_reason'] for r in selected)))
            for name in ('baseline', 'stateless', 'candidate'):
                values = [r[name] for r in selected if r[name] is not None]
                group.update({name+'_accepted':len(values), name+'_preserved':sum(v['preserved'] for v in values),
                              name+'_px':metrics([v['px'] for v in values]), name+'_mm':metrics([v['mm'] for v in values])})
            groups[f'{length}:{missing}'] = group
    return dict(groups=groups, records=records, restoration=restoration, skipped_windows=skipped,
                window_scope='Overlapping mask lengths and IDs are correlated cases, not independent experiments',
                restoration_scope='Raw target-coordinate step includes real camera motion, not just algorithmic jump')


def replay(path, profiles, *, first_frame=None, last_frame=None):
    path = Path(path)
    trace_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    camera, workspace, meta = profiles
    rows = []
    last_time = -1
    for row in selected_rows(path, first_frame, last_frame):
        d = row.get('presentation_diagnostics')
        if not isinstance(d, dict) or any(d.get(k) != meta[k] for k in ('camera_profile_sha256', 'workspace_profile_sha256')):
            raise ValueError('Trace/profile binding mismatch')
        if d.get('image_size') != list(camera.image_size):
            raise ValueError('Trace resolution mismatch')
        if not numeric_evidence(d) and not (d.get('marker_ids') == [] and d.get('detected_corners_px') == {}):
            raise ValueError('Incomplete numeric marker evidence')
        capture = row.get('filter_input', {})
        if type(capture.get('frame_id')) is not int or capture['frame_id'] != row['frame_id']:
            raise ValueError('Capture/diagnostic frame mismatch')
        now = capture.get('timestamp_ms')
        if type(now) is not int or now <= last_time:
            raise ValueError('Capture times must be strictly increasing')
        last_time = now
        detections = {int(k):finite_array(v, (4, 2), 'stored corners') for k,v in d['detected_corners_px'].items()}
        if set(detections) - set(workspace.markers):
            raise ValueError('Unregistered marker ID')
        rows.append(dict(frame_id=row['frame_id'], timestamp_ms=now, detections=detections,
                         recorded_reason=d['reason_code']))
    if not rows:
        raise ValueError('No selected rows')
    tracker = ShortOcclusionCandidate(camera, workspace)
    actual, baseline_mismatches = [], []
    for row in rows:
        baseline, candidate, detail = tracker.update(row['frame_id'], row['timestamp_ms'], row['detections'], camera.image_size)
        if detail['baseline_reason'] != row['recorded_reason']:
            baseline_mismatches.append(row['frame_id'])
        actual.append(dict(frame_id=row['frame_id'], **detail))
    windows = compare_windows(rows, camera, workspace)
    if hashlib.sha256(path.read_bytes()).hexdigest() != trace_hash:
        raise ValueError('Trace changed during replay')
    return dict(schema_version='beast_short_occlusion_replay_v1', offline_only=True, live_enabled=False,
        optical_alignment_verified=False, source_trace_sha256=trace_hash, source_trace=str(path.resolve()),
        camera_profile_sha256=meta['camera_profile_sha256'], workspace_profile_sha256=meta['workspace_profile_sha256'],
        frame_range=[rows[0]['frame_id'],rows[-1]['frame_id']], opencv_version=cv2.__version__,
        fixed_policy=dict(reference_ms=300, max_rotation_deg=5., max_translation_mm=30.,
                          rms_px=3., max_point_error_px=5., pose_ambiguity_gap_px=.25),
        scope='Past-only numerical hypothesis; no detector simulation, physical truth, rendering or step advancement',
        actual=dict(frames=len(actual), baseline_mismatches=baseline_mismatches,
                    baseline_reasons=dict(Counter(r['baseline_reason'] for r in actual)),
                    candidate_reasons=dict(Counter(r['candidate_reason'] for r in actual)),
                    methods=dict(Counter(r['method'] for r in actual)), records=actual),
        masked=windows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--camera-profile', type=Path, required=True)
    parser.add_argument('--workspace-profile', type=Path, required=True)
    parser.add_argument('--first-frame', type=int)
    parser.add_argument('--last-frame', type=int)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError('Output exists; choose a new path')
        report = replay(args.results, load_profiles(args.camera_profile, args.workspace_profile),
                        first_frame=args.first_frame, last_frame=args.last_frame)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
        print(json.dumps(dict(output=str(args.output), frames=report['actual']['frames'],
            methods=report['actual']['methods'], baseline_mismatches=report['actual']['baseline_mismatches'],
            masked_cases=len(report['masked']['records']), live_enabled=False)))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f'Offline short occlusion replay failed: {exc}\n')


if __name__ == '__main__':
    main()
