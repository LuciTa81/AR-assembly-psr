"""Offline HOLD checkpoint audit; no hardware, network, or active configuration writes."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--session', type=Path, action='append', required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    sys.path.insert(0, str(args.root))
    import yaml
    from compare_neutral_recovery import trace, metrics
    from server.realtime.guidance_timing import TimedEvidenceGate
    from server.realtime.realtime_replay import validate_session

    report = dict(scope='Recorded numeric inputs; not a live success rate or time saving', sessions=[])
    original = TimedEvidenceGate.evaluate

    def run(rows, config):
        seen = {}
        def observed(gate, *a, **kw):
            before = gate.completed_hold
            active = gate.armed
            result = original(gate, *a, **kw)
            seen.setdefault(a[1], dict(frame=a[1], checkpoint=gate.completed_hold,
                checkpoint_lost=before and not gate.completed_hold,
                reauthorized=before and not active and gate.armed,
                source=kw['observation_id'], release_at=gate.release_at))
            return result
        TimedEvidenceGate.evaluate = observed
        try:
            details = trace(rows, config)
        finally:
            TimedEvidenceGate.evaluate = original
        for detail in details:
            extra = seen.get(detail['frame'], dict(checkpoint=False, checkpoint_lost=False, reauthorized=False))
            detail.update(extra)
            if detail['transition']:
                detail['checkpoint'] = False
        return details

    for session in args.session:
        exact = validate_session(session)
        rows = [json.loads(s) for s in (session / 'results.jsonl').read_text(encoding='utf8').splitlines() if s]
        cfg = yaml.safe_load((session / 'config_used.yaml').read_text(encoding='utf8'))
        candidate = deepcopy(cfg)
        candidate['state_filter']['timing']['retain_completed_hold'] = True
        baseline = run(rows, cfg)
        changed = run(rows, candidate)
        result = dict(session=session.name, exact_default_replay=exact,
                      baseline=metrics(baseline), candidate=metrics(changed))
        result['checkpoint_losses'] = [r['frame'] for r in changed if r['checkpoint_lost']]
        result['reauthorized_frames'] = [r['frame'] for r in changed if r['reauthorized']]
        result['completed_hold_restarts'] = {}
        for name, details in [('baseline', baseline), ('candidate', changed)]:
            seen_states, restarts = set(), []
            previous = None
            for r in details:
                if r['armed'] or r['checkpoint']:
                    seen_states.add(r['state'])
                if r['phase'] == 'OBSERVING' and r['state'] in seen_states and previous != (r['state'], 'OBSERVING'):
                    restarts.append(r['frame'])
                previous = (r['state'], r['phase'])
            result['completed_hold_restarts'][name] = restarts
        result['transition_audit'] = []
        for i, (old, new) in enumerate(zip(baseline, changed)):
            if old['transition'] != new['transition']:
                result['transition_audit'].append([
                    dict(input=rows[j]['filter_input'], baseline=baseline[j], candidate=changed[j])
                    for j in range(max(0, i-8), min(len(rows), i+2))])
        result['checkpoint_loss_context'] = [dict(input=rows[i]['filter_input'], candidate=r)
                                            for i,r in enumerate(changed) if r['checkpoint_lost']]
        result['default_loss_checkpoints'] = [dict(frame=a['frame'], checkpoint=b['checkpoint'],
            hold_progress=b['hold_progress'], phase=b['phase'])
            for a,b in zip(baseline,changed) if a['lost']]
        report['sessions'].append(result)
        print(json.dumps(dict(session=session.name, frames=len(rows),
            restarts=result['completed_hold_restarts'], checkpoint_losses=result['checkpoint_losses'],
            transitions={n:result[n]['transitions'] for n in ('baseline','candidate')})))

    manifest = json.loads((Path(__file__).parent / 'poll-protected-hashes-after.json').read_text(encoding='utf-8-sig'))
    report['protected'] = [dict(path=r['Path'], unchanged=hashlib.sha256(Path(r['Path']).read_bytes()).hexdigest().upper()==r['Hash'].upper()) for r in manifest]
    assert all(r['unchanged'] for r in report['protected'])
    with args.output.open('x', encoding='utf8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
