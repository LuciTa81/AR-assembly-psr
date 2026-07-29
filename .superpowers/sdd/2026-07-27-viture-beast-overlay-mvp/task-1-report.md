# Task 1 Report: Automated Test and Hardware-Gate Foundation

## Implementation Summary

- Added the realtime development requirements file with the required pytest and websockets pins.
- Added deterministic `probe_mode` camera probing with requested/actual mode data, sampled read timing, failure counts, previews, and CSV output fields.
- Refactored `probe_index` to delegate to `probe_mode`; added `--modes` and `--sample-seconds` CLI options.
- Added a sequential PowerShell gate runner. It probes DirectShow and MSMF one at a time, writes per-backend CSVs and previews, combines them into `outputs/realtime_camera_probe/beast_camera_modes.csv`, and prints the manual checklist path. It scans configurable indices and does not identify the Beast by a fixed index.
- Added the manual hardware checklist and report template for the required display, FOV, 30-minute concurrency, blur, tint, scaling, and USB observations.

## Tests and Exact Results

Fresh automated verification:

```text
.\\.venv_rt\\Scripts\\python.exe -m pytest tests\\realtime -v
3 passed in 0.26s
```

Fresh hardware-runner verification:

```text
.\\scripts\\run_beast_hardware_gate.ps1
Exit code: 0
```

The runner created `outputs/realtime_camera_probe/camera_probe_dshow.csv`, `camera_probe_msmf.csv`, `beast_camera_modes.csv`, and three preview files. Its final run observed a functioning camera at index 0 for both backends; this is probe output only, not Beast identity confirmation.

Additional verification:

```text
.\\.venv_rt\\Scripts\\python.exe server\\realtime\\probe_cameras.py --help
Exit code: 0

git diff --check
Exit code: 0
```

## TDD RED/GREEN Evidence

Initial RED run after adding the requested tests:

```text
.\\.venv_rt\\Scripts\\python.exe -m pytest tests\\realtime\\test_probe_cameras.py -v
2 failed in 0.54s
AttributeError: module 'server.realtime.probe_cameras' has no attribute 'probe_mode'
```

GREEN after the minimum `probe_mode` implementation:

```text
.\\.venv_rt\\Scripts\\python.exe -m pytest tests\\realtime\\test_probe_cameras.py -v
2 passed in 0.46s
```

Self-review found that a transient final read failure could discard an earlier successful preview frame. A focused regression test was added first.

```text
RED: 1 failed, 2 passed in 1.65s
Failure: expected the last successful frame, received None.

GREEN: 3 passed in 0.26s
```

## Files Changed

- `server/realtime/requirements-dev.txt`
- `server/realtime/probe_cameras.py`
- `tests/realtime/__init__.py`
- `tests/realtime/test_probe_cameras.py`
- `scripts/run_beast_hardware_gate.ps1`
- `docs/beast_hardware_gate.md`
- `.superpowers/sdd/2026-07-27-viture-beast-overlay-mvp/task-1-report.md`

## Self-Review

Reviewed the final diff against the task brief. The CSV contains every required field, unsuccessful captures release their handle, successful captures retain the latest valid preview frame, and both hardware backends are invoked sequentially. The runner has no permanent Beast camera index and produces the required combined CSV. No code findings remain from the self-review.

## Concerns

- The required `pip install -r server\\realtime\\requirements-dev.txt` initially exited 1 with `WinError 32` while writing a matplotlib backend file. The virtual environment subsequently contained the required packages, `pip check` reported `No broken requirements found`, and all task verification ran successfully. The installation event is recorded for reproducibility.
- The unattended runner cannot truthfully complete the 30-minute display/camera concurrency test, identify the Beast from a preview, or assess FOV overlap, blur, tint, brightness, Windows scaling, and USB adapter behavior. These remain explicit unchecked manual-gate items.
- The probe run found a working camera at index 0. Its identity has not been confirmed as the Beast, and the DirectShow 1280x720 sample measured approximately 4.7 FPS in the final run; those observations must be validated manually before subsequent AR work.
