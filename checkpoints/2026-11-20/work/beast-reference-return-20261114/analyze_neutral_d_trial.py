"""Compare an opt-in D run against the same numeric inputs with the option off."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import yaml
from compare_neutral_recovery import metrics, trace

ROOT = Path(r"C:/Users/fresh/OneDrive/Desktop/홍익대/4학년/2학기/vision/01_SUBMIT_KEEP/AR-assembly-psr_github_main_20260604/.worktrees/viture-beast-overlay-mvp")
HERE = Path(__file__).parent
sys.path.insert(0, str(ROOT))
from server.realtime.realtime_replay import validate_session

run = json.loads((HERE / 'neutral-D-current-run.json').read_text(encoding='utf-8-sig'))
session = HERE / 'neutral-D-sessions' / run['session']
config = yaml.safe_load((session / 'config_used.yaml').read_text(encoding='utf-8'))
rows = [json.loads(s) for s in (session / 'results.jsonl').read_text(encoding='utf-8').splitlines() if s.strip()]
assert config['state_filter']['initial_state'] == 'S5'
assert config['state_filter']['timing']['retain_neutral_recovery'] is True
assert config['logging']['save_frames'] is False
exact = validate_session(session)
candidate = trace(rows, config)
baseline_config = deepcopy(config)
baseline_config['state_filter']['timing']['retain_neutral_recovery'] = False
baseline = trace(rows, baseline_config)
selected = []
for raw, before, after in zip(rows, baseline, candidate):
    item, features = raw['filter_input'], raw['filter_input']['features']
    score = max(features.get('tool_score_d', 0), features.get('tip_screw_score_d', 0))
    if (after['phase'] == 'PAUSED' and after['hold_progress'] == 'retained'
            and after['reason'] == 'tool_position_unknown'
            and item['marker_ok'] and item['evidence_valid']
            and features.get('driver_visible') == 1 and features.get('driver_count') == 1
            and features.get('tool_tip_source') in (1, 2)
            and .15 < score < features.get('yolo_tool_score_threshold_d', features.get('yolo_tool_score_threshold', .35))):
        selected.append(dict(frame=item['frame_id'], observation=item['observation_id'],
            score=score, remaining_ms=after['hold_remaining_ms'],
            baseline=before, candidate=after))
result = dict(session=run['session'], scope='actual numeric replay versus fixed-action counterfactual',
    exact_actual_replay=exact, frames=len(rows),
    duration_ms=rows[-1]['filter_input']['timestamp_ms']-rows[0]['filter_input']['timestamp_ms'],
    baseline_off=metrics(baseline), candidate_on=metrics(candidate),
    neutral_recovery_frames=selected,
    marker_ok=dict(Counter(str(r['filter_input']['marker_ok']) for r in rows)),
    state_counts=dict(Counter(r['state'] for r in rows)),
    held_reasons=dict(Counter(r.get('held_reason') or 'none' for r in rows)),
    user_feedback='pending')
result['same_transition_frames'] = result['baseline_off']['transitions'] == result['candidate_on']['transitions']
manifest = json.loads((HERE / 'poll-protected-hashes-after.json').read_text(encoding='utf-8-sig'))
result['protected_unchanged'] = all(hashlib.sha256(Path(r['Path']).read_bytes()).hexdigest().upper() == r['Hash'].upper() for r in manifest)
assert result['protected_unchanged']
with (HERE / 'neutral-D-live-comparison.json').open('x', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
summary = {k:v for k,v in result.items() if k not in ('baseline_off','candidate_on','neutral_recovery_frames')}
summary['neutral_recovery'] = [{k:r[k] for k in ('frame','observation','score','remaining_ms')} for r in selected]
for variant in ('baseline_off','candidate_on'):
    data = result[variant]['stages']['screw_d']
    summary[variant] = dict(recheck_entries=data['recheck_entries'], armed_losses=data['armed_loss_frames'],
        recheck_frames_after_first_armed=len(data['recheck_frames_after_first_armed']),
        transitions=result[variant]['transitions'])
print(json.dumps(summary, ensure_ascii=False, indent=2))
