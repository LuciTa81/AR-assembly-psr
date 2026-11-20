"""Review the finite capture without opening a camera or changing calibration."""
from collections import Counter
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from server.realtime.camera_calibration import write_json
from server.realtime.workspace_live_preview import load_profiles
from server.realtime.workspace_roi_candidate import _save_png

ROOT = Path(__file__).resolve().parent
SOURCE = Path('C:/Users/fresh/AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/ARAssembly/beast-mvp/workspace_registration/live-20261030T145649Z-e73719b1')
PROFILE = Path('C:/Users/fresh/AppData/Local/ARAssembly/beast-mvp')
# Approximate manual readings, not independent ground truth or confidence intervals.
LABELS = {81: ([338., 411.], 4., (295, 370, 385, 455)),
          91: ([411., 354.], 3., (365, 310, 455, 395))}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    session = json.loads((ROOT / 'session.json').read_text())
    camera_path = PROFILE / 'camera_calibration/combined-review-20260927T065914Z-89414bbe/candidate.json'
    workspace_path = PROFILE / 'workspace_registration/comfort-layout-20261006-v1/workspace-candidate.json'
    camera, workspace, metadata = load_profiles(camera_path, workspace_path)
    for key in ('camera_profile_sha256', 'workspace_profile_sha256'):
        assert metadata[key] == session[key]
    hashes = {p.relative_to(SOURCE).as_posix(): digest(p) for p in SOURCE.rglob('*') if p.is_file()}
    assert len(hashes) == 33
    for relative, sha in hashes.items():
        assert digest(ROOT / relative) == sha
    records = [json.loads(line) for line in (ROOT / 'frames.jsonl').read_text().splitlines()]
    frames = [r for r in records if r['event'] == 'frame']
    contact = np.full((1920, 1280, 3), 245, np.uint8)
    comparison = np.full((770, 1600, 3), 245, np.uint8)
    measured = []
    saved_valid = []
    for index, raw in enumerate(sorted(ROOT.glob('frame-*/raw.png'))):
        image = cv2.imdecode(np.frombuffer(raw.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
        state = json.loads((raw.parent / 'report.json').read_text())
        frame_id = state['frame_id']
        x, y = (index % 2) * 640, (index // 2) * 384
        contact[y+24:y+384, x:x+640] = cv2.resize(image, (640, 360))
        cv2.putText(contact, f'frame {frame_id} | {state["status"]}', (x+8, y+18), cv2.FONT_HERSHEY_SIMPLEX, .5, (20,20,20), 1)
        if state['status'] != 'tracking':
            continue
        saved_valid.append(frame_id)
        observed, uncertainty, (x0,y0,x1,y1) = LABELS[frame_id]
        predicted = np.array(state['targets']['A']['pixel'])
        projected = cv2.projectPoints(np.asarray(workspace.targets['A']).reshape(1,3), np.array(state['rvec']), np.array(state['tvec_mm']), camera.matrix, camera.distortion)[0].reshape(2)
        np.testing.assert_allclose(projected, predicted, atol=1e-7)
        error = predicted - observed
        row = dict(frame_id=frame_id, visual_estimate_px=observed, approximate_range_per_axis_px=uncertainty,
                   predicted_A_px=predicted.tolist(), predicted_minus_estimate_px=error.tolist(),
                   distance_px=float(np.linalg.norm(error)), marker_ids=state['marker_ids'], marker_rms_px=state['rms_px'])
        measured.append(row)
        crop = cv2.resize(image[y0:y1,x0:x1], None, fx=8, fy=8, interpolation=cv2.INTER_NEAREST)
        def point(v):
            return tuple(np.rint((np.asarray(v)-[x0,y0])*8).astype(int))
        cv2.rectangle(crop, point(np.array(observed)-uncertainty), point(np.array(observed)+uncertainty), (40,180,40), 2)
        cv2.drawMarker(crop, point(observed), (40,180,40), cv2.MARKER_CROSS, 22, 2)
        cv2.circle(crop, point(predicted), 10, (230,180,0), 2, cv2.LINE_AA)
        ox = (len(measured)-1)*800
        comparison[60:740, ox+65:ox+785] = crop
        cv2.putText(comparison, f'frame {frame_id} | distance {row["distance_px"]:.2f} raw px', (ox+12,28), cv2.FONT_HERSHEY_SIMPLEX,.6,(20,20,20),1)
        cv2.putText(comparison, 'Green: manual estimate | Cyan: existing A projection', (ox+12,758),cv2.FONT_HERSHEY_SIMPLEX,.48,(20,20,20),1)
    assert set(saved_valid) == set(LABELS)
    tail = [r for r in frames if 91 <= r['frame_id'] <= 120]
    result = dict(scope='offline_review_of_finite_camera_capture', activation_status='not_activated',
        setup=dict(target='A', head_height_mm=60, height_source='user-confirmed approximate measurement', screw_state='seated as second supplied photo'),
        frame_counts=dict(Counter(r['status'] for r in frames)),
        rejected_reasons=dict(Counter(r['reason'] for r in frames if r['status'] != 'tracking')),
        late_window=dict(frame_ids=[91,120], counts=dict(Counter(r['status'] for r in tail)), duration_seconds=tail[-1]['received_at_monotonic']-tail[0]['received_at_monotonic']),
        raw_count=len(list(ROOT.glob('frame-*/raw.png'))), measured=measured,
        copied_input_sha256=hashes, camera_profile_sha256=metadata['camera_profile_sha256'], workspace_profile_sha256=metadata['workspace_profile_sha256'],
        limitations=['Initial photos show box side/room, so total tracking fraction is not a steady-view benchmark.',
                     'Only two saved images passed live pose gates; both are included.',
                     'Visual labels are approximate and not blind; frame 81 prediction was inspected first.',
                     'No metric accuracy, optical alignment or general tracking stability is established.'])
    output = ROOT / 'review'
    output.mkdir(exist_ok=False)
    _save_png(output / 'contact.png', contact)
    _save_png(output / 'A-comparison.png', comparison)
    write_json(output / 'analysis.json', result)
    for relative, sha in hashes.items():
        assert digest(ROOT / relative) == sha
    assert digest(camera_path) == session['camera_profile_sha256']
    assert digest(workspace_path) == session['workspace_profile_sha256']
    print(json.dumps({k: result[k] for k in ('frame_counts','rejected_reasons','late_window','raw_count','measured')}))


if __name__ == '__main__':
    with patch('cv2.VideoCapture', side_effect=AssertionError('Camera forbidden during review')):
        main()
