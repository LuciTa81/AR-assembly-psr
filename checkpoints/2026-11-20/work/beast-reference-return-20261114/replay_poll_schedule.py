"""Scheduling experiment, not measured Unity visibility. Uses saved capture times."""
import argparse
from bisect import bisect_right
import json
from pathlib import Path
import sys


def replay(rows, fps, rtt_ms, phase_ms, pumped):
    origin = rows[0]['received_at_monotonic']
    capture = [r['received_at_monotonic'] - origin for r in rows]
    published = [r['ingested_at_monotonic'] - origin for r in rows]
    assert published == sorted(published)
    next_poll = 0
    pending = None
    displayed = None
    latest_applied = -1
    requests = gaps = eligible = stale_visible = 0

    def apply(index, now):
        nonlocal displayed, latest_applied
        row = rows[index]
        # Current code rejects bad observations immediately and never renews a frame's age.
        if row['status'] != 'tracking' or now-capture[index] > .150:
            displayed = None
        elif index > latest_applied:
            displayed = index
        latest_applied = max(latest_applied, index)

    end = published[-1]
    tick = 0
    while (now := phase_ms / 1000 + tick / fps) <= end:
        tick += 1
        source = bisect_right(published, now) - 1
        if source < 0:
            continue
        if pumped and pending is not None and now >= pending[1]:
            apply(pending[0], now)
            pending = None
        if pending is None and now >= next_poll:
            pending = (source, now+rtt_ms/1000)
            requests += 1
            next_poll = now + (1/64 if pumped else 1/30)
        # Legacy coroutine resumes after Update but before OnGUI rendering.
        if not pumped and pending is not None and now >= pending[1]:
            apply(pending[0], now)
            pending = None
        visible = displayed is not None and now < capture[displayed] + .150
        if now > .5 and rows[source]['status'] == 'tracking' and now < capture[source]+.150:
            eligible += 1
            gaps += not visible
        if visible:
            stale_visible += now-capture[displayed] > .150+1e-9
    return dict(eligible_ticks=eligible, missing_fresh_ticks=gaps, requests=requests,
                expired_visible_ticks=stale_visible)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, args.root)
    from server.realtime.tracking_report import selected_rows
    base = Path(__file__).parent
    manifest = json.loads((base/'interruptions-20261114.json').read_text(encoding='utf-8'))
    experiments = []
    for session in manifest['sessions']:
        trace = Path.home()/'AppData/Local/ARAssembly/beast-mvp/display_correspondence'/session['session']/'pose-trace.jsonl'
        rows = list(selected_rows(trace, *session['frame_range'], pose_trace=True))
        for fps in [30, 60, 120]:
            for rtt in [2, 12, 20]:
                for phase in [0, 3, 7, 11]:
                    old = replay(rows, fps, rtt, phase, False)
                    new = replay(rows, fps, rtt, phase, True)
                    assert new['expired_visible_ticks'] == old['expired_visible_ticks'] == 0
                    experiments.append(dict(session=session['session'], fps=fps, rtt_ms=rtt, phase_ms=phase,
                                            legacy=old, candidate=new))
    result = dict(scope='Deterministic timing model using saved source frames; NOT actual display uptime',
        assumptions=['Fixed render rate and HTTP latency; response snapshots at request start.',
                     'Legacy coroutine completion is applied before rendering, after Update.',
                     'Bad source poses still hide; 150 ms capture expiry unchanged; no extrapolation.',
                     'CPU contention, GPU presentation and actual HTTP request phases are not recorded.'],
        experiments=experiments)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    for fps in [30, 60, 120]:
        subset = [e for e in experiments if e['fps']==fps]
        print(fps, 'old/new missing eligible ticks', sum(e['legacy']['missing_fresh_ticks'] for e in subset),
              sum(e['candidate']['missing_fresh_ticks'] for e in subset),
              'improved/equal/worse', sum(e['candidate']['missing_fresh_ticks']<e['legacy']['missing_fresh_ticks'] for e in subset),
              sum(e['candidate']['missing_fresh_ticks']==e['legacy']['missing_fresh_ticks'] for e in subset),
              sum(e['candidate']['missing_fresh_ticks']>e['legacy']['missing_fresh_ticks'] for e in subset))


if __name__ == '__main__':
    main()
