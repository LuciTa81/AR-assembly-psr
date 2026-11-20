from argparse import Namespace
from copy import deepcopy
from pathlib import Path
import sys

import pytest
import yaml
from run_neutral_d_server import ROOT

sys.path.insert(0, str(ROOT))


def test_flow_reuses_the_verified_d_candidate_options():
    from run_handle_linked_flow_server import trial_config
    base = yaml.safe_load((ROOT / 'configs/realtime_viture_beast_aruco.yaml').read_text(encoding='utf-8'))
    original = deepcopy(base)
    args = Namespace(guidance_mode='hybrid', presentation_config=ROOT/'outputs/demo/presentation.json',
                     nested_driver_dedup=True, source_recovery_boundary=True,
                     screw_resume_ms=600, completed_hold_resume_ms=2000)
    config = trial_config(base, args)
    previous = yaml.safe_load((Path(__file__).parent / 'handle-linked-D-sessions' /
        'viture_aruco_rt_20261115_141146_52bb3e0131c5/config_used.yaml').read_text(encoding='utf-8'))
    assert config['state_filter']['timing'] == previous['state_filter']['timing']
    assert config['yolo'] == previous['yolo']
    assert config['guidance_mode'] == 'hybrid' and not config['screw_auto_trial']
    assert config['state_filter']['initial_state'] == 'S2'
    assert config['state_filter']['max_state'] == 'S6'
    assert not config['logging']['save_frames']
    assert base == original


def test_full_candidate_flow_with_background_detection_and_interruptions(monkeypatch, tmp_path):
    from run_handle_linked_flow_server import trial_config
    monkeypatch.syspath_prepend(str(ROOT / 'tests'))
    from realtime import test_metric_tool_plane as integration

    def local_config(base, args):
        args.source_recovery_boundary = True
        config = trial_config(base, args)
        config['logging']['output_root'] = str(tmp_path / 'logs')
        return config

    monkeypatch.setattr(integration, 'build_effective_config', local_config)
    integration.test_real_tool_scoring_and_runtime_transition_share_one_metric_frame(
        monkeypatch, tmp_path, 'S6', True, 600, 2000, True, True)


def test_flow_runner_rejects_non_hybrid_mode():
    from run_handle_linked_flow_server import trial_config
    with pytest.raises(ValueError, match='hybrid'):
        trial_config({}, Namespace(guidance_mode='auto'))


def test_recorded_full_flow_keeps_completed_hold_and_manual_end_confirmation():
    import json
    from compare_neutral_recovery import trace
    from server.realtime.realtime_replay import validate_session

    session = Path(__file__).parent / 'handle-linked-flow-sessions/viture_aruco_rt_20261115_142256_ea194634ad7d'
    config = yaml.safe_load((session / 'config_used.yaml').read_text(encoding='utf-8'))
    rows = [json.loads(line) for line in (session / 'results.jsonl').read_text(encoding='utf-8').splitlines()]
    assert validate_session(session)['matched']
    transitions = [r['transition_event'] for r in rows if r['transition_event']]
    assert transitions == ['operator_confirmation', 'operator_confirmation',
                           'S2->S3', 'S3->S4', 'S4->S5', 'S5->S6', 'operator_confirmation']
    assert rows[-1]['guidance']['phase'] == 'COMPLETED'
    assert rows[-1]['operator']['completed']
    details = trace(rows, config)
    for target in ('screw_a', 'screw_b', 'screw_c', 'screw_d'):
        points = [r for r in details if r['target'] == target]
        first = next(i for i, r in enumerate(points) if r['phase'] == 'OBSERVED')
        assert all(r['phase'] != 'OBSERVING' for r in points[first:])
