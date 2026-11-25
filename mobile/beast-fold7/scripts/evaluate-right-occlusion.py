"""Priority: top-right ID2 and lower-right ID5 hidden, leaving 0/1/4."""
import json
import sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pose_replay_compare as replay
from corner_bridge_replay import CornerBridge


def main():
    retain=len(sys.argv)>1 and sys.argv[1]=='retain'
    output=ROOT/('pose-comparison/right-occlusion-retain-report.json' if retain else 'pose-comparison/right-occlusion-report.json')
    if output.exists():raise ValueError('Report exists')
    camera=replay.CameraModel.from_profile(json.loads((replay.ASSETS/'camera-profile.json').read_bytes()))
    workspace=replay.MetricWorkspace.from_dict(json.loads((replay.ASSETS/'workspace-profile.json').read_bytes()))
    eye=json.loads((replay.ASSETS/'eye-projection.json').read_bytes())
    eyes=[np.array(eye[k]).reshape(3,4) for k in ('left_projection','right_projection')]
    source=json.loads((ROOT/'pose-comparison/guarded-bridge-report.json').read_bytes())
    results={}
    for name,data in source['datasets'].items():
        rows=[{**r,'detections':{int(k):np.array(v) for k,v in r['detections'].items()}} for r in data['rows']]
        records=[]
        for i,row in enumerate(rows):
            base,_=replay.baseline(row['detections'],workspace,camera)
            if base is None or len(row['detections'])<5:continue
            trial=CornerBridge(workspace,camera,max_age_ms=30000,conservative_three=True,retain_reference_on_loss=retain)
            trial.update(row['frame_ms'],row['detections'])
            for j in range(i+1,len(rows)):
                current=rows[j];age=current['frame_ms']-row['frame_ms']
                if age>30000:break
                subset={k:v for k,v in current['detections'].items() if k in (0,1,4)}
                pose,detail=trial.update(current['frame_ms'],subset)
                reference,_=replay.baseline(current['detections'],workspace,camera)
                if reference is None or len(current['detections'])<5 or len(subset)!=3:continue
                records.append(dict(anchor=i,index=j,age_ms=age,reason=detail['reason'],
                    comparison=replay.comparison(reference,pose,workspace,camera,eyes)))
        summary=replay.summary(records)
        for key in 'ABCD':
            values=[r['comparison']['targets'][key]['camera_px'] for r in records if r['comparison']]
            summary[key+'_camera_px']=np.percentile(values,[50,95,100]).tolist() if values else None
        summary['over_10s']=replay.summary([r for r in records if r['age_ms']>10000])
        results[name]=dict(summary=summary,records=records)
        print(name,json.dumps(summary),flush=True)
    with output.open('x',encoding='utf-8') as f:
        json.dump(dict(offline_only=True,visible_ids=[0,1,4],hidden_ids=[2,5],datasets=results),f,indent=2,allow_nan=False)


if __name__=='__main__':main()
