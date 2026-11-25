"""Generate numeric Android parity fixtures from saved observations only."""
import json
import sys
from pathlib import Path
import cv2
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pose_replay_compare as replay
from corner_bridge_replay import CornerBridge


def main():
    output=ROOT/'app/src/androidTest/assets/partial-marker-fixtures.json'
    if output.exists(): raise ValueError('Fixtures exist')
    camera=replay.CameraModel.from_profile(json.loads((replay.ASSETS/'camera-profile.json').read_bytes()))
    workspace=replay.MetricWorkspace.from_dict(json.loads((replay.ASSETS/'workspace-profile.json').read_bytes()))
    report=json.loads((ROOT/'pose-comparison/guarded-bridge-30000-report.json').read_bytes())
    fixtures=[]
    for name,data in report['datasets'].items():
        rows=data['rows']
        trials=data['masked']
        stride=max(1,len(trials)//160)
        for trial in trials[::stride]:
            anchor=rows[trial['anchor']]['detections']
            current={k:v for k,v in rows[trial['index']]['detections'].items() if int(k) in trial['ids']}
            tracker=CornerBridge(workspace,camera,max_age_ms=30000,conservative_three=True)
            tracker.update(0,{int(k):np.array(v) for k,v in anchor.items()})
            pose,detail=tracker.update(trial['age_ms'],{int(k):np.array(v) for k,v in current.items()})
            xyz={} if pose is None else {k:(cv2.Rodrigues(pose.rvec)[0]@p+pose.tvec.reshape(3)).tolist() for k,p in workspace.targets.items()}
            fixtures.append(dict(dataset=name,anchor=anchor,current=current,age_ms=round(trial['age_ms']),
                                 valid=pose is not None,reason=detail['reason'],camera_targets=xyz))
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as f: json.dump(fixtures,f,allow_nan=False)
    print('fixtures',len(fixtures),'accepted',sum(x['valid'] for x in fixtures))


if __name__=='__main__':main()
