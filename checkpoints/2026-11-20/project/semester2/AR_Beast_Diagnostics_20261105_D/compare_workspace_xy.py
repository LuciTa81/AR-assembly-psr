"""Offline common-XY workspace trial; never changes active profiles or eye calibration."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np

from server.realtime.workspace_projection import CameraModel, MetricWorkspace, pixel_to_plane

ROOT = Path(__file__).resolve().parent / "live-20261104T154154Z-3ad8cfe7"
FIT_FRAMES = (13, 97)
FIT_TARGETS = "AD"
# Read from unmarked photos after the fit was frozen; estimates, not ground truth.
EXTRA_CHECK_LABELS = {
    1: {"A": [454, 481], "D": [635, 618]},
    37: {"A": [296, 350], "D": [497, 458]},
    73: {"A": [383, 385], "D": [576, 490]},
}


def fit_offset(camera, workspace, observations):
    deltas = []
    for frame in FIT_FRAMES:
        record = observations[frame]
        rvec = np.array(record["rvec"], dtype=float)
        tvec = np.array(record["tvec_mm"], dtype=float)
        pose = SimpleNamespace(rvec=rvec, camera_position_mm=-(cv2.Rodrigues(rvec)[0].T @ tvec))
        for name in FIT_TARGETS:
            original = workspace.targets[name]
            measured = pixel_to_plane(record["labels"][name], original[2], pose, camera)
            deltas.append(measured - original)
    offset = np.mean(deltas, axis=0)
    offset[2] = 0.
    return offset


def make_candidate(source, offset, parent_sha256):
    offset = np.asarray(offset, dtype=float)
    if offset.shape != (3,) or not np.isfinite(offset).all() or offset[2] != 0:
        raise ValueError("Expected finite XY-only translation")
    candidate = copy.deepcopy(source)
    candidate.update(profile_id=source["profile_id"] + "-xy-trial-20261105",
                     status="common_xy_camera_trial_only", activation_status="not_activated",
                     physical_accuracy_verified=False, display_alignment_verified=False)
    candidate["targets_mm"] = {k: (np.asarray(v, dtype=float) + offset).tolist()
                               for k, v in source["targets_mm"].items()}
    candidate["coordinate_adjustment"] = dict(
        method="offline_common_xy_translation", parent_profile_id=source["profile_id"],
        parent_profile_sha256=parent_sha256, delta_mm=offset.tolist(),
        fit_frame_ids=list(FIT_FRAMES), fit_targets=list(FIT_TARGETS),
        annotation_source="assistant_visual_estimates_not_user_confirmed",
        estimate_uncertainty_per_axis_px=5, frozen_height_mm=60,
        geometry_preserved=True, eye_calibration_rebound=False,
        validation="Camera-only hypothesis; live and optical validation pending")
    return candidate


def project(points, record, camera):
    return cv2.projectPoints(np.asarray(points, dtype=float), np.array(record["rvec"]),
                             np.array(record["tvec_mm"]), camera.matrix,
                             camera.distortion)[0].reshape(-1, 2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    session = json.loads((ROOT / "session.json").read_bytes())
    previous = json.loads((ROOT / "offline-review/report.json").read_bytes())
    labels = {int(k): v for k, v in previous["labels"].items()}
    labels.update(EXTRA_CHECK_LABELS)
    camera = CameraModel.from_profile(session["camera_profile"])
    workspace = MetricWorkspace.from_dict(session["workspace_profile"])
    observations = {frame: dict(json.loads((ROOT / f"frame-{frame:06d}" / "report.json").read_bytes()),
                                labels=points) for frame, points in labels.items()}
    offset = fit_offset(camera, workspace, observations)
    candidate = make_candidate(session["workspace_profile"], offset, session["workspace_profile_sha256"])
    MetricWorkspace.from_dict(candidate)
    original_points = np.array([workspace.targets[k] for k in "ABCD"])
    candidate_points = np.array([candidate["targets_mm"][k] for k in "ABCD"])
    np.testing.assert_allclose(candidate_points[:,None] - candidate_points,
                               original_points[:,None] - original_points, atol=1e-9)
    rows = []
    checks = sorted(set(observations) - set(FIT_FRAMES))
    sheet = np.full((len(checks) * 270, 760, 3), 245, np.uint8)
    images = {}
    for frame, record in sorted(observations.items()):
        old = project(original_points, record, camera)
        new = project(candidate_points, record, camera)
        np.testing.assert_allclose(old, [record["targets"][k]["pixel"] for k in "ABCD"], atol=1e-7)
        raw_path = ROOT / f"frame-{frame:06d}" / "raw.png"
        raw = raw_path.read_bytes()
        row = dict(frame_id=frame, split="fit" if frame in FIT_FRAMES else "check",
                   raw_sha256=hashlib.sha256(raw).hexdigest(),
                   report_sha256=hashlib.sha256((raw_path.parent / "report.json").read_bytes()).hexdigest(),
                   labels_px=record["labels"], targets={})
        for index, name in enumerate("ABCD"):
            target = dict(before_px=old[index].tolist(), candidate_px=new[index].tolist())
            if name in record["labels"]:
                label = np.array(record["labels"][name])
                target.update(before_error_px=float(np.linalg.norm(old[index]-label)),
                              candidate_error_px=float(np.linalg.norm(new[index]-label)),
                              label_kind="seated_head_estimate" if name in FIT_TARGETS else "empty_recess_reference_only")
            row["targets"][name] = target
        rows.append(row)
        if frame not in checks:
            continue
        image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        assert image is not None
        actual = np.array(record["labels"]["D"])
        origin = np.floor(np.minimum(old[3], actual) - [50, 30]).astype(int)
        x0,y0 = origin
        assert x0 >= 0 and y0 >= 0 and x0+130 <= image.shape[1] and y0+100 <= image.shape[0]
        crop = image[y0:y0+100, x0:x0+130].copy()
        marked = crop.copy()
        cv2.circle(marked, tuple(np.rint(old[3]-origin).astype(int)), 7, (220,190,0), 1, cv2.LINE_AA)
        cv2.circle(marked, tuple(np.rint(new[3]-origin).astype(int)), 6, (40,220,60), 1, cv2.LINE_AA)
        cv2.drawMarker(marked, tuple(np.rint(actual-origin).astype(int)), (0,170,255), cv2.MARKER_CROSS, 11, 1)
        y = checks.index(frame)*270
        for column, panel in enumerate((crop,marked)):
            sheet[y+35:y+235, column*380+45:column*380+305] = cv2.resize(
                panel, (260,200), interpolation=cv2.INTER_NEAREST)
        cv2.putText(sheet, f"CHECK frame {frame} | raw D (left) / old + candidate (right)",
                    (15,y+22), cv2.FONT_HERSHEY_SIMPLEX,.46,(20,20,20),1)
        cv2.putText(sheet, "CYAN old | GREEN trial | ORANGE visual estimate (+/-5px)",
                    (15,y+256),cv2.FONT_HERSHEY_SIMPLEX,.44,(20,20,20),1)
        if frame == 109:
            marked_full = image.copy()
            for points, color in ((old,(220,190,0)),(new,(40,220,60))):
                cv2.polylines(marked_full,[np.rint(points[[0,1,3,2]]).astype(np.int32)],True,color,1,cv2.LINE_AA)
                for i,p in enumerate(points):
                    center=tuple(np.rint(p).astype(int))
                    cv2.circle(marked_full,center,7,color,1,cv2.LINE_AA)
                    cv2.putText(marked_full,"ABCD"[i],(center[0]+9,center[1]),cv2.FONT_HERSHEY_SIMPLEX,.55,color,1)
            cv2.rectangle(marked_full,(0,0),(1280,40),(0,0,0),-1)
            cv2.putText(marked_full,"CAMERA CHECK ONLY | CYAN old | GREEN XY trial | NOT ACTIVATED",
                        (10,26),cv2.FONT_HERSHEY_SIMPLEX,.57,(255,255,255),1)
            images["all-corners-check-109.png"] = marked_full
    check_rows = [r for r in rows if r["split"] == "check"]
    metrics = {}
    for name in FIT_TARGETS:
        before = np.array([r["targets"][name]["before_error_px"] for r in check_rows])
        after = np.array([r["targets"][name]["candidate_error_px"] for r in check_rows])
        metrics[name] = dict(check_count=len(before), mean_before_px=float(before.mean()),
                             mean_candidate_px=float(after.mean()), max_candidate_px=float(after.max()),
                             improved_count=int((after<before).sum()))
    report = dict(scope="offline_common_xy_translation_hypothesis", activation_status="not_activated",
                  calibration_valid=False, display_alignment_verified=False, physical_accuracy_verified=False,
                  fit_frames=list(FIT_FRAMES), check_frames=checks, fit_targets=list(FIT_TARGETS),
                  reference_only_targets=list("BC"), offset_mm=offset.tolist(),
                  uncertainty_per_axis_px=5, annotation_source="assistant_visual_estimates_not_ground_truth",
                  source_session=str(ROOT), camera_profile_sha256=session["camera_profile_sha256"],
                  parent_workspace_sha256=session["workspace_profile_sha256"],
                  check_metrics=metrics, observations=rows, limitations=[
                      "Check frames were not used in fitting; all frames share one short session.",
                      "Visual labels are approximate, not user-confirmed ground truth.",
                      "No proof of physical box movement; pose/registration bias remains possible.",
                      "B/C recesses are not seated screw heads and are excluded from fitting and headline metrics.",
                      "A camera-only improvement cannot validate SBS, wearing stability, or millimeter accuracy.",
                      "No height, rotation, scale, camera intrinsics, marker pose, gates or eye model changed.",
                      "Do not rebind or refit historical eye data until physical target movement vs registration correction is resolved."
                  ])
    args.out_dir.mkdir(parents=True, exist_ok=False)
    candidate_path = args.out_dir/"workspace-xy-camera-candidate.json"
    candidate_path.write_text(json.dumps(candidate,indent=2,ensure_ascii=False),encoding="utf-8")
    report["candidate_sha256"] = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
    (args.out_dir/"analysis.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    images["D-check-comparison.png"] = sheet
    for name, value in images.items():
        ok, encoded = cv2.imencode(".png",value)
        assert ok
        (args.out_dir/name).write_bytes(encoded.tobytes())
    print(json.dumps(dict(output=str(args.out_dir),offset_mm=offset.tolist(),check_metrics=metrics)))


if __name__ == "__main__":
    with patch.object(cv2,"VideoCapture",side_effect=AssertionError("Offline only")):
        main()

