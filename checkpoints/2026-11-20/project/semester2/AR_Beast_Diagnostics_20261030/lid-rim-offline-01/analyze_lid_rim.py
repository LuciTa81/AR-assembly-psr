"""Fixed rim bands on two saved photographs; no camera or recognition changes."""
from pathlib import Path
import hashlib
import json
from unittest.mock import patch
import cv2
import numpy as np
from server.realtime.camera_calibration import write_json
from server.realtime.roi_realtime import distance
from server.realtime.workspace_live_preview import analyze_frame, load_profiles
from server.realtime.workspace_roi_candidate import roi_quads, sample_region, _save_png

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent
PROFILE = Path('C:/Users/fresh/AppData/Local/ARAssembly/beast-mvp')
CAMERA = PROFILE / 'camera_calibration/combined-review-20260927T065914Z-89414bbe/candidate.json'
WORKSPACE = PROFILE / 'workspace_registration/comfort-layout-20261006-v1/workspace-candidate.json'
COLORS = [(220, 180, 0), (30, 180, 240), (220, 120, 220), (80, 210, 80), (255, 170, 70)]


def rim_regions(workspace):
    quads = {'center': roi_quads(workspace)['lid_surface']}
    center = np.mean(list(workspace.targets.values()), axis=0)
    # Fixed 12 mm bands; exclude 15% at both ends, before inspecting differences.
    for name, pair in [('back_AB', 'AB'), ('right_BD', 'BD'), ('front_DC', 'DC'), ('left_CA', 'CA')]:
        a, b = [workspace.targets[p] for p in pair]
        delta = b - a
        tangent = delta / np.linalg.norm(delta)
        inward = np.array([-tangent[1], tangent[0], 0.])
        if np.dot(inward, center - (a + b) / 2) < 0:
            inward = -inward
        start, end = a + .15 * delta, b - .15 * delta
        quad = np.array([start - 6 * inward, end - 6 * inward, end + 6 * inward, start + 6 * inward])
        np.testing.assert_allclose(np.linalg.norm(quad[3]-quad[0]), 12.)
        np.testing.assert_allclose(np.linalg.norm(quad[1]-quad[0]), .7*np.linalg.norm(delta))
        np.testing.assert_allclose(quad[:, 2], a[2])
        assert np.dot(quad[3]-quad[0], center-(a+b)/2) > 0
        quads[name] = quad
    return quads


def label(image, text, xy, color=(30, 30, 30), size=.55):
    cv2.putText(image, text, xy, cv2.FONT_HERSHEY_SIMPLEX, size, color, 1, cv2.LINE_AA)


