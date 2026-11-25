"""Offline-only four-marker comparison. Does not load hardware or write calibration."""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent / 'AR-Assembly-Checkpoint-20261120/repository'
sys.path.insert(0, str(REPO))
from server.realtime.workspace_projection import (
    CameraModel, MetricWorkspace, estimate_pose, marker_center_px, _estimate_planar_pose,
)
from server.realtime.partial_marker_replay import target_deltas
from server.realtime.temporal_marker_replay import ShortOcclusionCandidate
from server.realtime.display_observation_server import pose_reason_code

ASSETS = ROOT / 'app/src/main/assets'
BINDINGS = {
    'camera-profile.json': '25f025bc5c2f71e4c83e6645e5cdc742bda81cd75d30c55ff7e5aca99924872e',
    'workspace-profile.json': '5d4f4c6610af3264e0583eb64b038b3d66b12a9fc4844849d21d4f770d5c7acc',
    'eye-projection.json': '1127d29fb5022d005373d12eb0a8886fabafa53c852ac4bb3fd281ccd10904f3',
}


def baseline(detections, workspace, camera):
    try:
        pose = estimate_pose(detections, workspace, camera, (1280, 720), max_rms_px=3.2)
        return pose, 'tracking'
    except ValueError as exc:
        return None, pose_reason_code('pose_rejected', str(exc))


def candidate(detections, workspace, camera):
    original, reason = baseline(detections, workspace, camera)
    if original is not None or reason != 'marker_geometry' or len(detections) != 4:
        return original, reason, False
    ids = sorted(detections)
    objects = np.array([workspace.markers[k] for k in ids], np.float64)
    observed = np.array([marker_center_px(detections[k], camera) for k in ids], np.float64)
    try:
        pose = _estimate_planar_pose(objects, observed, ids, camera, 3.2, 5., .25,
                                    solver=cv2.SOLVEPNP_SQPNP)
        return pose, 'tracking', True
    except ValueError as exc:
        return None, pose_reason_code('pose_rejected', str(exc)), True


def comparison(reference, alternative, workspace, camera, eye):
    if alternative is None:
        return None
    delta = target_deltas(reference, alternative, workspace, camera)
    objects = np.array([workspace.targets[k] for k in 'ABCD'])
    projections = []
    for pose in (reference, alternative):
        xyz = objects @ cv2.Rodrigues(pose.rvec)[0].T + pose.tvec.reshape(3)
        homogeneous = np.column_stack([xyz, np.ones(4)])
        views = []
        for matrix in eye:
            q = homogeneous @ matrix.T
            if not np.isfinite(q).all() or np.any(q[:, 2] <= 0):
                raise ValueError('invalid eye projection')
            views.append(q[:, :2] / q[:, 2:])
        projections.append(np.array(views))
    delta['max_eye_delta_px'] = float(np.linalg.norm(projections[1]-projections[0], axis=2).max())
    delta['preserved'] = delta['max_target_delta_px'] <= 5 and delta['max_target_delta_mm'] <= 5
    return delta


def summary(records):
    values = [r['comparison'] for r in records if r.get('comparison') is not None]
    result = dict(cases=len(records), accepted=len(values),
                  preserved=sum(v['preserved'] for v in values),
                  reasons=dict(Counter(r['reason'] for r in records)))
    for key in ('max_target_delta_px', 'max_target_delta_mm', 'max_eye_delta_px'):
        numbers = [v[key] for v in values]
        result[key] = dict(zip(('median', 'p95', 'max'),
                              map(float, np.percentile(numbers, [50, 95, 100])))) if numbers else None
    return result


def load_rows(path):
    rows = []
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if 'BeastPoseFrame: ' not in line:
            continue
        row = json.loads(line.split('BeastPoseFrame: ', 1)[1])
        row['detections'] = {int(k): np.array(v, np.float64) for k, v in row['corners'].items()}
        assert len(row['detections']) == row['count']
        assert all(v.shape == (4, 2) and np.isfinite(v).all() for v in row['detections'].values())
        assert not rows or (row['session'] == rows[-1]['session'] and row['frame_ms'] > rows[-1]['frame_ms'])
        rows.append(row)
    assert rows, 'No numeric observations'
    return rows


