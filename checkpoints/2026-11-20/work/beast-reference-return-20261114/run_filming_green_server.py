"""Explicit filming runner; production filter and calibration remain unchanged."""
import os
from pathlib import Path

from run_release_recovery_flow_server import server, trial_config as baseline_config
from server.realtime import online_state_filter
from filming_green import FilmingGreenGate


def trial_config(base, args):
    config = baseline_config(base, args)
    config['logging']['output_root'] = str(Path(__file__).parent / 'filming-green-sessions')
    return config


if __name__ == '__main__':
    log = os.environ.get('AR_FILMING_PLAYER_LOG')
    if not log or not Path(log).is_absolute():
        raise SystemExit('A unique absolute player log path is required for filming mode')
    online_state_filter.TimedEvidenceGate = lambda timing: FilmingGreenGate(timing, log_path=log)
    server.build_effective_config = trial_config
    print('[FILMING MODE] Unity rendered Release tone + 2000 ms; not automatic fastening verification', flush=True)
    raise SystemExit(server.main())
