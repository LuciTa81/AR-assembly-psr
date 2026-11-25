"""Compare 69/70 mm offline corner hypotheses; never writes an active profile."""
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
import numpy as np
import pose_replay_compare as replay
from server.realtime.workspace_projection import pixel_to_plane, estimate_corner_pose


def fit_orientations(rows, workspace, camera):
    square = np.array([[-.5, .5], [.5, .5], [.5, -.5], [-.5, -.5]])
    angles, edges = {}, {}
    for row in rows:
        pose, _ = replay.baseline(row['detections'], workspace, camera)
        assert pose is not None
        for key, quad in row['detections'].items():
            points = np.array([pixel_to_plane(p, 0., pose, camera) for p in quad])
            xy = points[:, :2] - points[:, :2].mean(axis=0)
            angle = math.atan2(np.sum(square[:, 0]*xy[:, 1]-square[:, 1]*xy[:, 0]), np.sum(square*xy))
            angles.setdefault(key, []).append(angle)
            edges.setdefault(key, []).extend(np.linalg.norm(np.roll(points, -1, axis=0)-points, axis=1).tolist())
    result = {}
    for key, samples in angles.items():
        average = math.atan2(np.sin(samples).mean(), np.cos(samples).mean())
        deviations = np.angle(np.exp(1j*(np.array(samples)-average)))
        result[key] = dict(radians=average, degrees=math.degrees(average),
                           max_deviation_degrees=float(np.degrees(np.abs(deviations)).max()),
                           inferred_edges_mm=dict(min=min(edges[key]), median=float(np.median(edges[key])), max=max(edges[key])))
    return result


def corners_for(side, orientation, workspace):
    square = np.array([[-.5, .5], [.5, .5], [.5, -.5], [-.5, -.5]])
    world = {}
    for key, item in orientation.items():
        a = item['radians']
        rotation = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
        world[key] = workspace.markers[key] + np.column_stack([side*square@rotation.T, np.zeros(4)])
    return world


def corner_pose(detections, world, camera):
    if len(detections) < 4:
        return None, 'fewer_than_four'
    if set(detections)-set(world):
        return None, 'orientation_unknown'
    try:
        return estimate_corner_pose(detections, world, camera, (1280, 720), max_rms_px=3.2), 'tracking'
    except ValueError as exc:
        return None, replay.pose_reason_code('pose_rejected', str(exc))


def run(output):
    if output.exists():
        raise ValueError('Report already exists')
    paths = [replay.ROOT/'pose-live-device.txt', *(replay.ASSETS/k for k in replay.BINDINGS)]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    for name, value in replay.BINDINGS.items():
        assert hashes[str(replay.ASSETS/name)] == value
    camera = replay.CameraModel.from_profile(json.loads((replay.ASSETS/'camera-profile.json').read_bytes()))
    workspace = replay.MetricWorkspace.from_dict(json.loads((replay.ASSETS/'workspace-profile.json').read_bytes()))
    raw_eye = json.loads((replay.ASSETS/'eye-projection.json').read_bytes())
    eyes = [np.array(raw_eye[k]).reshape(3, 4) for k in ('left_projection', 'right_projection')]
    rows = replay.load_rows(paths[0])
    fit_rows = [r for r in rows if r['valid'] and r['count']==5][:8]
    assert len(fit_rows)==8
    orientation = fit_orientations(fit_rows, workspace, camera)
    cutoff = fit_rows[-1]['frame_ms']
    evaluation = [r for r in rows if r['frame_ms']>cutoff]
    assert not set(r['frame_ms'] for r in fit_rows)&set(r['frame_ms'] for r in evaluation)
    geometries = {side: corners_for(side, orientation, workspace) for side in (69, 70)}
    records = {side: dict(actual=[], full=[], masked=[]) for side in (69, 70)}
    size_changes = []
    for row in evaluation:
        detections = row['detections']
        reference, base_reason = replay.baseline(detections, workspace, camera)
        alternatives = {}
        for side, geometry in geometries.items():
            pose, reason = corner_pose(detections, geometry, camera)
            alternatives[side] = pose
            fallback_allowed = reference is None and base_reason=='marker_geometry' and len(detections)==4
            records[side]['actual'].append(dict(frame_ms=row['frame_ms'], ids=sorted(detections), reason=reason,
                baseline_reason=base_reason, fallback_allowed=fallback_allowed,
                candidate_accepted=pose is not None, rms=None if pose is None else pose.rms_px))
            if reference is not None and len(detections)==5:
                records[side]['full'].append(dict(frame_ms=row['frame_ms'], reason=reason,
                    comparison=replay.comparison(reference, pose, workspace, camera, eyes)))
                for removed in (4, 5):
                    subset={k:v for k,v in detections.items() if k!=removed}
                    partial, partial_reason=corner_pose(subset, geometry, camera)
                    records[side]['masked'].append(dict(frame_ms=row['frame_ms'], removed=removed, reason=partial_reason,
                        comparison=replay.comparison(reference, partial, workspace, camera, eyes)))
        if alternatives[69] is not None and alternatives[70] is not None:
            size_changes.append(dict(frame_ms=row['frame_ms'], reason='both_sizes_accepted',
                comparison=replay.comparison(alternatives[69], alternatives[70], workspace, camera, eyes)))
    summaries={}
    for side, items in records.items():
        actual=items['actual'];eligible=[r for r in actual if r['fallback_allowed']]
        summaries[side]=dict(actual=len(actual), corner_reasons=dict(Counter(r['reason'] for r in actual)),
            geometry_fallback_eligible=len(eligible), geometry_fallback_returned=sum(r['candidate_accepted'] for r in eligible),
            full=replay.summary(items['full']),
            masked={str(k): replay.summary([r for r in items['masked'] if r['removed']==k]) for k in (4,5)})
    report=dict(offline_only=True, live_enabled=False, geometry_measured=False, hashes=hashes,
        protocol='First eight accepted five-marker frames fit orientation only; later frames evaluate fixed 69/70 mm hypotheses.',
        caveats=['Current measured-size report is approximate; inferred orientation is not physical ground truth.',
                 'Registered centers are held fixed; unknown marker 3 orientation is not invented.',
                 'Full-five-marker result is a consistency reference, not independent truth.',
                 'Side-to-side comparison compares two hypotheses, not accuracy.',
                 'Frame subsets are correlated samples from one session.'],
        fit_frames=[r['frame_ms'] for r in fit_rows], cutoff_ms=cutoff,
        evaluation_frames=[r['frame_ms'] for r in evaluation], orientations=orientation,
        missing_marker_ids=sorted(set(workspace.markers)-set(orientation)),
        corner_hypotheses={str(k): {str(i):v.tolist() for i,v in world.items()} for k,world in geometries.items()},
        summaries=summaries, records=records, size_change_summary=replay.summary(size_changes), size_changes=size_changes)
    assert hashes == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
    print(json.dumps(dict(summaries=summaries, size_change=report['size_change_summary'],orientation=orientation), indent=2))


if __name__=='__main__':
    run(replay.ROOT/'pose-comparison/corner-size-report.json')
