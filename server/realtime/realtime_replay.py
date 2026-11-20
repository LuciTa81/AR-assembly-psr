from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from server.realtime.online_state_filter import OnlineStateFilter


def replay_filter_inputs(rows: Iterable[dict], filter_config: dict, *, guidance_mode='auto') -> list[dict]:
    state_filter = OnlineStateFilter.from_config(filter_config)
    assembly = None
    if guidance_mode == 'hybrid':
        from .assembly_session import AssemblySession
        assembly = AssemblySession('replay', state_filter)
    predictions = []
    required = {"frame_id", "marker_ok", "features", "observation_id", "evidence_valid"}
    if state_filter.timed_gate is not None:
        required |= {"timestamp_ms", "observation_timestamp_ms", "roi_valid"}
    for row in rows:
        item = row.get("filter_input")
        if not isinstance(item, dict) or not required.issubset(item):
            raise ValueError("Missing exact filter_input; legacy logs support inspection only")
        inputs = {k: item[k] for k in required}
        if assembly is not None:
            control = row.get('assembly_input')
            if (not isinstance(control, dict) or set(control) != {'confirmation_revision', 'fresh_input'}
                    or type(control['fresh_input']) is not bool):
                raise ValueError('Missing exact assembly confirmation input')
            if control['confirmation_revision'] is not None:
                assembly.request('replay', control['confirmation_revision'])
            estimate = assembly.update(inputs, control['fresh_input'])
        else:
            estimate = state_filter.update(**inputs)
        prediction = {"frame_id": item["frame_id"], "state": estimate.state,
                      "transition_event": estimate.transition_event}
        if estimate.guidance is not None:
            prediction.update(target=estimate.target, next_action=estimate.next_action,
                              held_reason=estimate.held_reason, guidance=asdict(estimate.guidance))
        predictions.append(prediction)
    return predictions


def validate_session(session_dir: Path) -> dict:
    import yaml
    rows = [json.loads(line) for line in (session_dir / "results.jsonl").read_text(
        encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        raise ValueError("No recorded filter inputs")
    config = yaml.safe_load((session_dir / "config_used.yaml").read_text(encoding="utf-8"))
    predictions = replay_filter_inputs(rows, config.get("state_filter", {}),
                                      guidance_mode=config.get('guidance_mode', 'auto'))
    for index, (row, prediction) in enumerate(zip(rows, predictions)):
        recorded = row.get('guidance')
        if isinstance(recorded, dict) and not {'hold_progress', 'hold_remaining_ms'} & recorded.keys():
            # Old sessions predate read-only HOLD metadata; all original fields still match exactly.
            prediction['guidance'] = {k: v for k, v in prediction['guidance'].items()
                                      if k not in ('hold_progress', 'hold_remaining_ms')}
        if any(row.get(key) != value for key, value in prediction.items()):
            raise ValueError(f"Filter replay mismatch at row {index + 1}: {prediction}")
    report = {"matched": True, "frames": len(rows), "scope": "exact_filter_inputs_only"}
    print(json.dumps(report))
    return report


def parse_args():
    parser = argparse.ArgumentParser(description="Inspect a saved realtime harness session.")
    parser.add_argument("--session", required=True)
    parser.add_argument("--tail", type=int, default=10)
    parser.add_argument("--validate-filter", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    session_dir = Path(args.session)
    if args.validate_filter:
        try:
            validate_session(session_dir)
            return 0
        except (OSError, ValueError, TypeError, KeyError) as exc:
            print(f"[ERROR] {exc}", file=sys.stderr)
            return 2
    results = session_dir / "results.jsonl"
    events = session_dir / "events.csv"
    if not results.exists():
        raise FileNotFoundError(results)
    rows = []
    with results.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    print(f"[SESSION] {session_dir}")
    print(f"[RESULT ROWS] {len(rows)}")
    if rows:
        print("[LAST RESULTS]")
        for row in rows[-args.tail:]:
            print(json.dumps(row, ensure_ascii=False))
    if events.exists():
        print(f"[EVENTS] {events}")
        print(events.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

