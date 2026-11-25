"""Measure detector precision on an existing recording, no hardware access."""
import json
import sys
from pathlib import Path
import cv2
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pose_replay_compare as replay
from corner_bridge_replay import fit_homography, warp


def main():
    output = ROOT/'pose-comparison/refinement-audit.json'
    if output.exists():
        raise ValueError('Report exists')
    camera = replay.CameraModel.from_profile(json.loads((replay.ASSETS/'camera-profile.json').read_bytes()))
    detectors = {}
    for name, method in [('subpix', cv2.aruco.CORNER_REFINE_SUBPIX),
                         ('contour', cv2.aruco.CORNER_REFINE_CONTOUR),
                         ('apriltag', cv2.aruco.CORNER_REFINE_APRILTAG)]:
        p = cv2.aruco.DetectorParameters()
        p.adaptiveThreshWinSizeMin=3; p.adaptiveThreshWinSizeMax=53; p.adaptiveThreshWinSizeStep=4
        p.minMarkerPerimeterRate=.015; p.maxMarkerPerimeterRate=4; p.polygonalApproxAccuracyRate=.03
        p.cornerRefinementMethod=method
        detectors[name] = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50), p)
    cap = cv2.VideoCapture(str(ROOT/'baseline/exhibition-v1-20261125/success-20261125-1756.mp4'))
    rows = {k: [] for k in detectors}; next_ms = 0
    try:
        while True:
            ok, image = cap.read()
            if not ok: break
            ms = cap.get(cv2.CAP_PROP_POS_MSEC)
            if ms < next_ms: continue
            next_ms = ms+500
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            for name, detector in detectors.items():
                corners, ids, _ = detector.detectMarkers(gray)
                found = {str(int(k)): q.reshape(4,2).astype(float).tolist()
                         for k,q in zip([] if ids is None else ids.flatten(),corners) if int(k) in range(6)}
                rows[name].append(dict(frame_ms=ms,detections=found))
    finally: cap.release()
    summaries = {}
    for name, data in rows.items():
        residuals = []
        for a,b in zip(data,data[1:]):
            keys = sorted(set(a['detections'])&set(b['detections']))
            if len(keys)<3: continue
            und = lambda q: cv2.undistortPoints(np.array(q).reshape(-1,1,2),camera.matrix,
                       camera.distortion,P=camera.matrix).reshape(-1,2)
            source=np.concatenate([und(a['detections'][k]) for k in keys])
            target=np.concatenate([und(b['detections'][k]) for k in keys])
            h=fit_homography(source,target)
            residuals.append(float(np.sqrt(np.mean(np.sum((warp(source,h)-target)**2,axis=1)))))
        summaries[name]=dict(frames=len(data),five=sum(len(r['detections'])>=5 for r in data),
                            pair_rms_percentiles=np.percentile(residuals,[50,95,100]).tolist())
    with output.open('x',encoding='utf-8') as f:
        json.dump(dict(offline_only=True,rows=rows,summary=summaries),f,allow_nan=False)
    print(json.dumps(summaries))


if __name__=='__main__': main()
