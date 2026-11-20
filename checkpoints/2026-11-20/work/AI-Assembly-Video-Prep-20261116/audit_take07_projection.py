"""Replay saved numeric marker evidence without camera or calibration changes."""
import json
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np

from server.realtime.workspace_live_preview import load_profiles
from server.realtime.workspace_projection import estimate_pose

ROOT = Path('C:/Users/fresh/Documents/Codex')
config = json.loads((ROOT / 'beast-pose-continuation-20261116/presentation-rms32.json').read_text(encoding='utf-8-sig'))
candidate = json.loads((ROOT / 'beast-reference-return-20261114/candidate-ABCD-joint-unverified.json').read_text(encoding='utf-8-sig'))
camera, workspace, binding = load_profiles(config['camera_profile'], config['workspace_profile'])
for key in ('camera_profile_sha256', 'workspace_profile_sha256'):
    assert candidate[key] == binding[key]
matrices = [np.array(candidate[e + '_projection']).reshape(3, 4) for e in ('left', 'right')]
source = ROOT / 'beast-reference-return-20261114/filming-green-sessions/viture_aruco_rt_20261116_024431_3bf80d920992/results.jsonl'
counts = defaultdict(Counter)
pixels = defaultdict(list)
for line in source.read_text(encoding='utf-8-sig').splitlines():
    row = json.loads(line)
    stage = row['state']
    if stage not in ('S2', 'S3', 'S4', 'S5'):
        continue
    d = row['presentation_diagnostics']
    counts[stage]['all_frames'] += 1
    if d['analysis_status'] != 'tracking':
        continue
    assert all(d[k] == binding[k] for k in ('camera_profile_sha256', 'workspace_profile_sha256'))
    try:
        pose = estimate_pose({int(k): v for k, v in d['detected_corners_px'].items()}, workspace,
                             camera, d['image_size'], max_rms_px=3.2, max_point_error_px=5.)
    except ValueError:
        counts[stage]['replay_rejected'] += 1
        continue
    target = 'ABCD'[int(stage[1:]) - 2]
    xyz = cv2.Rodrigues(pose.rvec)[0] @ workspace.targets[target] + pose.tvec.reshape(3)
    projected = [m @ np.r_[xyz, 1.] for m in matrices]
    uv = np.array([p[:2] / p[2] for p in projected])
    pixels[stage].append(uv)
    valid = all(p[2] > 1e-9 and 0 <= q[0] < 1920 and 0 <= q[1] < 1080 for p, q in zip(projected, uv))
    counts[stage]['in_view' if valid else 'out_of_view'] += 1
    if np.any(uv[:, 1] < 0):
        counts[stage]['above_top'] += 1
output = {}
for stage, count in counts.items():
    values = np.array(pixels[stage])
    output[stage] = dict(count, median_left_right_xy=np.median(values, axis=0).round(1).tolist(),
                         min_left_right_xy=values.min(axis=0).round(1).tolist(),
                         max_left_right_xy=values.max(axis=0).round(1).tolist())
destination = ROOT / 'AI-Assembly-Video-Prep-20261116/recordings/20261116_024507_take07/projection-audit.json'
destination.write_text(json.dumps(output, indent=2), encoding='utf-8')
print(json.dumps(output, indent=2))