def main():
    camera, workspace, metadata = load_profiles(CAMERA, WORKSPACE)
    previous = json.loads((BASE/'lid-open-closed-check-20261030.json').read_text(encoding='utf-8'))
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (CAMERA, WORKSPACE)}
    quads, items, rows = rim_regions(workspace), {}, []
    for condition in ('open', 'closed'):
        expected = previous['samples'][condition]
        path = Path(expected['source'])
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        assert digest == expected['source_sha256'], 'Source changed'
        for key in ('camera_profile_sha256', 'workspace_profile_sha256'):
            assert metadata[key] == expected[key], 'Profile changed'
        before[path] = digest
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        state = analyze_frame(image, camera, workspace, corner_refinement='apriltag')
        assert state['status'] == 'tracking', state['reason']
        reports, crops, visual = {}, {}, image.copy()
        for index, (name, quad) in enumerate(quads.items()):
            report, crop = sample_region(image, camera, state, quad)
            assert report['valid'] and crop is not None, (condition, name, report['reason'])
            reports[name], crops[name] = report, crop
            points = np.rint(report['boundary_raw_px']).astype(np.int32)
            cv2.polylines(visual, [points], True, (20, 20, 20), 4, cv2.LINE_AA)
            cv2.polylines(visual, [points], True, COLORS[index], 2, cv2.LINE_AA)
        cv2.rectangle(visual, (0, 0), (1279, 38), (15, 15, 15), -1)
        label(visual, f'{condition.upper()} | SAVED IMAGE | FIXED 12mm RIM BANDS | NOT ACTIVE', (10, 25), (255, 255, 255))
        items[condition] = dict(source=str(path), source_sha256=digest, pose=state, regions=reports, crops=crops, visual=visual)
    for name in quads:
        row = dict(region=name, feature_distance=distance(items['open']['crops'][name], items['closed']['crops'][name]))
        for condition, item in items.items():
            gray = cv2.cvtColor(item['crops'][name], cv2.COLOR_BGR2GRAY)
            p = np.asarray(item['regions'][name]['corners_raw_px'])
            row[condition] = dict(gray_mean=float(gray.mean()), gray_std=float(gray.std()),
                projected_length_px=float((np.linalg.norm(p[1]-p[0])+np.linalg.norm(p[2]-p[3]))/2),
                projected_width_px=float((np.linalg.norm(p[3]-p[0])+np.linalg.norm(p[2]-p[1]))/2))
        rows.append(row)
    canvas = np.full((790, 1080, 3), 245, np.uint8)
    label(canvas, 'FIXED REGIONS: OPEN / CLOSED | same 60mm plane | no classifier fitted', (18, 27))
    label(canvas, 'OPEN', (285, 61))
    label(canvas, 'CLOSED', (735, 61))
    for index, (name, quad) in enumerate(quads.items()):
        y = 78 if index == 0 else 315+(index-1)*110
        label(canvas, name, (18, y+20), COLORS[index])
        label(canvas, f'distance {rows[index]["feature_distance"]:.3f}', (18, y+43), size=.45)
        width = 200 if index == 0 else 400
        height = round(width*np.linalg.norm(quad[3]-quad[0])/np.linalg.norm(quad[1]-quad[0]))
        for column, condition in enumerate(('open', 'closed')):
            x = 190+column*445
            crop = cv2.resize(items[condition]['crops'][name], (width, height), interpolation=cv2.INTER_NEAREST)
            canvas[y:y+height, x:x+width] = crop
    label(canvas, 'Distance is NOT probability or accuracy. 1 photo per state; viewpoints differ.', (18, 770))
    output = ROOT/'results'
    output.mkdir(exist_ok=False)
    for condition, item in items.items():
        _save_png(output/f'{condition}-regions.png', item['visual'])
    _save_png(output/'comparison.png', canvas)
    result = dict(schema_version='beast_lid_rim_offline_pair_v1', activation_status='not_activated',
        scope='saved_images_only', raw_images_per_condition=1, crop_size=[64, 64],
        band_width_mm=12, endpoint_trim_fraction=.15, height_mm=60, corner_refinement='apriltag',
        camera_profile_sha256=metadata['camera_profile_sha256'], workspace_profile_sha256=metadata['workspace_profile_sha256'],
        camera_position_change_mm=previous['camera_position_change_mm'],
        regions_mm={name: q.tolist() for name, q in quads.items()}, metrics=rows,
        inputs={condition: {key: item[key] for key in ('source', 'source_sha256', 'pose', 'regions')} for condition, item in items.items()},
        limitations=['Bands follow registered screw centers, not independently measured lid edges.',
                     'User-supplied open/closed labels; this script does not classify state.',
                     'Same two photos as prior comparison; no independent validation.',
                     'Viewpoint, transparency, blur and registration uncertainty confound the differences.',
                     'Larger distance does not establish a better detector; no thresholds/templates activated.'])
    for path, digest in before.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, 'Input modified'
    write_json(output/'analysis.json', result)
    print(json.dumps(dict(output=str(output), metrics=rows, camera_open_calls=0, inputs_unchanged=True)))


if __name__ == '__main__':
    with patch('cv2.VideoCapture', side_effect=AssertionError('Camera forbidden in offline analysis')):
        main()

