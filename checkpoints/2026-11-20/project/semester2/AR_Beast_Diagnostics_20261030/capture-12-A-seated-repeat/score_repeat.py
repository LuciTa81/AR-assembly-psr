"""Approximate image-space check of all six saved valid poses; not calibration."""
from collections import Counter
import hashlib
import json
from unittest.mock import patch
import numpy as np
import cv2
from inspect_repeat import ROOT
from server.realtime.camera_calibration import write_json
from server.realtime.workspace_projection import CameraModel, MetricWorkspace
from server.realtime.workspace_roi_candidate import _save_png

# Read from unmarked crops. The crops were located using predictions, so not blind.
LABELS = {1: ([570.,458.],3.), 11: ([511.,378.],4.), 41: ([770.,400.],3.),
          51: ([718.,277.],4.), 61: ([673.,507.],4.), 81: ([631.,351.],5.)}


def main():
    manifest = json.loads((ROOT/'inspection/sources.json').read_text())
    session = json.loads((ROOT/'session.json').read_text())
    camera = CameraModel.from_profile(session['camera_profile'])
    workspace = MetricWorkspace.from_dict(session['workspace_profile'])
    sheet = np.full((2310,1600,3),245,np.uint8)
    results = []
    for index,item in enumerate(manifest['inputs']):
        frame_id = item['frame_id']
        raw_path = ROOT/f'frame-{frame_id:06d}'/'raw.png'
        raw = raw_path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == manifest['raw_sha256'][str(raw_path.relative_to(ROOT))]
        state = json.loads((raw_path.parent/'report.json').read_text())
        expected = np.array(state['targets']['A']['pixel'])
        projected = cv2.projectPoints(np.asarray(workspace.targets['A']).reshape(1,3),np.array(state['rvec']),np.array(state['tvec_mm']),camera.matrix,camera.distortion)[0].reshape(2)
        np.testing.assert_allclose(expected,projected,atol=1e-7)
        observed,uncertainty = LABELS[frame_id]
        difference = expected-observed
        distance = float(np.linalg.norm(difference))
        results.append(dict(frame_id=frame_id,estimate_px=observed,approximate_range_per_axis_px=uncertainty,
                            predicted_px=expected.tolist(),predicted_minus_estimate_px=difference.tolist(),distance_px=distance))
        image = cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR)
        x0,y0,x1,y1 = item['crop_xyxy']
        crop = cv2.resize(image[y0:y1,x0:x1],None,fx=8,fy=8,interpolation=cv2.INTER_NEAREST)
        def point(v): return tuple(np.rint((np.asarray(v)-[x0,y0])*8).astype(int))
        cv2.rectangle(crop,point(np.array(observed)-uncertainty),point(np.array(observed)+uncertainty),(40,180,40),2)
        cv2.drawMarker(crop,point(observed),(40,180,40),cv2.MARKER_CROSS,22,2)
        cv2.circle(crop,point(expected),10,(230,180,0),2,cv2.LINE_AA)
        ox,oy = index%2*800,index//2*770
        sheet[oy+60:oy+740,ox+65:ox+785] = crop
        cv2.putText(sheet,f'frame {frame_id} | distance {distance:.2f} raw px',(ox+12,oy+28),cv2.FONT_HERSHEY_SIMPLEX,.6,(20,20,20),1)
        cv2.putText(sheet,'Green: approximate center | Cyan: A projection',(ox+12,oy+758),cv2.FONT_HERSHEY_SIMPLEX,.5,(20,20,20),1)
    frames = [json.loads(line) for line in (ROOT/'frames.jsonl').read_text().splitlines()]
    frames = [row for row in frames if row['event']=='frame']
    output = dict(scope='camera_projection_only',activation_status='not_activated',head_motion='user-confirmed movement',
                  counts=dict(Counter(r['status'] for r in frames)),
                  rejection_reasons=dict(Counter(r['reason'] for r in frames if r['status']!='tracking')),
                  estimates=results,distance_range_px=[min(r['distance_px'] for r in results),max(r['distance_px'] for r in results)],
                  limitations=['Manual estimates with blur, not independent ground truth.',
                               'Pose-accepted saved frames only; all six are included.',
                               'Not a stationary benchmark, metric accuracy measurement, or SBS verification.'])
    _save_png(ROOT/'inspection/A-comparison.png',sheet)
    write_json(ROOT/'inspection/analysis.json',output)
    print(json.dumps(output))


if __name__=='__main__':
    with patch('cv2.VideoCapture',side_effect=AssertionError('Camera forbidden')):
        main()
