import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='PowerShell console adapter')


@pytest.mark.parametrize('display', ['baseline', 'korean', 'missing'])
def test_console_selects_local_display_without_changing_workflow(tmp_path, display):
    trial = tmp_path / 'trial'
    korean = tmp_path / 'korean'
    trial.mkdir()
    korean.mkdir()
    stub = '''param(
        [string]$UnityOutputDirectory, [string]$CandidateProjection,
        [int]$ObservedCueDelayMs, [switch]$Managed, [switch]$NoBrowser,
        [string]$ExternalStopFile, [string]$ManagedRunFolder
    )
    $PSBoundParameters | ConvertTo-Json -Compress
    '''
    (trial / 'run-neutral-D-trial.ps1').write_text(stub, encoding='utf-8-sig')
    (trial / 'lid-prism-build').mkdir()
    (korean / 'run-korean-trial.ps1').write_text(stub, encoding='utf-8-sig')
    (korean / 'player-v2').mkdir()
    profile = {'schema_version': 'beast_console_profile_v1', 'python': sys.executable,
               'trial_directory': str(trial)}
    if display != 'baseline':
        profile['action_guidance_directory'] = str(korean if display == 'korean' else tmp_path / 'missing')
    profile_path = tmp_path / 'profile.json'
    profile_path.write_text(json.dumps(profile), encoding='utf-8')
    gate = tmp_path / 'gate'
    gate.touch()
    command = ['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
               '-File', str(ROOT / 'scripts/run_beast_console_session.ps1'),
               '-Profile', str(profile_path), '-GateFile', str(gate), '-RunFolder', str(tmp_path),
               '-Managed', '-ExternalStopFile', str(tmp_path / 'stop')]
    result = subprocess.run(command, capture_output=True, timeout=20)
    if display == 'missing':
        assert result.returncode != 0, 'Missing selected display must not silently use the baseline'
        return
    assert result.returncode == 0, result.stderr.decode('utf-8', errors='replace')
    options = json.loads(result.stdout.decode('utf-8-sig').strip())
    expected = korean / 'player-v2' if display == 'korean' else trial / 'lid-prism-build'
    assert Path(options['UnityOutputDirectory']) == expected
    assert Path(options['CandidateProjection']) == trial / 'candidate-ABCD-joint-unverified.json'
    assert options['ObservedCueDelayMs'] == 2000
    assert options['Managed'] and options['NoBrowser']
    assert Path(options['ExternalStopFile']) == tmp_path / 'stop'
    assert Path(options['ManagedRunFolder']) == tmp_path
