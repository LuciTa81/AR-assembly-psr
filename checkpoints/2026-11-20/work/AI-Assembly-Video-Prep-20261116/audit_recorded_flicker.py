"""Read-only pose replay of saved recording metadata; never opens a camera."""

import hashlib
import json
from collections import Counter
from pathlib import Path
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent
TRIAL = ROOT.parent / 'beast-reference-return-20261114'
protected = json.loads((TRIAL / 'poll-protected-hashes-after.json').read_text(encoding='utf-8-sig'))
repo = Path(protected[0]['Path']).parents[2]
sys.path.insert(0, str(repo))
from server.realtime.workspace_live_preview import load_profiles
from server.realtime.workspace_projection import estimate_pose
from server.realtime.display_observation_server import pose_reason_code


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stats(values):
    return None if not values else dict(zip(('min', 'median', 'p95', 'max'),
        map(float, np.percentile(values, [0, 50, 95, 100]))))


def policy_summary(rows, rms, maximum):
    accepted = [r['rms'] is not None and r['rms'] <= rms and r['max'] <= maximum for r in rows]
    spans, start = [], None
    for i, valid in enumerate(accepted + [True]):
        if not valid and start is None:
            start = i
        elif valid and start is not None:
            end = rows[i]['time'] if i < len(rows) else rows[-1]['time']
            spans.append(end - rows[start]['time'])
            start = None
    return dict(accepted=sum(accepted), total=len(rows),
        fraction=sum(accepted)/len(rows), rejection_runs=len(spans),
        max_rejection_sample_span_ms=max(spans, default=0),
        transitions=sum(a != b for a,b in zip(accepted,accepted[1:])))


def audit(path, camera, workspace, meta, projections, cutoff=None):
    raw = path.read_bytes()
    source_hash = hashlib.sha256(raw).hexdigest()
    unique, samples, completed = {}, 0, False
    for line in raw.decode('utf-8').splitlines():
        record = json.loads(line)
        if cutoff is not None and record['video_seconds'] > cutoff:
            continue
        state = record.get('state')
        if not state:
            continue
        samples += 1
        d = state.get('extra', {}).get('presentation_diagnostics')
        if not d:
            continue
        key = (state['session_id'], state['frame_id'])
        if key in unique:
            continue
        for field in ('camera_profile_sha256','workspace_profile_sha256'):
            assert d[field] == meta[field], (path, field)
        assert d['image_size'] == list(camera.image_size)
        assert d['frame_id'] == state['frame_id']
        unique[key] = (state, d, record['video_seconds'])
    rows, coords, residuals = [], [], {}
    objects = np.array([workspace.targets[k] for k in 'ABCD'])
    for state, d, seconds in unique.values():
        detected = {int(k):np.asarray(v,float) for k,v in d['detected_corners_px'].items()}
        row = dict(frame=state['frame_id'], time=state['timestamp_ms'], video_seconds=seconds,
            stage=state['current_state'], markers=d['marker_ids'], reason=d['reason_code'],
            rms=None, max=None, worst_marker=None)
        try:
            fit = estimate_pose(detected, workspace, camera, camera.image_size,
                                max_rms_px=1e6, max_point_error_px=1e6)
        except ValueError as exc:
            reproduced = pose_reason_code('pose_rejected', str(exc))
            coords.append(None)
        else:
            row.update(rms=fit.rms_px, max=fit.max_error_px)
            reproduced = 'tracking' if fit.rms_px <= 3 and fit.max_error_px <= 5 else 'pose_quality'
            diff = fit.observed_centers_px - fit.projected_centers_px
            row['worst_marker'] = fit.marker_ids[int(np.argmax(np.linalg.norm(diff, axis=1)))]
            for marker, delta in zip(fit.marker_ids, diff):
                residuals.setdefault(marker, []).append(delta)
            xyz = objects @ cv2.Rodrigues(fit.rvec)[0].T + fit.tvec.reshape(3)
            pixels = cv2.projectPoints(objects,fit.rvec,fit.tvec,camera.matrix,camera.distortion)[0].reshape(4,2)
            homogeneous = np.column_stack((xyz, np.ones(4)))
            eyes = []
            for p in projections:
                screen = homogeneous @ p.T
                assert (screen[:,2] > 0).all()
                eyes.append(screen[:,:2] / screen[:,2,None])
            coords.append(dict(xyz=xyz, camera=pixels, eye=np.concatenate(eyes)))
        assert reproduced == row['reason'], (path, row['frame'], reproduced, row['reason'])
        if rows:
            assert row['time'] > rows[-1]['time']
        rows.append(row)
    summaries = {}
    for name, rms, maximum in [('baseline',3,5),('rms_3p5_max_5',3.5,5),
                               ('rms_3p5_max_6',3.5,6),('rms_4_max_6',4,6)]:
        summary = policy_summary(rows,rms,maximum)
        added = [i for i,r in enumerate(rows) if r['reason']!='tracking' and r['rms'] is not None
                 and r['rms']<=rms and r['max']<=maximum]
        comparisons = []
        # Nearest accepted neighbors are continuity references, not ground truth.
        good = [i for i,r in enumerate(rows) if r['reason']=='tracking']
        for i in added:
            neighbors = [j for j in good if rows[j]['stage']==rows[i]['stage']
                         and abs(rows[j]['time']-rows[i]['time'])<=250]
            if not neighbors:
                continue
            j = min(neighbors,key=lambda j:abs(rows[j]['time']-rows[i]['time']))
            comparisons.append(dict(frame=rows[i]['frame'], reference_frame=rows[j]['frame'],
                dt_ms=abs(rows[j]['time']-rows[i]['time']),
                **{k:float(np.linalg.norm(coords[i][k]-coords[j][k],axis=1).max())
                   for k in ('xyz','camera','eye')}))
        summary.update(extra_frames=len(added), neighbor_comparisons=len(comparisons),
            neighbor_camera_px=stats([c['camera'] for c in comparisons]),
            neighbor_eye_px=stats([c['eye'] for c in comparisons]),
            neighbor_xyz_mm=stats([c['xyz'] for c in comparisons]),
            comparisons=comparisons)
        summaries[name] = summary
    assert digest(path) == source_hash
    return dict(source=str(path), source_sha256=source_hash, samples=samples, unique_frames=len(rows),
        cutoff_seconds=cutoff, reasons=dict(Counter(r['reason'] for r in rows)),
        marker_counts=dict(Counter(len(r['markers']) for r in rows)),
        policies=summaries,
        stages={s:dict(frames=len(rs),reasons=dict(Counter(r['reason'] for r in rs)),
                       baseline=policy_summary(rs,3,5),relaxed=policy_summary(rs,3.5,6))
                for s in sorted({r['stage'] for r in rows})
                for rs in [[r for r in rows if r['stage']==s]]},
        quality_worst_markers=dict(Counter(r['worst_marker'] for r in rows if r['reason']=='pose_quality')),
        residual_median_px={str(k):np.median(v,axis=0).tolist() for k,v in residuals.items()},
        baseline_exactly_reproduced=True, rows=rows)


