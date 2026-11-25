# Small translucent sphere appearance candidate

User requested replacing the active screw's outline ring with a small translucent sphere while retaining calibration and orange/blue/green states.

## Scope

- Opt-in intent `--ez target_sphere true` includes the current box outline and top-right part preview. Existing `--ez box_outline true` retains the ring. Exact pre-change APK: `baseline/box-outline-before-sphere-20261121/candidate.apk` (SHA256 9B20AC8C89A513A10ED7E12DF69E8FDDE84AE5D909EE17BFA70C88B77F34A5AF).
- Locally bundled Three.js renders SphereGeometry with soft directional/ambient lighting into three transparent 96x96 PNG sprites. Generator: `render-sphere-markers.mjs`; assets: `app/src/main/assets/markers/`.
- Base RGB unchanged: orange #FFB841, blue #59D9FF, green #59FFBF. Opacity 0.58 with shading. 44px texture rectangle, approximately 40px visible sphere diameter, compared with the former 48px ring. No crosshair in sphere mode.
- Native Canvas draws each sprite at the existing eye-local center. The calibrated binocular center depth is unchanged; this is a shaded sphere image, not newly calibrated volumetric sphere geometry. Surface shading and alpha change apparent brightness; see-through visibility must be checked by the wearer.
- No changes to EyeProjection, WorkspaceTracker, workspace/camera/eye calibration, box dimensions, timing, tool evidence or green acknowledgement rules. Stale/invalid projections still hide the marker. Missing assets prevent starting this candidate. Bitmaps are loaded once and released after presentation teardown.

## Verification

- Initial regression test failed because the candidate class was absent (`sphere-marker-test-red.txt`).
- Six Playwright desktop/mobile Three.js renders passed: nonblank, centered bounded alpha coverage, translucency, visible shading, no JS errors. Screenshots/stats: `sphere-marker-qa/`.
- Build/lint passed (existing warnings remain).
- All 38 Android instrumentation tests passed (`sphere-marker-tests-device.txt`), including all prior 34 tests and four sphere tests: alpha/hue/shading, separate calibrated eye centers, all A-D phase colors, green acknowledgement, stale/future/missing inputs, wrong display size, clear/inspection, synthetic SBS renders.
- Synthetic native screenshots in `sphere-marker-native-qa/`; inspected WORKING rendering. No camera photos/video used.
- All three calibration asset hashes match the accepted checkpoint.
- Installed and opened at 03:43 KST. BOX_OUTLINE_READY, SPHERE_MARKER_READY, TRACKER_READY and YOLO_READY verified. No Beast display reported yet; camera remains off. Wearer visibility, alignment, occlusion and preference are pending.

## Next trial

Superseded before a wearing trial: the user requested four laptop-like reference rings with only the active screw colored. See `SCREW_CONTEXT_RESULTS.md`. Sphere code remains an opt-in alternative; it is not enabled in the new candidate.

Same wearing/display configuration, unchanged workspace. Observe A orange sphere, then bring driver near A without additional tightening to see blue and green; stop after transition to B. Numeric logs only. Restore ring mode if sphere brightness or occlusion is uncomfortable.
