# Self-Service Console Implementation Plan

**Goal:** Open the laptop console independently and start/stop a fresh owned session.
**Architecture:** Loopback controller, fixed candidate adapter, existing supervisor UI.
**Tech Stack:** Python standard library, PowerShell, existing JavaScript/CSS.
**Spec:** docs/beast_self_service_console.md

## Constraints

No calibration/FSM changes; no live capture in development tests; no remote access.
No automatic baseline promotion. Stop only owned processes. Keep numeric logs.

## Tasks

- [x] Add tests/realtime/test_console_controller.py: lifecycle, concurrency,
  preflight failure, startup cancellation, restart, same-origin API and proxy.
  Observe failure before implementing server/realtime/console_controller.py.
- [x] Add server/realtime/console_process.py and scripts/run_beast_console_session.ps1;
  extend the existing isolated trial launcher with opt-in managed lifetime only.
  Test actual dummy child cleanup and timeout, without hardware.
- [x] Add web_overlay/supervisor_console.js/css, loaded only on controller hosting;
  keep the original supervisor unchanged on the old live server.
  Test desktop/mobile, reload persistence, start/stop and failure messaging.
- [x] Add scripts/open_beast_console.ps1, local user profile and one-click opener.
  Run preflight without capture, project regressions, hash checks; leave UI idle.

## Review Focus

Cross-origin start/confirm rejected; no arbitrary paths/URLs from requests.
Stop during check/start must never launch a late camera after stop.
Server/Unity failure must not leave the other running.
Stale browser requests must not confirm a new session.
Controller death must release all child processes.
