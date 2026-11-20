"""Audit the single-tool D trial from numeric logs only; never open hardware."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

import yaml
from run_neutral_d_server import ROOT
from compare_neutral_recovery import trace, metrics

sys.path.insert(0, str(ROOT))
from server.realtime.realtime_replay import validate_session

HERE = Path(__file__).parent
session = HERE / 'handle-linked-D-sessions/viture_aruco_rt_20261115_141146_52bb3e0131c5'
config = yaml.safe_load((session / 'config_used.yaml').read_text(encoding='utf-8'))
rows = [json.loads(s) for s in (session / 'results.jsonl').read_text(encoding='utf-8').splitlines() if s]
assert config['yolo']['handle_linked_driver'] is True
assert config['state_filter']['timing']['retain_completed_hold'] is True
assert config['logging']['save_frames'] is False
assert not any(p.suffix.lower() in ('.jpg','.jpeg','.png','.mp4','.avi') for p in session.rglob('*'))
exact = validate_session(session)
assert exact['matched']
details = trace(rows, config)
transitions = [i for i, r in enumerate(details) if r['transition']]
assert len(transitions) == 1 and details[transitions[0]]['transition'] == 'S5->S6'
first = next((r['frame'] for r in details if r['active_armed']), None)
after = [r for r in details if first is not None and r['frame'] >= first and r['state'] == 'S5']
restarts = [r['frame'] for prev,r in zip(details,details[1:])
            if first is not None and r['frame'] > first and r['phase']=='OBSERVING'
            and prev['phase']!='OBSERVING']
at = transitions[0]
context = [dict(frame=rows[i]['frame_id'], input=rows[i]['filter_input'], trace=details[i])
           for i in range(max(0,at-10),at+1)]
player = HERE / 'checkpoint-text-build/player-20261115-141150-698.log'
manifest = json.loads((HERE / 'poll-protected-hashes-after.json').read_text(encoding='utf-8-sig'))
unchanged = all(hashlib.sha256(Path(r['Path']).read_bytes()).hexdigest().upper()==r['Hash'].upper()
                for r in manifest)
assert unchanged
result = dict(session=session.name, scope='One actual isolated D trial, not full A-D validation.',
    frames=len(rows), duration_ms=rows[-1]['filter_input']['timestamp_ms']-rows[0]['filter_input']['timestamp_ms'],
    exact_actual_replay=exact, first_completed_hold_frame=first, restarts_after_completed_hold=restarts,
    metrics=metrics(details), paused_reasons_after_hold=dict(Counter(r['reason'] for r in after if r['phase']=='PAUSED')),
    phases=dict(Counter(r['phase'] for r in details)),
    unlinked_candidate_removed_frames=sum(r['filter_input']['features'].get('driver_unlinked_candidates',0)>0 for r in rows),
    player_cue_log_entries=dict(Counter(re.findall(r'cue=(.*?) instruction=', player.read_text(encoding='utf-8', errors='replace')))),
    transition_context=context, image_saving=False, protected_unchanged=unchanged,
    user_feedback=dict(completion='초록 안내 뒤에 뗐고 최종 확인도 봤어', smoothness='확실히 매끄러워졌어'))
output = HERE / 'handle-linked-D-live-result.json'
with output.open('x', encoding='utf-8') as stream:
    json.dump(result, stream, ensure_ascii=False, indent=2)
print(json.dumps({k:v for k,v in result.items() if k not in ('metrics','transition_context')}, ensure_ascii=False, indent=2))
print(json.dumps(result['metrics']['transitions']))
