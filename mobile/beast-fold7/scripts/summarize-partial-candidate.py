"""Availability on chronological real observations; no accuracy claim for missing markers."""
import hashlib
import json
import sys
from pathlib import Path
from collections import Counter
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pose_replay_compare as replay
import measured_spacing_compare as capture
from corner_bridge_replay import CornerBridge


def main():
    output=ROOT/'pose-comparison/partial-candidate-fallback-availability.json'
    if output.exists():raise ValueError('Report exists')
    camera=replay.CameraModel.from_profile(json.loads((replay.ASSETS/'camera-profile.json').read_bytes()))
    workspace=replay.MetricWorkspace.from_dict(json.loads((replay.ASSETS/'workspace-profile.json').read_bytes()))
    source=json.loads((ROOT/'pose-comparison/guarded-bridge-report.json').read_bytes())['datasets']
    video=json.loads((ROOT/'pose-comparison/v1-video-marker-audit.json').read_bytes())['rows']
    old={'success_video':{r['frame_ms']:{int(k):np.array(v) for k,v in r['detections'].items()} for r in video},
         'independent_retake':{r['frame_ms']:r['detections'] for r in capture.capture_rows()}}
    result={}
    for name,data in source.items():
        tracker=CornerBridge(workspace,camera,max_age_ms=30000,conservative_three=True,retain_reference_on_loss=True)
        rows=[]
        for r in data['rows']:
            found={int(k):np.array(v) for k,v in r['detections'].items()}
            pose,detail=tracker.update(r['frame_ms'],found)
            before,why=replay.baseline(old[name][r['frame_ms']],workspace,camera)
            if pose is None and before is not None:
                pose=before
                detail=dict(reason='legacy_fallback',method='unchanged_baseline')
            rows.append(dict(frame_ms=r['frame_ms'],original_valid=before is not None,
                original_ids=sorted(old[name][r['frame_ms']]),original_reason=why,
                candidate_valid=pose is not None,candidate_ids=sorted(found),detail=detail))
        summary=dict(frames=len(rows),original_valid=sum(r['original_valid'] for r in rows),
                     candidate_valid=sum(r['candidate_valid'] for r in rows),
                     gained=sum(r['candidate_valid'] and not r['original_valid'] for r in rows),
                     lost=sum(r['original_valid'] and not r['candidate_valid'] for r in rows),
                     reasons=dict(Counter(r['detail']['reason'] for r in rows)))
        result[name]=dict(summary=summary,rows=rows)
        print(name,json.dumps(summary))
    hashes={k:hashlib.sha256((replay.ASSETS/k).read_bytes()).hexdigest() for k in replay.BINDINGS}
    assert hashes==replay.BINDINGS
    with output.open('x',encoding='utf-8') as f:
        json.dump(dict(offline_only=True,profile_hashes=hashes,datasets=result),f,indent=2,allow_nan=False)


if __name__=='__main__':main()
