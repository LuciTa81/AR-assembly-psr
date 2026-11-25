"""Held-out partial observations with an independent corner-refinement path."""
import json
import sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pose_replay_compare as replay
import recent_corner_compare as evaluator
from corner_bridge_replay import CornerBridge


def main():
    mode = sys.argv[1] if len(sys.argv)>1 else 'hybrid'
    if mode not in ('hybrid','precise'): raise ValueError('Unknown mode')
    output=ROOT/('pose-comparison/precise-bridge-report.json' if mode=='hybrid' else 'pose-comparison/precise-only-bridge-report.json')
    if output.exists(): raise ValueError('Report exists')
    camera=replay.CameraModel.from_profile(json.loads((replay.ASSETS/'camera-profile.json').read_bytes()))
    workspace=replay.MetricWorkspace.from_dict(json.loads((replay.ASSETS/'workspace-profile.json').read_bytes()))
    eye=json.loads((replay.ASSETS/'eye-projection.json').read_bytes())
    eyes=[np.array(eye[k]).reshape(3,4) for k in ('left_projection','right_projection')]
    data=json.loads((ROOT/'pose-comparison/refinement-audit.json').read_bytes())['rows']
    rows=[{**r,'detections':{int(k):np.array(v) for k,v in r['detections'].items()}} for r in data['subpix']]
    precise={r['frame_ms']:{int(k):np.array(v) for k,v in r['detections'].items()} for r in data['apriltag']}
    class Adapter(CornerBridge):
        def update(self,timestamp,detections):
            visible={k:q for k,q in precise[timestamp].items() if k in detections}
            pose,detail=super().update(timestamp,detections,visible)
            return pose,detail['reason']
    changes=[]
    if mode=='precise':
        for row in rows:
            original,_=replay.baseline(row['detections'],workspace,camera)
            refined=precise[row['frame_ms']]
            alternative,reason=replay.baseline(refined,workspace,camera)
            if original is not None and len(row['detections'])>=5 and len(refined)>=5:
                changes.append(dict(reason=reason,comparison=replay.comparison(original,alternative,workspace,camera,eyes)))
            row['detections']=refined
    result=evaluator.evaluate(rows,workspace,camera,eyes,tracker_factory=Adapter)
    with output.open('x',encoding='utf-8') as f:
        json.dump(dict(offline_only=True,live_enabled=False,mode=mode,full_changes=replay.summary(changes),result=result),f,indent=2,allow_nan=False)
    print('full_changes',json.dumps(replay.summary(changes)))
    print(json.dumps({k:v for k,v in result['summary'].items() if k!='combinations'}))


if __name__=='__main__': main()
