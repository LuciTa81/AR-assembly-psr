"""Opt-in release recovery. Reuse the successful full flow without changing it."""
from pathlib import Path

from run_handle_linked_flow_server import trial_config as baseline_config, server


def trial_config(base, args):
    config = baseline_config(base, args)
    config['state_filter']['timing']['release_resume_ms'] = 2000
    config['logging']['output_root'] = str(Path(__file__).parent / 'release-recovery-flow-sessions')
    server.validate_config(config)
    return config


if __name__ == '__main__':
    server.build_effective_config = trial_config
    raise SystemExit(server.main())
