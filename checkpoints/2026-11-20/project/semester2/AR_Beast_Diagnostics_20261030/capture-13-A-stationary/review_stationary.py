"""Offline comparison of all saved accepted frames from the final requested test."""
from collections import Counter
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
import cv2
import numpy as np
from server.realtime.camera_calibration import write_json
from server.realtime.workspace_live_preview import analyze_frame, load_profiles
from server.realtime.workspace_roi_candidate import _save_png

ROOT = Path(__file__).resolve().parent
PROFILE = Path('C:/Users/fresh/AppData/Local/ARAssembly/beast-mvp')
# Read from unmarked crops; pixel estimates and ranges are approximate, not ground truth.
LABELS = {21:([440.,335.],4.),31:([440.,340.],3.),41:([434.,348.],3.),
          51:([560.,311.],5.),61:([576.,317.],3.),71:([552.,312.],3.),
          81:([562.,314.],3.),91:([567.,314.],3.)}


def main():
    manifest = json.loads((ROOT/'inspection/sources.json').read_text())
    session = json.loads((ROOT/'session.json').read_text())
    camera_path = PROFILE/'camera_calibration/combined-review-20260927T065914Z-89414bbe/candidate.json'
    workspace_path = PROFILE/'workspace_registration/comfort-layout-20261006-v1/workspace-candidate.json'
    camera,workspace,metadata = load_profiles(camera_path,workspace_path)
    for key in ('camera_profile_sha256','workspace_profile_sha256'):
        assert metadata[key] == session[key]
    assert set(LABELS) == {item['frame_id'] for item in manifest['inputs']}
    sheet = np.full((770*((len(LABELS)+1)//2),1600,3),245,np.uint8)
    rows = []
    for index,item in enumerate(manifest['inputs']):
        frame_id = item['frame_id']
        path = ROOT/f'frame-{frame_id:06d}'/'raw.png'
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == manifest['raw_sha256'][str(path.relative_to(ROOT))]
        image = cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_COLOR)
        live = json.loads((path.parent/'report.json').read_text())
        observed,uncertainty = LABELS[frame_id]
        x0,y0,x1,y1 = item['crop_xyxy']
        crop = cv2.resize(image[y0:y1,x0:x1],None,fx=8,fy=8,interpolation=cv2.INTER_NEAREST)
        def point(v): return tuple(np.rint((np.asarray(v)-[x0,y0])*8).astype(int))
        cv2.rectangle(crop,point(np.array(observed)-uncertainty),point(np.array(observed)+uncertainty),(40,180,40),2)
        cv2.drawMarker(crop,point(observed),(40,180,40),cv2.MARKER_CROSS,22,2)
        row = dict(frame_id=frame_id,estimate_px=observed,approximate_range_per_axis_px=uncertainty,methods={})
        for method,color in [('subpix',(230,180,0)),('apriltag',(220,50,220))]:
            state = analyze_frame(image,camera,workspace,corner_refinement=method)
            result = dict(status=state['status'],reason=state['reason'],marker_ids=state['marker_ids'])
            if method=='subpix':
                assert state['status']==live['status']
            if state['status']=='tracking' and state['targets']['A']['visible']:
                predicted = np.array(state['targets']['A']['pixel'])
                direct = cv2.projectPoints(np.asarray(workspace.targets['A']).reshape(1,3),np.array(state['rvec']),np.array(state['tvec_mm']),camera.matrix,camera.distortion)[0].reshape(2)
                np.testing.assert_allclose(predicted,direct,atol=1e-7)
                if method=='subpix':
                    np.testing.assert_allclose(predicted,live['targets']['A']['pixel'],atol=1e-7)
                difference = predicted-observed
                result.update(predicted_px=predicted.tolist(),predicted_minus_estimate_px=difference.tolist(),distance_px=float(np.linalg.norm(difference)),marker_rms_px=state['rms_px'])
                cv2.circle(crop,point(predicted),10,color,2,cv2.LINE_AA)
            row['methods'][method]=result
        rows.append(row)
        ox,oy = index%2*800,index//2*770
        sheet[oy+60:oy+740,ox+65:ox+785]=crop
        cv2.putText(sheet,f'frame {frame_id} | approximate A center',(ox+12,oy+28),cv2.FONT_HERSHEY_SIMPLEX,.6,(20,20,20),1)
        cv2.putText(sheet,'Green: estimate | Cyan: SUBPIX | Magenta: APRILTAG',(ox+12,oy+758),cv2.FONT_HERSHEY_SIMPLEX,.48,(20,20,20),1)
    summary = {}
    for method in ('subpix','apriltag'):
        accepted = [r['methods'][method] for r in rows if 'distance_px' in r['methods'][method]]
        distances = [r['distance_px'] for r in accepted]
        summary[method] = dict(scored=len(accepted),distance_range_px=[min(distances),max(distances)] if distances else None,
            mean_residual_xy_px=np.mean([r['predicted_minus_estimate_px'] for r in accepted],axis=0).tolist() if accepted else None)
    frames = [json.loads(line) for line in (ROOT/'frames.jsonl').read_text().splitlines()]
    frames = [r for r in frames if r['event']=='frame']
    late = [r for r in frames if r['frame_id']>=21]
    report = dict(scope='offline_camera_projection_review',activation_status='not_activated',
        setup=dict(head_height_mm=60,height_source='user approximate measurement',instruction='keep head still',observed_condition='some viewpoint change and blur remain'),
        counts=dict(Counter(r['status'] for r in frames)),failure_ids=[r['frame_id'] for r in frames if r['status']!='tracking'],
        rejected_reasons=dict(Counter(r['reason'] for r in frames if r['status']!='tracking')),
        after_frame_20=dict(counts=dict(Counter(r['status'] for r in late)),duration_seconds=late[-1]['received_at_monotonic']-late[0]['received_at_monotonic']),
        summary=summary,observations=rows,camera_profile_sha256=metadata['camera_profile_sha256'],workspace_profile_sha256=metadata['workspace_profile_sha256'],
        limitations=['Not a fully immobilized camera test; image location changes during the capture.',
                     'All eight saved accepted frames included; two saved rejected frames excluded from residual scoring.',
                     'Manual readings are approximate and not blind; uncertainty ranges are not confidence intervals.',
                     'No metric accuracy or optical SBS alignment is established. APRILTAG is only an offline comparison.'])
    output=ROOT/'review'
    output.mkdir(exist_ok=False)
    _save_png(output/'A-comparison.png',sheet)
    write_json(output/'analysis.json',report)
    for relative,sha in manifest['raw_sha256'].items():
        assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==sha
    assert hashlib.sha256(camera_path.read_bytes()).hexdigest()==metadata['camera_profile_sha256']
    assert hashlib.sha256(workspace_path.read_bytes()).hexdigest()==metadata['workspace_profile_sha256']
    print(json.dumps(dict(summary=summary,observations=rows,counts=report['counts'],after_frame_20=report['after_frame_20'])))


if __name__=='__main__':
    with patch('cv2.VideoCapture',side_effect=AssertionError('Camera forbidden during review')):
        main()
