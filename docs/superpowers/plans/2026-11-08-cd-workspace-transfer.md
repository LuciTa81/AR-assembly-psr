# C/D Workspace Transfer Implementation Plan

> Native execution in this session; no commit, camera, live server, or default activation.

**Goal:** Opt-in connection of immutable C/D depth records to the measured 202mm workspace.
**Architecture:** An explicit depth manifest pins source/destination candidate and workspace hashes. The loader verifies equal camera, display matrices, axes, units, and A-D targets, then uses the original source-bound depth functions at destination camera coordinates. Legacy manifests retain their existing behavior.
**Tech Stack:** Existing C# core, Unity JsonUtility, NUnitLite; no new dependencies.
**Spec:** docs/beast_cd_202mm_offline_review_20261108.md (next minimum step approved by user).

## Constraints and Decisions
- Do not rewrite original observations or change inverse-depth interpolation/range limits.
- No transfer field means legacy binding; malformed transfer fails closed, never falls back.
- Keep all validation flags false. Defaults, success binary, and automatic stage recognition stay unchanged.
- Workspace hashes pin the reviewed files; preparing this trial checks that only marker 1 X changes 205 to 202mm.
- Prefer source-bound models over relabeling old observations or recollecting C/D.

## Tasks
- [x] Add loader tests: legacy parity, explicit transfer, changed candidate/workspace/targets/camera/matrices/record bytes, malformed manifest, unchanged strict depth endpoints.
- [x] Implement StageDepthConfig loader and a narrow source-bound binding method; call the same loader from SbsGuidancePresenter.
- [x] Generate a separate manifest/candidate from reviewed sources; run all stored cases through the real loader and presentation path.
- [x] Run C# regression and a separate Unity compile/build only if available without replacing the successful binary; document limitations and next readiness-confirmed C/D test.

## Verification
- C# regression: 358 passed, 0 failed, 3 optional data tests excluded; loaded transfer replay separately passed.
- All 3035 stored target cases match the source-bound model. This is synthetic fresh-state parity, not measured runtime visibility.
- Actual Unity JSON: both original legacy manifest and explicit v2 transfer pass.
- Review found Unity creates an omitted inline transfer object. Reproduced the legacy failure, then fixed format selection with a scalar v2 schema and rejected populated unversioned transfers.
- Separate final player: outputs/unity_cd202_trial/BeastAssemblyGuide.exe. Original outputs/unity_p1 remains untouched.
- Trial artifacts: outputs/marker1_measured_20261108/cd-bridge-20261108T020303Z-0ae26668.
