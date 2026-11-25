"""Extract numeric observations from an existing video; no camera or image output."""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pose_replay_compare as replay
import session_corner_replay as candidate


def main():
    video=ROOT/'baseline/exhibition-v1-20261125/success-20261125-1756.mp4'
    output=ROOT/'pose-comparison/v1-video-marker-audit.json'
    if output.exists():raise ValueError('Report exists')
    paths=[video,*(replay.ASSETS/name for name in replay.BINDINGS)]
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    camera=replay.CameraModel.from_profile(json.loads((replay.ASSETS/'camera-profile.json').read_bytes()))
    workspace=replay.MetricWorkspace.from_dict(json.loads((replay.ASSETS/'workspace-profile.json').read_bytes()))
    eye=json.loads((replay.ASSETS/'eye-projection.json').read_bytes())
    eyes=[np.array(eye[k]).reshape(3,4) for k in ('left_projection','right_projection')]
    params=cv2.aruco.DetectorParameters()
    params.adaptiveThreshWinSizeMin=3;params.adaptiveThreshWinSizeMax=53;params.adaptiveThreshWinSizeStep=4
    params.minMarkerPerimeterRate=.015;params.maxMarkerPerimeterRate=4
    params.polygonalApproxAccuracyRate=.03;params.cornerRefinementMethod=cv2.aruco.CORNER_REFINE_SUBPIX
    detector=cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50),params)
    capture=cv2.VideoCapture(str(video));rows=[];next_ms=0
    try:
        while True:
            ok,image=capture.read()
            if not ok:break
            ms=capture.get(cv2.CAP_PROP_POS_MSEC)
            if ms<next_ms:continue
            next_ms=ms+500
            assert image.shape[:2]==(720,1280)
            corners,ids,_=detector.detectMarkers(cv2.cvtColor(image,cv2.COLOR_BGR2GRAY))
            found={}
            duplicate=False
            if ids is not None:
                for key,quad in zip(ids.flatten(),corners):
                    key=int(key)
                    if key not in workspace.markers:continue
                    duplicate|=key in found
                    found[key]=quad.reshape(4,2).astype(float)
            if duplicate:continue
            pose,reason=replay.baseline(found,workspace,camera)
            rows.append(dict(frame_ms=ms,detections=found,valid=pose is not None,reason=reason))
    finally:capture.release()
    result=candidate.evaluate(rows,workspace,camera,eyes)
    summary=dict(sampled_frames=len(rows),combinations=dict(Counter(','.join(map(str,sorted(r['detections']))) for r in rows)),
                 baseline_reasons=dict(Counter(r['reason'] for r in rows)))
    serial=[{**r,'detections':{str(k):v.tolist() for k,v in r['detections'].items()}} for r in rows]
    assert hashes=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    with output.open('x',encoding='utf-8') as f:
        json.dump(dict(offline_only=True,compressed_video=True,opencv=cv2.__version__,hashes=hashes,
                       summary=summary,rows=serial,candidate=result),f,indent=2,allow_nan=False)
    print(json.dumps(summary))
    for n,m in result['summary']['masked'].items():
        print(n,json.dumps({k:v for k,v in m.items() if k!='reasons'}))


if __name__=='__main__':main()
