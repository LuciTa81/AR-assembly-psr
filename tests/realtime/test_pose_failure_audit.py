import copy
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from .test_workspace_projection import corner_scene
from .test_temporal_marker_replay import saved_trace


def api():
    from server.realtime import pose_failure_audit
    return pose_failure_audit


def sample():
    camera, workspace, _, detected, _, _ = corner_scene((0, 1, 2, 4, 5))
    return camera, workspace, detected


def test_normal_result_is_unchanged_and_no_camera_is_opened():
    camera, workspace, detected = sample()
    original = copy.deepcopy(detected)
    with patch('cv2.VideoCapture', side_effect=AssertionError('no camera')):
        baseline, candidate, detail = api().evaluate(detected, workspace, camera)
    assert candidate is baseline and baseline is not None
    assert detail['method'] == 'baseline'
    for key in detected:
        np.testing.assert_array_equal(detected[key], original[key])


def test_single_center_fault_is_removed_only_in_offline_candidate():
    camera, workspace, detected = sample()
    detected[1] += [15, 0]
    before = copy.deepcopy(workspace.markers)
    baseline, candidate, detail = api().evaluate(detected, workspace, camera)
    assert baseline is None and candidate is not None
    assert detail['method'] == 'single_center_omission'
    assert detail['omitted_marker'] == 1
    assert candidate.marker_ids == [0, 2, 4, 5]
    np.testing.assert_allclose(candidate.camera_position_mm, [213, -175, 507], atol=.01)
    for key in before:
        np.testing.assert_array_equal(workspace.markers[key], before[key])


def test_three_centers_are_diagnosed_but_never_returned_as_pose():
    camera, workspace, detected = sample()
    detected = {k:detected[k] for k in (1, 2, 5)}
    baseline, candidate, detail = api().evaluate(detected, workspace, camera)
    assert baseline is candidate is None
    assert detail['three_center']['physical_solutions'] >= 2
    assert len(detail['three_center']['solutions']) >= 2
    assert detail['method'] == 'unavailable'


def test_collinear_three_centers_are_rejected_before_solver():
    camera, workspace, detected = sample()
    detected = {k:detected[k] for k in (0, 1, 2)}
    _, candidate, detail = api().evaluate(detected, workspace, camera)
    assert candidate is None and detail['three_center']['physical_solutions'] == 0
    assert 'line' in detail['three_center']['error']


def test_four_marker_quality_failure_is_not_rescued():
    camera, workspace, detected = sample()
    del detected[2]
    detected[1] += [30, 0]
    _, candidate, detail = api().evaluate(detected, workspace, camera)
    assert candidate is None and detail['baseline_reason'] == 'pose_quality'


@pytest.mark.parametrize('fault', ['unknown', 'nan', 'nonconvex'])
def test_invalid_evidence_cannot_enter_candidate(fault):
    camera, workspace, detected = sample()
    if fault == 'unknown': detected[49] = detected.pop(4)
    elif fault == 'nan': detected[1][0,0] = np.nan
    else: detected[1][[1,2]] = detected[1][[2,1]]
    with pytest.raises(ValueError):
        api().evaluate(detected, workspace, camera)


def test_two_centers_over_limit_do_not_choose_one_by_convenience():
    camera, workspace, detected = sample()
    m = api()
    normal, _, _ = m.evaluate(detected, workspace, camera)
    residuals = normal.projected_centers_px.copy()
    residuals[0,0] -= 9
    residuals[1,0] -= 8
    from dataclasses import replace
    fit = replace(normal, projected_centers_px=residuals)
    with patch.object(m, 'estimate_pose', side_effect=[ValueError('Workspace pose reprojection error too high'), fit]):
        _, candidate, detail = m.evaluate(detected, workspace, camera)
    assert candidate is None and detail['over_limit_ids'] == [0,1]


def test_failure_runs_use_capture_time_and_never_merge_across_stages():
    records = [dict(frame_id=i, timestamp_ms=t, state=s, baseline_reason=r)
               for i,t,s,r in [(1,100,'S4','tracking'),(2,210,'S4','insufficient_markers'),
                               (3,330,'S4','insufficient_markers'),(4,440,'S5','pose_quality'),
                               (5,550,'S5','tracking')]]
    runs = api().failure_runs(records)
    assert [(r['first'],r['last'],r['sample_span_ms']) for r in runs] == [(2,3,120),(4,4,0)]


def test_fault_sweep_is_deterministic_and_does_not_modify_input():
    camera, workspace, detected = sample()
    before = copy.deepcopy(detected)
    report = api().fault_sweep([(1,detected)], workspace, camera)
    assert report['cases'] == 20
    assert report['fallback_accepted'] >= 1
    assert report['reference'] == 'same-frame unmodified five-marker fit; not physical truth'
    for key in detected:
        np.testing.assert_array_equal(detected[key], before[key])


def test_row_fit_changes_only_middle_center_and_preserves_collinearity():
    from dataclasses import replace
    camera, workspace, detected = sample()
    markers = {k:v.copy() for k,v in workspace.markers.items()}
    markers[1] += [3,0,0]
    registered = replace(workspace, markers=markers)
    candidate, detail = api().fit_top_row([(n,detected) for n in range(1,4)], registered, camera)
    np.testing.assert_allclose(candidate.markers[1], workspace.markers[1], atol=.01)
    np.testing.assert_array_equal(registered.markers[1], workspace.markers[1]+[3,0,0])
    for key in workspace.markers:
        if key != 1: np.testing.assert_array_equal(candidate.markers[key],workspace.markers[key])
    assert candidate.targets is registered.targets
    assert candidate.markers[1][1] == registered.markers[0][1]
    assert candidate.markers[1][2] == 0
    assert detail['sample_count'] == 3
    assert detail['physical_measurement'] is False


