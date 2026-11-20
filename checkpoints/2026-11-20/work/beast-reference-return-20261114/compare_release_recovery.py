"""Replay saved numeric inputs; never open a camera or change active configuration."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import yaml

from run_neutral_d_server import ROOT
from compare_neutral_recovery import trace, metrics
from server.realtime.realtime_replay import validate_session


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    base = Path(__file__).parent
    report = dict(scope='Fixed numeric log replay, not live completion-time improvement',
                  release_resume_ms=2000, sessions=[])
    for session in sorted((base / 'handle-linked-flow-sessions').iterdir()):
        if not (session / 'results.jsonl').is_file():
            continue
        config = yaml.safe_load((session / 'config_used.yaml').read_text(encoding='utf-8'))
        rows = [json.loads(s) for s in (session / 'results.jsonl').read_text(encoding='utf-8').splitlines()]
        baseline = trace(rows, config)
        candidate_config = deepcopy(config)
        candidate_config['state_filter']['timing']['release_resume_ms'] = 2000
        candidate = trace(rows, candidate_config)
        before, after = metrics(baseline)['transitions'], metrics(candidate)['transitions']
        result = dict(session=session.name, exact_default_replay=validate_session(session),
                      baseline=before, candidate=after,
                      same_transition_order=[e['event'] for e in before] == [e['event'] for e in after])
        assert result['same_transition_order'], result
        lookup = {r['frame_id']: r for r in rows}
        result['changed_transition_context'] = []
        for b, c in zip(before, after):
            if b == c:
                continue
            assert c['event'] != 'operator_confirmation'
            index = next(i for i, r in enumerate(rows) if r['frame_id'] == c['frame'])
            context = []
            for row, state in zip(rows[max(0, index-20):index+3], candidate[max(0, index-20):index+3]):
                item = row['filter_input']
                f = item['features']
                context.append(dict(frame=item['frame_id'], source=item['observation_id'],
                    time=item['timestamp_ms'], source_time=item['observation_timestamp_ms'],
                    marker_ok=item['marker_ok'], evidence_valid=item['evidence_valid'],
                    driver_count=f['driver_count'], handle_count=f.get('handle_count'),
                    scores={n: max(f['tool_score_'+n], f['tip_screw_score_'+n]) for n in 'abcd'},
                    phase=state['phase'], reason=state['reason'], transition=state['transition']))
            fresh = lookup[c['frame']]['filter_input']
            assert fresh['marker_ok'] and fresh['evidence_valid']
            assert fresh['features']['driver_visible'] == fresh['features']['driver_count'] == 1
            assert all(max(fresh['features']['tool_score_'+n], fresh['features']['tip_screw_score_'+n]) <= .15 for n in 'abcd')
            assert 0 <= fresh['timestamp_ms'] - fresh['observation_timestamp_ms'] <= 350
            result['changed_transition_context'].append(dict(baseline_frame=b['frame'],
                candidate_frame=c['frame'], event=c['event'],
                recorded_input_shift_ms=lookup[b['frame']]['filter_input']['timestamp_ms'] - fresh['timestamp_ms'],
                context=context))
        for name, details in [('baseline', baseline), ('candidate', candidate)]:
            start = next((r['frame'] for r in details if r['state'] == 'S2'), None)
            end = next((r['frame'] for r in details if r['transition'] == 'S2->S3'), None)
            result[name+'_a_ms'] = (lookup[end]['filter_input']['timestamp_ms'] - lookup[start]['filter_input']['timestamp_ms']
                                   if start and end else None)
        report['sessions'].append(result)
        print(json.dumps({k: result[k] for k in ('session', 'baseline_a_ms', 'candidate_a_ms', 'same_transition_order')}))
    manifest = json.loads((base / 'poll-protected-hashes-after.json').read_text(encoding='utf-8-sig'))
    report['protected'] = [dict(path=r['Path'], unchanged=hashlib.sha256(Path(r['Path']).read_bytes()).hexdigest().upper()==r['Hash']) for r in manifest]
    assert all(r['unchanged'] for r in report['protected'])
    report['implementation_sha256'] = hashlib.sha256((ROOT/'server/realtime/guidance_timing.py').read_bytes()).hexdigest()
    with args.output.open('x', encoding='utf-8') as out:
        json.dump(report, out, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
