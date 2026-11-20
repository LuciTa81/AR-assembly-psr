# R4 Timed State Guidance Implementation Plan

> Execute directly with superpowers:executing-plans and one scoped final review.

Goal: keep the current screw instruction until continuous observed engagement
and a positively observed tool withdrawal; never infer withdrawal from loss.
Architecture: OnlineStateFilter remains the sole assembly authority. A small
timed evidence gate supplies phase/candidate evidence; Unity only presents it.
Tech: existing Python, metadata replay, Unity IMGUI/JSON and NUnit.
Spec: ../specs/2026-09-26-beast-minimal-harness-design.md; R4 of
2026-09-27-beast-software-first-roadmap.md.

## Constraints and Decisions

- No camera/Beast activation, real calibration, HMM changes, cloud, commit/push.
- Preserve earlier dirty work and before snapshots in this plan's ledger directory.
- Explicit guidance_policy=timed_v1 for the Beast config; absent policy retains
  legacy_frames for exact replay of earlier logs. No silent old-log conversion.
- Use source observation timestamps, not callback/frame counts, for dwell.
  Initial software values: placement300ms, engagement800ms, withdrawal400ms,
  max consecutive observation gap350ms, recognition age800ms, acknowledgement1200ms.
  These are configurable starting values, not measured physical accuracy.
- Unique current target must meet the existing proximity/confidence threshold.
  Actual driver + valid tip geometry are mandatory. Equal or stronger competing
  target is not an engagement; positive withdrawal uses target proximity<=0.15,
  with visible valid tool geometry. Missing detections are unknown, not withdrawal.
- Loss/invalid/stale/long gap clears pending evidence and acknowledgement, keeps
  confirmed assembly state. Repaired/duplicate/older observations never add time.
- Engagement and withdrawal must be separate continuous runs. During engagement,
  OBSERVING; after sufficient engagement, OBSERVED while still targeting A;
  only withdrawal commits S2->S3. Fresh near evidence cancels partial withdrawal.
- UI phase is orthogonal to assembly and pose. Current phases: GUIDING,
  OBSERVING, OBSERVED, PAUSED, AWAITING_CONFIRMATION. Marker/connection/pose/
  calibration gates retain precedence. S6 requires user confirmation, no torque claim.
- Acknowledgement is separate text, never overrides next_action/target. Its
  remaining lifetime derives from original transition time and does not refresh
  through duplicate snapshots. No automatic final confirmation command this stage.

## Task 1: Timed Evidence and Replay

Files: create server/realtime/guidance_timing.py; modify online_state_filter.py,
realtime_replay.py; tests/realtime/test_timed_guidance.py and test_replay.py.
Interfaces: OnlineStateFilter.update gains timestamp_ms, observation_timestamp_ms,
roi_valid. StateEstimate gains guidance (optional immutable-value DTO).
- [x] Add RED tests: long near does not advance; near800ms then visible far400ms
  advances exactly once; brief touch/wrong target/ambiguous target cannot arm;
  zero detections, invalid tip, stale/lost/duplicate/older/future/missing data
  cannot release; loss clears pending; gap requires re-engagement.
- [x] Add FPS-independent source-time tests and S0/S1 continuous placement tests,
  max_state cap, S6 confirmation and timed acknowledgement tests.
- [x] Implement timed gate and integrate one-step advancement in OnlineStateFilter.
  Keep legacy unchanged; reject invalid timing/policy configuration.
- [x] Extend exact replay input/output for timed guidance, target, instruction
  and acknowledgement. Require timing/validity fields for timed logs.
- [x] Run pytest full suite. Expected: all pass, legacy replay unchanged.

## Task 2: Runtime and Unity Contract

Files: schemas.py, run_realtime_server.py, harness_check.py, primary Beast config;
GuidanceSnapshot.cs, GuidanceState.cs, GuidancePresenter.cs, SbsGuidancePresenter.cs;
tests/realtime and tests/unity; new actual Unity guidance smoke.
Interface: optional guidance schema assembly_guidance_v1, phase, reason,
acknowledgement, acknowledgement_remaining_ms. Existing next_action and target
remain authoritative. Do not add spatial calibration/pose inference.
- [x] RED test real runtime input timestamp/validity wiring and replay parity;
  share a small runtime input/message helper between runtime and metadata fixture.
- [x] Wire policy/timing and source timestamps. Stop legacy frame-based instruction
  replacement in timed mode. Persist exact filter inputs and full guidance result.
- [x] RED C# tests for phase/target contract, presentation precedence,
  bounded acknowledgement independent of duplicate receipt, missing/invalid
  fields, lost/connection/uncalibrated/pose states and terminal confirmation.
- [x] Implement optional DTO and one shared presentation decision in GuidanceState;
  both normal and SBS presenters consume it. No secondary state inference.
- [x] Run full pytest/NUnit and actual Unity JSON smoke. Expected: pass.

## Task 3: End-to-End Software Evidence

- [x] Replay a scripted S0-S6 metadata sequence including false approach,
  sustained work, no-tool gap, marker loss, withdrawal and final confirmation.
  Hand-checked milestone states and target/action/phase must agree.
- [x] Build Windows Player, serve finite loopback fixture using actual filter +
  runtime message code, inspect its own rendered normal/SBS UI with no camera.
  Keep synthetic spatial coordinates isolated as R3 and never enable real rings.
- [x] Run existing Unity spatial/collection regression smokes and full suites.
- [x] One independent review; fix substantive findings with RED->GREEN tests.
- [x] Update roadmap and user-facing status/commands/known limitations.

Completed 2026-09-28: pytest288, NUnit165, actual Unity guidance629/spatial26/
correspondence37; Windows build; final R4 SBS57 frames and R3 regression40 frames
pass pixel checks. Normal text rendering inspected from C/D through confirmation
and disconnect. Full state-sequence coverage uses the metadata/SBS fixture.
Independent review fixes and actual Unity legacy parser fix are recorded in the
ledger. No hardware/camera/cloud, commit or push. Physical H1/H2 remain open.
User-facing details: ../../beast_state_guidance.md.

## Review Focus

1. Reused YOLO frame with a fresh parent frame cannot accrue dwell or end a step.
2. A successful but empty detection is not positive withdrawal.
3. Loss during release must not let late pre-loss observations finish the step.
4. Acknowledgement of A must not replace an instruction or ring for B.
5. Uncalibrated positional output must not suppress valid nonpositional S0/S1
   instructions, while pose loss must not look like active spatial guidance.
