"""Independent capture replay and exploratory video replay of conservative policy."""
import json
import sys
from pathlib import Path
import cv2
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pose_replay_compare as replay
import measured_spacing_compare as capture
import recent_corner_compare as evaluator
from corner_bridge_replay import CornerBridge


def main():
    age_ms=int(sys.argv[1]) if len(sys.argv)>1 else 3000
    output=ROOT/('pose-comparison/guarded-bridge-report.json' if age_ms==3000 else f'pose-comparison/guarded-bridge-{age_ms}-report.json')
    if output.exists(): raise ValueError('Report exists')
    camera=replay.CameraModel.from_profile(json.loads((replay.ASSETS/'camera-profile.json').read_bytes()))
    workspace=replay.MetricWorkspace.from_dict(json.loads((replay.ASSETS/'workspace-profile.json').read_bytes()))
    eye=json.loads((replay.ASSETS/'eye-projection.json').read_bytes())
    eyes=[np.array(eye[k]).reshape(3,4) for k in ('left_projection','right_projection')]
    raw=json.loads((ROOT/'pose-comparison/refinement-audit.json').read_bytes())['rows']['apriltag']
    video=[{**r,'detections':{int(k):np.array(v) for k,v in r['detections'].items()}} for r in raw]
    p=cv2.aruco.DetectorParameters();p.cornerRefinementMethod=cv2.aruco.CORNER_REFINE_APRILTAG
    p.adaptiveThreshWinSizeMin=3;p.adaptiveThreshWinSizeMax=53;p.adaptiveThreshWinSizeStep=4
    p.minMarkerPerimeterRate=.015;p.maxMarkerPerimeterRate=4;p.polygonalApproxAccuracyRate=.03
    detector=cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50),p)
    retake=[]
    for row in capture.capture_rows():
        gray=cv2.imread(str(capture.CAPTURE/row['image']),cv2.IMREAD_GRAYSCALE)
        if gray is None: raise ValueError('Missing image')
        quads,ids,_=detector.detectMarkers(gray)
        found={int(k):q.reshape(4,2).astype(float) for k,q in zip([] if ids is None else ids.flatten(),quads) if int(k) in workspace.markers}
        retake.append(dict(frame_ms=row['frame_ms'],detections=found))
    class Adapter(CornerBridge):
        def __init__(self,w,c): super().__init__(w,c,max_age_ms=age_ms,conservative_three=True)
        def update(self,timestamp,detections):
            pose,detail=super().update(timestamp,detections)
            return pose,detail['reason']
    results={}
    for name,rows in [('success_video',video),('independent_retake',retake)]:
        result=evaluator.evaluate(rows,workspace,camera,eyes,tracker_factory=Adapter,max_age_ms=age_ms,anchor_stride=1 if age_ms==3000 else 10)
        results[name]=dict(rows=[{**r,'detections':{str(k):v.tolist() for k,v in r['detections'].items()}} for r in rows],**result)
        print(name,json.dumps({k:v for k,v in result['summary'].items() if k!='combinations'}),flush=True)
    with output.open('x',encoding='utf-8') as f:
        json.dump(dict(offline_only=True,live_enabled=False,max_age_ms=age_ms,datasets=results),f,indent=2,allow_nan=False)


if __name__=='__main__':main()
