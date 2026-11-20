"""Opt-in D withdrawal trial; reuse the isolated recovery runner."""
from pathlib import Path

from run_neutral_d_server import server, trial_config as recovery_config


def trial_config(base, args):
    config = recovery_config(base, args)
    config['state_filter']['timing']['release_absence_ms'] = 600
    config['logging']['output_root'] = str(Path(__file__).parent / 'release-absence-D-sessions')
    server.validate_config(config)
    return config


if __name__ == '__main__':
    server.build_effective_config = trial_config
    raise SystemExit(server.main())
