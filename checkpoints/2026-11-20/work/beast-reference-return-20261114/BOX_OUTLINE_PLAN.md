# Box outline trial

## Approved direction
- Preserve successful players, server policies and all A-D calibration files.
- Brighter context rings remain; replace the screw-center quad with a separately registered box wireframe, only with explicit opt-in.
- Start at S1 as a lid placement reference, not lid detection. S2-S5 keep the existing active target and blue/green cues. S0/S6 have no outline.
- Top rim is stronger; lower and vertical edges are subordinate. No fill or occlusion claim.

## Approach
Use the existing fresh observation rvec/tvec and existing eye projections; no server protocol or inference changes. A separate small profile binds eight world vertices to the exact camera/workspace hashes. Height alone cannot define the exterior. Saved photographs support registration; unobserved dimensions require confirmation. A provisional profile must remain labeled unverified and cannot replace the baseline.

## Implementation and checks
- [x] Inspect saved photos and register a separate provisional exterior; record assumptions and held-out comparison.
- [x] Add opt-in profile validation and fresh-pose access, with session, stale, rejection, geometry and pose-consistency tests.
- [x] S1 polling and context-only rendering; active target remains unchanged and independent of outline failure.
- [x] Run complete C# suite, source compile, server regression and protected-file hash comparison.
- [x] Build separately, without camera access; real optical check requires readiness and geometry confirmation.

## Result (2026-11-15)
- User estimates: upper and bottom 124 x 124 mm; prior closed height 60 mm retained as approximate. Profile: `box-outline-124mm/box-outline-124mm.json`.
- Three saved images were reprojected using the unchanged active workspace. All 24 box vertices match OpenCV-to-C# camera XYZ and eye pixels within 1e-8. This proves transform parity, not physical or optical accuracy.
- Saved photographs show residual differences at the near upper rim (roughly 9-15 pixels against approximate manual edge marks). Do not claim exact box alignment or adjust the successful screw coordinates to hide this.
- C# suite: 443 passed, 0 failed, 3 optional legacy audits not run. Server regression: 4 passed. Source compile: passed.
- Independent review: no blocking defects; active-target preservation test now includes all S2-S5 stage-target paths.
- Separate Unity player: `box-outline-build`; verified manifest: `box-outline-build-verified.json`. Launch preflight passed with BoxOutlineTrial and CheckOnly. No camera or presentation session started.
- Nine protected baseline/calibration files and three prior players remain unchanged. Server transition policy is unchanged.
- Saved live S1 record confirmed phase GUIDING, reason operator_confirmation, target lid; new outline is a placement reference, not a detected lid.
- Pending: actual Unity stereo rendering, wireframe clipping and real optical agreement. Start with a short S1 check after fresh readiness; do not assume lower/back corners are validated.

## Next trial
Use `run-neutral-D-trial.ps1` with the previous successful AssemblyFlow/HandleLinkedDriverTrial options, plus StageContextTrial, BoxOutlineTrial and explicit UnityOutputDirectory `box-outline-build`. Keep ObservedCueDelayMs=2000, ScrewResumeMs=600, CompletedHoldResumeMs=2000, DurationSeconds=180. Do not mix legacy per-target offsets. Verify the S1 box reference before proceeding through the screw stages. No image/video saving.

## Completion boundary
Software preparation is not optical alignment validation. Bottom/back exterior accuracy is not established by an upper screw-plane check. Do not start capture or activate defaults in this task.
