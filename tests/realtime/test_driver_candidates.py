from argparse import Namespace
from types import SimpleNamespace

import numpy as np
import pytest

from server.realtime.run_realtime_server import build_effective_config
from server.realtime.yolo_realtime import RealtimeYoloAnalyzer
from .test_timed_guidance import arm, make_filter, tick, tool


def detection(coords, confidence=.8, kind='driver'):
    return dict(zip(('x1', 'y1', 'x2', 'y2'), coords), confidence=confidence, **{'class': kind})


def analyze(detections, enabled=True, metric=True, linked=False, centers=None):
    plane = SimpleNamespace(camera=SimpleNamespace(matrix=np.eye(3), distortion=np.zeros(5)),
        width_mm=2000, depth_mm=2000, centers={s: (590. + i*100, 460.) for i,s in enumerate('abcd')})
    if centers is not None:
        plane.centers = centers
    analyzer = RealtimeYoloAnalyzer(False, '', '', metric_plane=plane if metric else None)
    analyzer.nested_driver_dedup = enabled
    analyzer.handle_linked_driver = linked
    analyzer.centers = plane.centers
    classes = ['driver', 'handle', 'screw']
    boxes = [SimpleNamespace(cls=np.array([classes.index(d['class'])]),
        conf=np.array([d['confidence']]), xyxy=np.array([[d[k] for k in ('x1','y1','x2','y2')]])) for d in detections]
    analyzer.model = SimpleNamespace(predict=lambda **_: [SimpleNamespace(boxes=boxes, names=dict(enumerate(classes)))])
    return analyzer._process(1, np.zeros((720,1280,3), np.uint8), np.eye(3))


# Rounded numeric detections at the four overlapping-box HOLD resets, not images.
@pytest.mark.parametrize('first,second,handle,expected', [
    ([577.21,327.14,597.04,459.18], [581.34,371.32,600.73,462.74], [548.96,212.64,604.,329.60], 1),
    ([563.92,376.06,582.41,508.13], [566.30,454.16,585.34,510.61], [526.90,184.48,590.02,377.22], 1),
    ([564.22,397.31,588.11,550.75], [560.79,401.24,581.89,615.81], [515.03,155.31,599.05,401.39], 2),
    ([531.39,211.03,595.28,400.25], [528.37,207.63,599.34,560.21], [451.09,0.,567.54,214.68], 2),
])
def test_recorded_nested_boxes_merge_only_when_tips_agree(first, second, handle, expected):
    boxes = [detection(first), detection(second, .3), detection(handle, .9, 'handle')]
    result = analyze(boxes)
    assert result.features['driver_count'] == expected
    assert result.features['driver_count_raw'] == result.features['driver_count_in_workspace'] == 2
    assert len(result.detections) == 3
    assert result.features['nested_driver_dedup'] == 1
    assert result.features['driver_nested_duplicates'] == 2-expected


@pytest.mark.parametrize('enabled,metric', [(False,True), (True,False)])
def test_successful_default_and_legacy_pixel_mode_are_unchanged(enabled, metric):
    result = analyze([detection([100,100,120,230]), detection([103,175,123,232], .3),
                      detection([95,70,125,105], .9, 'handle')], enabled, metric)
    assert result.features['driver_count'] == 2
    assert 'nested_driver_dedup' not in result.features


@pytest.mark.parametrize('variant', ['no_handle','other_tip','other_tool','equal_confidence','different_handles'])
def test_ambiguous_candidates_stay_blocked(variant):
    boxes = [detection([100,100,120,230]), detection([103,175,123,232], .3)]
    if variant != 'no_handle': boxes.append(detection([95,70,125,105], .9, 'handle'))
    if variant == 'other_tip': boxes[1] = detection([103,175,123,280], .3)
    if variant == 'other_tool': boxes[1] = detection([200,175,220,232], .3)
    if variant == 'equal_confidence': boxes[1]['confidence'] = .75
    if variant == 'different_handles': boxes.append(detection([100,180,126,210], .95, 'handle'))
    result = analyze(boxes)
    assert result.features['driver_count'] == 2


