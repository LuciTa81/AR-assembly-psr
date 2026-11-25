"""Chronological three-second occlusion experiments, never a runtime setting."""
import hashlib
import itertools
import json
from collections import Counter
import numpy as np
import session_corner_replay as candidate
import pose_replay_compare as replay
import measured_spacing_compare as capture


def evaluate(rows,workspace,camera,eyes,tracker_factory=candidate.RecentReference,max_age_ms=3000,anchor_stride=1):
    actual=[];masked=[]
    tracker=tracker_factory(workspace,camera)
    for i,row in enumerate(rows):
        pose,reason=tracker.update(row['frame_ms'],row['detections'])
        base,why=replay.baseline(row['detections'],workspace,camera)
        actual.append(dict(index=i,count=len(row['detections']),accepted=pose is not None,reason=reason,baseline=why,
            comparison=replay.comparison(base,pose,workspace,camera,eyes) if base is not None else None))
        if base is None or len(row['detections'])<5 or i % anchor_stride:
            continue
        for count in (3,4):
            for ids in itertools.combinations(sorted(row['detections']),count):
                trial=tracker_factory(workspace,camera)
                trial.update(row['frame_ms'],row['detections'])
                for index in range(i+1,len(rows)):
                    current=rows[index];age=current['frame_ms']-row['frame_ms']
                    if age>max_age_ms:
                        break
                    # Never supply withheld detections to the candidate, including intermediate frames.
                    subset={k:v for k,v in current['detections'].items() if k in ids}
                    alt,reason=trial.update(current['frame_ms'],subset)
                    reference,_=replay.baseline(current['detections'],workspace,camera)
                    if reference is None or len(current['detections'])<5 or len(subset)!=count:
                        continue
                    masked.append(dict(anchor=i,index=index,age_ms=age,ids=ids,count=count,reason=reason,
                        comparison=replay.comparison(reference,alt,workspace,camera,eyes)))
    return dict(actual=actual,masked=masked,summary=dict(
        actual_reasons=dict(Counter(r['reason'] for r in actual)),
        normal=replay.summary([r for r in actual if r['count']>=5 and r['baseline']=='tracking']),
        actual_partial=sum(r['count'] in (3,4) for r in actual),
        actual_partial_returned=sum(r['count'] in (3,4) and r['accepted'] for r in actual),
        masked={str(n):replay.summary([r for r in masked if r['count']==n]) for n in (3,4)},
        combinations={','.join(map(str,ids)):replay.summary([r for r in masked if r['ids']==ids]) for ids in sorted({r['ids'] for r in masked})}))


def main():
    out=replay.ROOT/'pose-comparison/recent-corner-report.json'
    if out.exists():raise ValueError('Report exists')
    camera=replay.CameraModel.from_profile(json.loads((replay.ASSETS/'camera-profile.json').read_bytes()))
    workspace=replay.MetricWorkspace.from_dict(json.loads((replay.ASSETS/'workspace-profile.json').read_bytes()))
    eye=json.loads((replay.ASSETS/'eye-projection.json').read_bytes())
    eyes=[np.array(eye[k]).reshape(3,4) for k in ('left_projection','right_projection')]
    protected=[*(replay.ASSETS/k for k in replay.BINDINGS),replay.ROOT/'pose-live-device.txt',*sorted(capture.CAPTURE.glob('*.json'))]
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    for name,h in replay.BINDINGS.items():assert hashes[str(replay.ASSETS/name)]==h
    datasets={'numeric_trace':replay.load_rows(replay.ROOT/'pose-live-device.txt'),'capture_retake':capture.capture_rows()}
    result={name:evaluate(rows,workspace,camera,eyes) for name,rows in datasets.items()}
    assert hashes=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    with out.open('x',encoding='utf-8') as f:
        json.dump(dict(offline_only=True,live_enabled=False,max_anchor_age_ms=3000,hashes=hashes,
            caveats=['Correlated overlapping windows, not independent accuracy trials.',
                     'Only past five-marker anchor is used. Partial frames never renew it.',
                     'Actual partial frames have no independent reference.',
                     'Three-second limit does not solve sustained partial visibility.'],datasets=result),f,indent=2,allow_nan=False)
    for name,data in result.items():
        s=data['summary'];print(name,'actual partial',s['actual_partial_returned'],'/',s['actual_partial'])
        for n,m in s['masked'].items():
            print(n,json.dumps({k:v for k,v in m.items() if k!='reasons'}))


if __name__=='__main__':main()
