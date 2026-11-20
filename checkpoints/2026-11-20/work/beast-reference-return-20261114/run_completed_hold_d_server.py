"""Opt-in completed-HOLD checkpoint trial; never changes the production config."""
from pathlib import Path

from run_release_absence_d_server import server, trial_config as previous_trial_config


def trial_config(base, args):
    config = previous_trial_config(base, args)
    config['state_filter']['timing']['retain_completed_hold'] = True
    config['logging']['output_root'] = str(Path(__file__).parent / 'checkpoint-D-sessions')
    server.validate_config(config)
    return config


if __name__ == '__main__':
    server.build_effective_config = trial_config
    raise SystemExit(server.main())
