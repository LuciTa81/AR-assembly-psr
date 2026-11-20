"""Opt-in single physical driver trial; leave production and calibration files alone."""
from pathlib import Path

from run_completed_hold_d_server import server, trial_config as previous_trial_config


def trial_config(base, args):
    config = previous_trial_config(base, args)
    config['yolo']['handle_linked_driver'] = True
    config['logging']['output_root'] = str(Path(__file__).parent / 'handle-linked-D-sessions')
    server.validate_config(config)
    return config


if __name__ == '__main__':
    server.build_effective_config = trial_config
    raise SystemExit(server.main())
