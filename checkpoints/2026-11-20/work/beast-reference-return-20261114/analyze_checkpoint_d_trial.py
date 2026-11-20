"""Audit the completed-HOLD trial using stored numeric inputs only."""
from collections import Counter
from copy import deepcopy
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
run = json.loads((HERE / 'checkpoint-D-current-run.json').read_text(encoding='utf-8-sig'))
session = HERE / 'checkpoint-D-sessions' / run['session']
config = yaml.safe_load((session / 'config_used.yaml').read_text(encoding='utf-8'))
rows = [json.loads(s) for s in (session / 'results.jsonl').read_text(encoding='utf-8').splitlines() if s]
assert config['state_filter']['timing']['retain_completed_hold'] is True
assert config['logging']['save_frames'] is False
exact = validate_session(session)
candidate = trace(rows, config)
baseline_config = deepcopy(config)
baseline_config['state_filter']['timing']['retain_completed_hold'] = False
baseline = trace(rows, baseline_config)


def restarts(details):
    armed_once, previous, result = False, None, []
    for r in details:
        armed_once |= r['armed']
        if armed_once and r['phase'] == 'OBSERVING' and previous != 'OBSERVING':
            result.append(r['frame'])
        previous = r['phase']
    return result


first = next((r['frame'] for r in candidate if r['active_armed']), None)
after = [r for r in candidate if first is not None and r['frame'] >= first]
player = HERE / 'checkpoint-candidate-build' / 'player-20261115-133636-593.log'
result = dict(session=run['session'], scope='actual candidate versus same recorded actions with option off',
    frames=len(rows), exact_actual_replay=exact,
    duration_ms=rows[-1]['filter_input']['timestamp_ms']-rows[0]['filter_input']['timestamp_ms'],
    first_completed_hold_frame=first, baseline=metrics(baseline), candidate=metrics(candidate),
    restarts=dict(baseline=restarts(baseline), candidate=restarts(candidate)),
    checkpoint_frames=[r['frame'] for r in candidate if r['hold_progress'] == 'checkpoint'],
    phases=dict(Counter(r['phase'] for r in candidate)),
    paused_reasons_after_hold=dict(Counter(r['reason'] for r in after if r['phase'] == 'PAUSED')),
    marker_ok=dict(Counter(str(r['filter_input']['marker_ok']) for r in rows)),
    player_cue_change_events=dict(Counter(re.findall(r'cue=(.*?) instruction=', player.read_text(encoding='utf-8', errors='replace')))),
    image_saving=False, user_feedback='pending')
manifest = json.loads((HERE / 'poll-protected-hashes-after.json').read_text(encoding='utf-8-sig'))
result['protected_unchanged'] = all(hashlib.sha256(Path(r['Path']).read_bytes()).hexdigest().upper() == r['Hash'].upper() for r in manifest)
assert result['protected_unchanged']
with (HERE / 'checkpoint-D-live-comparison.json').open('x', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
summary = {k:v for k,v in result.items() if k not in ('baseline', 'candidate', 'checkpoint_frames')}
summary['checkpoint_frame_count'] = len(result['checkpoint_frames'])
summary['transitions'] = {k:result[k]['transitions'] for k in ('baseline', 'candidate')}
print(json.dumps(summary, ensure_ascii=False, indent=2))
