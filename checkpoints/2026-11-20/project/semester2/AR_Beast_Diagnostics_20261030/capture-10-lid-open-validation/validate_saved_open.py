"""Compare every new saved photo against frozen references; never classify live state."""
from pathlib import Path
from collections import Counter
from unittest.mock import patch
import hashlib
import json
import cv2
import numpy as np
from server.realtime.camera_calibration import write_json
from server.realtime.roi_realtime import distance
from server.realtime.workspace_live_preview import load_profiles, analyze_frame
from server.realtime.workspace_roi_candidate import sample_region, _save_png

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent
PROFILE = Path('C:/Users/fresh/AppData/Local/ARAssembly/beast-mvp')
CAMERA = PROFILE/'camera_calibration/combined-review-20260927T065914Z-89414bbe/candidate.json'
WORKSPACE = PROFILE/'workspace_registration/comfort-layout-20261006-v1/workspace-candidate.json'


def text(image, value, xy, scale=.5):
    cv2.putText(image, value, xy, cv2.FONT_HERSHEY_SIMPLEX, scale, (20, 20, 20), 1, cv2.LINE_AA)


def main():
    previous = json.loads((BASE/'lid-rim-offline-01/results/analysis.json').read_text())
    session = json.loads((ROOT/'session.json').read_text())
    camera, workspace, metadata = load_profiles(CAMERA, WORKSPACE)
    for key in ('camera_profile_sha256', 'workspace_profile_sha256'):
        assert previous[key] == session[key] == metadata[key], 'Profile changed'
    quads = {k: np.array(v) for k, v in previous['regions_mm'].items()}
    refs, before = {}, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (CAMERA, WORKSPACE)}
    for condition, item in previous['inputs'].items():
        path = Path(item['source'])
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        assert digest == item['source_sha256']
        before[path] = digest
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        refs[condition] = {}
        for name, quad in quads.items():
            report, crop = sample_region(image, camera, item['pose'], quad)
            assert report['valid'] and crop is not None
            refs[condition][name] = crop
    sources = sorted(ROOT.glob('frame-*/raw.png'))
    assert len(sources) == 10, 'Expected all ten captured raw photographs'
    overview = np.full((1530, 960, 3), 245, np.uint8)
    strips = np.full((1120, 1100, 3), 245, np.uint8)
    text(strips, 'RIGHT BD                                 BACK AB | frozen references, no threshold', (240, 26))
    for row, condition in enumerate(('open', 'closed')):
        y = 42 + row*86
        text(strips, 'REF '+condition.upper(), (12, y+24))
        for col, name in enumerate(('right_BD', 'back_AB')):
            x = 240 + col*425
            strips[y:y+60, x:x+400] = cv2.resize(refs[condition][name], (400, 60), interpolation=cv2.INTER_NEAREST)
    results = []
    for index, path in enumerate(sources):
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        before[path] = digest
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        state = analyze_frame(image, camera, workspace, corner_refinement='apriltag')
        measurements, crops = {}, {}
        for name, quad in quads.items():
            report, crop = sample_region(image, camera, state, quad)
            row = dict(valid=report['valid'], reason=report['reason'])
            if crop is not None:
                d_open, d_closed = distance(crop, refs['open'][name]), distance(crop, refs['closed'][name])
                row.update(distance_to_open=d_open, distance_to_closed=d_closed,
                           open_margin=d_closed-d_open,
                           nearer='open' if d_open < d_closed else 'closed' if d_closed < d_open else 'tie')
                crops[name] = crop
            measurements[name] = row
        selected = [measurements[name] for name in ('right_BD', 'back_AB')]
        if not all(row['valid'] for row in selected):
            agreement = 'unusable'
        elif all(row['nearer'] == 'open' for row in selected):
            agreement = 'both_nearer_open'
        elif all(row['nearer'] == 'closed' for row in selected):
            agreement = 'both_nearer_closed'
        else:
            agreement = 'mixed_or_tied'
        results.append(dict(source=str(path), source_sha256=digest, frame_id=int(path.parent.name.split('-')[1]),
                            pose=state, regions=measurements, reference_agreement=agreement))
        y, x = (index//2)*306, (index%2)*480
        text(overview, f'{path.parent.name} | user-labelled OPEN | {state["status"]}', (x+8, y+22), .45)
        overview[y+30:y+300, x:x+480] = cv2.resize(image, (480, 270))
        y = 214 + index*86
        text(strips, path.parent.name, (12, y+22))
        for col, name in enumerate(('right_BD', 'back_AB')):
            x = 240 + col*425
            if name in crops:
                strips[y:y+60, x:x+400] = cv2.resize(crops[name], (400, 60), interpolation=cv2.INTER_NEAREST)
                text(strips, f'open margin {measurements[name]["open_margin"]:+.3f}', (x, y+76), .45)
            else:
                text(strips, 'POSE / ROI UNAVAILABLE', (x, y+30))
    events = [json.loads(s) for s in (ROOT/'frames.jsonl').read_text().splitlines() if s]
    frames = [e for e in events if e.get('event') == 'frame']
    result = dict(schema_version='beast_lid_open_saved_validation_v1', activation_status='not_activated',
        label='open, supplied by user before capture; confirm against overview',
        reference_policy='frozen; current validation photos are not new references',
        regions_mm=previous['regions_mm'], band_width_mm=12, endpoint_trim_fraction=.15,
        camera_profile_sha256=metadata['camera_profile_sha256'], workspace_profile_sha256=metadata['workspace_profile_sha256'],
        live_corner_refinement=session['corner_refinement'], offline_corner_refinement='apriltag',
        reference_sources={condition: {k: v[k] for k in ('source', 'source_sha256')} for condition, v in previous['inputs'].items()},
        live_frame_counts=dict(Counter(e['status'] for e in frames)),
        live_stale_events=sum(e['status']=='stale' for e in events),
        observed_seconds=frames[-1]['observed_at_monotonic']-frames[0]['observed_at_monotonic'],
        saved_raw_count=len(sources), reference_agreement_counts=dict(Counter(r['reference_agreement'] for r in results)),
        samples=results, limitations=['Ten correlated photographs from one short open session, not ten independent experiments.',
                                     'Nearest-reference agreement is not a validated live classifier or confidence.',
                                     'Unusable frames are retained and reported, not counted as correct.',
                                     'No thresholds, reference templates, state transitions or eye calibration changed.'])
    for path, digest in before.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    output = ROOT/'validation'
    output.mkdir(exist_ok=False)
    _save_png(output/'overview.png', overview)
    _save_png(output/'rim-comparison.png', strips)
    write_json(output/'analysis.json', result)
    print(json.dumps(dict(output=str(output), counts=result['reference_agreement_counts'],
        live=result['live_frame_counts'], stale=result['live_stale_events'],
        samples=[dict(frame_id=r['frame_id'], status=r['pose']['status'], agreement=r['reference_agreement'],
                      selected={n:r['regions'][n] for n in ('right_BD','back_AB')}) for r in results])))


if __name__ == '__main__':
    with patch('cv2.VideoCapture', side_effect=AssertionError('Camera forbidden during validation')):
        main()

