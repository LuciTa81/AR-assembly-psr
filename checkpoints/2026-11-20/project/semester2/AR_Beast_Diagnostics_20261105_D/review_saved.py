"""Camera-only review of saved evidence. Never opens a camera or activates profiles."""
from pathlib import Path
from unittest.mock import patch
import hashlib
import json

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent / "live-20261104T154154Z-3ad8cfe7"
# Visual estimates only, not user-confirmed labels. B/C have empty screw recesses.
LABELS = {
    13: {"A": [464, 470], "B": [642, 460], "C": [430, 614], "D": [644, 604]},
    97: {"A": [325, 419], "B": [526, 403], "C": [327, 580], "D": [563, 550]},
    109: {"A": [375, 398], "B": [564, 378], "C": [389, 550], "D": [615, 520]},
}


def main():
    session = json.loads((ROOT / "session.json").read_bytes())
    camera = session["camera_profile"]
    workspace = session["workspace_profile"]
    matrix = np.array(camera["camera_matrix"], dtype=float)
    distortion = np.array(camera["distortion_coefficients"], dtype=float)
    world = np.array([workspace["targets_mm"][k] for k in "ABCD"], dtype=float)
    records, annotated = [], []
    # Three rows of raw/marked D crops; exact crop mapping retained in the report.
    sheet = np.full((3 * 270, 760, 3), 245, np.uint8)
    max_reprojection_difference = 0.
    for folder in sorted(ROOT.glob("frame-*")):
        state = json.loads((folder / "report.json").read_bytes())
        raw = (folder / "raw.png").read_bytes()
        frame = state["frame_id"]
        row = dict(frame_id=frame, raw_sha256=hashlib.sha256(raw).hexdigest(), status=state["status"])
        if state["status"] != "tracking":
            records.append(row)
            continue
        points = cv2.projectPoints(world, np.array(state["rvec"]), np.array(state["tvec_mm"]),
                                   matrix, distortion)[0].reshape(4, 2)
        stored = np.array([state["targets"][k]["pixel"] for k in "ABCD"])
        np.testing.assert_allclose(points, stored, atol=1e-7, rtol=0)
        max_reprojection_difference = max(max_reprojection_difference, float(np.max(np.abs(points - stored))))
        row.update(projected_px={k: points[i].tolist() for i, k in enumerate("ABCD")},
                   marker_ids=state["marker_ids"], marker_rms_px=state["rms_px"])
        if frame in LABELS:
            labels = np.array([LABELS[frame][k] for k in "ABCD"], dtype=float)
            delta = points - labels
            row.update(visual_estimates_px=LABELS[frame],
                       projected_minus_estimate_px={k: delta[i].tolist() for i, k in enumerate("ABCD")})
            image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
            assert image is not None and (image.shape[1], image.shape[0]) == tuple(camera["image_size"])
            actual = labels[3]
            x0, y0 = np.floor(np.minimum(points[3], actual) - [50, 30]).astype(int)
            assert x0 >= 0 and y0 >= 0 and x0 + 130 <= image.shape[1] and y0 + 100 <= image.shape[0]
            crop = image[y0:y0 + 100, x0:x0 + 130].copy()
            marked = crop.copy()
            predicted_local = tuple(np.rint(points[3] - [x0, y0]).astype(int))
            actual_local = tuple(np.rint(actual - [x0, y0]).astype(int))
            cv2.circle(marked, predicted_local, 7, (220, 190, 0), 1, cv2.LINE_AA)
            cv2.drawMarker(marked, actual_local, (0, 170, 255), cv2.MARKER_CROSS, 11, 1)
            index = len(annotated)
            y = index * 270
            for column, panel in enumerate((crop, marked)):
                sheet[y + 35:y + 235, column * 380 + 45:column * 380 + 305] = cv2.resize(
                    panel, (260, 200), interpolation=cv2.INTER_NEAREST)
            cv2.putText(sheet, f"frame {frame} | raw D (left) / projection + visual estimate (right)",
                        (15, y + 22), cv2.FONT_HERSHEY_SIMPLEX, .45, (20, 20, 20), 1)
            cv2.putText(sheet, f"D projected - estimate: dx={delta[3,0]:+.1f}px dy={delta[3,1]:+.1f}px",
                        (15, y + 258), cv2.FONT_HERSHEY_SIMPLEX, .5, (20, 20, 20), 1)
            row["crop_raw_origin_px"] = [int(x0), int(y0)]
            annotated.append(row)
        records.append(row)
    assert len(records) == 10 and len(annotated) == 3
    d = np.array([r["projected_minus_estimate_px"]["D"] for r in annotated])
    report = dict(scope="saved_camera_images_only", activated=False, calibration_valid=False,
                  display_alignment_verified=False, source_session=str(ROOT), labels=LABELS,
                  annotation_source="assistant_visual_estimate_not_user_ground_truth",
                  estimate_uncertainty_per_axis_px=5,
                  limitations=[
                      "Visual estimates are approximate; uncertainty is not a statistical confidence interval.",
                      "B/C mark empty recess centers, not seated screw heads; do not fit geometry from these labels.",
                      "Camera projection mismatch does not identify movement, pose bias, intrinsics or registration as the cause.",
                      "No eye display accuracy or physical millimeter accuracy was measured.",
                  ],
                  camera_profile_sha256=session["camera_profile_sha256"],
                  workspace_profile_sha256=session["workspace_profile_sha256"],
                  sample_count=len(records), annotated_count=len(annotated),
                  max_reprojection_difference_px=max_reprojection_difference,
                  D_projected_minus_estimate_px_min=d.min(axis=0).tolist(),
                  D_projected_minus_estimate_px_max=d.max(axis=0).tolist(),
                  observations=records)
    out = ROOT / "offline-review"
    out.mkdir(exist_ok=False)
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    ok, encoded = cv2.imencode(".png", sheet)
    assert ok
    (out / "D-comparison.png").write_bytes(encoded.tobytes())
    print(json.dumps(dict(output=str(out), samples=len(records), annotated=len(annotated),
                          D_delta_min=report["D_projected_minus_estimate_px_min"],
                          D_delta_max=report["D_projected_minus_estimate_px_max"],
                          max_reprojection_difference_px=max_reprojection_difference)))


if __name__ == "__main__":
    with patch.object(cv2, "VideoCapture", side_effect=AssertionError("Offline only")):
        main()