@pytest.mark.parametrize('frames', [[], [1,1,2], [1,2]])
def test_row_fit_rejects_missing_or_duplicate_training_samples(frames):
    camera, workspace, detected = sample()
    with pytest.raises(ValueError):
        api().fit_top_row([(n,detected) for n in frames], workspace, camera)


@pytest.mark.parametrize('fault', ['binding','resolution','frame','time','duplicate_ids','nan','unknown'])
def test_audit_rejects_invalid_trace(saved_trace,fault):
    path,profiles,_,rows = saved_trace
    d = rows[0]['presentation_diagnostics']
    if fault=='binding': d['camera_profile_sha256']='bad'
    if fault=='resolution': d['image_size']=[640,480]
    if fault=='frame': rows[0]['filter_input']['frame_id']=99
    if fault=='time': rows[1]['filter_input']['timestamp_ms']=1000
    if fault=='duplicate_ids': d['marker_ids'].append(1)
    if fault=='nan': d['detected_corners_px']['1'][0][0]=float('nan')
    if fault=='unknown':
        d['marker_ids'].append(49)
        d['marker_count']+=1
        d['detected_corners_px']['49']=d['detected_corners_px']['1']
    path.write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
    with pytest.raises(ValueError): api().audit(path,profiles)


def test_row_comparison_keeps_training_out_of_same_trace_evaluation(saved_trace):
    path,profiles,_,_ = saved_trace
    module = api()
    with patch.object(module,'fit_top_row',wraps=module.fit_top_row) as fit:
        report = module.compare_top_row(path,[path],profiles,3)
    assert [r[0] for r in fit.call_args.args[0]]==[1,2,3]
    assert report['fit']['frames']==[1,2,3]
    assert [r['frame_id'] for r in report['evaluations'][0]['records']]==[4,5,6,7,8]
    assert report['evaluations'][0]['counts']=={'both':5}
    assert report['live_enabled'] is report['calibration_valid'] is False


def test_cli_does_not_overwrite_report_and_audit_replays_baseline(saved_trace,tmp_path):
    path,profiles,paths,_=saved_trace
    output=tmp_path/'audit.json'
    argv=['audit','--results',str(path),'--camera-profile',str(paths[0]),
          '--workspace-profile',str(paths[1]),'--output',str(output)]
    with patch('sys.argv',argv), patch('cv2.VideoCapture',side_effect=AssertionError('no camera')):
        api().main()
        before=output.read_bytes()
        with pytest.raises(SystemExit): api().main()
    assert before==output.read_bytes()
    report=json.loads(before)
    assert report['states']['S4']['methods']=={'baseline':8}
    assert not report['live_enabled']


def test_mutation_during_comparison_is_rejected(saved_trace):
    path,profiles,_,_=saved_trace
    module=api()
    original=module.fit_top_row
    def mutate(*args,**kwargs):
        result=original(*args,**kwargs)
        with path.open('a',encoding='utf-8') as stream: stream.write('\n')
        return result
    with patch.object(module,'fit_top_row',mutate),pytest.raises(ValueError,match='changed'):
        module.compare_top_row(path,[path],profiles,3)


def test_copied_training_trace_cannot_enter_heldout_metrics(saved_trace,tmp_path):
    path,profiles,_,_=saved_trace
    duplicate=tmp_path/'duplicate.jsonl'
    duplicate.write_bytes(path.read_bytes())
    report=api().compare_top_row(path,[duplicate],profiles,3)
    assert [r['frame_id'] for r in report['evaluations'][0]['records']]==[4,5,6,7,8]


def saved_case():
    from server.realtime.workspace_projection import CameraModel,MetricWorkspace
    data=json.loads((Path(__file__).parents[1]/'fixtures/pose_failure_audit_20261108.json').read_text())
    detected={r['frame_id']:{int(k):np.array(v) for k,v in r['detected_corners_px'].items()} for r in data['frames']}
    return CameraModel.from_profile(data['camera']),MetricWorkspace.from_dict(data['workspace']),detected,data


def test_saved_c_and_d_failure_diagnoses_are_reproducible():
    camera,workspace,detected,_=saved_case()
    _,candidate,detail=api().evaluate(detected[640],workspace,camera)
    assert candidate is None and detail['three_center']['physical_solutions']==2
    assert max(v['rms_px'] for v in detail['three_center']['solutions'])<1e-6
    _,candidate,detail=api().evaluate(detected[1030],workspace,camera)
    assert candidate is not None and detail['omitted_marker']==1


def test_known_wrong_omission_remains_visible_in_stress_metrics():
    camera,workspace,detected,data=saved_case()
    frame=data['counterexample']['frame_id']
    report=api().fault_sweep([(frame,detected[frame])],workspace,camera)
    assert report['wrong_omission']>0
    cases=[r for r in report['records'] if r['method']=='single_center_omission'
           and r['perturbed_marker']==data['counterexample']['perturbed_marker']
           and r['shift_px']==data['counterexample']['shift_px']]
    assert len(cases)==1 and not cases[0]['preserved']
