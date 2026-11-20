# Observed Cue Delay Implementation Plan

**Goal:** Delay only the SBS green ring and MOVE CLEAR cue by 2000 ms after
the first current OBSERVED presentation. Keep engagement at 800 ms and
all server transitions unchanged, as explicitly requested on 2026-11-14.

**Architecture:** A small pure C# presentation filter runs before the existing
text-stability filter. Its clock belongs to session/state/target, not pose frames.
Short pauses hide actionable output without restarting the clock; recheck,
renewed engagement, faults, or a new context clear it. No previous actionable
view is cached. Disabled by default.

**Tech Stack:** Existing Unity/C#, NUnitLite and PowerShell launchers.

## Constraints and Review Focus

- Do not change Python state logic, calibration, camera parameters or recognition.
- Preserve outputs/unity_p1; build outputs/unity_cue_delay_20261114 separately.
- Delaying presentation must not delay a stage change or final confirmation.
- A pause/disconnect must never be replaced with delayed MOVE CLEAR.
- Repeated GUI calls and repeated snapshots must not restart the clock.
- Test time reversal/non-finite time and independent session/target clocks.
- No camera or live trial until build verification and user readiness.

## Implementation

- [x] Add failing NUnit tests for cue timing, recovery, faults, scope and options.
- [x] Implement ObservedCueDelay and --observed-cue-delay-ms (0..5000, default 0).
- [x] Apply one filtered view to SBS ring color and instruction text.
- [x] Forward opt-in delay and separate Unity output directory through launchers.
- [x] Run focused and complete C# regressions and launcher syntax checks.
- [x] Build the separate player, verify baseline hashes, and run offline playback.
- [x] Record validation and request readiness for the bounded comparison.
- [x] Apply user's post-trial blue working cue and revalidate the separate build.

## Validation

- RED: 29 focused tests, 20 expected failures before implementation, no errors.
- GREEN: full C# suite 390 passed, 0 failed, 3 skipped (opt-in coordinate audits).
  Includes 32 cue-delay cases after boundary/recovery additions.
- Four changed PowerShell scripts parsed without errors.
- Separate Unity build succeeded; existing player, assembly, calibration config,
  candidate, runtime config and two Python timing/filter modules: 8 hashes unchanged.
- No-camera Unity playback exited normally: WORKING shown for OBSERVED, next stages
  and FINAL CHECK still arrive. Pixel check passed for 65 SBS frames, A-D rings,
  independent eye positions and hidden rings during input faults.
- Playback evidence: outputs/cue-delay-playback-20261114-162119.
- Preflight with the original C/D records passed. No camera inference is performed
  by preflight. User readiness confirmed before the bounded A-to-B live comparison.
- Live session viture_aruco_rt_20261114_162327_ab096174a63f: S2-to-S3 transition
  recorded. Unity logged HOLD AT A, WORKING, MOVE CLEAR, then WORK AT B.
  User confirmed releasing after green and seeing B; timing felt approximately right.
  Camera and owned Unity process stopped. No live image or video saving.
- User requested blue instead of amber during work. In the opt-in trial, OBSERVING
  (HOLD and delayed WORKING) uses the existing cyan/blue ready color. PAUSED
  remains amber and OBSERVED after the delay remains green. Default behavior unchanged.
- Blue revision: build succeeded, C# suite again 390 passed / 0 failed / 3 skipped.
  outputs/cue-delay-blue-playback-20261114-162748: 67 SBS frames passed pixel checks;
  blue ring pixels present during delayed OBSERVED and WORKING visually verified.
  This color revision was checked offline only. Eight baseline hashes still match.
  No Unity players or port-8765 listener remain after validation.

## Trial Use

Build with scripts/build_beast_unity.ps1 -OutputDirectory outputs/unity_cue_delay_20261114.
Opt in via -ObservedCueDelayMs 2000 -UnityOutputDirectory outputs/unity_cue_delay_20261114.
Default launch and outputs/unity_p1 remain unchanged. This is a presentation delay,
not tightening verification; an early valid release can still advance the server.
