"""Compare frozen profiles on the second capture; never refit or activate anything."""
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from compare_workspace_xy import ROOT, project
from server.realtime.workspace_projection import CameraModel

CANDIDATE_ROOT = ROOT.parent / "common-xy-candidate-01"
LIVE = CANDIDATE_ROOT / "live-check/live-20261104T161004Z-f9b6a7b5"
LABELS = {15: {"A": [434, 404], "D": [610, 500]},
          51: {"A": [430, 423], "D": [623, 523]},
          99: {"A": [467, 458], "D": [660, 544]}}


def main():
    original = json.loads((ROOT / "session.json").read_bytes())
    current = json.loads((LIVE / "session.json").read_bytes())
    assert current["camera_profile_sha256"] == original["camera_profile_sha256"]
    assert current["workspace_profile"]["marker_centers_mm"] == original["workspace_profile"]["marker_centers_mm"]
    camera = CameraModel.from_profile(current["camera_profile"])
    names = "AD"
    old = np.array([original["workspace_profile"]["targets_mm"][k] for k in names])
    trial = np.array([current["workspace_profile"]["targets_mm"][k] for k in names])
    rows = []
    sheet = np.full((810, 760, 3), 245, np.uint8)
    for index, (frame, labels) in enumerate(LABELS.items()):
        folder = LIVE / f"frame-{frame:06d}"
        raw = (folder / "raw.png").read_bytes()
        state = json.loads((folder / "report.json").read_bytes())
        assert state["status"] == "tracking"
        baseline = project(old, state, camera)
        candidate = project(trial, state, camera)
        np.testing.assert_allclose(candidate, [state["targets"][k]["pixel"] for k in names], atol=1e-7)
        row = dict(frame_id=frame, raw_sha256=hashlib.sha256(raw).hexdigest(), labels_px=labels, targets={})
        for i, name in enumerate(names):
            label = np.array(labels[name])
            row["targets"][name] = dict(original_px=baseline[i].tolist(), candidate_px=candidate[i].tolist(),
                original_error_px=float(np.linalg.norm(baseline[i]-label)),
                candidate_error_px=float(np.linalg.norm(candidate[i]-label)))
        rows.append(row)
        image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        actual = np.array(labels["D"])
        origin = np.floor(np.minimum(baseline[1], actual) - [50, 30]).astype(int)
        x0,y0=origin
        assert x0 >= 0 and y0 >= 0 and x0+130 <= image.shape[1] and y0+100 <= image.shape[0]
        crop = image[y0:y0+100,x0:x0+130].copy()
        marked = crop.copy()
        for point,color in ((baseline[1],(220,190,0)),(candidate[1],(40,220,60))):
            cv2.circle(marked,tuple(np.rint(point-origin).astype(int)),6,color,1,cv2.LINE_AA)
        cv2.drawMarker(marked,tuple(np.rint(actual-origin).astype(int)),(0,170,255),cv2.MARKER_CROSS,11,1)
        y=index*270
        for column,panel in enumerate((crop,marked)):
            sheet[y+35:y+235,column*380+45:column*380+305]=cv2.resize(panel,(260,200),interpolation=cv2.INTER_NEAREST)
        cv2.putText(sheet,f"SECOND LAYOUT frame {frame} | raw D (left) / comparison (right)",
                    (15,y+22),cv2.FONT_HERSHEY_SIMPLEX,.43,(20,20,20),1)
        cv2.putText(sheet,"CYAN original | GREEN first-layout trial | ORANGE estimate +/-5px",
                    (15,y+256),cv2.FONT_HERSHEY_SIMPLEX,.42,(20,20,20),1)
    metrics = {k: {mode: float(np.mean([r["targets"][k][mode+"_error_px"] for r in rows]))
                   for mode in ("original","candidate")} for k in names}
    decision = dict(scope="second_layout_camera_review", activation_status="not_activated",
        candidate_decision="do_not_activate_for_current_layout", refit=False,
        physical_accuracy_verified=False, display_alignment_verified=False,
        first_session=str(ROOT), second_session=str(LIVE),
        parent_workspace_sha256=original["workspace_profile_sha256"],
        candidate_workspace_sha256=current["workspace_profile_sha256"],
        user_feedback=["상자나 마커를 조금 움직였어", "박스가 살짝 앞에 나와있었네"],
        interpretation="Different physical layouts; do not score this as same-layout calibration regression.",
        current_layout_result="Original coordinates are within approximate visual-label uncertainty in selected photos.",
        annotation_source="assistant_visual_estimate_not_user_ground_truth", uncertainty_per_axis_px=5,
        limitations=["No millimeter or optical accuracy claim; no eye model validation.",
                     "Head movement is expected; box-to-marker changes require separate workspace registration.",
                     "Do not average or refit observations across the two layouts."],
        mean_pixel_errors=metrics, observations=rows)
    out=LIVE/"offline-layout-review"
    out.mkdir(exist_ok=False)
    (out/"decision.json").write_text(json.dumps(decision,indent=2,ensure_ascii=False),encoding="utf-8")
    ok,encoded=cv2.imencode(".png",sheet)
    assert ok
    (out/"D-layout-comparison.png").write_bytes(encoded.tobytes())
    print(json.dumps(dict(output=str(out),mean_errors=metrics,candidate_decision=decision["candidate_decision"])))


if __name__ == "__main__":
    with patch.object(cv2,"VideoCapture",side_effect=AssertionError("Offline only")):
        main()

