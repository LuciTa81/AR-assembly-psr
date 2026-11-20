"""Offline tracking evidence summary and optional numeric pose replay; no camera."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import statistics

from .display_observation_server import pose_reason_code
from .workspace_projection import estimate_pose, project_targets


def selected_rows(path, first_frame=None, last_frame=None, *, pose_trace=False):
    if ((first_frame is not None and first_frame < 1)
            or (last_frame is not None and last_frame < (first_frame or 1))):
        raise ValueError("Invalid frame range")
    previous = 0
    trace_binding = None
    with Path(path).open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError as exc:
                raise ValueError(f"Invalid JSON at line {line_number}") from exc
            frame = row.get("frame_id") if isinstance(row, dict) else None
            if type(frame) is not int or frame <= previous:
                raise ValueError(f"Non-increasing or invalid frame at line {line_number}")
            previous = frame
            if pose_trace:
                if row.get("schema_version") != "beast_display_pose_trace_v1":
                    raise ValueError(f"Unsupported pose trace at line {line_number}")
                binding = tuple(row.get(key) for key in (
                    "session_id", "camera_profile_id", "workspace_profile_id",
                    "camera_profile_sha256", "workspace_profile_sha256"))
                if any(not isinstance(value, str) or not value.strip() for value in binding):
                    raise ValueError(f"Missing pose trace provenance at line {line_number}")
                if trace_binding is not None and binding != trace_binding:
                    raise ValueError(f"Mixed pose trace provenance at line {line_number}")
                trace_binding = binding
                # Source analysis can be good while the served observation is stale.
                # Do not substitute observation marker_ids, which can be absent then.
                row["presentation_diagnostics"] = dict(
                    frame_id=frame, analysis_status=row.get("analysis_status"),
                    analysis_reason=row.get("analysis_reason"),
                    marker_ids=row.get("analysis_marker_ids"),
                    detected_corners_px=row.get("detected_corners_px"),
                    image_size=row.get("image_size"), publish_age_ms=row.get("age_ms"),
                    camera_profile_sha256=row["camera_profile_sha256"],
                    workspace_profile_sha256=row["workspace_profile_sha256"])
            if (first_frame is not None and frame < first_frame) or (last_frame is not None and frame > last_frame):
                continue
            d = row.get("presentation_diagnostics")
            if d is not None and (not isinstance(d, dict) or d.get("frame_id") != frame):
                raise ValueError(f"Diagnostic frame mismatch at line {line_number}")
            yield row


def numeric_evidence(d):
    ids, corners = d.get("marker_ids"), d.get("detected_corners_px")
    return (isinstance(ids, list) and isinstance(corners, dict) and bool(corners)
            and all(type(key) is int for key in ids) and len(set(ids)) == len(ids)
            and set(corners) == {str(key) for key in ids})


def replay_pose(d, camera, workspace, camera_hash, workspace_hash):
    if (d.get("camera_profile_sha256") != camera_hash
            or d.get("workspace_profile_sha256") != workspace_hash):
        raise ValueError("Numeric evidence profile binding mismatch")
    if not numeric_evidence(d):
        return {"reason_code": "pose_unavailable", "reason": "Incomplete or duplicate numeric marker evidence"}
    try:
        detections = {int(key): value for key, value in d["detected_corners_px"].items()}
        if any(key not in workspace.markers for key in detections):
            raise ValueError("Unregistered numeric markers")
        pose = estimate_pose(detections, workspace, camera, d.get("image_size", ()))
        return {"reason_code": "tracking", "rms_px": pose.rms_px,
                "camera_position_mm": pose.camera_position_mm.tolist(),
                "targets": project_targets(pose, workspace, camera)}
    except ValueError as exc:
        return {"reason_code": pose_reason_code("pose_rejected", str(exc)), "reason": str(exc)}


def summarize(path, first_frame=None, last_frame=None, *, profiles=None, pose_trace=False):
    rows = poses = missing_ids = numeric = 0
    first = last = None
    states, reasons, raw_reasons, combinations, replay_counts = Counter(), Counter(), Counter(), Counter(), Counter()
    observations, marker_counts, marker_presence = Counter(), Counter(), Counter()
    timing = {key: [] for key in ("analysis_ms", "preview_ms", "publish_age_ms", "source_interval_ms")}
    for row in selected_rows(path, first_frame, last_frame, pose_trace=pose_trace):
        rows += 1
        last = row["frame_id"]
        if first is None:
            first = last
        states[str(row.get("state", "unknown"))] += 1
        d = row.get("presentation_diagnostics")
        if d is None:
            continue
        if pose_trace:
            observations[pose_reason_code(row.get("status"), row.get("reason") or "")] += 1
            if profiles is not None and (d["camera_profile_sha256"], d["workspace_profile_sha256"]) != profiles[2:]:
                raise ValueError("Numeric evidence profile binding mismatch")
        poses += 1
        # Reclassify historical prose too; never infer geometry from marker count.
        reasons[pose_reason_code(d.get("analysis_status"), d.get("analysis_reason") or "")] += 1
        if d.get("analysis_reason"):
            raw_reasons[d["analysis_reason"]] += 1
        ids = d.get("marker_ids")
        if (not isinstance(ids, list) or any(type(key) is not int for key in ids)
                or len(set(ids)) != len(ids)):
            missing_ids += 1
        else:
            combinations[",".join(map(str, sorted(ids))) or "(none)"] += 1
            marker_counts[str(len(ids))] += 1
            marker_presence.update(map(str, ids))
        available = numeric_evidence(d)
        numeric += int(available)
        if profiles is not None and available:
            replay_counts[replay_pose(d, *profiles)["reason_code"]] += 1
        for key, values in timing.items():
            value = d.get(key)
            if type(value) in (float, int) and math.isfinite(value) and value >= 0:
                values.append(value)
    if rows == 0:
        raise ValueError("No selected frames")
    metrics = {}
    for key, values in timing.items():
        values.sort()
        metrics[key] = None if not values else {
            "n": len(values), "mean": round(statistics.mean(values), 3),
            "p95": values[math.ceil(.95 * len(values)) - 1], "max": values[-1]}
    return {
        "schema_version": "beast_tracking_report_v1",
        "scope": "server numeric evidence, not Unity visibility or optical accuracy",
        "optical_alignment_verified": False,
        "rows": rows, "frame_range": [first, last], "state_counts": dict(states),
        "pose_frames": poses, "missing_pose_diagnostics_frames": rows - poses,
        "pose_reason_counts": dict(reasons),
        "observation_reason_counts": dict(observations) if pose_trace else None,
        "raw_rejection_counts": dict(raw_reasons),
        "pose_tracking_fraction": reasons["tracking"] / poses if poses else None,
        "marker_ids_missing_frames": missing_ids, "marker_combinations": dict(combinations),
        "marker_count_frames": dict(marker_counts), "marker_presence_frames": dict(marker_presence),
        "numeric_replay_available_frames": numeric,
        "replay_reason_counts": dict(replay_counts) if profiles is not None else None,
        "timings_ms": metrics,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--session", type=Path, help="Realtime session containing results.jsonl")
    source.add_argument("--pose-trace", type=Path, help="Calibration pose-trace.jsonl (numeric only)")
    parser.add_argument("--first-frame", type=int)
    parser.add_argument("--last-frame", type=int)
    parser.add_argument("--camera-profile", type=Path)
    parser.add_argument("--workspace-profile", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if bool(args.camera_profile) != bool(args.workspace_profile):
        parser.error("Numeric replay requires both camera and workspace profiles")
    try:
        profiles = None
        if args.camera_profile:
            from .workspace_live_preview import load_profiles
            camera, workspace, meta = load_profiles(args.camera_profile, args.workspace_profile)
            profiles = (camera, workspace, meta["camera_profile_sha256"], meta["workspace_profile_sha256"])
        path = args.pose_trace if args.pose_trace else args.session / "results.jsonl"
        report = summarize(path, args.first_frame, args.last_frame,
                           profiles=profiles, pose_trace=args.pose_trace is not None)
        text = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(text + "\n")
        print(text)
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f"Tracking report failed: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
