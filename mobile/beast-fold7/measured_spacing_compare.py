"""Offline measured-spacing hypothesis; never writes active profile assets."""
import copy
import hashlib
import json
from collections import Counter
import numpy as np
import pose_replay_compare as replay
import corner_size_compare as corner

CAPTURE=replay.ROOT/'pose-comparison/workbench-capture-20261121/marker-d9bb5186-0b42-4a1b-8ab7-e1cd3a3fac88'


def measured_profile(raw):
    result=copy.deepcopy(raw)
    x0=result['marker_centers_mm']['0'][0]
    result['marker_centers_mm']['1'][0]=x0+200.
    result['marker_centers_mm']['2'][0]=x0+405.
    return result


def capture_rows():
    rows=[]
    for path in sorted(CAPTURE.glob('*.json')):
        row=json.loads(path.read_bytes())
        assert (CAPTURE/row['image']).is_file()
        row['detections']={int(k):np.array(v,np.float64) for k,v in row['corners'].items()}
        rows.append(row)
    return rows


def run():
    output=replay.ROOT/'pose-comparison/measured-spacing-report.json'
    if output.exists():raise ValueError('Report already exists')
    protected=[*(replay.ASSETS/k for k in replay.BINDINGS),replay.ROOT/'pose-comparison/corner-size-report.json',*sorted(CAPTURE.glob('*.json')),*sorted(CAPTURE.glob('*.png'))]
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    for name,value in replay.BINDINGS.items():assert hashes[str(replay.ASSETS/name)]==value
    raw=json.loads((replay.ASSETS/'workspace-profile.json').read_bytes())
    workspaces={name:replay.MetricWorkspace.from_dict(profile) for name,profile in
        [('registered',raw),('measured',measured_profile(raw))]}
    camera=replay.CameraModel.from_profile(json.loads((replay.ASSETS/'camera-profile.json').read_bytes()))
    eye_raw=json.loads((replay.ASSETS/'eye-projection.json').read_bytes())
    eyes=[np.array(eye_raw[k]).reshape(3,4) for k in ('left_projection','right_projection')]
    prior=json.loads((replay.ROOT/'pose-comparison/corner-size-report.json').read_bytes())
    orientations={int(k):v for k,v in prior['orientations'].items()}
    geometries={(name,side):corner.corners_for(side,orientations,w) for name,w in workspaces.items() for side in (69,70)}
    records={f'{name}_{mode}':dict(actual=[],full=[],masked=[]) for name in workspaces for mode in ('centers','corners69','corners70')}
    mismatches=[]
    reference_count=0
    for row in capture_rows():
        detections=row['detections']
        reference,base_reason=replay.baseline(detections,workspaces['registered'],camera)
        if (reference is not None)!=row['valid']:mismatches.append(row['image'])
        usable=reference is not None and len(detections)==5
        if usable:reference_count+=1
        for name,workspace in workspaces.items():
            for mode in ('centers','corners69','corners70'):
                def solve(points):
                    if mode=='centers':return replay.baseline(points,workspace,camera)
                    return corner.corner_pose(points,geometries[(name,int(mode[-2:]))],camera)
                full,reason=solve(detections)
                group=records[f'{name}_{mode}']
                group['actual'].append(dict(image=row['image'],ids=sorted(detections),reason=reason,baseline_reason=base_reason,
                    accepted=full is not None,rms=None if full is None else float(full.rms_px)))
                if not usable:continue
                group['full'].append(dict(image=row['image'],reason=reason,
                    comparison=replay.comparison(reference,full,workspaces['registered'],camera,eyes)))
                for missing in (4,5):
                    partial,partial_reason=solve({k:v for k,v in detections.items() if k!=missing})
                    group['masked'].append(dict(image=row['image'],removed=missing,reason=partial_reason,
                        comparison=replay.comparison(reference,partial,workspaces['registered'],camera,eyes),
                        self_comparison=None if full is None else replay.comparison(full,partial,workspace,camera,eyes)))
    assert not mismatches,mismatches
    summaries={}
    for name,items in records.items():
        eligible=[r for r in items['actual'] if r['baseline_reason']=='marker_geometry']
        summaries[name]=dict(actual_reasons=dict(Counter(r['reason'] for r in items['actual'])),
            geometry_rejects=len(eligible),geometry_returned=sum(r['accepted'] for r in eligible),
            full=replay.summary(items['full']),masked={})
        for missing in (4,5):
            rows=[r for r in items['masked'] if r['removed']==missing]
            self_rows=[dict(reason=r['reason'],comparison=r['self_comparison']) for r in rows if r['self_comparison'] is not None]
            summaries[name]['masked'][str(missing)]=dict(versus_frozen=replay.summary(rows),
                self_reference_available=len(self_rows),versus_own_full=replay.summary(self_rows))
    report=dict(offline_only=True,live_enabled=False,hashes=hashes,reference_frames=reference_count,
        measurement=dict(top_0_1_mm=200,top_1_2_mm=205,source='User ruler report 2026-11-21',uncertainty_mm=None),
        assumptions=['Marker 0 remains anchored; row y/z and all other markers remain unchanged.',
            'Distances do not establish row orientation, absolute placement or marker4/5 centers.',
            'Orientations are frozen from prior eight-frame fit; no retake frame is used for fitting.',
            '69/70mm are side-length hypotheses, not certified measured sizes.',
            'Five-marker baseline is a consistency reference, not physical ground truth.',
            'Preservation uses camera <=5px and XYZ <=5mm; eye changes are also reported, including offscreen points.',
            'Correlated saved samples and synthetic deletion do not estimate field success rate.'],
        candidate_marker_centers_mm=measured_profile(raw)['marker_centers_mm'],
        summaries=summaries,records=records,baseline_mismatches=mismatches)
    assert hashes=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    with output.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2,allow_nan=False)
    print(json.dumps(summaries,indent=2))


if __name__=='__main__':run()
