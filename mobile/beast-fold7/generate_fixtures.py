"""Generate numeric fixtures from the frozen Windows implementation; no camera IO."""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent / 'AR-Assembly-Checkpoint-20261120/repository'
sys.path.insert(0, str(REPO))
from server.realtime.workspace_projection import CameraModel, MetricWorkspace, estimate_pose, project_targets

assets = ROOT / 'app/src/main/assets'
camera = CameraModel.from_profile(json.loads((assets / 'camera-profile.json').read_bytes()))
workspace = MetricWorkspace.from_dict(json.loads((assets / 'workspace-profile.json').read_bytes()))
cases = []
for name, eye in [('middle', [205, -310, 480]), ('near', [210, -210, 400]), ('side', [310, -250, 450])]:
    eye = np.array(eye, dtype=float)
    forward = np.array([205, 150, 0]) - eye
    forward /= np.linalg.norm(forward)
    right = np.cross(forward, [0, 0, 1]); right /= np.linalg.norm(right)
    down = np.cross(forward, right)
    rotation = np.vstack([right, down, forward])
    rvec = cv2.Rodrigues(rotation)[0]
    tvec = -rotation @ eye
    mapping = {}
    for marker_id, center in workspace.markers.items():
        corners = center + np.array([[-35, 35, 0], [35, 35, 0], [35, -35, 0], [-35, -35, 0]])
        px = cv2.projectPoints(corners, rvec, tvec, camera.matrix, camera.distortion)[0].reshape(4, 2)
        if (px >= 0).all() and (px < [1280, 720]).all():
            mapping[marker_id] = px
    pose = estimate_pose(mapping, workspace, camera, (1280, 720), max_rms_px=3.2)
    camera_targets = {name: (cv2.Rodrigues(pose.rvec)[0] @ point + pose.tvec.reshape(3)).tolist()
                      for name, point in workspace.targets.items()}
    cases.append(dict(name=name, detections={str(k):v.tolist() for k,v in mapping.items()},
                      targets=project_targets(pose, workspace, camera), camera_targets=camera_targets, rms=pose.rms_px))
(assets / 'pose-fixtures.json').write_text(json.dumps(cases, indent=2), encoding='utf-8')
print([(case['name'], len(case['detections']), case['rms']) for case in cases])
