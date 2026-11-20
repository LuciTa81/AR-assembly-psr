# Supervisor Demo Implementation Plan

**Goal:** Make the existing assembly workflow easier to operate and demonstrate without changing recognition or calibration.

**Architecture:** Additive HTML/CSS with the original supervisor controller, state model, and video client. A small candidate script renders a schematic and bounded page-local change history from the same model, with no additional network polling.

**Stack:** Plain HTML/CSS/JavaScript, Node test runner, Playwright, existing camera-free Python assembly fixture.

**Spec:** `../specs/2026-11-08-supervisor-demo-design.md`

**Constraints:** Preserve successful files. No camera/Unity, external image upload, deployment, or commit. Do not imply torque verification or through-lens registration from a dashboard image.

**Review Focus:** Stale state must not appear actionable; history must not invent completion; confirmation and video privacy behavior must remain unchanged.

## Tasks

- [x] Add failing tests for bounded history, session changes, transient states, and connection faults.
- [x] Implement candidate HTML/CSS and minimal page-local enhancement.
- [x] Verify existing unit tests and candidate browser flows, privacy, keyboard, and responsive layout.
- [x] Inspect screenshots and launch the existing offline rehearsal server at the candidate URL.

## Verified

- 45 Node tests passed, including semantic replay of the saved successful session.
- 45 browser state/viewport checks passed across 320, 390, 1280, 1440, and 1920px widths.
- Real assembly controller with synthetic inputs completed S0-S1-A-B-C-D-S6-COMPLETED with three confirmations.
- Reproduced and fixed mode-label mismatch, target/cue transition lag, and page-cache restoration handling.
- Original supervisor/controller/video, recognition, Unity, and calibration files were not edited.

See `../specs/2026-11-08-supervisor-demo-verification.md` for evidence and operating limits.
