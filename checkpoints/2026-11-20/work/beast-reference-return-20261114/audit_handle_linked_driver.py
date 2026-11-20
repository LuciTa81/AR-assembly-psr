"""Replay saved detector boxes and source-frame poses; no camera or model inference."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import yaml
from run_neutral_d_server import ROOT
from compare_neutral_recovery import trace

sys.path.insert(0, str(ROOT))
from server.realtime.realtime_replay import validate_session
from server.realtime.workspace_live_preview import load_profiles
from server.realtime.workspace_projection import estimate_pose
from server.realtime.yolo_realtime import RealtimeYoloAnalyzer, MetricToolPlane


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(s) for s in (args.session/'results.jsonl').read_text(encoding='utf-8').splitlines()]
    config = yaml.safe_load((args.session/'config_used.yaml').read_text(encoding='utf-8'))
    exact = validate_session(args.session)
    presentation = json.loads((ROOT/'outputs/demo/presentation.json').read_text(encoding='utf-8'))
    camera, workspace, meta = load_profiles(presentation['camera_profile'], presentation['workspace_profile'])
    plane = MetricToolPlane(camera, workspace)
    before = RealtimeYoloAnalyzer(False, '', '', metric_plane=plane,
        nested_driver_dedup=config['yolo'].get('nested_driver_dedup', False))
    after = RealtimeYoloAnalyzer(False, '', '', metric_plane=plane,
        nested_driver_dedup=config['yolo'].get('nested_driver_dedup', False), handle_linked_driver=True)
    before.centers = after.centers = dict(plane.centers)
    image = np.zeros((camera.image_size[1], camera.image_size[0], 3), np.uint8)
    classes = ['driver', 'handle', 'screw']
    by_frame = {r['frame_id']: r for r in rows}
    changed, cached, candidate = [], {}, deepcopy(rows)
    for row, revised in zip(rows, candidate):
        if not row['filter_input']['evidence_valid']:
            continue
        source_id = row['filter_input']['observation_id']
        if source_id not in cached:
            diag = by_frame[source_id]['presentation_diagnostics']
            for key in ('camera_profile_sha256', 'workspace_profile_sha256'):
                assert diag[key] == meta[key], (args.session.name, key)
            pose = estimate_pose({int(k): np.array(v) for k, v in diag['detected_corners_px'].items()},
                                 workspace, camera, camera.image_size)
            matrix = plane.homography(dict(received_at=1., analysis=dict(status='tracking',
                rvec=pose.rvec.ravel().tolist(), tvec_mm=pose.tvec.ravel().tolist())), 1.)
            assert matrix is not None
            boxes = [SimpleNamespace(cls=np.array([classes.index(d['class'])]),
                conf=np.array([d['confidence']]),
                xyxy=np.array([[d[k] for k in ('x1','y1','x2','y2')]])) for d in row['yolo_detections']]
            prediction = SimpleNamespace(boxes=boxes, names=dict(enumerate(classes)))
            before.model = after.model = SimpleNamespace(predict=lambda **_: [prediction])
            old = before._process(source_id, image, matrix).features
            new = after._process(source_id, image, matrix).features
            cached[source_id] = old, new
        old, new = cached[source_id]
        original = row['filter_input']['features']
        for key, value in old.items():
            if key != 'yolo_age_frames':
                np.testing.assert_allclose(value, original[key], atol=.0002, rtol=.00001,
                                           err_msg=f'{args.session.name} frame {row["frame_id"]} {key}')
        revised['filter_input']['features'].update({k:v for k,v in new.items() if k != 'yolo_age_frames'})
        if new.get('driver_unlinked_candidates', 0):
            changed.append(dict(frame=row['frame_id'], source=source_id,
                old_count=old['driver_count'], new_count=new['driver_count'],
                old_score_d=old['tool_score_d'], new_score_d=new['tool_score_d']))
    original_trace, candidate_trace = trace(rows, config), trace(candidate, config)
    def summarize(details):
        return dict(phases=dict(Counter(r['phase'] for r in details)),
            reasons=dict(Counter(r['reason'] for r in details if r['phase']=='PAUSED')),
            first_hold=next((r['frame'] for r in details if r['active_armed']), None),
            release_timer_frames=[r['frame'] for r in details if r['release_started_at'] is not None],
            transitions=[dict(frame=r['frame'],event=r['transition']) for r in details if r['transition']])
    transition_context = []
    for i, (a,b) in enumerate(zip(original_trace,candidate_trace)):
        if a['transition'] != b['transition']:
            transition_context.append([dict(frame=candidate[j]['frame_id'],
                input=candidate[j]['filter_input'], trace=candidate_trace[j])
                for j in range(max(0,i-8),i+1)])
    manifest = json.loads((Path(__file__).parent/'poll-protected-hashes-after.json').read_text(encoding='utf-8-sig'))
    assert all(hashlib.sha256(Path(r['Path']).read_bytes()).hexdigest().upper() == r['Hash'].upper() for r in manifest)
    report = dict(session=args.session.name, frames=len(rows), exact_original_replay=exact,
        unique_reprojected_observations=len(cached), baseline_features_match=True,
        scope='Single physical tool; fixed recorded actions; source-frame geometry verified. Not new live evidence.',
        changed=changed, baseline=summarize(original_trace), candidate=summarize(candidate_trace),
        changed_transition_context=transition_context, protected_unchanged=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(json.dumps({k:v for k,v in report.items() if k not in ('changed','changed_transition_context')},
                     ensure_ascii=False, indent=2))
    print('changed_frames',len(changed))


if __name__ == '__main__':
    main()
