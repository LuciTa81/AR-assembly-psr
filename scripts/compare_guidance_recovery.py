"""Replay numeric inputs only; hypothetical earlier transitions are not live performance."""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server.realtime.realtime_replay import replay_filter_inputs, validate_session


def compare(session_dir, grace_ms, completed_hold_ms=0, *, source_recovery_boundary=False):
    baseline = validate_session(session_dir)
    rows = [json.loads(line) for line in (session_dir/'results.jsonl').read_text(encoding='utf-8').splitlines()]
    config = yaml.safe_load((session_dir/'config_used.yaml').read_text(encoding='utf-8'))
    trial_config = deepcopy(config['state_filter'])
    trial_config.setdefault('timing', {})['resume_grace_ms'] = grace_ms
    trial_config['timing']['completed_hold_resume_ms'] = completed_hold_ms
    if source_recovery_boundary:
        trial_config['timing']['source_recovery_boundary'] = True
    trial = replay_filter_inputs(rows, trial_config, guidance_mode=config.get('guidance_mode','auto'))
    def events(sequence):
        return [dict(event=r['transition_event'], frame=r['frame_id'], timestamp_ms=source['filter_input']['timestamp_ms'])
                for source,r in zip(rows,sequence) if r['transition_event']]
    reference_events, trial_events = events(rows), events(trial)
    windows = {}
    for state in ('S2', 'S3', 'S4', 'S5'):
        pairs = [(a, b) for a, b in zip(rows, trial) if a['state'] == state]
        windows[state] = dict(frames=len(pairs),
            baseline_paused=sum(a['guidance']['phase'] == 'PAUSED' for a, b in pairs),
            trial_paused=sum(b['guidance']['phase'] == 'PAUSED' for a, b in pairs),
            different_state_frames=sum(a['state'] != b['state'] for a, b in pairs),
            baseline_pause_reasons=dict(Counter(a['guidance']['reason'] for a, b in pairs if a['guidance']['phase'] == 'PAUSED')),
            trial_pause_reasons=dict(Counter(b['guidance']['reason'] for a, b in pairs if b['guidance']['phase'] == 'PAUSED')))
    return dict(session=session_dir.name, baseline=baseline, resume_grace_ms=grace_ms,
        completed_hold_resume_ms=completed_hold_ms,
        source_recovery_boundary=source_recovery_boundary,
        recorded_state_windows=windows,
        same_transition_frames=reference_events == trial_events,
        same_state_all_frames=all(a['state'] == b['state'] for a,b in zip(rows,trial)),
        same_event_order=[r['event'] for r in reference_events] == [r['event'] for r in trial_events],
        baseline_events=reference_events, trial_events=trial_events,
        changed_phase_frames=sum(a['guidance']['phase'] != b['guidance']['phase'] for a,b in zip(rows,trial)),
        baseline_phases=dict(Counter(r['guidance']['phase'] for r in rows)),
        trial_phases=dict(Counter(r['guidance']['phase'] for r in trial)),
        final_state=trial[-1]['state'], final_phase=trial[-1]['guidance']['phase'],
        scope='counterfactual_same_inputs_not_live_accuracy_or_task_time')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', type=Path, action='append', required=True)
    parser.add_argument('--resume-ms', type=int, default=600)
    parser.add_argument('--completed-hold-resume-ms', type=int, default=0)
    parser.add_argument('--source-recovery-boundary', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    reports = [compare(path,args.resume_ms,args.completed_hold_resume_ms,
                       source_recovery_boundary=args.source_recovery_boundary) for path in args.session]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(reports,stream,indent=2,allow_nan=False)
    print(json.dumps(reports))
    return 0 if all(r['baseline']['matched'] and r['same_event_order'] for r in reports) else 2


if __name__ == '__main__':
    raise SystemExit(main())
