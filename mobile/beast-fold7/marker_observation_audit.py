"""Per-marker consistency audit of saved coordinates; no runtime/profile edits."""
import hashlib
import json
from collections import Counter
from pathlib import Path
import cv2
import numpy as np
import pose_replay_compare as replay
import corner_size_compare as corner
from server.realtime.workspace_projection import marker_center_px, pixel_to_plane


def stats(values):
    a=np.array(values, dtype=float)
    if not len(a):
        return None
    return dict(n=len(a), median=float(np.median(a)), p95=float(np.percentile(a,95)),
                min=float(a.min()), max=float(a.max()))


def measure(quad, marker_id, pose, geometry, workspace, camera):
    predicted=cv2.projectPoints(geometry[marker_id],pose.rvec,pose.tvec,camera.matrix,camera.distortion)[0].reshape(4,2)
    residual=quad-predicted
    common=residual.mean(axis=0)
    shape=residual-common
    center=marker_center_px(quad,camera)
    center_prediction=cv2.projectPoints(np.array([workspace.markers[marker_id]]),pose.rvec,pose.tvec,camera.matrix,None)[0].reshape(2)
    center_residual=center-center_prediction
    plane=np.array([pixel_to_plane(p,0.,pose,camera) for p in quad])
    lengths=np.linalg.norm(np.roll(plane,-1,axis=0)-plane,axis=1)
    return dict(center_residual_px=center_residual.tolist(), center_error_px=float(np.linalg.norm(center_residual)),
                corner_residuals_px=residual.tolist(), corner_rms_px=float(np.sqrt(np.mean(np.sum(residual**2,axis=1)))),
                common_offset_px=common.tolist(), shape_rms_px=float(np.sqrt(np.mean(np.sum(shape**2,axis=1)))),
                inferred_edge_lengths_mm=lengths.tolist(),
                opposite_edge_difference_mm=float(max(abs(lengths[0]-lengths[2]),abs(lengths[1]-lengths[3]))),
                plane_corners_mm=plane.tolist())


def summarize(records):
    result={}
    for key in sorted({r['marker_id'] for r in records}):
        group=[r for r in records if r['marker_id']==key]
        result[str(key)]={name:stats([r[name] for r in group]) for name in
                         ('center_error_px','corner_rms_px','shape_rms_px','opposite_edge_difference_mm')}
        result[str(key)]['center_residual_median_px']=np.median([r['center_residual_px'] for r in group],axis=0).tolist()
        result[str(key)]['edge_lengths_mm']=stats([v for r in group for v in r['inferred_edge_lengths_mm']])
        result[str(key)]['edge_medians_mm']=np.median([r['inferred_edge_lengths_mm'] for r in group],axis=0).tolist()
    return result


def run(output):
    if output.exists():
        raise ValueError('Report exists')
    paths=[replay.ROOT/'pose-live-device.txt',replay.ROOT/'pose-comparison/corner-size-report.json',
           *(replay.ASSETS/k for k in replay.BINDINGS)]
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    for name,expected in replay.BINDINGS.items():
        assert hashes[str(replay.ASSETS/name)]==expected
    camera=replay.CameraModel.from_profile(json.loads((replay.ASSETS/'camera-profile.json').read_bytes()))
    workspace=replay.MetricWorkspace.from_dict(json.loads((replay.ASSETS/'workspace-profile.json').read_bytes()))
    prior=json.loads(paths[1].read_bytes())
    orientations={int(k):v for k,v in prior['orientations'].items()}
    geometries={side:corner.corners_for(side,orientations,workspace) for side in (69,70)}
    rows=replay.load_rows(paths[0])
    records={side:[] for side in geometries}
    excluded=Counter()
    used=[]
    for row in rows:
        if row['frame_ms']<=prior['cutoff_ms']:
            excluded['orientation_fit_or_earlier']+=1
            continue
        pose,reason=replay.baseline(row['detections'],workspace,camera)
        if pose is None or row['count']!=5:
            excluded['no_accepted_five_marker_reference']+=1
            continue
        used.append(row['frame_ms'])
        for side,geometry in geometries.items():
            for key,quad in row['detections'].items():
                record=measure(quad,key,pose,geometry,workspace,camera)
                records[side].append(dict(frame_ms=row['frame_ms'],marker_id=key,**record))
    # Consecutive observations only; remove a frame-wide edge scale change for ranking.
    # This is an inconsistency diagnostic, not separation of motion/pose/detection causes.
    changes=[]
    base=records[69]
    for first,second in zip(used,used[1:]):
        if second-first>350:
            continue
        a={r['marker_id']:r for r in base if r['frame_ms']==first}
        b={r['marker_id']:r for r in base if r['frame_ms']==second}
        deltas={k:np.array(b[k]['inferred_edge_lengths_mm'])-a[k]['inferred_edge_lengths_mm'] for k in a}
        common=float(np.median(np.concatenate(list(deltas.values()))))
        for key,delta in deltas.items():
            changes.append(dict(frame_ms=second,previous_ms=first,marker_id=key,
                                max_edge_change_mm=float(np.abs(delta).max()),
                                max_relative_edge_change_mm=float(np.abs(delta-common).max())))
    winners={}
    for side,items in records.items():
        winners[side]=dict(Counter(max((r for r in items if r['frame_ms']==time),key=lambda r:r['shape_rms_px'])['marker_id'] for time in used))
    report=dict(offline_only=True,live_enabled=False,hashes=hashes,used_frames=used,excluded=dict(excluded),
                reference='Existing full-five-marker pose; the same observations contribute to its fit. Not independent physical truth.',
                shape_definition='RMS corner residual after removing the common 2D offset; does not remove scale/rotation or isolate detection error.',
                edge_definition='Corners backprojected through existing pose to z=0; inferred lengths, not ruler measurements.',
                marker_3='No accepted five-marker reference includes ID3; cannot assess its geometry.',
                summaries={str(side):summarize(items) for side,items in records.items()},
                worst_shape_counts=winners,records=records,adjacent_changes=changes,
                adjacent_summary={str(k):{name:stats([r[name] for r in changes if r['marker_id']==k])
                    for name in ('max_edge_change_mm','max_relative_edge_change_mm')} for k in (0,1,2,4,5)})
    assert hashes=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as f:
        json.dump(report,f,indent=2,allow_nan=False)
    print(json.dumps({k:report[k] for k in ('summaries','worst_shape_counts','adjacent_summary')},indent=2))


if __name__=='__main__':
    run(replay.ROOT/'pose-comparison/marker-audit.json')
