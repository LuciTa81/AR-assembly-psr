# Four screw reference rings candidate

## Scope

- User superseded the sphere candidate before its wearing trial. Use `--ez screw_context true`; this takes priority over `target_sphere` and includes the existing box outline and headlocked part preview.
- Screw stages show four calibrated ring centers. Only the current screw uses orange #FFB841, blue #59D9FF, or green #59FFBF. Inactive screws are neutral gray (RGB 210, alpha 153), not a completion indicator.
- Laptop `SbsGuidancePresenter.DrawStageContext` uses 36px reference textures and 48px active textures. Native rings reproduce their effective radii (15.75px / 21px) and approximate stroke widths (2.53px / 2.625px). Laptop inactive tint was mint; neutral gray intentionally follows the user's request that only the current screw receive color.
- No center crosshair in this mode and no lines connecting screw centers. Existing body/lid outlines remain unchanged.
- Reference rings start at A, not during box/lid preparation. Final inspection shows four mint rings (#4D8577), matching the existing whole-box outline. This is an inspection cue, not an automatic fastening verification indicator.
- Every center uses the existing EyeProjection and the same valid >=5-marker pose. Each failed projection is omitted; stale/future observations hide rings. A reference ring cannot acknowledge an active green cue or advance the assembly.
- No changes to camera/workspace/eye calibration, pose acceptance, box geometry, preparation timing (7s/6s), or the 3s green-to-next-stage timer. Previous accepted APK backups remain untouched. A subsequent user request increases the armed-to-green working delay from 2s to 3s for all A-D targets; see below.

## Verification

- Build and lint passed (existing warnings remain).
- All 42 device instrumentation tests passed: previous 38 plus four context-ring tests. Results: `screw-context-test-results.txt`.
- New checks cover all A-D active targets, all three phase colors, separate eye centers, neutral inactive rings, no connection lines/crosshair, preparation/inspection, stale/future/null inputs, wrong SBS size, clear, and no green acknowledgement from context alone.
- Synthetic SBS images: `screw-context-native-qa/`; WORKING inspected visually. These are generated Canvas tests, not camera images.
- SHA256 unchanged: camera 25F025BC5C2F71E4C83E6645E5CDC742BDA81CD75D30C55FF7E5ACA99924872E; workspace 5D4F4C6610AF3264E0583EB64B038B3D66B12A9FC4844849D21D4F770D5C7ACC; eye 1127D29FB5022D005373D12EB0A8886FABAFA53C852AC4BB3FD281CCD10904F3.
- Installed and opened with screw_context at 03:51 KST. SCREW_CONTEXT_READY, BOX_OUTLINE_READY, TRACKER_READY, YOLO_READY verified. No Beast external display reported at opening; camera remains off. Wearer brightness/alignment check pending.

## Wearing trial and final inspection color

- User started the candidate at 03:51:44 with Full SBS 3840x1080. BOX->LID at 03:51:55, LID->A at 03:52:03. Green-to-transition delays A/B/C/D: 3032/3002/3014/3050ms. Final inspection at 03:52:59; automatic camera stop at 03:53:09. Numeric log: `screw-context-trial-20261121.txt`. No camera images/video saved.
- User completed the flow and accepted the other visuals. Requested only that final inspection rings match the other mint outlines rather than gray. Inspection rings now use RGB 77/133/119; screw-stage neutral references and active phase colors are unchanged. The regression test checks the exact inspection color for all four centers in both eyes.

## Additional working time

- User requested one additional second of blue guidance. `AssemblyProbe.WORKING_CUE_DELAY_MS` is now 3000ms, used for both release eligibility and green acknowledgement. The existing 800ms proximity accumulation and valid fresh near-observation requirement are unchanged. Blue can remain visible longer if valid near observations are unavailable; this is not an unconditional wall-clock color change.
- The green-to-next-target delay remains 3000ms. The full-sequence regression checks all four targets at 2999/3000ms after arming and 2999/3000ms after acknowledged green.
- Accepted pre-change APK was pulled from the device before installation: `baseline/four-rings-wearer-accepted-20261121/accepted.apk`, SHA256 5E3B79B453FF8F9A1743FD40F68E25FD03EF362100BDFD3CC1DE8E03FF8544FE. It retains gray inspection rings and the former 2s working delay.
- Revised build/lint passed; all 42 device tests passed (`screw-context-mint-working3s-tests.txt`), including exact mint pixels in both eyes and timing boundaries for A-D. Calibration hashes rechecked unchanged. Revised APK installed and launched with screw_context at 03:57 KST; initialization passed, frames=0, camera off. No new wearing trial yet for these two final adjustments.

## Current working delay: 4 seconds

- User requested one more second of blue guidance after the 3s revision. `WORKING_CUE_DELAY_MS` is now 4000ms for all A-D targets. The 800ms proximity accumulation, fresh near-observation requirement, and 3000ms after acknowledged green remain unchanged.
- Tests now check 3999/4000ms after arming for each screw, plus the unchanged 2999/3000ms green-to-next boundary. The former 3000ms working boundary must remain blue.
- Pre-change 3s APK preserved at `baseline/four-rings-mint-working3s-20261121/candidate.apk`. No visual, calibration or tracking edits in this revision.
- Build/lint and all 42 device instrumentation tests passed (`screw-context-working4s-tests.txt`). Revised APK installed; camera not started. Real-wear timing feedback remains pending.
