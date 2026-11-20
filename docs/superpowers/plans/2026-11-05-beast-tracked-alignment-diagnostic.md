# Tracked Alignment Diagnostic Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement task-by-task.

**Goal:** Add an opt-in following-circle adjustment diagnostic for A/D, without changing calibration.
**Architecture:** Keep one target per collection session. Project the latest validated observation with the existing candidate; apply temporary eye-local offsets. Save the last actually rendered observation and final pixels, not a newly requested pose.
**Tech Stack:** Existing Python/OpenCV observation server, Unity C#, NUnitLite, pytest, PowerShell.
**Spec:** User approved following circle + per-eye adjustment, same-wearing A/D comparison, no automatic activation, no live device test until ready (2026-11-05).

## Constraints
- Preserve existing A-only defaults, read-only 30-second candidate probe, workspace and eye profiles.
- New opt-in collection may run up to 300 seconds at 3840x1080.
- One explicit target A-D per session; retain exact profile hashes and setup_id.
- Save numeric diagnostics only, under the existing local collection directory.
- New diagnostic schema must not be accepted as fit/activation input.
- Keep the 150ms observation freshness rule. No synthetic successful tracking.
- Pair confirmation is user evidence, not an automatic alignment certification.
- No camera, wearer test, commit, push or deployment in this implementation.

## Review Focus
- A/D identity mix-up: target must match session config and payload.
- Frame race: cached rendered pose and displayed final coordinates must stay paired.
- Stale/failed pose and changes before repaint: hide/reject, never refresh age by polling the same frame.
- Invalid offsets or output: reject nonfinite/offscreen pixels and wrong SBS dimensions.
- Old behavior: default A and read-only candidate probe remain unchanged.

## Tasks
- [x] Target binding: add --target-id (default A) to display_observation_server.py; validate C# config/payload binding. Test D XYZ/pixel, mismatches, invalid targets.
- [x] Pure diagnostic model: TrackedAlignmentDiagnostic.cs stores temporary per-eye offsets, confirmation, immutable rendered observation/pixels, and numeric diagnostic records. NUnit tests cover movement, snapshot cloning, stale samples, pending repaint, confirmation and bounds.
- [x] Wire recorder/probe and launcher: --tracked-alignment / -TrackedAlignment, single target, pair-only diagnostic save. Keep old manual and candidate paths. Candidate duration override only for explicit diagnostic mode.
- [x] Verify pytest + NUnit + Unity parser/render-data smoke + Windows build. Record limitations and next A/D wearer sequence.

## Files
- server/realtime/display_observation_server.py; tests/realtime/test_display_observation_server.py
- client_unity/Assets/Scripts/DisplayObservation.cs, DisplayObservationRecorder.cs, StereoAlignmentProbe.cs
- client_unity/Assets/Scripts/TrackedAlignmentDiagnostic.cs (new)
- scripts/run_beast_unity.ps1
- tests/unity/TrackedAlignmentDiagnosticTests.cs (new), GuidanceTests.csproj
- client_unity/Assets/Editor/CandidateProjectionSmoke.cs

## Verification
- Python: pytest tests/realtime
- C#: dotnet run --project tests/unity/GuidanceTests.csproj
- Unity: scripts/build_beast_unity.ps1; existing batch smoke tests and player build
- Hardware validation remains pending. Next: same wearing/settings, A reference then D diagnostic then A return check; no refit from these three samples.

## Results
- pytest realtime: 618 passed.
- NUnit: 263 passed, 1 optional external-data check skipped.
- Unity batch smoke: PASS (JSON, original corners, diagnostic atomic save, duplicate/lost rejection).
- Final Windows build: outputs/unity_p1/build-20261105-015754-392.log.
- Read-only review found a Channels-to-Both cache edge case; fixed by invalidating on every view transition, regression-tested and re-reviewed.
- No camera/wearer test, fit, profile activation, commit or push performed.
