"""Replay recorded numeric inputs only; never open hardware or change active config."""
import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys


def trace(rows, config):
    from server.realtime.assembly_session import AssemblySession
    from server.realtime.online_state_filter import OnlineStateFilter
    from server.realtime.realtime_replay import replay_filter_inputs
    filt = OnlineStateFilter.from_config(config['state_filter'])
    assembly = AssemblySession('replay', filt) if config['guidance_mode'] == 'hybrid' else None
    predictions, details = [], []
    for row in rows:
        item = row['filter_input']
        gate = filt.timed_gate
        before_armed = gate.armed or bool(gate._suspended and gate._suspended[2])
        before_state = filt.state_index
        if assembly:
            control = row['assembly_input']
            if control['confirmation_revision'] is not None:
                assembly.request('replay', control['confirmation_revision'])
            estimate = assembly.update(item, control['fresh_input'])
        else:
            estimate = filt.update(**item)
        prediction = dict(frame_id=item['frame_id'], state=estimate.state,
                          transition_event=estimate.transition_event,
                          target=estimate.target, next_action=estimate.next_action,
                          held_reason=estimate.held_reason, guidance=asdict(estimate.guidance))
        predictions.append(prediction)
        armed = gate.armed or bool(gate._suspended and gate._suspended[2])
        details.append(dict(frame=item['frame_id'], state=estimate.state,
            target=estimate.target, armed=armed, active_armed=gate.armed,
            suspended=gate._suspended, started_at=gate.started_at,
            release_started_at=gate.release_at,
            acquired=armed and not before_armed,
            lost=before_armed and not armed and before_state == filt.state_index,
            phase=estimate.guidance.phase, hold_progress=estimate.guidance.hold_progress,
            hold_remaining_ms=estimate.guidance.hold_remaining_ms,
            reason=estimate.held_reason, transition=estimate.transition_event))
    assert predictions == replay_filter_inputs(rows, config['state_filter'],
                                               guidance_mode=config['guidance_mode'])
    return details


def metrics(details):
    stages = {}
    for target in ('screw_a', 'screw_b', 'screw_c', 'screw_d'):
        points = [r for r in details if r['target'] == target]
        armed_once, previous, rechecks, after_armed = False, None, [], []
        for row in points:
            armed_once |= row['armed']
            if row['hold_progress'] == 'recheck':
                if previous != 'recheck':
                    rechecks.append(row['frame'])
                if armed_once:
                    after_armed.append(row['frame'])
            previous = row['hold_progress']
        stages[target] = dict(frames=len(points), recheck_entries=rechecks,
            recheck_frames_after_first_armed=after_armed,
            armed_loss_frames=[r['frame'] for r in points if r['lost']],
            last_armed_acquired_frame=next((r['frame'] for r in reversed(points) if r['acquired']), None),
            phases=dict(Counter(r['phase'] for r in points)))
    return dict(stages=stages, transitions=[dict(frame=r['frame'], event=r['transition'])
                                           for r in details if r['transition']])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--session', action='append', required=True)
    args = p.parse_args()
    sys.path.insert(0, str(args.root))
    import yaml
    from server.realtime.realtime_replay import validate_session
    report = dict(scope='Fixed recorded actions, not live validation or measured time savings', sessions=[])
    for name in args.session:
        session = args.root / 'outputs/realtime_sessions' / name
        rows = [json.loads(s) for s in (session / 'results.jsonl').read_text(encoding='utf-8').splitlines() if s.strip()]
        config = yaml.safe_load((session / 'config_used.yaml').read_text(encoding='utf-8'))
        result = dict(session=name)
        try:
            result['exact_default_replay'] = validate_session(session)
        except (ValueError, KeyError, TypeError) as exc:
            result['excluded'] = str(exc)
            report['sessions'].append(result)
            continue
        baseline = trace(rows, config)
        candidate_config = deepcopy(config)
        candidate_config['state_filter']['timing']['retain_neutral_recovery'] = True
        candidate = trace(rows, candidate_config)
        result.update(baseline=metrics(baseline), candidate=metrics(candidate))
        result['same_transition_order'] = ([r['event'] for r in result['baseline']['transitions']]
                                           == [r['event'] for r in result['candidate']['transitions']])
        result['same_transition_frames'] = result['baseline']['transitions'] == result['candidate']['transitions']
        changed = [i for i, (a, b) in enumerate(zip(baseline, candidate)) if a != b]
        result['changed_frames'] = [rows[i]['frame_id'] for i in changed]
        result['changed_transition_context'] = []
        for i, (a, b) in enumerate(zip(baseline, candidate)):
            if a['transition'] != b['transition']:
                context = []
                for j in range(max(0, i-4), min(len(rows), i+2)):
                    context.append(dict(input=rows[j]['filter_input'], baseline=baseline[j], candidate=candidate[j]))
                result['changed_transition_context'].append(context)
        if '214414' in name:
            result['selected_frames'] = [dict(input=row['filter_input'], baseline=a, candidate=b)
                for row, a, b in zip(rows, baseline, candidate)
                if row['frame_id'] in (973,1204,1205,1206,1363,1364,1365,1366,1367,1372)]
        report['sessions'].append(result)
        print(json.dumps(dict(session=name, changed_frames=len(changed),
            same_transition_frames=result['same_transition_frames'],
            rechecks={variant:{target:len(data['recheck_entries']) for target,data in result[variant]['stages'].items()}
                      for variant in ('baseline','candidate')})))
    manifest = json.loads((Path(__file__).parent / 'poll-protected-hashes-after.json').read_text(encoding='utf-8-sig'))
    report['protected'] = [dict(path=r['Path'], unchanged=hashlib.sha256(Path(r['Path']).read_bytes()).hexdigest().upper()==r['Hash'].upper()) for r in manifest]
    assert all(r['unchanged'] for r in report['protected'])
    with args.output.open('x', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
