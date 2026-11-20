"""Fit one diagnostic A coordinate on capture 13; evaluate frozen on 11 and 12."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np

from server.realtime.camera_calibration import write_json
from server.realtime.workspace_live_preview import load_profiles
from server.realtime.workspace_projection import pixel_to_plane
from server.realtime.workspace_roi_candidate import _save_png

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent
PROFILE = Path('C:/Users/fresh/AppData/Local/ARAssembly/beast-mvp')
TRAIN = 'capture-13-A-stationary'
DATASETS = [
    (TRAIN, 'review/analysis.json', 'observations', 'estimate_px'),
    ('capture-11-A-seated', 'review/analysis.json', 'measured', 'visual_estimate_px'),
    ('capture-12-A-seated-repeat', 'inspection/analysis.json', 'estimates', 'estimate_px'),
]


def project(xyz, pose, camera):
    xyz = np.asarray(xyz, dtype=float)
    depth = (cv2.Rodrigues(pose.rvec)[0] @ xyz + pose.tvec)[2]
    assert depth > 0
    return cv2.projectPoints(xyz.reshape(1, 3), pose.rvec, pose.tvec,
                            camera.matrix, camera.distortion)[0].reshape(2)


def fit(records, camera, height, label_offset=(0., 0.)):
    points = [pixel_to_plane(r['observed'] + label_offset, height, r['pose'], camera)
              for r in records]
    candidate = np.median(points, axis=0)
    np.testing.assert_allclose(candidate[2], height, atol=1e-8)
    return candidate, np.asarray(points)


def statistics(rows):
    before = np.array([r['before_distance_px'] for r in rows])
    after = np.array([r['after_distance_px'] for r in rows])
    return dict(count=len(rows), mean_before_px=float(before.mean()),
                mean_after_px=float(after.mean()), median_before_px=float(np.median(before)),
                median_after_px=float(np.median(after)), max_before_px=float(before.max()),
                max_after_px=float(after.max()), improved=int((after < before).sum()),
                worsened=int((after > before).sum()))


def main():
    hashes = {}
    def read(path):
        data = path.read_bytes()
        hashes[str(path)] = hashlib.sha256(data).hexdigest()
        return data
    def read_json(path):
        return json.loads(read(path))

    camera_path = PROFILE / 'camera_calibration/combined-review-20260927T065914Z-89414bbe/candidate.json'
    workspace_path = PROFILE / 'workspace_registration/comfort-layout-20261006-v1/workspace-candidate.json'
    read(camera_path)
    read(workspace_path)
    camera, workspace, metadata = load_profiles(camera_path, workspace_path)
    original = workspace.targets['A'].copy()
    assert original[2] == 60.
    records = []
    for capture, report_name, key, label_key in DATASETS:
        directory = BASE / capture
        session = read_json(directory / 'session.json')
        for name in ('camera_profile_sha256', 'workspace_profile_sha256'):
            assert session[name] == metadata[name]
        assert session['corner_refinement'] == 'subpix'
        report = read_json(directory / report_name)
        for row in report[key]:
            frame_id = row['frame_id']
            folder = directory / f'frame-{frame_id:06d}'
            state = read_json(folder / 'report.json')
            assert state['status'] == 'tracking'
            pose = SimpleNamespace(rvec=np.array(state['rvec']), tvec=np.array(state['tvec_mm']),
                                   camera_position_mm=np.array(state['camera_position_mm']))
            observed = np.array(row[label_key], dtype=float)
            uncertainty = row['approximate_range_per_axis_px']
            assert uncertainty >= 3.
            raw = read(folder / 'raw.png')
            image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
            assert image.shape[:2] == (720, 1280)
            np.testing.assert_allclose(project(original, pose, camera), state['targets']['A']['pixel'], atol=1e-7)
            world = pixel_to_plane(observed, 60., pose, camera)
            np.testing.assert_allclose(project(world, pose, camera), observed, atol=.02)
            records.append(dict(capture=capture, frame_id=frame_id, observed=observed,
                                uncertainty=uncertainty, pose=pose, image=image, source=str(folder/'raw.png')))
    training = [r for r in records if r['capture'] == TRAIN]
    held_out = [r for r in records if r['capture'] != TRAIN]
    assert len(training) == 8 and len(held_out) == 8
    assert not ({r['source'] for r in training} & {r['source'] for r in held_out})
    candidate, training_world = fit(training, camera, 60.)
    # Only training labels influence this coordinate. It is frozen before holdout scoring.
    candidate.setflags(write=False)
    results = []
    for r in records:
        before = project(original, r['pose'], camera)
        after = project(candidate, r['pose'], camera)
        results.append(dict(capture=r['capture'], frame_id=r['frame_id'],
                            role='fit' if r['capture'] == TRAIN else 'held_out',
                            observed_px=r['observed'].tolist(), approximate_range_per_axis_px=r['uncertainty'],
                            before_px=before.tolist(), after_px=after.tolist(),
                            before_distance_px=float(np.linalg.norm(before-r['observed'])),
                            after_distance_px=float(np.linalg.norm(after-r['observed']))))
    groups = defaultdict(list)
    for row in results:
        groups[row['capture']].append(row)
    summary = {name: statistics(rows) for name, rows in groups.items()}
    summary['held_out_combined'] = statistics([r for r in results if r['role'] == 'held_out'])
    sensitivity = []
    for dx in (-3., 0., 3.):
        for dy in (-3., 0., 3.):
            shifted, _ = fit(training, camera, 60., np.array([dx,dy]))
            sensitivity.append(dict(common_label_shift_px=[dx,dy], candidate_mm=shifted.tolist(),
                                    delta_from_original_mm=(shifted-original).tolist()))
    np.testing.assert_allclose(sensitivity[4]['candidate_mm'], candidate, atol=1e-8)
    # Deterministic consistency check: perfect labels recover the existing point.
    ideal = [dict(r, observed=project(original,r['pose'],camera)) for r in training]
    recovered, _ = fit(ideal,camera,60.)
    np.testing.assert_allclose(recovered,original,atol=.02)

    output = ROOT/'results'
    output.mkdir(exist_ok=False)
    panel_w,panel_h,scale = 500,350,5
    panels = np.full((4*panel_h,2*panel_w,3),245,np.uint8)
    for index,r in enumerate(held_out):
        row = next(x for x in results if x['capture']==r['capture'] and x['frame_id']==r['frame_id'])
        x0,y0 = np.rint(r['observed']-[40,28]).astype(int)
        crop = cv2.resize(r['image'][y0:y0+56,x0:x0+80],None,fx=scale,fy=scale,interpolation=cv2.INTER_NEAREST)
        assert crop.shape[:2] == (280,400)
        def point(p): return tuple(np.rint((np.array(p)-[x0,y0])*scale).astype(int))
        cv2.rectangle(crop,point(r['observed']-r['uncertainty']),point(r['observed']+r['uncertainty']),(40,180,40),1)
        cv2.drawMarker(crop,point(r['observed']),(40,180,40),cv2.MARKER_CROSS,14,1)
        cv2.circle(crop,point(row['before_px']),7,(230,180,0),2,cv2.LINE_AA)
        cv2.circle(crop,point(row['after_px']),5,(220,50,220),2,cv2.LINE_AA)
        ox,oy = index%2*panel_w,index//2*panel_h
        panels[oy+40:oy+320,ox+50:ox+450] = crop
        title = f'{r["capture"].split("-")[1]} / {r["frame_id"]} | {row["before_distance_px"]:.2f} -> {row["after_distance_px"]:.2f} px'
        cv2.putText(panels,title,(ox+10,oy+25),cv2.FONT_HERSHEY_SIMPLEX,.55,(20,20,20),1)
        cv2.putText(panels,'Green: estimate | Cyan: old | Magenta: hypothesis',(ox+10,oy+340),cv2.FONT_HERSHEY_SIMPLEX,.43,(20,20,20),1)
    _save_png(output/'held-out-comparison.png',panels)
    result = dict(schema_version='A_coordinate_hypothesis_v1',activation_status='not_activated',
                  scope='offline_A_only_constant_height',method='coordinate-wise median of training ray intersections',
                  fit_capture=TRAIN,holdout_captures=[name for name in groups if name != TRAIN],
                  original_A_mm=original.tolist(),hypothesis_A_mm=candidate.tolist(),delta_mm=(candidate-original).tolist(),
                  training_world_points_mm=training_world.tolist(),summary=summary,observations=results,
                  annotation_sensitivity=sensitivity,input_sha256=hashes,
                  checks=dict(profile_bindings_match=True,no_fit_holdout_overlap=True,synthetic_recovery_passed=True,
                              original_projection_reproduced=True,ray_plane_roundtrip_passed=True),
                  limitations=['User-reported height is approximate. Existing camera/marker pose errors are not refitted.',
                               'All labels are assistant visual estimates, not independent user ground truth.',
                               'Held-out means excluded from coordinate fitting, not newly collected or previously unseen.',
                               'Common +/-3 px label shifts are sensitivity probes, not statistical confidence intervals.',
                               'Does not validate B-D, screw torque, optical SBS alignment, or motion robustness.'])
    for path,sha in hashes.items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==sha
    write_json(output/'analysis.json',result)
    print(json.dumps(dict(original=result['original_A_mm'],hypothesis=result['hypothesis_A_mm'],delta=result['delta_mm'],
                          summary=summary,sensitivity=sensitivity)))


if __name__=='__main__':
    with patch('cv2.VideoCapture',side_effect=AssertionError('Camera access forbidden during offline analysis')):
        main()
