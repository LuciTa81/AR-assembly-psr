# Beast Collection R1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Execute approved R1 only; no camera or Beast session in this task.

**Goal:** Make the next correspondence capture diagnosable and resumable without claiming calibration.
**Architecture:** One camera worker optionally sends its image to a local no-save Tk preview. The store/HTTP remain metadata-only. Unity uses serialized fresh HTTP requests for feedback and captures, and restores only explicitly selected eye coordinates.
**Tech Stack:** Existing Python/OpenCV/Tk, Unity/C#, pytest/NUnit, Unity batch smoke.
**Spec:** 2026-09-27-beast-software-first-roadmap.md (R1), ../specs/2026-09-27-beast-display-correspondence-design.md.

## Constraints
- No hardware capture, external services, video storage, commit/push.
- Preserve all previous worktree changes and old camera-free probes.
- Missing diagnostic count differs from observed zero. Rejected/stale data cannot become a saved candidate.
- Fresh capture on Enter, not a previously polled observation. One HTTP request in flight.
- Restored coordinates never restore marked count, channel confirmation or calibration.
- Preview is explicit opt-in and ignores image-save keys. Existing standalone preview default behavior stays unchanged.

## Task 1: Python diagnostic metadata and same-source preview
Files: server/realtime/display_observation_server.py, workspace_live_preview.py; tests/realtime/test_display_observation_server.py, test_workspace_live_preview.py.
- [x] RED tests for rejected marker IDs/count, unknown/stale status, metadata-only store, one-worker preview lifecycle and disabled saving.
- [x] Preserve marker_ids/marker_count when observed, null/-1 when unknown; no old target on failure.
- [x] Add run_collection(..., preview=False), CLI --preview. PreviewWindow(..., allow_save=False) and same packet display. Ignore save key even if emitted. Strip image before store copy.
- [x] GREEN focused pytest including preview-off compatibility, close/error cleanup and no image files.

## Task 2: Pure C# resume and live feedback
Files: StereoAlignmentState.cs, DisplayObservation.cs; tests/unity/StereoAlignmentStateTests.cs, DisplayObservationTests.cs.
- [x] RED coordinate restoration and per-eye saved-status tests. RestorePositions(point, now) validates scope/coordinates/size and resets all confirmations; restore only before any current-session mark.
- [x] Add MarkStatus for selected view so changed positions are UNSAVED; do not treat other eye's save as this eye's save.
- [x] Add DisplayObservationFeedback with Apply(config, observation, start, end), Status(now), Detail(now). Validate binding/geometry/quality, expire freshness including RTT; missing IDs show unknown.
- [x] GREEN NUnit including malformed restore, stale and cross-session feedback.

## Task 3: Unity transport/controls and integration
Files: DisplayObservationRecorder.cs, StereoAlignmentProbe.cs, scripts/run_beast_unity.ps1; Editor/DisplayObservationSmoke.cs.
- [x] RED actual Unity smoke cases: diagnostic polling never saves; collection uses a new HTTP observation; restore parser rejects missing coordinates; request serialization and cancellation.
- [x] Share one bounded HTTP/parser path. Poll at <=10Hz; Enter queues behind an active poll with adjustment frozen, then makes its own request. Queue wait counts toward the150ms freshness budget. Polls do not overwrite capture outcome.
- [x] Add explicit --stereo-start-point path (-StereoStartPoint in launcher) for a manual point or correspondence candidate; load only display coordinates using initialized DTO and size limits.
- [x] Render per-eye saved state separately from connection/marker feedback. Display detailed reason on a separate constrained line.
- [x] Run full pytest/NUnit, actual Unity batch smoke and Windows build; no camera, no wearable trial.

## Review Focus
- Zero vs missing marker IDs on rejected/stale responses.
- Preview exception/close still releases sole camera owner and HTTP server.
- Poll/Enter race cannot save cached observation or overlap requests.
- Returning to a saved eye cannot inherit another eye's SAVED; moving marks current eye unsaved.
- Restore JSON with missing/out-of-range coordinates, wrong scope/size cannot confirm or silently center an eye.

## Finish
- Record results and usage in docs/beast_manual_alignment_probe.md and update R1 roadmap checkboxes only.
- One independent scoped review, a single regression-backed fix pass if needed.
