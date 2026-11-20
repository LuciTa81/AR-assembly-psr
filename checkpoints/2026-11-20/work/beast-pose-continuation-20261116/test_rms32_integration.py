import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent
manifest = json.loads((ROOT.parent / 'beast-preparation-text-20261116/protected-before.json').read_text(encoding='utf-8-sig'))
REPO = Path(manifest[0]['Path']).parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / 'tests'))

from server.realtime import presentation_bridge, workspace_live_preview
from realtime.test_workspace_live_preview import profiles
from realtime.test_workspace_projection import models


@pytest.mark.parametrize('limit', [None, 3.2])
def test_frame_analysis_passes_only_requested_rms_limit_to_existing_solver(limit):
    camera, workspace, detections, _, _ = models()
    frame = np.zeros((720, 1280, 3), np.uint8)
    ids = np.array(list(detections)).reshape(-1, 1)
    options = {} if limit is None else {'max_rms_px': limit}
    with patch.object(workspace_live_preview, 'detect_markers', return_value=(detections, [], ids)), \
         patch.object(workspace_live_preview, 'estimate_pose', wraps=workspace_live_preview.estimate_pose) as solve:
        result = workspace_live_preview.analyze_frame(frame, camera, workspace, **options)
    assert result['status'] == 'tracking'
    assert solve.call_args.kwargs == {'max_rms_px': 3. if limit is None else limit,
                                      'max_point_error_px': 5.}


@pytest.mark.parametrize('limit', [None, 3.2])
def test_presentation_config_selects_limit_and_records_it(tmp_path, limit):
    camera, workspace = profiles(tmp_path)
    data = {'camera_profile': str(camera), 'workspace_profile': str(workspace)}
    if limit is not None:
        data['pose_max_rms_px'] = limit
    config = tmp_path / 'presentation.json'
    config.write_text(json.dumps(data), encoding='utf-8')
    packet = SimpleNamespace(frame_id=1, timestamp_ms=time.perf_counter()*1000,
                             frame=np.zeros((720, 1280, 3), np.uint8))
    analysis = {'status': 'pose_rejected', 'reason': 'need four markers',
                'marker_ids': [], 'targets': {}}
    bridge = presentation_bridge.PresentationBridge(config, 'rms-check', root=tmp_path / 'local')
    try:
        with patch.object(presentation_bridge, 'analyze_frame', return_value=analysis) as analyze:
            _, status = bridge.update(packet)
        expected = 3. if limit is None else limit
        assert analyze.call_args.kwargs == ({} if expected == 3. else {'max_rms_px': expected})
        assert status['diagnostics']['pose_max_rms_px'] == expected
        assert status['diagnostics']['pose_max_point_error_px'] == 5.
        assert bridge.store.snapshot(time.perf_counter())['status'] != 'tracking'
    finally:
        bridge.close()


@pytest.mark.parametrize('value', [True, False, None, '3.2', 0, -1, 3.6, float('nan'), float('inf')])
def test_invalid_quality_limit_rejected_before_starting_server(tmp_path, value):
    config = tmp_path / 'presentation.json'
    config.write_text(json.dumps({'pose_max_rms_px': value}), encoding='utf-8')
    with patch.object(presentation_bridge, 'start_server') as server:
        with pytest.raises(ValueError, match='pose_max_rms_px'):
            presentation_bridge.PresentationBridge(config, 'invalid', root=tmp_path / 'local')
    server.assert_not_called()


def test_saved_borderline_frame_passes_at_32_but_default_remains_rejected():
    from replay_quality_continuation import read_records
    data = json.loads((ROOT / 'replay-report.json').read_text(encoding='utf-8'))
    run = data['runs'][0]
    selected = next(row['frame'] for row in run['rows'] if row['rms'] and 3 < row['rms'] <= 3.2)
    row = next(row for row in read_records(Path(run['source']), None) if row['frame'] == selected)
    original = json.loads((ROOT / 'before-rms32/presentation.json').read_text(encoding='utf-8-sig'))
    camera, workspace, _ = workspace_live_preview.load_profiles(
        Path(original['camera_profile']), Path(original['workspace_profile']))
    mapping = {int(k): np.asarray(v) for k, v in row['diagnostic']['detected_corners_px'].items()}
    ids = np.array(list(mapping)).reshape(-1, 1)
    image = np.zeros((720, 1280, 3), np.uint8)
    with patch.object(workspace_live_preview, 'detect_markers', return_value=(mapping, [], ids)):
        baseline = workspace_live_preview.analyze_frame(image, camera, workspace)
        candidate = workspace_live_preview.analyze_frame(image, camera, workspace, max_rms_px=3.2)
    assert baseline['status'] == 'pose_rejected'
    assert candidate['status'] == 'tracking'
    assert 3 < candidate['rms_px'] <= 3.2
    assert candidate['max_error_px'] <= 5.
    with patch.object(workspace_live_preview, 'detect_markers', return_value=({}, [], None)):
        missing = workspace_live_preview.analyze_frame(image, camera, workspace, max_rms_px=3.2)
    assert missing['status'] == 'pose_rejected' and missing['targets'] == {}


def test_console_uses_separate_quality_config_without_changing_calibrations():
    profile = json.loads((ROOT.parent / 'AI-Assembly-Console/profile.json').read_text(encoding='utf-8-sig'))
    selected = Path(profile['presentation_config'])
    assert selected.is_absolute() and selected == ROOT / 'presentation-rms32.json'
    current = json.loads(selected.read_text(encoding='utf-8'))
    original = json.loads((ROOT / 'before-rms32/presentation.json').read_text(encoding='utf-8-sig'))
    assert current == dict(original, pose_max_rms_px=3.2)
    assert json.loads((REPO / 'outputs/demo/presentation.json').read_text(encoding='utf-8-sig')) == original
    launcher = (REPO / 'scripts/run_beast_console_session.ps1').read_text(encoding='utf-8-sig')
    assert '$p.presentation_config' in launcher
    assert '$options.PresentationConfig = $presentation' in launcher
