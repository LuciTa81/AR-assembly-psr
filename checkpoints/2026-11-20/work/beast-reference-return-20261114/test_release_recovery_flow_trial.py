from argparse import Namespace
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from run_neutral_d_server import ROOT
from run_handle_linked_flow_server import trial_config as baseline
from run_release_recovery_flow_server import trial_config


def test_candidate_changes_only_release_option_and_log_destination():
    base = yaml.safe_load((ROOT / 'configs/realtime_viture_beast_aruco.yaml').read_text(encoding='utf-8'))
    original = deepcopy(base)
    args = Namespace(guidance_mode='hybrid', presentation_config=ROOT/'outputs/demo/presentation.json',
                     nested_driver_dedup=True, source_recovery_boundary=True,
                     screw_resume_ms=600, completed_hold_resume_ms=2000)
    expected = baseline(base, args)
    actual = trial_config(base, args)
    assert actual['state_filter']['timing'].pop('release_resume_ms') == 2000
    assert Path(actual['logging']['output_root']).name == 'release-recovery-flow-sessions'
    actual['logging']['output_root'] = expected['logging']['output_root']
    assert actual == expected and base == original


def test_candidate_requires_hybrid_manual_start_and_finish():
    with pytest.raises(ValueError, match='hybrid'):
        trial_config({}, Namespace(guidance_mode='auto'))
