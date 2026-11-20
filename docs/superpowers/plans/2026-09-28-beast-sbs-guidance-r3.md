# R3 SBS Guidance Implementation Plan

> Execution: superpowers:executing-plans, direct implementation and one final independent review.

Goal: display independent eye-local rings in the normal guidance client using
the R2 contract, with explicit synthetic laptop preview and fail-closed expiry.
Architecture: GuidanceState retains assembly authority and owns a separate pure
SpatialGuidanceState. A small SBS presenter consumes that state; manual probes
remain unchanged. No real optical calibration can be activated yet.
Tech: existing Unity IMGUI/UnityWebRequest, C# NUnit, Python synthetic fixture.
Spec: 2026-09-27-beast-software-first-roadmap.md R3; ../../beast_display_contract.md.

## Constraints and Decisions

- No camera, Beast activation, real fitting, R4 recognition changes, cloud or paid resources.
- Preserve dirty work; no commit/push/merge. Record native ledger and before snapshots.
- Spatial lifetime is server pose age + full RTT + local elapsed, budget150ms;
  existing assembly-state budget500ms remains unchanged.
- Duplicate pose cannot change coordinates or refresh expiry. Invalid/lost data
  latches hidden until a newer valid observation, not a duplicate old success.
- Validate session, profile IDs/hashes, dimensions, convention, target/assembly
  consistency and synthetic provenance. Snapshot values are copied on acceptance.
- Explicit local preview config pins session/profiles/loopback endpoint and
  bounded duration (1..300s). It cannot be combined with a Beast display request
  or manual/test-ring mode. Preview goes to a non-VITURE display only.
- --sbs-guidance enables the layout; without preview config it remains uncalibrated.
  --spatial-preview-config enables synthetic rings in a laptop window only.
  H1 must add a separately validated real calibration loader before real AR rings.
- Fixed logical3840x1080 with per-eye1920x1080 is letterboxed for laptop preview.
  IMGUI is top-left already: do not flip Y; add1920 only to the right eye.
  Clip each half and keep a24px ring margin. Output size/name/mode change hides
  rings until restart (no automatic coordinate rescaling after registration).

## Tasks

### 1. Temporal State and Configuration
- [x] Add failing NUnit tests for config/mode isolation, independent pose/state
  ages, duplicates/mutation/older/future/missing data, lost/recovery, binding,
  target A-D consistency, uncalibrated mode and output changes.
- [x] Implement SpatialGuidanceState.cs and SbsGuidanceOptions.cs; connect through
  GuidanceState.Apply/Disconnect/InvalidResponse with no change to assembly policy.
- [x] Run full NUnit suite.

### 2. Transport and Renderer
- [x] Extend real Unity parser smoke with missing-nested-field/default checks and
  consumer expiry/duplicate/invalid cases before receiver changes.
- [x] Connect receiver configuration and parsed snapshots. Keep HTTP loopback,
  bounded response (64KiB), no redirects, one request at a time.
- [x] Add SbsGuidancePresenter.cs using independent clipped eye regions. Preserve
  existing normal/manual presenters; update bootstrap and launcher mode checks.
- [x] Add bounded Python fixture/replay for A-D movement, lost/stale/mismatch and
  recovery. Test fixture outputs and launcher's invalid combinations.
- [x] Extend the opt-in UI capture probe for SBS status/target screenshots only.

### 3. Integration and Review
- [x] Run pytest, NUnit, actual Unity parser/HTTP smoke and Windows build.
- [x] Run bounded interactive laptop preview; inspect Unity-rendered screenshots
  and pixels for both eye positions, movement, clipping and hidden failure states.
  No desktop screenshot or camera capture. End every process we start.
- [x] Run one scoped independent review, fix substantive findings with tests.
- [x] Update contract/roadmap with software-only results and remaining H1/R4 work.

## Review Focus

1. A duplicate good pose after loss/disconnect must not resurrect rings.
2. New state frames must not extend an old pose's lifetime.
3. Malformed/missing JSON must not inherit a previous fresh nested pose.
4. Preview must never migrate to Beast or silently accept a changed output.
5. Coordinates or profile objects mutated after acceptance must not move rings.

Each is pinned by task1 tests and transport/render checks in tasks2-3.

Validation: pytest242, NUnit146, Unity spatial smoke26, previous collection
HTTP/JSON smoke37, Windows build passed. Final Player pixel checks passed34
rendered images covering A-D and6 hidden states. Hidden-window captures were
black, so they are excluded and the visual check uses a visible laptop window.
See ../../beast_sbs_guidance.md for evidence paths and residual timing limits.
Independent review found a rejected bound pose ID could recover after missing
age was repaired. Six reproductions failed before the fix and passed afterward.
Consume identifiable bound IDs before payload validation; preserve timestamp
ordering without letting invalid timestamps poison subsequent valid observations.
Actual Unity JSON regression and final rebuilt Player were rerun successfully.
