"""A projection audit against approximate landmarks; no calibration fitting."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import hashlib
import json
import cv2
import numpy as np
from inspect_landmarks import SOURCES
from server.realtime.camera_calibration import write_json
from server.realtime.workspace_live_preview import load_profiles, analyze_frame
from server.realtime.workspace_projection import pixel_to_plane
from server.realtime.workspace_roi_candidate import _save_png

ROOT=Path(__file__).resolve().parent
PROFILE=Path('C:/Users/fresh/AppData/Local/ARAssembly/beast-mvp')
CAMERA=PROFILE/'camera_calibration/combined-review-20260927T065914Z-89414bbe/candidate.json'
WORKSPACE=PROFILE/'workspace_registration/comfort-layout-20261006-v1/workspace-candidate.json'


def main():
    camera,workspace,meta=load_profiles(CAMERA,WORKSPACE)
    labels=json.loads((ROOT/'visual-estimates.json').read_text())['observations']
    manifest=json.loads((ROOT/'sources.json').read_text())['inputs']
    hashes={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in (CAMERA,WORKSPACE)}
    expected={r['name']:r for r in manifest}
    rows=[]
    sheet=np.full((1540,1600,3),245,np.uint8)
    for index,(name,path,box) in enumerate(SOURCES):
        data=path.read_bytes()
        digest=hashlib.sha256(data).hexdigest()
        assert digest==expected[name]['sha256']
        hashes[path]=digest
        image=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_COLOR)
        label=labels[name]
        result=dict(name=name,source=str(path),source_sha256=digest,visual_estimate=label,methods={})
        x0,y0,x1,y1=box
        crop=cv2.resize(image[y0:y1,x0:x1],None,fx=8,fy=8,interpolation=cv2.INTER_NEAREST)
        def coordinate(point): return tuple(np.rint((np.asarray(point)-[x0,y0])*8).astype(int))
        if label['pixel'] is not None:
            observed=np.asarray(label['pixel'],float)
            uncertainty=label['uncertainty_px_per_axis']
            cv2.rectangle(crop,coordinate(observed-uncertainty),coordinate(observed+uncertainty),(40,180,40),2)
            cv2.drawMarker(crop,coordinate(observed),(40,180,40),cv2.MARKER_CROSS,22,2)
        for method,color in [('subpix',(230,180,0)),('apriltag',(220,50,220))]:
            state=analyze_frame(image,camera,workspace,corner_refinement=method)
            detail=dict(status=state['status'],reason=state['reason'],marker_ids=state['marker_ids'])
            if state['status']=='tracking' and state['targets']['A']['visible']:
                predicted=np.array(state['targets']['A']['pixel'])
                rvec=np.array(state['rvec']); tvec=np.array(state['tvec_mm'])
                def project(xyz):
                    return cv2.projectPoints(np.asarray(xyz).reshape(1,3),rvec,tvec,camera.matrix,camera.distortion)[0].reshape(2)
                np.testing.assert_allclose(project(workspace.targets['A']),predicted,atol=1e-7)
                detail.update(predicted_A_pixel=predicted.tolist(),marker_rms_px=state['rms_px'],rvec=state['rvec'],tvec_mm=state['tvec_mm'])
                cv2.circle(crop,coordinate(predicted),10,color,2,cv2.LINE_AA)
                if label['pixel'] is not None:
                    diff=predicted-observed
                    conditional=SimpleNamespace(rvec=rvec,tvec=tvec,camera_position_mm=np.array(state['camera_position_mm']))
                    world=pixel_to_plane(observed,60.,conditional,camera)
                    np.testing.assert_allclose(project(world),observed,atol=.02)
                    detail.update(predicted_minus_estimate_px=diff.tolist(),distance_px=float(np.linalg.norm(diff)),
                        minimum_distance_to_estimate_box_px=float(np.linalg.norm(np.maximum(np.abs(diff)-uncertainty,0))),
                        conditional_observed_world_at_z60_mm=world.tolist(),
                        conditional_xy_delta_from_registered_A_mm=(world-workspace.targets['A']).tolist(),
                        height_sensitivity={str(z):project([*workspace.targets['A'][:2],z]).tolist() for z in (55.,60.,65.)})
                    cv2.line(crop,coordinate(observed),coordinate(predicted),color,1,cv2.LINE_AA)
            result['methods'][method]=detail
        rows.append(result)
        ox,oy=(index%2)*800,(index//2)*770
        sheet[oy+60:oy+740,ox+65:ox+785]=crop
        score='ESTIMATED HEAD CENTER' if label['pixel'] is not None else 'NOT SCORED: NO CLEAR MATCHING HEAD'
        cv2.putText(sheet,name+' | '+score,(ox+12,oy+28),cv2.FONT_HERSHEY_SIMPLEX,.5,(20,20,20),1,cv2.LINE_AA)
        cv2.putText(sheet,'Green: visual +/-3px | Cyan: SUBPIX | Magenta: APRILTAG',(ox+12,oy+758),cv2.FONT_HERSHEY_SIMPLEX,.47,(20,20,20),1,cv2.LINE_AA)
    summary={}
    for method in ('subpix','apriltag'):
        valid=[r['methods'][method] for r in rows if 'distance_px' in r['methods'][method]]
        residuals=np.array([v['predicted_minus_estimate_px'] for v in valid])
        summary[method]=dict(scored_images=len(valid),mean_residual_xy_px=residuals.mean(axis=0).tolist(),
                            distance_min_max_px=[min(v['distance_px'] for v in valid),max(v['distance_px'] for v in valid)],
                            conditional_xy_delta_mean_mm=np.mean([v['conditional_xy_delta_from_registered_A_mm'] for v in valid],axis=0).tolist())
    output=ROOT/'results'
    output.mkdir(exist_ok=False)
    _save_png(output/'A-comparison.png',sheet)
    report=dict(schema_version='beast_A_projection_visual_audit_v1',scope='offline_camera_projection_only',
        activation_status='not_activated',camera_profile_sha256=meta['camera_profile_sha256'],
        workspace_profile_sha256=meta['workspace_profile_sha256'],registered_A_mm=workspace.targets['A'].tolist(),
        observations=rows,summary=summary,
        limitations=['Visual estimates are not independent user ground truth; +/-3px is not statistical uncertainty.',
                     'Actual screw head height was not measured for these photographs.',
                     'z=60 inverse projection is conditional and is not a corrected registration.',
                     'Three usable frames are correlated observations from one prior capture.',
                     'No optical eye/display accuracy or live tracking continuity is established.'])
    for path,digest in hashes.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
    write_json(output/'analysis.json',report)
    print(json.dumps(dict(summary=summary,observations=[dict(name=r['name'],estimate=r['visual_estimate'],methods={k:{kk:vv for kk,vv in d.items() if kk in ['status','reason','predicted_A_pixel','predicted_minus_estimate_px','distance_px','marker_rms_px','conditional_xy_delta_from_registered_A_mm','height_sensitivity']} for k,d in r['methods'].items()}) for r in rows])))


if __name__=='__main__':
    with patch('cv2.VideoCapture',side_effect=AssertionError('Camera forbidden during offline audit')):
        main()

