# Beast Four-Corner Probe Implementation Plan

> Execute inline with superpowers:executing-plans. No commit or push in this task.

**Goal:** Add an opt-in 30-second SBS probe showing A-D rings and the lid perimeter.
**Spec:** User-approved scope in this chat: four rings, A highlighted, A-B-D-C-A thin lines; preserve the original A probe.
**Architecture:** The server adds optional named camera-space targets calculated from one pose and the registered workspace. Unity validates and retains them with the same observation/freshness gate, projects each through the existing eye matrices, and draws them in eye-local groups.
**Tech Stack:** Existing Python/OpenCV, C#/Unity 6000.3.25f1, NUnitLite, pytest.

## Constraints

- Same camera/workspace/candidate profile hashes; no recalibration or threshold changes.
- Existing A-only/manual/continuous modes retain their behavior.
- Explicit `--candidate-corners` / `-CandidateCorners` for the bounded probe only.
- Require all four named, finite, positive-depth targets from one current frame. Missing/invalid data or a point outside either eye hides the entire quad; never mix frames.
- Keep 150ms freshness and existing display/channel-confirmation guards.
- No stage arrows, vertical box edges, new servers, dependencies, images, or activation of calibration.

## Tasks

- [x] Data contract: add regression tests in `tests/realtime/test_display_observation_server.py`; run red, then add `camera_targets` to valid observations in `server/realtime/display_observation_server.py`. Check R @ world + t and absence on rejected/stale input.
- [x] Client geometry: extend `tests/unity/CandidateProjectionTests.cs` for all four eyes/targets, duplicate/missing/nonfinite/mixed-A data, stale/repeated/rejected frames and ABDCA edge order. Run red, then extend `DisplayObservation.cs` and `CandidateProjection.cs` without changing A-only behavior.
- [x] Probe drawing: extend `StereoAlignmentProbe.cs` and `scripts/run_beast_unity.ps1` with the opt-in switch; render four rings and four lines per eye, A highlighted. Extend wiring tests and actual Unity JSON smoke.
- [x] Verify: targeted pytest, full C# suite, Unity JSON smoke against a server-produced recorded-pose fixture, Windows build. Review scoped changes; record outcomes below.
- [ ] Physical trial only with user ready: same settings, max 30s, numeric logs only. Report optical alignment separately from software verification.

## Review Focus

- Missing/duplicate targets must not reuse old corners or disable the legacy A-only path.
- Same-frame polls must neither refresh expiry nor mutate displayed coordinates.
- A in the target array must agree with the validated A observation.
- Perimeter must be ABDCA, not crossing ABCDA, and each eye is clipped separately.
- Launch switch without the candidate probe must fail before starting an app.

## Outcomes

- Python contract tests: 58 passed (part of the 67-test run; only not-yet-wired drawing guard initially failed). Drawing wiring then passed, 9/9 lifecycle tests.
- C# red observed with the unimplemented corner projection; after implementation 254 passed, 1 optional external-report test skipped.
- Initial sandbox pytest temporary-directory permission errors were environment-only; reran with approved host permissions.
- Freshness, rendering thresholds and candidate profile files unchanged. Optical accuracy remains unverified.
- Full Python realtime suite: 612 passed; invalid launcher opt-in rejected before app start.
- Actual Unity parser/projector smoke passed with a server-produced payload from recorded frame 21, session d0a37e998ee244c290f24e7af6daf8f7. Log: `outputs/unity_p1/corners-smoke-20261105-000910.log`.
- Windows build passed: `outputs/unity_p1/build-20261105-001244-437.log`.
- Independent read-only review found no actionable defects. Remaining check: actual Unity line rendering and per-eye clipping, then physical optical alignment. User readiness requested once; no automatic camera launch during implementation.
