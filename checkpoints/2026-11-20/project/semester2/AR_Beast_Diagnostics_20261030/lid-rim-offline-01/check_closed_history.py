from pathlib import Path
from unittest.mock import patch
import runpy, json, hashlib
import numpy as np
import cv2
from server.realtime.workspace_live_preview import load_profiles, analyze_frame
from server.realtime.workspace_roi_candidate import sample_region
from server.realtime.roi_realtime import distance
root=Path('C:/Users/fresh/Downloads/AR_Beast_Diagnostics_20261030/lid-rim-offline-01')
mod=runpy.run_path(str(root/'analyze_lid_rim.py'))
camera,workspace,meta=load_profiles(mod['CAMERA'],mod['WORKSPACE'])
quads=mod['rim_regions'](workspace)
original=json.loads((root/'results/analysis.json').read_text())
refs={}
for label,row in original['inputs'].items():
    im=cv2.imdecode(np.frombuffer(Path(row['source']).read_bytes(),np.uint8),cv2.IMREAD_COLOR)
    refs[label]={name:sample_region(im,camera,row['pose'],quad)[1] for name,quad in quads.items()}
history=root.parent/'capture-07-live-roi'
session=json.loads((history/'session.json').read_text())
assert all(session[k]==meta[k] for k in ['camera_profile_sha256','workspace_profile_sha256'])
rows=[]
with patch('cv2.VideoCapture',side_effect=AssertionError('No camera')):
    for fid in [51,76,101]:
        path=history/f'frame-{fid:06d}'/'raw.png'
        data=path.read_bytes()
        im=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_COLOR)
        pose=analyze_frame(im,camera,workspace,corner_refinement='apriltag')
        row=dict(source=str(path),source_sha256=hashlib.sha256(data).hexdigest(),label='closed (visual review)',pose=pose,regions={})
        for name,quad in quads.items():
            report,crop=sample_region(im,camera,pose,quad)
            row['regions'][name]=dict(valid=report['valid'],reason=report['reason'])
            if crop is not None:
                row['regions'][name].update(distance_to_open_ref=distance(crop,refs['open'][name]),distance_to_closed_ref=distance(crop,refs['closed'][name]))
        rows.append(row)
out=dict(scope='closed-only historical sanity check, not accuracy evaluation',camera_profile_sha256=meta['camera_profile_sha256'],workspace_profile_sha256=meta['workspace_profile_sha256'],samples=rows,limitations=['No independent open validation image','History includes loose screws inside the box unlike the current reference pair','Same fixed bands and APRILTAG method; no parameter tuning'])
print(json.dumps(out))

