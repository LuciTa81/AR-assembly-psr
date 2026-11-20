"""Frozen before/after comparison on new photos, using approximate visual labels."""
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

ROOT = Path(__file__).resolve().parent / 'live-20261030T154733Z-6c8b70d6'
PROFILE = Path('C:/Users/fresh/AppData/Local/ARAssembly/beast-mvp')
CAMERA = PROFILE / 'camera_calibration/combined-review-20260927T065914Z-89414bbe/candidate.json'
WORKSPACE = PROFILE / 'workspace_registration/comfort-layout-20261006-v1/workspace-candidate.json'
# Approximate groove centers read from unmarked crops, not user-confirmed truth.
LABELS = {2: [622, 407], 13: [615, 407], 23: [612, 402], 33: [606, 403],
          43: [603, 402], 53: [601, 404], 63: [602, 405], 73: [601, 404],
          83: [599, 394], 93: [598, 397]}


def main():
    session = json.loads((ROOT / 'session.json').read_bytes())
    camera, old, metadata = load_profiles(CAMERA, WORKSPACE)
    hashes = json.loads((ROOT / 'inspection/sources.json').read_bytes())['raw_sha256']
    original = old.targets['A']
    candidate = np.array(session['workspace_profile']['targets_mm']['A'])
    assert session['camera_profile_sha256'] == metadata['camera_profile_sha256']
    assert session['corner_refinement'] == 'subpix'
    assert session['workspace_profile']['target_adjustment']['parent_profile_sha256'] == metadata['workspace_profile_sha256']
    rows = []
    sheet = np.full((1500, 900, 3), 245, np.uint8)
    for index, (frame_id, label) in enumerate(LABELS.items()):
        folder = ROOT / f'frame-{frame_id:06d}'
        raw = (folder / 'raw.png').read_bytes()
        assert hashlib.sha256(raw).hexdigest() == hashes[str((folder/'raw.png').relative_to(ROOT))]
        image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        state = json.loads((folder / 'report.json').read_bytes())
        assert state['status'] == 'tracking'
        points = cv2.projectPoints(np.array([original, candidate]), np.array(state['rvec']),
                                   np.array(state['tvec_mm']), camera.matrix, camera.distortion)[0].reshape(2, 2)
        np.testing.assert_allclose(points[1], state['targets']['A']['pixel'], atol=1e-7)
        distances = np.linalg.norm(points - label, axis=1)
        rows.append(dict(frame_id=frame_id, approximate_center_px=label,
                         approximate_range_per_axis_px=3, before_px=points[0].tolist(),
                         candidate_px=points[1].tolist(), before_distance_px=float(distances[0]),
                         candidate_distance_px=float(distances[1])))
        x0, y0 = label[0]-35, label[1]-22
        crop = cv2.resize(image[y0:y0+44, x0:x0+70], None, fx=5, fy=5, interpolation=cv2.INTER_NEAREST)
        def pixel(point):
            return tuple(np.rint((np.array(point) - [x0,y0] + .5)*5 - .5).astype(int))
        cv2.rectangle(crop, pixel(np.array(label)-3), pixel(np.array(label)+3), (40,180,40), 1)
        cv2.drawMarker(crop, pixel(label), (40,180,40), cv2.MARKER_CROSS, 12, 1)
        cv2.circle(crop, pixel(points[0]), 7, (230,180,0), 2, cv2.LINE_AA)
        cv2.circle(crop, pixel(points[1]), 5, (220,50,220), 2, cv2.LINE_AA)
        x,y = index%2*450,index//2*300
        sheet[y+45:y+265,x+50:x+400] = crop
        cv2.putText(sheet, f'frame {frame_id}: old {distances[0]:.1f}px, trial {distances[1]:.1f}px',
                    (x+10,y+25), cv2.FONT_HERSHEY_SIMPLEX,.5,(20,20,20),1)
        cv2.putText(sheet, 'CYAN old | MAGENTA trial | GREEN estimate +/-3px',
                    (x+8,y+285), cv2.FONT_HERSHEY_SIMPLEX,.37,(20,20,20),1)
    events = [json.loads(line) for line in (ROOT/'frames.jsonl').read_text().splitlines()]
    frames = [r for r in events if r['event']=='frame']
    a = np.array([[r['before_distance_px'], r['candidate_distance_px']] for r in rows])
    report = dict(scope='new_saved_photos_camera_only', activation_status='not_activated',
                  annotation_source='assistant_visual_estimate', refit=False,
                  limitations=['Approximate +/-3px labels, not user-confirmed ground truth or confidence intervals',
                               'Small stationary-request view range, not full-motion validation',
                               'Not an optical SBS alignment or physical mm accuracy test'],
                  observations=rows, mean_before_px=float(a[:,0].mean()), mean_candidate_px=float(a[:,1].mean()),
                  improved=int((a[:,1]<a[:,0]).sum()), worsened=int((a[:,1]>a[:,0]).sum()),
                  frame_counts=dict(Counter(r['status'] for r in frames)),
                  rejection_reasons=dict(Counter(r.get('reason','') for r in frames if r['status']!='tracking')))
    write_json(ROOT/'inspection/comparison.json', report)
    _save_png(ROOT/'inspection/comparison.png',sheet)
    print(json.dumps({k:v for k,v in report.items() if k!='observations'}), flush=True)


if __name__ == '__main__':
    with patch.object(cv2,'VideoCapture',side_effect=AssertionError('Offline only')):
        main()