def run(output):
    if output.exists():
        raise ValueError('Refusing to overwrite an existing report')
    source = ROOT / 'pose-live-device.txt'
    protected = [source, *(ASSETS / k for k in BINDINGS)]
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    for name, expected in BINDINGS.items():
        assert before[str(ASSETS / name)] == expected, name
    camera = CameraModel.from_profile(json.loads((ASSETS / 'camera-profile.json').read_bytes()))
    workspace = MetricWorkspace.from_dict(json.loads((ASSETS / 'workspace-profile.json').read_bytes()))
    eye_json = json.loads((ASSETS / 'eye-projection.json').read_bytes())
    eye = [np.array(eye_json[k]).reshape(3, 4) for k in ('left_projection', 'right_projection')]
    rows = load_rows(source)
    temporal = ShortOcclusionCandidate(camera, workspace)
    actual, masked, historical, mismatches = [], [], [], []
    accepted_references = []
    for index, row in enumerate(rows):
        detections = row['detections']
        reference, base_reason = baseline(detections, workspace, camera)
        if (reference is not None) != row['valid']:
            mismatches.append(dict(frame_ms=row['frame_ms'], recorded=row['reason'], replay=base_reason))
        alternative, reason, fallback = candidate(detections, workspace, camera)
        _, temporal_pose, detail = temporal.update(index+1, row['frame_ms'], detections, (1280, 720))
        actual.append(dict(frame_ms=row['frame_ms'], ids=sorted(detections), baseline=base_reason,
                           fallback=fallback, sqpnp_reason=reason, sqpnp_accepted=alternative is not None,
                           temporal_method=detail['method'], temporal_reason=detail['candidate_reason'],
                           temporal_accepted=temporal_pose is not None))
        if reference is None or len(detections) != 5:
            continue
        accepted_references.append(index)
        for removed in sorted(detections):
            subset = {k: v for k, v in detections.items() if k != removed}
            pose, reason, fallback = candidate(subset, workspace, camera)
            masked.append(dict(frame_ms=row['frame_ms'], removed=removed, fallback=fallback,
                               reason=reason, comparison=comparison(reference, pose, workspace, camera, eye)))
        # This historical candidate uses an earlier actual frame only, never the current full pose.
        if index == 0:
            continue
        previous = rows[index-1]
        previous_pose, _ = baseline(previous['detections'], workspace, camera)
        if (previous_pose is None or len(previous['detections']) != 5
                or set(previous['detections']) != set(detections)):
            continue
        for removed in (4, 5):
            if removed not in detections:
                continue
            trial = ShortOcclusionCandidate(camera, workspace)
            trial.update(1, previous['frame_ms'], previous['detections'], (1280, 720))
            subset = {k: v for k, v in detections.items() if k != removed}
            _, pose, detail = trial.update(2, row['frame_ms'], subset, (1280, 720))
            historical.append(dict(frame_ms=row['frame_ms'], removed=removed,
                                   anchor_age_ms=row['frame_ms']-previous['frame_ms'], reason=detail['candidate_reason'],
                                   comparison=comparison(reference, pose, workspace, camera, eye)))
    assert not mismatches, mismatches
    fallback_rows = [r for r in actual if r['fallback']]
    report = dict(offline_only=True, live_enabled=False, opencv=cv2.__version__, hashes=before,
                  limits=dict(rms_px=3.2, point_px=5, ambiguity_gap_px=.25),
                  caveats=['Five-marker references are consistency references, not physical ground truth.',
                           '5px camera / 5mm XYZ are report-only preservation criteria, not accuracy guarantees.',
                           'Historical temporal candidate retains its original stricter 3.0px RMS / 300ms policy.',
                           'Masked cases share frames and are correlated; raw missing-marker frames have no reference pose.',
                           'Eye differences include offscreen points and are not physical binocular accuracy measurements.'],
                  observed=dict(frames=len(rows), baseline_accepted=sum(r['baseline']=='tracking' for r in actual),
                                baseline_mismatches=mismatches, fallback_attempts=len(fallback_rows),
                                sqpnp_additional=sum(r['sqpnp_accepted'] for r in fallback_rows),
                                temporal_additional=sum(r['temporal_method']=='temporal_centers' for r in actual),
                                fallback_reasons=dict(Counter(r['sqpnp_reason'] for r in fallback_rows)),records=actual),
                  masked=dict(reference_frames=len(accepted_references), summary=summary(masked),
                              by_removed={str(k):summary([r for r in masked if r['removed']==k]) for k in sorted({r['removed'] for r in masked})},records=masked),
                  historical_temporal=dict(summary=summary(historical),by_removed={str(k):summary([r for r in historical if r['removed']==k]) for k in (4,5)},records=historical))
    assert before == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
    print(json.dumps(dict(observed={k:v for k,v in report['observed'].items() if k!='records'},
                          masked=report['masked']['by_removed'], temporal=report['historical_temporal']['by_removed']), indent=2))


if __name__ == '__main__':
    run(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT / 'pose-comparison/report.json')
