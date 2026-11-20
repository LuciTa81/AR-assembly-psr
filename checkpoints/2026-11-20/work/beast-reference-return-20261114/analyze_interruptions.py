"""Read-only analysis of the eight bounded optical trials; no device access."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import statistics
import sys


def stats(values):
    values = sorted(values)
    if not values:
        return None
    return dict(n=len(values), median=round(statistics.median(values), 3),
                p95=round(values[min(len(values)-1, int(len(values)*.95))], 3),
                max=round(values[-1], 3))


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.root))
    from server.realtime.tracking_report import selected_rows
    from server.realtime.display_observation_server import pose_reason_code

    base = Path(__file__).parent
    files = ['joint-AC-optical-trial-20261114.json', 'joint-BD-optical-trial-20261114.json']
    files += [f'joint-{target}-side-optical-trial-20261114.json' for target in 'ACDB']
    result = dict(scope='Saved server frames and 1 Hz Unity snapshots, NOT display uptime',
                  sessions=[], warnings=['No synchronized per-render-frame trace; queue and visibility effects cannot be measured directly.'])
    total_reasons, total_snapshots, total_combos = Counter(), Counter(), Counter()
    for name in files:
        report = json.loads((base / name).read_text(encoding='utf-8-sig'))
        for session in report['sessions']:
            trace = Path.home() / 'AppData/Local/ARAssembly/beast-mvp/display_correspondence' / session['session_id'] / 'pose-trace.jsonl'
            log = args.root / session['unity_log']
            assert digest(trace) == session['trace_sha256']
            assert digest(log) == session['unity_log_sha256']
            rows = list(selected_rows(trace, *session['logged_frame_range'], pose_trace=True))
            reasons, combos = Counter(), Counter()
            run_lengths, run_ms, current = [], [], []
            for row in rows:
                reason = pose_reason_code(row['analysis_status'], row.get('analysis_reason') or '')
                reasons[reason] += 1
                if reason != 'tracking':
                    combos[(reason, tuple(row['analysis_marker_ids']))] += 1
                    current.append(row)
                elif current:
                    run_lengths.append(len(current))
                    run_ms.append((row['received_at_monotonic'] - current[0]['received_at_monotonic']) * 1000)
                    current = []
            # Right-censored final runs are not recovery durations.
            snapshots = []
            for line in log.read_text(encoding='utf-8-sig', errors='replace').splitlines():
                if '[CANDIDATE PROBE] visible=' not in line:
                    continue
                status = re.search(r'pose=(.*?) (?:[abcd]_z_mm=\S+ )?corners=', line).group(1)
                fields = dict(re.findall(r'(pose_frame|response|server_age_ms|rtt_ms|age_now_ms|network_ms)=(\S+)', line))
                snapshots.append(dict(status=status, **{k: (v if k == 'response' else float(v)) for k, v in fields.items()}))
            snap_counts = Counter(s['status'] for s in snapshots)
            intervals = [(b['received_at_monotonic'] - a['received_at_monotonic']) * 1000 for a, b in zip(rows, rows[1:])]
            processing = [(r['ingested_at_monotonic'] - r['received_at_monotonic']) * 1000 for r in rows]
            stale_tracking = [s for s in snapshots if s['status'] == 'STALE' and s['response'] == 'tracking']
            combo_list = [dict(reason=k[0], ids=list(k[1]), frames=v) for k, v in combos.most_common()]
            result['sessions'].append(dict(session=session['session_id'], report=name, target=session['target_id'],
                trace_sha256=digest(trace), log_sha256=digest(log), frame_range=session['logged_frame_range'],
                frames=len(rows), reasons=dict(reasons), rejected_marker_combinations=combo_list,
                input_interval_ms=stats(intervals), receipt_to_ingestion_ms=stats(processing),
                rejection_run_frames=stats(run_lengths), rejection_to_next_tracking_ms=stats(run_ms),
                trailing_rejection_frames=len(current), snapshot_counts=dict(snap_counts),
                stale_snapshots_with_tracking_response=len(stale_tracking),
                response_rtt_ms=stats([s['rtt_ms'] for s in snapshots]),
                network_ms=stats([s['network_ms'] for s in snapshots]),
                snapshot_age_ms=stats([s['age_now_ms'] for s in snapshots]),
                stale_tracking_details=stale_tracking))
            total_reasons.update(reasons)
            total_snapshots.update(snap_counts)
            total_combos.update(combos)
    result['aggregate'] = dict(reasons=dict(total_reasons), snapshots=dict(total_snapshots),
        rejected_marker_combinations=[dict(reason=k[0], ids=list(k[1]), frames=v) for k, v in total_combos.most_common()])
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps(result['aggregate'], ensure_ascii=False, indent=2))
    for session in result['sessions']:
        print(session['target'], session['report'], session['input_interval_ms'], session['receipt_to_ingestion_ms'],
              session['response_rtt_ms'], session['network_ms'], 'stale/tracking', session['stale_snapshots_with_tracking_response'])


if __name__ == '__main__':
    main()
