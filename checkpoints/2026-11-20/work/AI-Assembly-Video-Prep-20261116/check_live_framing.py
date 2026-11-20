"""Inspect eye-display coverage from this console run's numeric observations."""
import json
import sys
import urllib.request
from pathlib import Path
import cv2
import numpy as np
from server.realtime.workspace_live_preview import load_profiles
from server.realtime.workspace_projection import estimate_pose

root = Path('C:/Users/fresh/Documents/Codex')
if len(sys.argv) > 1:
    session = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))['session']
else:
    with urllib.request.urlopen('http://127.0.0.1:8764/console/status', timeout=3) as response:
        status = json.load(response)
    session = status['session_id']
if not session:
    raise SystemExit('No active session')
config = json.loads((root / 'beast-pose-continuation-20261116/presentation-rms32.json').read_text(encoding='utf-8-sig'))
candidate = json.loads((root / 'beast-reference-return-20261114/candidate-ABCD-joint-unverified.json').read_text(encoding='utf-8-sig'))
box = json.loads((root / 'beast-reference-return-20261114/rounded-box-124mm.json').read_text(encoding='utf-8-sig'))
camera, workspace, binding = load_profiles(config['camera_profile'], config['workspace_profile'])
for key in ('camera_profile_sha256', 'workspace_profile_sha256'):
    assert candidate[key] == box[key] == binding[key]
source = root / 'beast-reference-return-20261114/filming-green-sessions' / session / 'results.jsonl'
rows = source.read_text(encoding='utf-8-sig').splitlines()
for line in reversed(rows[-30:]):
    try:
        row = json.loads(line)
    except json.JSONDecodeError:
        continue
    d = row['presentation_diagnostics']
    if d['analysis_status'] != 'tracking':
        continue
    try:
        pose = estimate_pose({int(k): v for k, v in d['detected_corners_px'].items()}, workspace,
                             camera, d['image_size'], max_rms_px=3.2, max_point_error_px=5.)
    except ValueError:
        continue
    rotation = cv2.Rodrigues(pose.rvec)[0]
    points = dict(workspace.targets)
    points.update({f'box_{i}': p for i, p in enumerate(np.array(box['vertices_mm']).reshape(-1, 3))})
    result = {'session': session, 'frame_id': row['frame_id'], 'stage': row['state'], 'points': {}}
    for name, p in points.items():
        xyz = rotation @ p + pose.tvec.reshape(3)
        eyes = []
        for eye in ('left', 'right'):
            q = np.array(candidate[eye + '_projection']).reshape(3, 4) @ np.r_[xyz, 1.]
            uv = q[:2] / q[2]
            eyes.append({'xy': uv.round(1).tolist(), 'inside': bool(q[2] > 0 and 0 <= uv[0] < 1920 and 0 <= uv[1] < 1080)})
        result['points'][name] = eyes
    print(json.dumps(result, indent=2))
    break
else:
    print('No accepted pose in last 30 frames; not a visibility pass.')
