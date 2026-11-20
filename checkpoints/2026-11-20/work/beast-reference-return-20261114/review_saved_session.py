"""Read-only source/log review; no camera, model inference or runtime writes."""
import argparse
from collections import Counter
from copy import deepcopy
import csv
import hashlib
import json
from pathlib import Path
import statistics
import sys


def stats(values):
    values = sorted(values)
    if not values:
        return None
    return dict(n=len(values), mean=round(statistics.mean(values), 3),
                median=round(statistics.median(values), 3),
                p95=round(values[min(len(values)-1, int(len(values)*.95))], 3),
                max=round(values[-1], 3))


def replay(rows, config):
    from server.realtime.online_state_filter import OnlineStateFilter
    from server.realtime.assembly_session import AssemblySession
    filt = OnlineStateFilter.from_config(config)
    assembly = AssemblySession("review", filt)
    invalid, rechecks, losses, transitions = Counter(), [], [], []
    last_feedback = "none"
    for row in rows:
        item, control = row["filter_input"], row["assembly_input"]
        if control["confirmation_revision"] is not None:
            assembly.request("review", control["confirmation_revision"])
        gate = filt.timed_gate
        before = dict(boundary=gate.recovery_after_frame, suspended=gate._suspended,
                      armed=gate.armed, started=gate.started_at, state=filt.state_index)
        estimate = assembly.update(item, control["fresh_input"])
        if estimate.held_reason == "invalid_observation":
            source = row["yolo_reason"]
            if source == "ok":
                source = ("stage_entry_boundary" if control["confirmation_revision"] is not None
                          and before["state"] == 2 and item["observation_id"] <= item["frame_id"]
                          else "gate_recovery_boundary"
                          if 0 < item["observation_id"] <= before["boundary"]
                          else "gate_other_invalid")
            invalid[(estimate.target, source)] += 1
        feedback = estimate.guidance.hold_progress
        if feedback == "recheck" and last_feedback != "recheck":
            rechecks.append(dict(frame=row["frame_id"], target=estimate.target,
                reason=estimate.held_reason, before_armed=before["armed"],
                before_suspended=before["suspended"]))
        old = before["suspended"]
        if old is not None and gate._suspended is None and gate.started_at is None:
            losses.append(dict(frame=row["frame_id"], target=estimate.target,
                reason=estimate.held_reason, source_age_ms=item["timestamp_ms"]-old[0],
                saved_elapsed_ms=old[1], saved_armed=old[2]))
        if estimate.transition_event:
            transitions.append(dict(frame=row["frame_id"], time_ms=item["timestamp_ms"],
                                    transition=estimate.transition_event, state=estimate.state))
        last_feedback = feedback
    return dict(invalid_breakdown=[dict(target=k[0], reason=k[1], frames=v)
                                  for k, v in sorted(invalid.items())],
                recheck_events=rechecks, suspended_losses=losses,
                transitions=transitions, completed=assembly.metadata()["completed"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.root))
    import yaml
    from server.realtime.realtime_replay import validate_session
    from server.realtime.guidance_timing import GuidanceTiming, TimedEvidenceGate
    session = args.root / "outputs/realtime_sessions/viture_aruco_rt_20261114_214414_1b5738df444c"
    rows = [json.loads(line) for line in (session / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    config = yaml.safe_load((session / "config_used.yaml").read_text(encoding="utf-8"))
    latency = {int(r["frame_id"]): r for r in csv.DictReader((session / "latency.csv").open(encoding="utf-8-sig"))}
    result = dict(scope="fixed recorded inputs, not user response or measured work-time savings",
                  exact_replay=validate_session(session), stages={})
    for target in "ABCD":
        group = [r for r in rows if r["target"] == "screw_" + target.lower()]
        unique = {r["yolo_frame_id"]: r for r in group if r["yolo_frame_id"] > 0}
        ok_unique = {r["yolo_frame_id"]: r for r in group if r["yolo_reason"] == "ok"}
        times = [r["filter_input"]["observation_timestamp_ms"] for r in unique.values()]
        ok_times = [r["filter_input"]["observation_timestamp_ms"] for r in ok_unique.values()]
        result["stages"][target] = dict(frames=len(group), frame_range=[group[0]["frame_id"], group[-1]["frame_id"]],
            input_interval_ms=stats([r["presentation_diagnostics"]["source_interval_ms"] for r in group]),
            loop_processing_ms=stats([float(latency[r["frame_id"]]["total_latency_ms"]) for r in group]),
            pose=dict(Counter(r["presentation_diagnostics"]["reason_code"] for r in group)),
            yolo_reason=dict(Counter(r["yolo_reason"] for r in group)),
            held_reason=dict(Counter(r["held_reason"] or "none" for r in group)),
            unique_yolo_results=len(unique), unique_ok_results=len(ok_unique),
            result_source_interval_ms=stats([b-a for a,b in zip(times,times[1:])]),
            ok_source_interval_ms=stats([b-a for a,b in zip(ok_times,ok_times[1:])]),
            unique_yolo_processing_ms=stats([r["yolo_latency_ms"] for r in unique.values()]),
            latest_result_age_ms=stats([r["yolo_age_ms"] for r in group if r["yolo_age_ms"] >= 0]),
            screw_count=dict(Counter(str(int(r["screw_count"])) for r in group if r["yolo_reason"] == "ok")))
    result["variants"] = {}
    for name, grace, completed in [("baseline",600,2000),("partial_1000",1000,2000),
                                    ("armed_3000",600,3000),("both_max",1000,3000)]:
        candidate = deepcopy(config["state_filter"])
        candidate["timing"].update(resume_grace_ms=grace, completed_hold_resume_ms=completed)
        result["variants"][name] = replay(rows, candidate)
    result["selected_frames"] = []
    for row in rows:
        if row["frame_id"] in (396, 973, 1204, 1205, 1206, 1364):
            item = row["filter_input"]
            result["selected_frames"].append(dict(
                frame=row["frame_id"], state=row["state"], reason=row["held_reason"],
                timestamp_ms=item["timestamp_ms"], observation_id=item["observation_id"],
                observation_timestamp_ms=item["observation_timestamp_ms"],
                marker_ok=item["marker_ok"], yolo_reason=row["yolo_reason"],
                guidance=row["guidance"],
                scores={name:item["features"].get("tool_score_"+name) for name in "abcd"},
                distances={name:item["features"].get("tool_dist_"+name) for name in "abcd"}))
    result["rejected_configurations"] = {}
    for name, options in [("partial_2000",dict(resume_grace_ms=2000)),
                          ("armed_999999",dict(completed_hold_resume_ms=999999))]:
        try:
            GuidanceTiming(**options)
        except ValueError as exc:
            result["rejected_configurations"][name] = str(exc)
        else:
            raise AssertionError("Expected configured bounds")
    # Controlled source-time sequences isolate restoration and next-target behavior.
    result["synthetic_recovery"] = {}
    for scenario in ("near_current", "near_next", "neutral_band", "clear_all"):
        gate = TimedEvidenceGate(GuidanceTiming(resume_grace_ms=600, completed_hold_resume_ms=2000,
                                               source_recovery_boundary=True))
        def step(frame, timestamp, current=.95, other=.01, marker=True):
            features = dict(driver_visible=1, driver_count=1, tool_tip_source=1,
                            tool_tip_x=100., tool_tip_y=100., yolo_tool_score_threshold=.3,
                            yolo_target_dominance_ratio=.75, screw_min_confidence=.55)
            for name, score in zip("abcd", [current,other,.01,.01]):
                features.update({f"tool_score_{name}": score, f"tip_screw_score_{name}": score,
                                 f"tool_dist_{name}": 1. if score > .3 else 30.})
            d = gate.evaluate(2,frame,timestamp,marker,features,observation_id=frame,
                              observation_timestamp_ms=timestamp,evidence_valid=True,
                              roi_valid=False,min_confidence=.55)
            return dict(phase=d.phase, advance=d.advance, armed=gate.armed,
                        retained=gate._suspended is not None)
        for i in range(5):
            step(i+1,1000+i*200)
        assert gate.armed
        step(6,1900,marker=False)
        current, other = {"near_current":(.95,.01),"near_next":(.01,.95),
                          "neutral_band":(.22,.01),"clear_all":(.01,.01)}[scenario]
        trace = [step(7+i,2000+i*200,current,other) for i in range(3)]
        result["synthetic_recovery"][scenario] = trace
    manifest = json.loads((Path(__file__).parent / "poll-protected-hashes-after.json").read_text(encoding="utf-8-sig"))
    result["protected"] = [dict(path=p["Path"], unchanged=hashlib.sha256(Path(p["Path"]).read_bytes()).hexdigest().upper()==p["Hash"].upper()) for p in manifest]
    assert all(item["unchanged"] for item in result["protected"])
    with args.output.open("x",encoding="utf-8") as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k not in ("protected",)},ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
