"""Generate camera-free Android parity fixtures from past-only replay cases."""
import json
import sys
from pathlib import Path
import numpy as np
import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pose_replay_compare as replay
from tracking_continuity import ReferenceBank
from learned_corner_tracker import LearnedCornerTracker,MultiWindowCorners


def main():
    camera = replay.CameraModel.from_profile(json.loads((replay.ASSETS/'camera-profile.json').read_bytes()))
    workspace = replay.MetricWorkspace.from_dict(json.loads((replay.ASSETS/'workspace-profile.json').read_bytes()))
    source = json.loads((ROOT/'pose-comparison/guarded-bridge-report.json').read_bytes())
    mode=sys.argv[1] if len(sys.argv)>1 else 'bank'
    learned=mode=='corners'
    report = json.loads((ROOT/f"pose-comparison/continuity-{mode}{'-full' if mode=='multi' else ''}-report.json").read_bytes())['results']
    fixtures = []
    for name, result in report.items():
        dataset, side = name.split('/')
        rows = source['datasets'][dataset]['rows']
        visible = (0, 1, 4) if side == 'right_hidden' else (1, 2, 5)
        added = [r for r in result['records'] if not r['previous_valid'] and r['comparison']][:4]
        rejected = [r for r in result['records'] if r['comparison'] is None][:3]
        for record in added+rejected:
            anchor, last = record['anchor'], record['index']
            start_ms = rows[anchor]['frame_ms']-30000
            tracker = MultiWindowCorners(workspace,camera) if mode=='multi' else LearnedCornerTracker(workspace, camera) if learned else ReferenceBank(workspace, camera)
            observations = []
            for i, row in enumerate(rows[:last+1]):
                if row['frame_ms'] < start_ms:
                    continue
                detections = {int(k): np.array(v) for k, v in row['detections'].items()
                              if i <= anchor or int(k) in visible}
                # Android monotonic clock uses integer milliseconds.
                ms = round(row['frame_ms'])
                pose, detail = tracker.update(ms, detections)
                observations.append(dict(time_ms=ms, detections={str(k): v.tolist() for k, v in detections.items()}))
            fixtures.append(dict(name=name, observations=observations, valid=pose is not None,
                method=detail.get('method'), camera_targets={} if pose is None else
                {k: (cv2.Rodrigues(pose.rvec)[0] @ p+pose.tvec.reshape(3)).tolist() for k, p in workspace.targets.items()}))
    filename='multi-corner' if mode=='multi' else 'learned-corner' if learned else 'reference-bank'
    output = ROOT/f'app/src/androidTest/assets/{filename}-fixtures.json'
    with output.open('x', encoding='utf-8') as f:
        json.dump(fixtures, f, allow_nan=False)
    print('fixtures', len(fixtures), 'valid', sum(f['valid'] for f in fixtures))


if __name__ == '__main__':
    main()
