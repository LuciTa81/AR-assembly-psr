"""Offline evidence audit. Does not access a camera or produce calibration files."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

import cv2
import numpy as np


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project(matrix, xyz):
    homogeneous = np.r_[xyz, 1.0]
    q = matrix @ homogeneous
    if not np.isfinite(q).all() or q[2] <= 1e-9:
        raise ValueError("Invalid projection depth")
    return q[:2] / q[2]


def jacobian(matrix, xyz):
    q = matrix @ np.r_[xyz, 1.0]
    return (matrix[:2, :3] * q[2] - q[:2, None] * matrix[2, :3]) / q[2] ** 2


def summary(values):
    values = np.asarray(values, dtype=float)
    return None if values.size == 0 else np.percentile(values, [0, 50, 95, 100], axis=0).tolist()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.root))
    from server.realtime.workspace_live_preview import load_profiles
    from server.realtime.workspace_projection import estimate_pose

    source = args.root / "outputs/display_retarget/fit-20261104T133307Z-3f75411a/candidate-probe.json"
    presentation = json.loads((args.root / "outputs/demo/presentation.json").read_text(encoding="utf-8-sig"))
    camera, workspace, meta = load_profiles(presentation["camera_profile"], presentation["workspace_profile"])
    candidate = json.loads(source.read_text(encoding="utf-8-sig"))
    matrices = [np.array(candidate[f"{eye}_projection"]).reshape(3, 4) for eye in ("left", "right")]
    groups = [("middle", "7c0002ecf5cc425b9953fc4451a2498e", 1277),
              ("near_1", "51f12f2b79724a649ad57d420dbbdca8", 1392),
              ("near_2", "51f12f2b79724a649ad57d420dbbdca8", 1899)]
    output = dict(schema_version="beast_saved_pose_audit_v1", live_enabled=False,
                  optical_accuracy_measured=False, source_candidate_sha256=digest(source),
                  percentile_order=[0, 50, 95, 100], groups=[], input_hashes={})
    records = []
    for label, session, frame in groups:
        folder = args.data_root / session
        path = folder / f"diagnostic-frame-{frame}.json"
        trace = folder / "pose-trace.jsonl"
        output["input_hashes"].update({str(path): digest(path), str(trace): digest(trace)})
        record = json.loads(path.read_text(encoding="utf-8-sig"))
        observation = record["observation"]
        assert record["candidate_sha256"] == digest(source)
        assert record["setup_id"] == "20261114-A-mid-near-1652"
        assert record["rendered_view"] == "Both" and record["binocular_confirmed_by_user"]
        assert observation["target_id"] == "A" and observation["status"] == "tracking"
        assert 0 <= record["conservative_age_ms"] <= 150
        rows = [json.loads(line) for line in trace.read_text().splitlines()]
        row = next(r for r in rows if r["frame_id"] == frame)
        assert all(row[k] == observation[k] == meta[k] for k in ("camera_profile_sha256", "workspace_profile_sha256"))
        detections = {int(k): np.array(v) for k, v in row["detected_corners_px"].items()}
        pose = estimate_pose(detections, workspace, camera, camera.image_size)
        rotation = cv2.Rodrigues(pose.rvec)[0]
        xyz = rotation @ workspace.targets["A"] + pose.tvec.reshape(3)
        assert np.allclose(xyz, observation["camera_xyz_mm"], atol=1e-6, rtol=0)
        offsets = np.array([record[f"{eye}_offset_px"] for eye in ("left", "right")])
        for eye, matrix in zip(("left", "right"), matrices):
            assert np.allclose(project(matrix, xyz) + record[f"{eye}_offset_px"], record[f"{eye}_final_px"], atol=1e-6, rtol=0)
            numerical = np.column_stack([(project(matrix, xyz + np.eye(3)[i] * 1e-3) -
                                          project(matrix, xyz - np.eye(3)[i] * 1e-3)) / 2e-3 for i in range(3)])
            assert np.allclose(jacobian(matrix, xyz), numerical, atol=1e-6, rtol=0)
        group = dict(label=label, frame_id=frame, camera_xyz_mm=xyz.tolist(),
                     offset_px=offsets.tolist(), marker_ids=pose.marker_ids, rms_px=pose.rms_px,
                     marker_residual_px={str(k): v.tolist() for k, v in zip(pose.marker_ids,
                         pose.observed_centers_px - pose.projected_centers_px)},
                     target_projection_gain_px_per_camera_mm={}, marker_omission=[])
        for target, world in workspace.targets.items():
            point = rotation @ world + pose.tvec.reshape(3)
            group["target_projection_gain_px_per_camera_mm"][target] = [
                float(np.linalg.svd(jacobian(m, point), compute_uv=False)[0]) for m in matrices]
        # Omission is a sensitivity experiment, not a better or valid ground-truth pose.
        for omitted in sorted(detections):
            case = dict(omitted=omitted)
            try:
                fit = estimate_pose({k: v for k, v in detections.items() if k != omitted}, workspace, camera, camera.image_size)
            except ValueError as exc:
                case.update(accepted=False, reason=str(exc))
            else:
                shifted = cv2.Rodrigues(fit.rvec)[0] @ workspace.targets["A"] + fit.tvec.reshape(3)
                case.update(accepted=True, rms_px=fit.rms_px, camera_xyz_delta_mm=(shifted-xyz).tolist(),
                            eye_delta_px=[(project(m, shifted)-project(m, xyz)).tolist() for m in matrices])
            group["marker_omission"].append(case)
        window = [r for r in rows if abs(r["received_at_monotonic"]-row["received_at_monotonic"]) <= .5]
        valid = [r for r in window if r["status"] == "tracking"]
        eye_shifts = [[np.linalg.norm(project(m, r["camera_xyz_mm"])-project(m, xyz)) for m in matrices] for r in valid]
        group["local_window"] = dict(seconds_each_side=.5, frames=len(window), tracking=len(valid),
            reasons=dict(Counter(r["reason_code"] for r in window)),
            camera_xyz_min_med_p95_max_mm=summary([r["camera_xyz_mm"] for r in valid]),
            eye_shift_min_med_p95_max_px=summary(eye_shifts),
            interpretation="Includes true head movement; not a noise estimate or optical error")
        records.append((xyz, offsets))
        output["groups"].append(group)

    z = np.array([r[0][2] for r in records])
    residual = np.array([r[1] for r in records]).reshape(3, 4)
    output["depth_only_leave_one_group_out"] = []
    for held in range(3):
        train = [i for i in range(3) if i != held]
        # Two-point interpolation/extrapolation is diagnostic only, never exported.
        weight = (1/z[held] - 1/z[train[0]]) / (1/z[train[1]] - 1/z[train[0]])
        prediction = residual[train[0]] + weight * (residual[train[1]]-residual[train[0]])
        error = (prediction-residual[held]).reshape(2, 2)
        output["depth_only_leave_one_group_out"].append(dict(held_out=groups[held][0],
            interpolation_weight=float(weight), extrapolation=not 0 <= weight <= 1,
            predicted_minus_confirmed_px=error.tolist(), per_eye_error_px=np.linalg.norm(error, axis=1).tolist()))
    assert digest(source) == output["source_candidate_sha256"]
    assert all(digest(Path(p)) == h for p, h in output["input_hashes"].items())
    args.output.write_text(json.dumps(output, indent=2, allow_nan=False), encoding="utf-8")
    for group in output["groups"]:
        print(json.dumps(group, separators=(",", ":")))
    print(json.dumps({"depth_only_leave_one_group_out": output["depth_only_leave_one_group_out"]}))
    print("PASS: exact pose replay, saved pixels, finite-difference Jacobians, unchanged inputs")


if __name__ == "__main__":
    main()
