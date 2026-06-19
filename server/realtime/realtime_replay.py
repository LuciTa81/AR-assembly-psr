from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Inspect a saved realtime harness session.")
    parser.add_argument("--session", required=True)
    parser.add_argument("--tail", type=int, default=10)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    session_dir = Path(args.session)
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

