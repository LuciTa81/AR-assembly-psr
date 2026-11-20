"""Audit numeric full-flow logs without opening hardware or changing the baseline."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

import yaml
from run_neutral_d_server import ROOT
from compare_neutral_recovery import trace, metrics

sys.path.insert(0, str(ROOT))
from server.realtime.realtime_replay import validate_session

HERE = Path(__file__).parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('session', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    config = yaml.safe_load((args.session / 'config_used.yaml').read_text(encoding='utf-8'))
    rows = [json.loads(line) for line in (args.session / 'results.jsonl').read_text(encoding='utf-8').splitlines() if line]
    previous = yaml.safe_load((HERE / 'handle-linked-D-sessions' /
        'viture_aruco_rt_20261115_141146_52bb3e0131c5/config_used.yaml').read_text(encoding='utf-8'))
    assert config['state_filter']['timing'] == previous['state_filter']['timing']
    assert config['yolo'] == previous['yolo']
    assert config['guidance_mode'] == 'hybrid'
    assert config['logging']['save_frames'] is False
    assert not any(p.suffix.lower() in ('.jpg', '.jpeg', '.png', '.mp4', '.avi') for p in args.session.rglob('*'))
    exact = validate_session(args.session)
    assert exact['matched']
    details = trace(rows, config)
    summary = metrics(details)
    stages = {}
    for target in ('screw_a', 'screw_b', 'screw_c', 'screw_d'):
        points = [r for r in details if r['target'] == target]
        first = next((r['frame'] for r in points if r['phase'] == 'OBSERVED'), None)
        after = [r for r in points if first is not None and r['frame'] >= first]
        stages[target] = dict(
            first_completed_hold_frame=first,
            observing_reentries_after_completed_hold=[r['frame'] for prev, r in zip(after, after[1:])
                if r['phase'] == 'OBSERVING' and prev['phase'] != 'OBSERVING'],
            paused_reasons=dict(Counter(r['reason'] for r in points if r['phase'] == 'PAUSED')),
            paused_reasons_after_completed_hold=dict(Counter(r['reason'] for r in after if r['phase'] == 'PAUSED')),
        )
    manifest = json.loads((HERE / 'poll-protected-hashes-after.json').read_text(encoding='utf-8-sig'))
    protected = [dict(path=r['Path'], unchanged=hashlib.sha256(Path(r['Path']).read_bytes()).hexdigest().upper()==r['Hash'].upper()) for r in manifest]
    assert all(r['unchanged'] for r in protected)
    transitions = [r['transition_event'] for r in rows if r['transition_event'] and r['transition_event'] != 'operator_confirmation']
    result = dict(session=args.session.name, frames=len(rows),
        duration_ms=rows[-1]['filter_input']['timestamp_ms'] - rows[0]['filter_input']['timestamp_ms'],
        exact_replay=exact, same_verified_D_policy=True,
        automatic_transition_order=transitions,
        automatic_sequence_complete=transitions == ['S2->S3', 'S3->S4', 'S4->S5', 'S5->S6'],
        operator_confirmations=[dict(frame=r['frame_id'], state=r['state']) for r in rows
            if r['transition_event']=='operator_confirmation'],
        final_state=rows[-1]['state'], final_phase=rows[-1]['guidance']['phase'],
        operator_completed=rows[-1]['operator']['completed'],
        stages=stages, trace_metrics=summary,
        unlinked_candidate_removed_frames=sum(r['filter_input']['features'].get('driver_unlinked_candidates',0)>0 for r in rows),
        protected=protected, image_saving=False,
        note='Numeric-log audit only. Physical action timing and visual comfort require user confirmation.')
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({k:v for k,v in result.items() if k not in ('trace_metrics','protected')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
