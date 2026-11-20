"""Offline replay of numeric logs. Never opens a camera or changes live files."""

from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

import cv2
import numpy as np

from pose_quality_continuation import QualityContinuation, project_geometry

ROOT = Path(__file__).resolve().parent
HOME = ROOT.parent
MANIFEST = HOME / 'beast-preparation-text-20261116/protected-before.json'
PROTECTED = json.loads(MANIFEST.read_text(encoding='utf-8-sig'))
REPO = Path(PROTECTED[0]['Path']).parents[2]
sys.path.insert(0, str(REPO))

from server.realtime.workspace_live_preview import load_profiles
from server.realtime.workspace_projection import estimate_pose
from server.realtime.display_observation_server import pose_reason_code


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stats(values):
    return None if not values else dict(zip(('min', 'median', 'p95', 'max'),
                                           map(float, np.percentile(values, [0, 50, 95, 100]))))


def read_records(path, cutoff):
    seen = set()
    rows = []
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        raw = json.loads(line)
        if cutoff is not None and raw['video_seconds'] > cutoff:
            continue
        if isinstance(raw.get('state'), dict):
            state = raw['state']
            d = state.get('extra', {}).get('presentation_diagnostics')
            if not d:
                continue
            frame, time, stage = state['frame_id'], state['timestamp_ms'], state['current_state']
            session = state['session_id']
        elif isinstance(raw.get('state'), str):
            d = raw['presentation_diagnostics']
            frame, time, stage = raw['frame_id'], raw['filter_input']['timestamp_ms'], raw['state']
            session = path.parent.name
        else:
            continue
        key = (session, frame)
        if key in seen:
            continue
        seen.add(key)
        rows.append(dict(frame=frame, time=time, stage=stage, session=session,
                         diagnostic=d))
    return rows


def summary(rows, mask):
    invalid_runs = []
    start = None
    for i, valid in enumerate(mask + [True]):
        if not valid and start is None:
            start = i
        elif valid and start is not None:
            invalid_runs.append(i-start)
            start = None
    return dict(accepted=sum(mask), total=len(mask), accepted_percent=100*sum(mask)/len(mask),
                rejected_runs=len(invalid_runs), one_or_two_frame_runs=sum(n <= 2 for n in invalid_runs),
                longest_rejected_run_samples=max(invalid_runs, default=0),
                acceptance_toggles=sum(a != b for a, b in zip(mask, mask[1:])))


def replay(path, cutoff, camera, workspace, meta, points, projections):
    source_hash = sha(path)
    rows = read_records(path, cutoff)
    gates = {f'bounded_{rms}': QualityContinuation(camera, points, projections, rms)
             for rms in (3.2, 3.25, 3.5)}
    masks = {key: [] for key in ('baseline', 'plain_3.2', 'plain_3.5', *gates)}
    geometries, decisions, fits = [], [], []
    prior = None
    for row in rows:
        d = row.pop('diagnostic')
        for key in ('camera_profile_sha256', 'workspace_profile_sha256'):
            assert d[key] == meta[key], (path, key)
        assert d['image_size'] == list(camera.image_size)
        assert d['frame_id'] == row['frame']
        assert prior is None or (row['session'] == prior['session']
                                and row['frame'] > prior['frame'] and row['time'] > prior['time'])
        prior = row
        row.update(markers=d['marker_ids'], reason=d['reason_code'], rms=None, maximum=None)
        fit = None
        try:
            detections = {int(k): np.asarray(v, float) for k, v in d['detected_corners_px'].items()}
            # The solver has a final quality gate, not a different relaxed fit.
            fit = estimate_pose(detections, workspace, camera, camera.image_size,
                                max_rms_px=3.5, max_point_error_px=5)
        except ValueError as exc:
            reproduced = pose_reason_code('pose_rejected', str(exc))
        else:
            row.update(rms=fit.rms_px, maximum=fit.max_error_px)
            reproduced = 'tracking' if fit.rms_px <= 3 else 'pose_quality'
        assert reproduced == row['reason'], (path, row['frame'], reproduced, row['reason'])
        strict = reproduced == 'tracking'
        masks['baseline'].append(strict)
        masks['plain_3.2'].append(fit is not None and fit.rms_px <= 3.2)
        masks['plain_3.5'].append(fit is not None)
        frame_decisions = {}
        age = d.get('publish_age_ms')
        age = float('nan') if age is None else age
        for key, gate in gates.items():
            result = gate.update(row['frame'], row['time'], fit, publish_age_ms=age)
            masks[key].append(result.mode != 'hidden')
            assert (result.mode == 'strict') == strict
            assert result.pose is None or result.pose is fit
            assert result.mode != 'continued' or (row['reason'] == 'pose_quality' and len(row['markers']) >= 5)
            frame_decisions[key] = dict(mode=result.mode, reason=result.reason,
                xyz_mm=result.delta_xyz_mm, camera_px=result.delta_camera_px, eye_px=result.delta_eye_px)
        decisions.append(frame_decisions)
        fits.append(fit)
        try:
            geometry = project_geometry(fit, camera, points, projections, require_in_view=False) if fit else None
        except (ValueError, cv2.error):
            geometry = None
        geometries.append(geometry)
    policies = {}
    for key, mask in masks.items():
        added = [i for i, valid in enumerate(mask) if valid and not masks['baseline'][i]]
        following_deltas = []
        for i in added:
            # Future samples are evaluation references only, never policy inputs.
            for j in range(i+1, len(rows)):
                if rows[j]['time'] - rows[i]['time'] > 250:
                    break
                if masks['baseline'][j] and geometries[i] is not None and geometries[j] is not None:
                    following_deltas.append(float(np.linalg.norm(
                        geometries[j].eye_px-geometries[i].eye_px, axis=-1).max()))
                    break
        policies[key] = dict(**summary(rows, mask), added=len(added),
            following_strict_reference_count=len(following_deltas),
            following_strict_eye_displacement_px=stats(following_deltas))
        if key in gates:
            policies[key]['decisions'] = dict(Counter(d[key]['reason'] for d in decisions))
            policies[key]['accepted_anchor_eye_displacement_px'] = stats(
                [decisions[i][key]['eye_px'] for i in added])
    for i, row in enumerate(rows):
        row['decisions'] = decisions[i]
    assert sha(path) == source_hash
    return dict(source=str(path), source_sha256=source_hash, cutoff_seconds=cutoff,
        baseline_exactly_reproduced=True, frames=len(rows),
        reasons=dict(Counter(row['reason'] for row in rows)), policies=policies,
        stages={stage: {key: summary([rows[i] for i in indices], [mask[i] for i in indices])
                         for key, mask in masks.items()}
                for stage in sorted({r['stage'] for r in rows})
                for indices in [[i for i, r in enumerate(rows) if r['stage'] == stage]]}, rows=rows)