def test_keeps_best_geometry_and_does_not_mutate_or_depend_on_detection_order():
    boxes = [detection([100,100,120,230]), detection([103,175,123,232], .3),
             detection([95,70,125,105], .9, 'handle')]
    forward, reverse = analyze(boxes), analyze(list(reversed(boxes)))
    for key in ('tool_tip_x','tool_tip_y','tool_score_a','driver_count'):
        assert forward.features[key] == reverse.features[key]
    assert forward.features['tool_tip_x'] == pytest.approx(110)
    assert forward.features['tool_tip_y'] == pytest.approx(230)
    assert [d['confidence'] for d in boxes] == [.8,.3,.9]


@pytest.mark.parametrize('enabled', [False,True])
def test_multiple_tool_reason_is_opt_in_and_still_clears_completed_hold(enabled):
    f = make_filter(timing={'resume_grace_ms':600, 'completed_hold_resume_ms':2000})
    arm(f)
    data = dict(tool(), driver_count=2)
    if enabled: data['nested_driver_dedup'] = 1.
    result = tick(f,1900,data)
    assert result.guidance.reason == ('multiple_tool_candidates' if enabled else 'tool_not_visible')
    assert ('Multiple tool candidates' in result.next_action) == enabled
    assert result.guidance.phase == 'PAUSED' and f.timed_gate._suspended is None
    for t in range(2000,2601,100):
        assert tick(f,t,tool(score=.05)).state == 'S2'


def test_missing_driver_does_not_get_multiple_candidate_message():
    f = make_filter()
    result = tick(f,1000,dict(tool(), driver_count=0, driver_visible=0, nested_driver_dedup=1.))
    assert result.guidance.reason == 'tool_not_visible'


@pytest.mark.parametrize('initial', ['S0','S1','S6'])
def test_non_screw_pause_does_not_format_a_screw_target(initial):
    f = make_filter(initial=initial)
    result = f.update(1,False,tool(),timestamp_ms=1000,observation_id=1,observation_timestamp_ms=1000)
    assert result.guidance.phase == 'PAUSED'
    assert result.guidance.reason == 'marker_not_stable'


def test_option_is_recorded_without_mutating_base_config():
    base = dict(yolo=dict(enabled=True))
    args = Namespace(screw_auto_trial=True, guidance_mode='auto', presentation_config='profiles.json',
                     nested_driver_dedup=True)
    assert build_effective_config(base,args)['yolo']['nested_driver_dedup'] is True
    assert 'nested_driver_dedup' not in base['yolo']


def test_option_cannot_enable_legacy_or_operator_mode():
    with pytest.raises(ValueError,match='dedup'):
        build_effective_config(dict(yolo=dict(enabled=True)), Namespace(nested_driver_dedup=True))


@pytest.mark.parametrize('value', ['true',1,None])
def test_config_rejects_non_boolean_option(value):
    with pytest.raises(ValueError,match='dedup'):
        build_effective_config(dict(yolo=dict(nested_driver_dedup=value)), Namespace())


@pytest.mark.parametrize('enabled,expected', [(False, 2), (True, 1)])
@pytest.mark.parametrize('reverse', [False, True])
def test_recorded_d_363_disconnected_background_does_not_hide_attached_driver(enabled, expected, reverse):
    boxes = [detection([725.23,432.35,748.44,590.21], .63),
             detection([545.19,5.69,587.94,371.91], .90),
             detection([718.76,207.10,790.34,434.80], .92, 'handle')]
    result = analyze(list(reversed(boxes)) if reverse else boxes, linked=enabled)
    assert result.features['driver_count'] == expected
    assert result.features['driver_count_raw'] == 2
    assert len(result.detections) == 3
    if enabled:
        assert result.features['driver_unlinked_candidates'] == 1
        assert result.features['tool_tip_x'] == pytest.approx((725.23+748.44)/2, abs=.001)
        assert result.features['tool_tip_y'] == pytest.approx(590.21, abs=.001)
    else:
        assert 'handle_linked_driver' not in result.features


