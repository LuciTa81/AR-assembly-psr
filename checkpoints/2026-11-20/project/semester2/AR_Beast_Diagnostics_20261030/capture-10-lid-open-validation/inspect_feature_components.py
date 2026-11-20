from pathlib import Path
import json
import numpy as np
import cv2
from server.realtime.workspace_live_preview import load_profiles
from server.realtime.workspace_roi_candidate import sample_region
from server.realtime.roi_realtime import preprocess
root=Path('C:/Users/fresh/Downloads/AR_Beast_Diagnostics_20261030/capture-10-lid-open-validation')
r=json.loads((root/'validation/analysis.json').read_text())
p=json.loads((root.parent/'lid-rim-offline-01/results/analysis.json').read_text())
base=Path('C:/Users/fresh/AppData/Local/ARAssembly/beast-mvp')
camera,w,_=load_profiles(base/'camera_calibration/combined-review-20260927T065914Z-89414bbe/candidate.json',base/'workspace_registration/comfort-layout-20261006-v1/workspace-candidate.json')
quad=np.array(r['regions_mm']['right_BD'])
def crop(item):
    im=cv2.imdecode(np.frombuffer(Path(item['source']).read_bytes(),np.uint8),cv2.IMREAD_COLOR)
    return sample_region(im,camera,item['pose'],quad)[1]
refs={k:crop(item) for k,item in p['inputs'].items()}
rows=[]
for s in r['samples']:
    if s['reference_agreement']=='unusable': continue
    c=crop(s)
    v=preprocess(c)
    row=dict(frame=s['frame_id'],gray_mean=float(cv2.cvtColor(c,cv2.COLOR_BGR2GRAY).mean()))
    for k,ref in refs.items():
        d=np.abs(v-preprocess(ref))
        row[k]=dict(equalized_gray_mae=float(d[:4096].mean()),weighted_edge_mae=float(d[4096:].mean()),
                    raw_gray_mae=float(np.abs(cv2.cvtColor(c,cv2.COLOR_BGR2GRAY).astype(float)-cv2.cvtColor(ref,cv2.COLOR_BGR2GRAY)).mean())/255)
    rows.append(row)
print(json.dumps(dict(scope='right-band feature decomposition, diagnostic only',reference_gray_means={k:float(cv2.cvtColor(ref,cv2.COLOR_BGR2GRAY).mean()) for k,ref in refs.items()},samples=rows,limitation='Components are not new decision rules. Geometry, viewpoint and blur are not experimentally isolated.')))

