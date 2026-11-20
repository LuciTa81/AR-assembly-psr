import importlib.util
import ctypes
from ctypes import wintypes
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def api():
    path = ROOT / 'server/realtime/console_process.py'
    assert path.exists(), 'Owned process adapter is not implemented'
    spec = importlib.util.spec_from_file_location('console_process_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows job ownership')
def test_job_close_kills_own_child_not_unrelated_process(tmp_path):
    m = api()
    sibling = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
    try:
        job = m.OwnedProcess([sys.executable, '-c', 'import time; time.sleep(30)'], tmp_path / 'log.txt')
        assert job.poll() is None
        job.close()
        assert job.poll() is not None
        assert sibling.poll() is None
    finally:
        sibling.terminate()
        sibling.wait(5)


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows job ownership')
def test_job_close_cleans_descendants(tmp_path):
    m = api()
    command = [sys.executable, '-u', '-c',
               "import subprocess,sys,time; child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); print(child.pid,flush=True); time.sleep(30)"]
    job = m.OwnedProcess(command, tmp_path / 'tree.log')
    handle = None
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    try:
        deadline = time.monotonic() + 5
        while not (text := (tmp_path / 'tree.log').read_text().strip()):
            assert time.monotonic() < deadline
            time.sleep(.01)
        handle = kernel.OpenProcess(0x100000, False, int(text))
        assert handle
        assert kernel.WaitForSingleObject(handle, 0) == 258
        job.close()
        assert kernel.WaitForSingleObject(handle, 5000) == 0
    finally:
        job.close()
        if handle:
            kernel.CloseHandle(handle)


def test_profile_command_cannot_be_changed_by_browser(tmp_path):
    m = api()
    backend = m.Backend.__new__(m.Backend)
    backend.root = ROOT
    backend.profile = tmp_path / 'profile.json'
    command = backend.command(tmp_path, check=True)
    assert '-CheckOnly' in command
    assert '-Managed' not in command
    run = backend.command(tmp_path, check=False)
    assert '-Managed' in run
    assert '-CheckOnly' not in run
    assert str(tmp_path / 'stop') in run


def test_display_and_camera_checks_do_not_claim_capture_verified():
    m = api()
    result = m.hardware_report({'camera': True, 'screens': [{'width': 3840, 'height': 1080},
                                                          {'width': 1920, 'height': 1080}]})
    assert result['ready']
    assert result['capture_verified'] is False
    assert not m.hardware_report({'camera': True, 'screens': [{'width': 3840, 'height': 1080}]})['ready']
    assert not m.hardware_report({'camera': False, 'screens': []})['ready']
