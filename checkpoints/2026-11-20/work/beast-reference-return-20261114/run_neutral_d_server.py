"""Isolated D recovery trial; keep the production launcher and configuration intact."""
import sys
from pathlib import Path

ROOT = Path(r"C:/Users/fresh/OneDrive/Desktop/홍익대/4학년/2학기/vision/01_SUBMIT_KEEP/AR-assembly-psr_github_main_20260604/.worktrees/viture-beast-overlay-mvp")
sys.path.insert(0, str(ROOT))
from server.realtime import run_realtime_server as server

original_build = server.build_effective_config


def trial_config(base, args):
    config = original_build(base, args)
    if config['guidance_mode'] != 'auto' or not config['screw_auto_trial']:
        raise ValueError('This runner requires an isolated screw trial')
    if config['state_filter']['max_state'] != 'S6' or config['logging']['save_frames']:
        raise ValueError('D trial must end at S6 without image saving')
    config['state_filter']['initial_state'] = 'S5'
    config['state_filter']['timing']['retain_neutral_recovery'] = True
    config['logging']['output_root'] = str(Path(__file__).parent / 'neutral-D-sessions')
    server.validate_config(config)
    return config


if __name__ == '__main__':
    server.build_effective_config = trial_config
    raise SystemExit(server.main())
