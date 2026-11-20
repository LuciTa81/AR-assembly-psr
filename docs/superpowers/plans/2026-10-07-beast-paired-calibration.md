# Beast paired calibration collection

## Scope and completion

Implement the next software-only registration step. No camera access, optical
validation claim, calibration activation, device setting changes, commit or push.
Preserve existing single-eye records and the unverified runtime probe.

1. Add an explicitly confirmed binocular snapshot in the existing Unity probe.
   One file contains both eye pixels and one fresh camera observation. Require a
   short window of distinct stable camera observations before accepting a pair.
2. Extend the offline fitter to read paired snapshots without treating old
   single-eye comparison coordinates as valid pairs. Preserve pose-level
   fit/check separation, duplicates and profile bindings.
3. Add dataset assembly and diagnostics: collection counts/coverage, held-out
   pixel error by depth, fitted eye centers and relative geometry. Reports never
   imply millimetre or optical accuracy and never auto-activate a profile.
4. Run focused red/green tests, full Python and C# regression suites, Unity
   HTTP/serialization smoke and Windows build. Reanalyze the existing dataset
   without overwriting the existing fit. Document the next physical test.

## Decisions

- Reuse A and deliberate camera-relative viewpoint/depth variation. Adding new
  physical target IDs or changing the workspace pose solver requires reference
  measurements and is outside this software-only step.
- Preserve normalized DLT for comparison. Diagnose coverage, held-out error and
  impossible fitted geometry first; do not introduce unmeasured eye/IPD priors
  or select an optimizer against the same check data.
- Stability uses recent distinct frames, not repeated polls of a cached frame.
  It is a numeric motion screen, not proof of camera/display synchronization.
- New pair acceptance is explicit Enter in Both view. Old per-eye Enter stays
  compatible; a legacy Both display object alone is never a paired observation.
- Calibration status remains false even when mathematical checks pass.
- No new service, package or cloud infrastructure.

## Progress

- Baseline: inspected collection, fitter, Unity state/recorder and existing tests.
- Pair capture: complete. Fresh shared observation, explicit Both Enter,
  distinct-frame stability screen, separate PAIR SAVED state; no auto-activation.
- Offline dataset and diagnostics: complete. Paired/legacy readers, explicit
  fit/check assembly, setup/session separation, depth and stereo diagnostics.
- Regression/build/review: complete. Final regression: 426 Python, 219 C#,
  52 Unity HTTP checks. Windows build-20261007-142302-544 passed.
  Existing 20261006 candidate reanalysis produced needs_review without activation.
- Handoff: docs/beast_paired_calibration_20261007.md records commands, collection
  protocol, heuristic limitations and the next one-pose hardware check.
- Review ruling: one pose per paired collection session; reject renamed pose
  groups that split that session between fit/check. Keep 1080p pair capture
  consistent with the offline reader rather than silently saving unusable 1200p.
- Review tooling: no independent subagent tool available; local contract and
  regression review performed, not represented as an independent review.
