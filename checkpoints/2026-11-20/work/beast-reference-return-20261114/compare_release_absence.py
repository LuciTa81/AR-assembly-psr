"""Offline only: compare confirmed-negative withdrawal against exact saved inputs."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

import yaml


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--session", type=Path, action="append", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    sys.path.insert(0, str(args.root))
    from server.realtime.guidance_timing import TimedEvidenceGate
    from server.realtime.realtime_replay import replay_filter_inputs, validate_session
    original = TimedEvidenceGate.evaluate

    def run(rows, config):
        samples = []

        def observe(gate, state_index, frame_id, timestamp_ms, marker_ok, features, **kw):
            result = original(gate, state_index, frame_id, timestamp_ms, marker_ok, features, **kw)
            if gate._release_absent_at is not None:
                samples.append(dict(frame=frame_id, state="S" + str(state_index),
                    observation_id=kw["observation_id"], observed_at=kw["observation_timestamp_ms"],
                    clear_at=gate._release_clear_at, absent_at=gate._release_absent_at,
                    advance=result.advance))
            return result

        with patch.object(TimedEvidenceGate, "evaluate", observe):
            predictions = replay_filter_inputs(rows, config["state_filter"],
                                                guidance_mode=config.get("guidance_mode", "auto"))
        return predictions, samples

    report = dict(scope="Fixed recorded input replay; no live test or physical withdrawal ground truth",
                  release_absence_ms=600, sessions=[])
    for session in args.session:
        rows = [json.loads(s) for s in (session / "results.jsonl").read_text(encoding="utf-8").splitlines() if s.strip()]
        config = yaml.safe_load((session / "config_used.yaml").read_text(encoding="utf-8"))
        result = dict(session=str(session), frames=len(rows))
        try:
            result["exact_recorded_replay"] = validate_session(session)
        except (ValueError, KeyError, TypeError) as exc:
            result["excluded"] = str(exc)
            report["sessions"].append(result)
            continue
        baseline_config = deepcopy(config)
        baseline_config["state_filter"]["timing"]["release_absence_ms"] = 0
        baseline, _ = run(rows, baseline_config)
        candidate_config = deepcopy(config)
        candidate_config["state_filter"]["timing"]["release_absence_ms"] = 600
        candidate, samples = run(rows, candidate_config)
        result["baseline_transitions"] = [r for r in baseline if r["transition_event"]]
        result["candidate_transitions"] = [r for r in candidate if r["transition_event"]]
        result["same_transition_frames"] = [
            (r["frame_id"], r["transition_event"]) for r in baseline if r["transition_event"]
        ] == [(r["frame_id"], r["transition_event"]) for r in candidate if r["transition_event"]]
        result["changed_frames"] = [a["frame_id"] for a, b in zip(baseline, candidate) if a != b]
        result["absence_branch_samples"] = samples
        result["absence_branch_unique_sources"] = len({r["observation_id"] for r in samples})
        result["absence_advances"] = [r for r in samples if r["advance"]]
        result["negative_counts"] = dict(Counter(
            "valid_full_negative" if item["evidence_valid"] and item["marker_ok"]
                and all(item["features"].get(k) == 0 for k in
                        ("driver_visible", "driver_count", "driver_count_raw", "handle_visible", "handle_count"))
            else "not_eligible_negative"
            for item in (r["filter_input"] for r in rows)))
        result["changed_transition_context"] = [
            dict(frame=before["frame_id"], baseline=before, candidate=after,
                 inputs=[r["filter_input"] for r in rows[max(0, i-12):i+2]])
            for i, (before, after) in enumerate(zip(baseline, candidate))
            if before["transition_event"] != after["transition_event"]]
        report["sessions"].append(result)
        print(json.dumps(dict(session=session.name, frames=len(rows),
            same_transition_frames=result["same_transition_frames"],
            changed_frames=len(result["changed_frames"]),
            negative_counts=result["negative_counts"],
            branch_unique_sources=result["absence_branch_unique_sources"],
            absence_advances=result["absence_advances"]), ensure_ascii=False))
    manifest = json.loads((Path(__file__).parent / "poll-protected-hashes-after.json").read_text(encoding="utf-8-sig"))
    report["protected"] = [dict(path=r["Path"], unchanged=
        hashlib.sha256(Path(r["Path"]).read_bytes()).hexdigest().upper() == r["Hash"].upper()) for r in manifest]
    assert all(r["unchanged"] for r in report["protected"])
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