def main():
    before = {item['Path']:digest(item['Path']) for item in protected}
    candidate_path = TRIAL / 'candidate-ABCD-joint-unverified.json'
    candidate = json.loads(candidate_path.read_text())
    paths = {item['Hash'].lower():item['Path'] for item in protected}
    camera, workspace, meta = load_profiles(paths[candidate['camera_profile_sha256']],
                                            paths[candidate['workspace_profile_sha256']])
    projections = [np.asarray(candidate[k],float).reshape(3,4) for k in ('left_projection','right_projection')]
    reports = [audit(ROOT / 'recordings' / name / 'states.jsonl', camera, workspace, meta,
                     projections, cutoff) for name,cutoff in
               [('20261116_010232_wgcverify2',None),('20261116_005052_take02',205)]]
    assert all(digest(path)==value for path,value in before.items())
    report = dict(live_enabled=False, calibration_changed=False, protected_files_unchanged=True,
        opencv_version=cv2.__version__, camera_profile_sha256=meta['camera_profile_sha256'],
        workspace_profile_sha256=meta['workspace_profile_sha256'],
        projection_sha256=digest(candidate_path),
        caveats=['HTTP-sampled unique observations, not every camera frame.',
                 'Threshold replay estimates pose acceptance, not Unity visibility.',
                 'Neighbor displacement includes real head motion; not optical accuracy.',
                 'Long take ends at 205s to exclude headset put-down after completion.'],
        recordings=reports)
    output = ROOT / 'flicker-offline-audit-20261116.json'
    with output.open('x',encoding='utf-8') as stream:
        json.dump(report,stream,ensure_ascii=False,indent=2,allow_nan=False)
    for r in reports:
        print(json.dumps({k:v for k,v in r.items() if k not in ('rows','policies')},ensure_ascii=True))
        for name, policy in r['policies'].items():
            print(name, json.dumps({k:v for k,v in policy.items() if k!='comparisons'}))


if __name__ == '__main__':
    main()
