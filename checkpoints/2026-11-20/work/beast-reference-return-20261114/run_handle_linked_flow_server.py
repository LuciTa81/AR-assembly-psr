"""Opt-in full flow using the same settings as the verified single-driver D trial."""
from pathlib import Path

from run_neutral_d_server import server, original_build


def trial_config(base, args):
    if getattr(args, 'guidance_mode', None) != 'hybrid':
        raise ValueError('This runner requires hybrid assembly flow')
    config = original_build(base, args)
    if config['screw_auto_trial'] or config['logging'].get('save_frames', False):
        raise ValueError('Full flow requires manual end confirmation and no image saving')
    config['state_filter']['timing'].update(
        retain_neutral_recovery=True,
        release_absence_ms=600,
        retain_completed_hold=True,
    )
    config['yolo']['handle_linked_driver'] = True
    config['logging']['output_root'] = str(Path(__file__).parent / 'handle-linked-flow-sessions')
    server.validate_config(config)
    return config


if __name__ == '__main__':
    server.build_effective_config = trial_config
    raise SystemExit(server.main())
