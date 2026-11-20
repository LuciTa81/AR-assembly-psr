# Rounded Body/Lid Candidate - 2026-11-15

## User clarification and stage mapping

- 10 mm means lid height, not body height.
- Retain approximate closed height 60 mm and 124 x 124 mm exterior from previous trial. Derived body height is 50 mm, not a new measured value.
- User-facing step 1 = S0: body outline only, emphasis 2; placement reference can show without the box, provided markers/pose are valid.
- Step 2 = S1: body 2, lid 3; no screw rings yet.
- Screw work = S2-S5: body/lid 2, hidden geometry 1, existing active screw and blue WORKING/green MOVE CLEAR unchanged. Passive rings remain unchanged.
- S6: no box outline.
- Corner joins approximate 3 mm with short quadratic curves. Screw centers/projection/calibration are not moved.
- Hidden edges use convex box surface direction, not camera-image hand/tool occlusion.

## Isolation

- New profile: `rounded-box-124mm.json`, opt-in `staged_rounded=true`.
- New player: `rounded-box-build/BeastAssemblyGuide.exe`.
- Launcher option: `-RoundedBoxTrial`, requires existing box/context trial switches.
- Previous successful player, three prior visual players, nine protected baseline/calibration files and old box profile verified unchanged.
- No camera, live player, photo/video capture or computer-use was started during this change. Unity Editor was used only for batch builds.

## Verification

- Unity tests: 456 passed, 0 failed, 3 optional legacy offline suites skipped.
- Server full-flow regressions: 4 passed. Initial collection failed because pytest traversed an unrelated Windows library junction; rerun with explicit test root passed.
- Saved OpenCV pose parity: 24 old box vertices unchanged; new rounded S0/S1/S2 strokes project inside both eye viewports across three saved poses.
- Actual candidate JSON loaded and validated in the saved-pose test.
- Reviewed corner-normal defect reproduced with a failing regression and corrected. Non-Repaint events skip drawing work; fixed geometry is cached; freshness/session checks remain per draw.
- Separate Unity batch build succeeded; old and new launcher preflight checks completed without devices.
- `rounded-box-geometry-preview.png` is a numerical projection preview, not a photograph or headset capture. Optical brightness/line thickness still pending user test.

## Previous trial result retained

Session `viture_aruco_rt_20261115_152335_de060539f1dd`: user confirmed the full rectangular outline was generally aligned in S1. This qualitative confirmation applies to the previous box-outline build only, not the new rounded candidate. No automatic activation or calibration promotion.

## Next bounded trial

Fresh readiness confirmation required. Same wearing position, Full SBS, 0DoF, Extra Large, 4.5 m, Windows extended display and unchanged box/markers. Maximum 180 seconds, numeric logs only. Check body-only S0, then manually confirm placement to see lid emphasis in S1. No extra screw tightening. Existing workflow rules are unchanged.
