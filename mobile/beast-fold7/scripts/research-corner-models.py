"""Compare precise corner maps on strictly later, masked observations."""
import json
import sys
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pose_replay_compare as replay
from session_corner_replay import fit_reference,partial_pose


def main():
    output=ROOT/'pose-comparison/c3-corner-models.json'
    if output.exists():raise ValueError('Report exists')
    camera=replay.CameraModel.from_profile(json.loads((replay.ASSETS/'camera-profile.json').read_bytes()))
    workspace=replay.MetricWorkspace.from_dict(json.loads((replay.ASSETS/'workspace-profile.json').read_bytes()))
    eye=json.loads((replay.ASSETS/'eye-projection.json').read_bytes())
    eyes=[np.array(eye[k]).reshape(3,4) for k in ('left_projection','right_projection')]
    source=json.loads((ROOT/'pose-comparison/guarded-bridge-report.json').read_bytes())
    results={}
    for name,data in source['datasets'].items():
        rows=[{**r,'detections':{int(k):np.array(v) for k,v in r['detections'].items()}} for r in data['rows']]
        history=[];records={mode:[] for mode in ('latest','median8','centered8')}
        for index,row in enumerate(rows):
            reference,_=replay.baseline(row['detections'],workspace,camera)
            if reference is None or len(row['detections'])<5:continue
            if len(history)>=8:
                geometries={'latest':fit_reference(history[-1:],workspace,camera),
                            'median8':fit_reference(history[-8:],workspace,camera)}
                geometries['centered8']={k:v-v.mean(axis=0)+workspace.markers[k]
                                         for k,v in geometries['median8'].items()}
                for visible in ((0,1,4),(1,2,5),(0,1,2,4),(0,1,2,5)):
                    subset={k:v for k,v in row['detections'].items() if k in visible}
                    if len(subset)!=len(visible):continue
                    for mode,geometry in geometries.items():
                        pose,why=partial_pose(subset,geometry,camera)
                        records[mode].append(dict(index=index,ids=visible,reason=why,
                            comparison=replay.comparison(reference,pose,workspace,camera,eyes)))
            history.append(row)
        results[name]={}
        for mode,items in records.items():
            summary={','.join(map(str,ids)):replay.summary([r for r in items if tuple(r['ids'])==ids])
                     for ids in ((0,1,4),(1,2,5),(0,1,2,4),(0,1,2,5))}
            results[name][mode]=dict(summary=summary,records=items)
            print(name,mode,json.dumps(summary),flush=True)
    with output.open('x',encoding='utf-8') as f:json.dump(results,f,allow_nan=False)


if __name__=='__main__':main()
