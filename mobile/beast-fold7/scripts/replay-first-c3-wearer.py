"""Replay returned numerical observations, not raw detector input or physical truth."""
import json
import sys
from pathlib import Path
from collections import Counter
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pose_replay_compare as replay
from learned_corner_tracker import MultiWindowCorners,CohortCorners


def main():
    cohort=len(sys.argv)>1 and sys.argv[1]=='cohort'
    factory=CohortCorners if cohort else MultiWindowCorners
    output=ROOT/('pose-comparison/c31-cohort-wearer-replay.json' if cohort else 'pose-comparison/c31-first-wearer-replay.json')
    if output.exists():raise ValueError('Report exists')
    camera=replay.CameraModel.from_profile(json.loads((replay.ASSETS/'camera-profile.json').read_bytes()))
    workspace=replay.MetricWorkspace.from_dict(json.loads((replay.ASSETS/'workspace-profile.json').read_bytes()))
    rows=[];tracker=factory(workspace,camera);session=None
    for line in (ROOT/'.local/c3-first-wearer-poses-20261125.txt').read_text(encoding='utf-8-sig').splitlines():
        if 'BeastPoseFrame: ' not in line:continue
        item=json.loads(line.split('BeastPoseFrame: ',1)[1])
        if item['session']!=session:
            tracker=factory(workspace,camera);session=item['session']
        pose,detail=tracker.update(item['frame_ms'],{int(k):np.array(v) for k,v in item['corners'].items()})
        rows.append(dict(frame_ms=item['frame_ms'],count=item['count'],logged_valid=item['valid'],
            logged_reason=item['reason'],replay_valid=pose is not None,replay_reason=detail['reason']))
    affected=[r for r in rows if r['logged_reason']=='invalid_corner_ids']
    summary=dict(frames=len(rows),logged_reasons=dict(Counter(r['logged_reason'] for r in rows)),
                 replay_reasons=dict(Counter(r['replay_reason'] for r in rows)),
                 affected=len(affected),affected_replay_returned=sum(r['replay_valid'] for r in affected))
    with output.open('x',encoding='utf-8') as f:json.dump(dict(summary=summary,records=rows,
        caveat='Logs contain returned detector observations including legacy fallback, not all precise inputs. No physical alignment ground truth.'),f,allow_nan=False)
    print(json.dumps(summary))


if __name__=='__main__':main()