@pytest.mark.parametrize('variant', ['no_handle', 'two_handles', 'two_attached',
                                   'ambiguous_handle'])
def test_linked_selection_never_resolves_ambiguous_work_tools(variant):
    boxes = [detection([725.23,432.35,748.44,590.21], .63),
             detection([545.19,5.69,587.94,371.91], .90)]
    if variant != 'no_handle':
        boxes.append(detection([718.76,207.10,790.34,434.80], .92, 'handle'))
    if variant == 'two_handles':
        boxes.append(detection([540,370,595,450], .8, 'handle'))
    if variant == 'two_attached':
        boxes[1] = detection([760,432,780,580], .9)
    if variant == 'ambiguous_handle':
        boxes.append(detection([720,300,775,435], .8, 'handle'))
    result = analyze(boxes, linked=True)
    assert result.features['driver_count'] == 2
    assert result.features['driver_unlinked_candidates'] == 0


def test_linked_selection_preserves_a_single_driver_without_visible_handle():
    boxes = [detection([725,432,748,590], .63)]
    assert analyze(boxes, linked=True).features['driver_count'] == 1


def test_single_tool_trial_prefers_connected_shaft_even_if_background_is_near_a_screw():
    boxes = [detection([725.23,432.35,748.44,590.21], .63),
             detection([580,300,600,460], .90),
             detection([718.76,207.10,790.34,434.80], .92, 'handle')]
    result = analyze(boxes, linked=True)
    assert result.features['driver_count'] == 1
    assert result.features['driver_unlinked_candidates'] == 1
    assert result.features['tool_tip_y'] == pytest.approx(590.21, abs=.001)


@pytest.mark.parametrize('value', ['true', 1, None])
def test_linked_option_rejects_non_boolean_config(value):
    with pytest.raises(ValueError, match='handle_linked_driver'):
        build_effective_config(dict(yolo=dict(handle_linked_driver=value)), Namespace())


def test_linked_option_requires_metric_trial():
    with pytest.raises(ValueError, match='handle_linked_driver'):
        build_effective_config(dict(yolo=dict(handle_linked_driver=True)), Namespace())
    with pytest.raises(ValueError, match='handle_linked_driver'):
        RealtimeYoloAnalyzer(False, '', '', handle_linked_driver=True)


@pytest.mark.parametrize('coords', [[np.nan, 10, 40, 100], [10, 10, 10, 100],
                                  [40, 10, 20, 100], [10, 10, np.inf, 100]])
def test_linked_selection_does_not_resolve_invalid_boxes(coords):
    analyzer = RealtimeYoloAnalyzer(False, '', '')
    drivers = [detection([100,100,120,230]), detection(coords)]
    handles = [detection([95,70,125,105], .9, 'handle')]
    kept, handle = analyzer._select_handle_linked(drivers, handles)
    assert kept is drivers and handle is None


def test_fragment_inside_handle_cannot_become_withdrawal_after_completed_hold():
    boxes = [detection([580,300,600,460]), detection([580,150,600,240], .9),
             detection([560,100,630,270], .9, 'handle')]
    result = analyze(boxes, linked=True)
    f = make_filter()
    arm(f)
    for t in range(1900, 2601, 100):
        assert tick(f, t, dict(tool(), **result.features)).state == 'S2'
    assert result.features['driver_count'] == 2


def test_connected_handle_outside_workspace_keeps_the_far_endpoint():
    boxes = [detection([0,100,6,260]), detection([100,100,106,260], .9),
             detection([-10,80,-.5,120], .9, 'handle')]
    centers = {s: (3. + i*300, 100.) for i,s in enumerate('abcd')}
    result = analyze(boxes, linked=True, centers=centers)
    f = make_filter()
    for t in range(1000, 2501, 100):
        observed = tick(f, t, dict(tool(), **result.features))
        assert observed.guidance.phase != 'OBSERVED'
        assert observed.state == 'S2'
    assert result.features['driver_count'] == 1
    assert result.features['tool_tip_x'] == pytest.approx(3.)
    assert result.features['tool_tip_y'] == pytest.approx(260.)
