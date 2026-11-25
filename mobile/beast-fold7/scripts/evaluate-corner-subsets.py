"""All 3/4-marker subsets on held-out next observations, with no current-frame fitting."""
import copy
import itertools
import json
import sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pose_replay_compare as replay
from learned_corner_tracker import LearnedCornerTracker,MultiWindowCorners


def main():
    multi=len(sys.argv)>1 and sys.argv[1]=='multi'
    output=ROOT/('pose-comparison/c3-multi-all-subsets.json' if multi else 'pose-comparison/c3-all-subsets.json')
    if output.exists():raise ValueError('Report exists')
    camera=replay.CameraModel.from_profile(json.loads((replay.ASSETS/'camera-profile.json').read_bytes()))
    workspace=replay.MetricWorkspace.from_dict(json.loads((replay.ASSETS/'workspace-profile.json').read_bytes()))
    eye=json.loads((replay.ASSETS/'eye-projection.json').read_bytes())
    eyes=[np.array(eye[k]).reshape(3,4) for k in ('left_projection','right_projection')]
    source=json.loads((ROOT/'pose-comparison/guarded-bridge-report.json').read_bytes())
    results={}
    for name,data in source['datasets'].items():
        tracker=MultiWindowCorners(workspace,camera) if multi else LearnedCornerTracker(workspace,camera)
        records=[];actual=[]
        for index,row in enumerate(data['rows']):
            detections={int(k):np.array(v) for k,v in row['detections'].items()}
            reference,_=replay.baseline(detections,workspace,camera)
            if reference is not None and len(detections)>=5:
                for count in (3,4):
                    for ids in itertools.combinations(sorted(detections),count):
                        trial=copy.deepcopy(tracker)
                        pose,detail=trial.update(row['frame_ms'],{k:detections[k] for k in ids})
                        records.append(dict(index=index,count=count,ids=ids,reason=detail['reason'],
                            comparison=replay.comparison(reference,pose,workspace,camera,eyes)))
            pose,detail=tracker.update(row['frame_ms'],detections)
            actual.append(dict(index=index,markers=len(detections),valid=pose is not None,reason=detail['reason']))
        summary={str(count):replay.summary([r for r in records if r['count']==count]) for count in (3,4)}
        results[name]=dict(summary=summary,records=records,actual=actual)
        print(name,json.dumps(summary),flush=True)
    with output.open('x',encoding='utf-8') as f:json.dump(results,f,allow_nan=False)


if __name__=='__main__':main()
