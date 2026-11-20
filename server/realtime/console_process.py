"""Fixed local session adapter and Windows-owned process cleanup."""
from __future__ import annotations

import ctypes
from ctypes import wintypes as w
import json
import os
import subprocess
import time
import uuid
from pathlib import Path


class BasicLimits(ctypes.Structure):
    _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
                ('flags', w.DWORD), ('min_working', ctypes.c_size_t), ('max_working', ctypes.c_size_t),
                ('active', w.DWORD), ('affinity', ctypes.c_size_t), ('priority', w.DWORD), ('scheduling', w.DWORD)]


class ExtendedLimits(ctypes.Structure):
    _fields_ = [('basic', BasicLimits), ('io', ctypes.c_uint64 * 6),
                ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                ('peak_process', ctypes.c_size_t), ('peak_job', ctypes.c_size_t)]


class OwnedProcess:
    """Kill-on-close job; the adapter waits on a gate before spawning children."""
    def __init__(self, command, log):
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        for name, args, result in (
            ('CreateJobObjectW', [w.LPVOID, w.LPCWSTR], w.HANDLE),
            ('SetInformationJobObject', [w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD], w.BOOL),
            ('AssignProcessToJobObject', [w.HANDLE, w.HANDLE], w.BOOL),
            ('CloseHandle', [w.HANDLE], w.BOOL),
        ):
            fn = getattr(self.kernel, name)
            fn.argtypes, fn.restype = args, result
        self.handle = self.kernel.CreateJobObjectW(None, None)
        self.process = None
        self.log = None
        try:
            limits = ExtendedLimits()
            limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not self.handle or not self.kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                raise ctypes.WinError(ctypes.get_last_error())
            self.log = Path(log).open('wb')
            env = os.environ.copy()
            # PowerShell 7's inherited module path hides Windows PowerShell built-ins.
            env.pop('PSModulePath', None)
            self.process = subprocess.Popen(command, stdout=self.log, stderr=subprocess.STDOUT,
                                            env=env, creationflags=subprocess.CREATE_NO_WINDOW)
            if not self.kernel.AssignProcessToJobObject(self.handle, int(self.process._handle)):
                self.process.terminate()
                self.process.wait(5)
                raise ctypes.WinError(ctypes.get_last_error())
        except Exception:
            self.close()
            raise

    def poll(self):
        return self.process.poll()

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None
        if self.process:
            self.process.wait(10)
        if self.log:
            self.log.close()


def hardware_report(data):
    screens = data.get('screens', [])
    display = len(screens) >= 2 and any(s.get('width') == 3840 and s.get('height') == 1080 for s in screens)
    checks = [dict(name='Beast 카메라 연결', ok=bool(data.get('camera'))),
              dict(name='확장 화면 · 3840×1080', ok=display)]
    return dict(ready=all(c['ok'] for c in checks), checks=checks, capture_verified=False)


class LiveJob:
    def __init__(self, process, folder):
        self.process, self.folder = process, folder

    def poll(self):
        return self.process.poll()

    def ready(self):
        try:
            return json.loads((self.folder / 'session.json').read_text(encoding='utf-8-sig'))
        except (OSError, ValueError):
            return None

    def stop(self):
        (self.folder / 'stop').touch()
        try:
            self.process.process.wait(12)
        except subprocess.TimeoutExpired:
            pass
        finally:
            self.process.close()


class Backend:
    def __init__(self, profile):
        self.profile = Path(profile).resolve(strict=True)
        self.root = Path(__file__).resolve().parents[2]

    def command(self, folder, check=False):
        command = ['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                   '-File', str(self.root / 'scripts/run_beast_console_session.ps1'),
                   '-Profile', str(self.profile), '-GateFile', str(folder / 'gate'),
                   '-RunFolder', str(folder)]
        if check:
            return command + ['-CheckOnly']
        return command + ['-Managed', '-ExternalStopFile', str(folder / 'stop')]

    def check(self, cancel=None):
        folder = self.profile.parent / 'checks' / uuid.uuid4().hex
        folder.mkdir(parents=True)
        job = OwnedProcess(self.command(folder, check=True), folder / 'check.log')
        try:
            (folder / 'gate').touch()
            deadline = time.monotonic() + 90
            while job.poll() is None:
                if cancel is not None and cancel.wait(.1):
                    return dict(ready=False, checks=[], capture_verified=False)
                if cancel is None:
                    time.sleep(.1)
                if time.monotonic() > deadline:
                    raise subprocess.TimeoutExpired('preflight', 90)
            result = json.loads((folder / 'check.json').read_text(encoding='utf-8-sig'))
            report = hardware_report(result)
            report['checks'].insert(0, dict(name='실행 파일 · 기존 보정', ok=bool(result.get('files'))))
            report['checks'].append(dict(name='다른 조립 안내 실행 없음', ok=not result.get('busy', False)))
            report['ready'] = report['ready'] and bool(result.get('files')) and not result.get('busy', False) and job.poll() == 0
            report['log_folder'] = str(folder)
            return report
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return dict(ready=False, capture_verified=False, checks=[dict(name='연결 점검 · 로그 확인 필요', ok=False)],
                        log_folder=str(folder))
        finally:
            job.close()

    def launch(self, folder):
        job = OwnedProcess(self.command(folder), folder / 'launcher.log')
        try:
            (folder / 'gate').touch()
            return LiveJob(job, folder)
        except Exception:
            job.close()
            raise
