"""Replay three independent existing datasets, never use camera or write profiles."""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pose_replay_compare as replay
import measured_spacing_compare as capture
import recent_corner_compare as evaluator
from corner_bridge_replay import CornerBridge


class Adapter(CornerBridge):
    def update(self, timestamp, detections):
        pose, detail = super().update(timestamp, detections)
        return pose, detail['reason']


def main():
    output = ROOT / 'pose-comparison/corner-bridge-report.json'
    if output.exists():
        raise ValueError('Report exists')
    camera = replay.CameraModel.from_profile(json.loads((replay.ASSETS/'camera-profile.json').read_bytes()))
    workspace = replay.MetricWorkspace.from_dict(json.loads((replay.ASSETS/'workspace-profile.json').read_bytes()))
    eye = json.loads((replay.ASSETS/'eye-projection.json').read_bytes())
    eyes = [np.array(eye[k]).reshape(3, 4) for k in ('left_projection', 'right_projection')]
    video = json.loads((ROOT/'pose-comparison/v1-video-marker-audit.json').read_bytes())
    rows = [{**r, 'detections': {int(k): np.array(v) for k, v in r['detections'].items()}} for r in video['rows']]
    datasets = {'numeric_trace': replay.load_rows(ROOT/'pose-live-device.txt'),
                'capture_retake': capture.capture_rows(), 'success_video': rows}
    hashes = {k: hashlib.sha256((replay.ASSETS/k).read_bytes()).hexdigest() for k in replay.BINDINGS}
    assert hashes == replay.BINDINGS
    results = {}
    for name, data in datasets.items():
        result = evaluator.evaluate(data, workspace, camera, eyes, tracker_factory=Adapter)
        results[name] = result
        print(name, json.dumps(result['summary']), flush=True)
    assert hashes == {k: hashlib.sha256((replay.ASSETS/k).read_bytes()).hexdigest() for k in hashes}
    with output.open('x', encoding='utf-8') as f:
        json.dump(dict(offline_only=True, calibration_hashes=hashes, datasets=results,
                       caveats=['Partial real frames have no independent ground truth.',
                                'Masked trials and overlapping windows are correlated.',
                                'Requires an earlier accepted five-marker frame; no cold partial start.']),
                  f, indent=2, allow_nan=False)


if __name__ == '__main__':
    main()
