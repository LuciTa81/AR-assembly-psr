"""Same real observations and legacy detector fallback for C2 and C3."""
import json
import sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pose_replay_compare as replay
import measured_spacing_compare as captured
from learned_corner_tracker import MultiWindowCorners
from tracking_continuity import ReferenceBank


def main():
    output=ROOT/'pose-comparison/c3-actual-availability.json'
    if output.exists():raise ValueError('Report exists')
    camera=replay.CameraModel.from_profile(json.loads((replay.ASSETS/'camera-profile.json').read_bytes()))
    workspace=replay.MetricWorkspace.from_dict(json.loads((replay.ASSETS/'workspace-profile.json').read_bytes()))
    source=json.loads((ROOT/'pose-comparison/guarded-bridge-report.json').read_bytes())
    legacy_video=json.loads((ROOT/'pose-comparison/refinement-audit.json').read_bytes())['rows']['subpix']
    legacy={'success_video':legacy_video,'independent_retake':captured.capture_rows()}
    results={}
    for name,data in source['datasets'].items():
        previous=ReferenceBank(workspace,camera);current=MultiWindowCorners(workspace,camera);records=[]
        for i,row in enumerate(data['rows']):
            detections={int(k):np.array(v) for k,v in row['detections'].items()}
            old,why=previous.update(row['frame_ms'],detections)
            new,detail=current.update(row['frame_ms'],detections)
            observed={int(k):np.array(v) for k,v in legacy[name][i]['detections'].items()}
            base,_=replay.baseline(observed,workspace,camera)
            records.append(dict(index=i,reason=detail['reason'],v1=base is not None,
                c2=old is not None or base is not None,c3=new is not None or base is not None,
                warmup_fallback=new is not None or base is not None or (detail['reason']=='map_expired' and old is not None)))
        summary={k:sum(r[k] for r in records) for k in ('v1','c2','c3','warmup_fallback')}
        summary['frames']=len(records)
        results[name]=dict(summary=summary,records=records)
        print(name,json.dumps(summary),flush=True)
    with output.open('x',encoding='utf-8') as f:json.dump(results,f,allow_nan=False)


if __name__=='__main__':main()
