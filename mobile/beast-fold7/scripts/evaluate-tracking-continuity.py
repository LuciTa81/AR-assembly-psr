"""Replay saved observations and images; never opens a live camera."""
import json
import sys
from pathlib import Path
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pose_replay_compare as replay
from tracking_continuity import ReferenceBank, FlowBridge
from corner_bridge_replay import CornerBridge
from learned_corner_tracker import LearnedCornerTracker,MultiWindowCorners


def load():
    camera = replay.CameraModel.from_profile(json.loads((replay.ASSETS/'camera-profile.json').read_bytes()))
    workspace = replay.MetricWorkspace.from_dict(json.loads((replay.ASSETS/'workspace-profile.json').read_bytes()))
    eye = json.loads((replay.ASSETS/'eye-projection.json').read_bytes())
    eyes = [np.array(eye[k]).reshape(3, 4) for k in ('left_projection', 'right_projection')]
    return workspace, camera, eyes


def single(workspace, camera):
    return CornerBridge(workspace, camera, max_age_ms=30000,
                        conservative_three=True, retain_reference_on_loss=True)


def bank_trials(workspace, camera, eyes, stride=5, learned=False, multi=False):
    source = json.loads((ROOT/'pose-comparison/guarded-bridge-report.json').read_bytes())
    results = {}
    for name, data in source['datasets'].items():
        rows = [{**r, 'detections': {int(k): np.array(v) for k, v in r['detections'].items()}}
                for r in data['rows']]
        for side, visible in [('right_hidden', (0, 1, 4)), ('left_hidden', (1, 2, 5))]:
            records = []
            for i in range(5, len(rows), stride):
                anchor = rows[i]
                reference, _ = replay.baseline(anchor['detections'], workspace, camera)
                if reference is None or len(anchor['detections']) < 5:
                    continue
                bank = MultiWindowCorners(workspace,camera) if multi else LearnedCornerTracker(workspace, camera) if learned else ReferenceBank(workspace, camera)
                old = LearnedCornerTracker(workspace,camera) if multi else ReferenceBank(workspace, camera) if learned else single(workspace, camera)
                # Only past observations populate the bank. Hidden future observations
                # are used for evaluation, never for tracking or reference refresh.
                for previous in rows[:i+1]:
                    if previous['frame_ms'] >= anchor['frame_ms']-30000:
                        bank.update(previous['frame_ms'], previous['detections'])
                        old.update(previous['frame_ms'], previous['detections'])
                for j in range(i+1, len(rows)):
                    row = rows[j]
                    age = row['frame_ms']-anchor['frame_ms']
                    if age > 30000:
                        break
                    subset = {k: v for k, v in row['detections'].items() if k in visible}
                    p, d = bank.update(row['frame_ms'], subset)
                    q, _ = old.update(row['frame_ms'], subset)
                    truth, _ = replay.baseline(row['detections'], workspace, camera)
                    if truth is None or len(row['detections']) < 5 or len(subset) != 3:
                        continue
                    records.append(dict(anchor=i, index=j, age_ms=age, reason=d['reason'],
                        previous_valid=q is not None,
                        comparison=replay.comparison(truth, p, workspace, camera, eyes)))
            added = [r for r in records if not r['previous_valid'] and r['comparison']]
            summary = dict(candidate=replay.summary(records), added=replay.summary(added),
                           previous_valid=sum(r['previous_valid'] for r in records),
                           lost=sum(r['previous_valid'] and r['comparison'] is None for r in records))
            key = name+'/'+side
            results[key] = dict(summary=summary, records=records)
            print(key, json.dumps(summary), flush=True)
    return results


def flow_trials(workspace, camera, eyes):
    params = cv2.aruco.DetectorParameters()
    params.adaptiveThreshWinSizeMin = 3
    params.adaptiveThreshWinSizeMax = 53
    params.adaptiveThreshWinSizeStep = 4
    params.minMarkerPerimeterRate = .015
    params.maxMarkerPerimeterRate = 4
    params.polygonalApproxAccuracyRate = .03
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_APRILTAG
    detector = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50), params)
    cap = cv2.VideoCapture(str(ROOT/'baseline/exhibition-v1-20261125/success-20261125-1756.mp4'))
    natural, dropout = FlowBridge(workspace, camera), FlowBridge(workspace, camera)
    tracker = ReferenceBank(workspace, camera)
    rows = []
    index = 0
    try:
        while True:
            ok, image = cap.read()
            if not ok:
                break
            ms = cap.get(cv2.CAP_PROP_POS_MSEC)
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            corners, ids, _ = detector.detectMarkers(gray)
            found = {int(k): q.reshape(4, 2).astype(float)
                     for k, q in zip([] if ids is None else ids.flatten(), corners) if int(k) in range(6)}
            pose, detail = tracker.update(ms, found)
            row = dict(index=index, frame_ms=ms, markers=len(found), marker_valid=pose is not None)
            if pose is not None:
                natural.seed(ms, gray, pose, found)
            else:
                p, d = natural.update(ms, gray, found)
                row['natural_flow_valid'] = p is not None
                row['natural_flow_reason'] = d['reason']
            # A deterministic two-frame detector outage with fresh image motion.
            if index % 10 in (6, 7):
                p, d = dropout.update(ms, gray, {})
                row['forced'] = dict(reason=d['reason'],
                    comparison=replay.comparison(pose, p, workspace, camera, eyes)
                    if pose is not None else None, valid=p is not None,
                    reference_valid=pose is not None)
            else:
                dropout.seed(ms, gray, pose, found)
            rows.append(row)
            index += 1
            if index % 200 == 0:
                print('flow frames', index, flush=True)
    finally:
        cap.release()
    forced = [r['forced'] for r in rows if 'forced' in r and r['forced']['reference_valid']]
    summary = dict(frames=len(rows), marker_valid=sum(r['marker_valid'] for r in rows),
                   natural_flow_added=sum(r.get('natural_flow_valid', False) for r in rows),
                   forced=replay.summary(forced))
    print('flow', json.dumps(summary), flush=True)
    return dict(summary=summary, records=rows)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'bank'
    stride = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    if mode not in ('bank', 'flow', 'corners', 'multi') or stride < 1:
        raise ValueError('Use bank/flow/corners/multi with positive optional anchor stride')
    suffix = '-full' if mode != 'flow' and stride == 1 else ''
    output = ROOT/f'pose-comparison/continuity-{mode}{suffix}-report.json'
    if output.exists():
        raise ValueError('Report exists')
    workspace, camera, eyes = load()
    result = bank_trials(workspace, camera, eyes, stride, mode == 'corners',mode == 'multi') if mode != 'flow' else flow_trials(workspace, camera, eyes)
    with output.open('x', encoding='utf-8') as f:
        json.dump(dict(offline_only=True, physical_ground_truth=False, results=result),
                  f, indent=2, allow_nan=False)


if __name__ == '__main__':
    main()