def main():
    protected = {r['Path']: sha(r['Path']) for r in PROTECTED}
    assert all(protected[r['Path']] == r['Hash'].lower() for r in PROTECTED)
    source_files = [REPO / 'server/realtime' / name for name in
                    ('workspace_projection.py', 'presentation_bridge.py', 'online_state_filter.py')]
    protected.update({str(p): sha(p) for p in source_files})
    paths = {r['Hash'].lower(): r['Path'] for r in PROTECTED}
    trial = HOME / 'beast-reference-return-20261114'
    candidate_path = trial / 'candidate-ABCD-joint-unverified.json'
    candidate = json.loads(candidate_path.read_text())
    camera, workspace, meta = load_profiles(paths[candidate['camera_profile_sha256']],
                                            paths[candidate['workspace_profile_sha256']])
    projections = [np.asarray(candidate[k], float).reshape(3, 4)
                   for k in ('left_projection', 'right_projection')]
    box = json.loads((trial / 'rounded-box-124mm.json').read_text())
    vertices = np.asarray(box['vertices_mm'], float).reshape(-1, 3)
    body_top = vertices[:4].copy()
    body_top[:, 2] -= box['lid_height_mm']
    points = np.vstack(([workspace.targets[k] for k in 'ABCD'], vertices, body_top))
    sources = [(trial / 'release-recovery-flow-sessions/viture_aruco_rt_20261116_013228_325d17b20d8a/results.jsonl', None),
        (HOME / 'AI-Assembly-Video-Prep-20261116/recordings/20261116_010232_wgcverify2/states.jsonl', None),
        (HOME / 'AI-Assembly-Video-Prep-20261116/recordings/20261116_005052_take02/states.jsonl', 205)]
    runs = []
    for source, cutoff in sources:
        report = replay(source, cutoff, camera, workspace, meta, points, projections)
        runs.append(report)
        print(json.dumps({k: v for k, v in report.items() if k not in ('rows', 'stages')}, indent=2))
    assert all(sha(p) == h for p, h in protected.items())
    output = dict(live_enabled=False, stage_evidence_enabled=False, calibration_changed=False,
        optical_accuracy_verified=False, protected_files_unchanged=True,
        opencv_version=cv2.__version__, projection_sha256=sha(candidate_path),
        policy=dict(strict_rms_px=3, max_error_px=5, soft_rms_px=[3.2, 3.25, 3.5],
                    duration_ms=200, publish_age_ms=150, minimum_markers=5,
                    same_markers_required=True, max_3d_mm=5, max_camera_px=5, max_eye_px=5,
                    geometry_points=len(points), deadline_renewal_on_rescue=False),
        caveats=['Pose acceptance, not Unity visibility or physical optical accuracy.',
                 'Earlier recording metadata is HTTP sampled and may omit frames.',
                 'Following strict displacement includes real motion and is not registration error.',
                 'No saved video or image is opened or changed. Numeric replay only.'],
        protected_hashes=protected, runs=runs)
    (ROOT / 'replay-report.json').write_text(json.dumps(output, ensure_ascii=True, indent=2, allow_nan=False), encoding='utf-8')


if __name__ == '__main__':
    main()
