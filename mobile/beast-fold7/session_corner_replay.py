"""Offline session-local corner reference; never used by the Android runtime."""
import hashlib
import itertools
import json
from collections import Counter
import cv2
import numpy as np
import pose_replay_compare as replay
from server.realtime.workspace_projection import pixel_to_plane, estimate_corner_pose


def fit_reference(rows, workspace, camera):
    if not rows:
        raise ValueError('No five-marker initialization')
    samples = {}
    for row in rows:
        detections = row['detections']
        pose, _ = replay.baseline(detections, workspace, camera)
        if pose is None or len(detections) < 5:
            raise ValueError('Initialization requires accepted five-marker observations')
        for key, quad in detections.items():
            corners = np.array([pixel_to_plane(point, 0., pose, camera) for point in quad])
            corners[:, 2] = 0.
            samples.setdefault(key, []).append(corners)
    # Preserve the observed quadrilaterals, not an assumed 69/70 mm square or center.
    return {key:np.median(values,axis=0) for key,values in samples.items() if len(values)==len(rows)}


def partial_pose(detections, geometry, camera):
    if len(detections)<3:
        return None,'need_three_markers'
    if not geometry or set(detections)-set(geometry):
        return None,'reference_missing'
    try:
        return estimate_corner_pose(detections,geometry,camera,(1280,720),max_rms_px=3.2),'tracking'
    except (ValueError,cv2.error) as exc:
        return None,str(exc)


class RecentReference:
    """Bounded offline hypothesis. Partial observations never renew reference age."""
    def __init__(self, workspace, camera):
        self.workspace,self.camera=workspace,camera
        self.geometry=None
        self.anchor_ms=None
        self.last_ms=None

    def update(self, timestamp, detections):
        if self.last_ms is not None and timestamp<=self.last_ms:
            self.geometry=None;self.anchor_ms=None;self.last_ms=timestamp
            return None,'nonmonotonic_time'
        self.last_ms=timestamp
        if not detections:
            self.geometry=None;self.anchor_ms=None
            return None,'tracking_lost'
        if len(detections)>=5:
            pose,reason=replay.baseline(detections,self.workspace,self.camera)
            if pose is not None:
                self.geometry=fit_reference([{'detections':detections}],self.workspace,self.camera)
                self.anchor_ms=timestamp
            return pose,reason
        if self.anchor_ms is None or timestamp-self.anchor_ms>3000:
            self.geometry=None;self.anchor_ms=None
            return None,'reference_expired'
        return partial_pose(detections,self.geometry,self.camera)


def evaluate(rows, workspace, camera, eyes):
    accepted = [i for i,r in enumerate(rows) if len(r['detections'])>=5 and replay.baseline(r['detections'],workspace,camera)[0] is not None]
    if len(accepted)<9:
        raise ValueError('Need eight initialization frames and separate validation')
    fit_indices=accepted[:8]
    geometry=fit_reference([rows[i] for i in fit_indices],workspace,camera)
    cutoff=fit_indices[-1]
    actual,masked,full=[],[],[]
    for index,row in enumerate(rows):
        if index<=cutoff:
            continue
        detections=row['detections']
        reference,base_reason=replay.baseline(detections,workspace,camera)
        pose,reason=partial_pose(detections,geometry,camera)
        actual.append(dict(index=index,ids=sorted(detections),baseline=base_reason,
                           accepted=pose is not None,reason=reason))
        if reference is None or len(detections)<5:
            continue
        full.append(dict(index=index,reason=reason,comparison=replay.comparison(reference,pose,workspace,camera,eyes)))
        for count in (3,4):
            for ids in itertools.combinations(sorted(detections),count):
                subset={key:detections[key] for key in ids}
                alternative,why=partial_pose(subset,geometry,camera)
                old,old_reason=replay.baseline(subset,workspace,camera)
                masked.append(dict(index=index,ids=ids,count=count,reason=why,
                    baseline_reason=old_reason,baseline_accepted=old is not None,
                    comparison=replay.comparison(reference,alternative,workspace,camera,eyes)))
    groups={str(n):replay.summary([r for r in masked if r['count']==n]) for n in (3,4)}
    combinations={','.join(map(str,ids)):replay.summary([r for r in masked if r['ids']==ids]) for ids in sorted({r['ids'] for r in masked})}
    return dict(fit_indices=fit_indices,evaluation_start=cutoff+1,
        inferred_corners={str(k):v.tolist() for k,v in geometry.items()},
        summary=dict(actual=len(actual),baseline_accepted=sum(r['baseline']=='tracking' for r in actual),
            candidate_returned=sum(r['accepted'] for r in actual),
            actual_low_marker_returned=sum(r['accepted'] and len(r['ids']) in (3,4) for r in actual),
            actual_low_marker_count=sum(len(r['ids']) in (3,4) for r in actual),
            actual_reasons=dict(Counter(r['reason'] for r in actual)),full=replay.summary(full),masked=groups,combinations=combinations),
        actual=actual,full=full,masked=masked)


def run(output):
    if output.exists():
        raise ValueError('Refusing to overwrite a report')
    import measured_spacing_compare as captured
    protected=[*(replay.ASSETS/k for k in replay.BINDINGS),replay.ROOT/'pose-live-device.txt',*sorted(captured.CAPTURE.glob('*.json'))]
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    for name,value in replay.BINDINGS.items():
        assert hashes[str(replay.ASSETS/name)]==value
    camera=replay.CameraModel.from_profile(json.loads((replay.ASSETS/'camera-profile.json').read_bytes()))
    workspace=replay.MetricWorkspace.from_dict(json.loads((replay.ASSETS/'workspace-profile.json').read_bytes()))
    eye=json.loads((replay.ASSETS/'eye-projection.json').read_bytes())
    eyes=[np.array(eye[k]).reshape(3,4) for k in ('left_projection','right_projection')]
    datasets={'numeric_trace':replay.load_rows(replay.ROOT/'pose-live-device.txt'),'capture_retake':captured.capture_rows()}
    reports={key:evaluate(rows,workspace,camera,eyes) for key,rows in datasets.items()}
    report=dict(offline_only=True,live_enabled=False,opencv=cv2.__version__,hashes=hashes,
        protocol='First eight accepted >=5-marker frames infer session-local corners; freeze before all later evaluation; no hidden current markers enter fitting.',
        limits=dict(rms_px=3.2,max_px=5,ambiguity_px=.25),
        caveats=['Inferred geometry is relative to existing pose, not measured board geometry.',
                 'Preservation measures consistency with full-marker reference, not physical optical accuracy.',
                 'Masks from the same frame are correlated; no cold-start three-marker support.',
                 'No temporal extension of stale output; each candidate solves fresh observed corners.',
                 'Android remains unchanged; no candidate drives assembly progress.'],datasets=reports)
    assert hashes=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    with output.open('x',encoding='utf-8') as stream:
        json.dump(report,stream,indent=2,allow_nan=False)
    print(json.dumps({key:{k:v for k,v in data['summary'].items() if k!='combinations'} for key,data in reports.items()},indent=2))


if __name__=='__main__':
    run(replay.ROOT/'pose-comparison/session-corner-report.json')
