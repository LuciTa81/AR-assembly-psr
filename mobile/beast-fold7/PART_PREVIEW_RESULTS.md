# Headlocked 3D part preview candidate

Date: 2026-11-21 (Asia/Seoul)

## Scope and presentation

- Opt-in `part_preview=true` also enables the existing complete preparation/assembly flow.
- Box instructions: open enclosure with rounded walls and screw bosses (currently green edge-only styling).
- Lid instructions: shallow lid with four screw recesses.
- A/B/C/D: enlarged threaded cross-head screw.
- Final inspection: closed enclosure. Stop: preview cleared.
- Procedural illustrative models, not measured manufacturing CAD or evidence of assembly state.
- Revised eye-local model viewport: x=1511..1759, y=162..378 (248x216, 80% of original width/height). Transparent rounded outline bounds: x=1491..1779, y=142..398 (288x256). Native title at y=100 and action at y=960 remain unchanged.
- Both eyes get identical headlocked model images, with 3D perspective/light shading but no additional binocular disparity or distance calibration. User comfort and apparent placement still require a wearing test.
- Short 550 ms entrance movement at up to 25 fps only on a part change, then static. No continual spinning or motion tied to tracking.
- Native calibrated rings/text remain a separate layer. The preview consumes stage values but supplies no evidence or transitions.

## Implementation and security

Three.js r180 is bundled locally with its MIT license; no CDN, runtime fetch, new camera permissions, microphone access or recording. Native WebView is transparent and restricted to a five-file local allowlist under `https://appassets.androidplatform.net/parts/`. All other requests receive empty content. File/content access, mixed content, DOM storage and network loads are disabled. There is no JavaScript-to-Java bridge; native only sends a validated part integer.

Three.js source:
- https://github.com/mrdoob/three.js/tree/r180
- `three.module.min.js` SHA256: E2B5EE6BCCD38FD6D8A2428546B83C5F2426D84B152EF82BE8055556E3B40EB6
- `three.core.min.js` SHA256: 61BA0DF005B05991361D040D8FF670E1AADFD0CE7AEEBD1FDB0725957A8957DE

Renderer errors hide/remove only the preview. Presentation teardown destroys the WebView. Existing A-to-D and preparation flags remain available without this layer. Prior verified APK: `baseline/beast-gate-v05-preparation-7s-6s-verified.apk`.

## Verification

- Build and Android lint passed.
- 27 Android instrumentation tests passed (`part-preview-tests-device.txt`), including stage-to-part selection and all preexisting timing/optical tests.
- `verify-part-preview.mjs` passed 12 part/viewport combinations at 3840x1080, 1920x1080, and 412x915 using Playwright/Chrome WebGL.
- Canvas pixels verified both eyes nonblank, matching coverage, bounded to designated viewports, visible entrance movement, and clear on stop; no JS page errors.
- Manually inspected rendered close-ups of all four parts: `part-preview-qa/detail-0.png` through `detail-3.png`. Full screenshots and pixel statistics in the same directory.
- Camera/workspace/eye-projection asset hashes unchanged.
- Phone APK installed and opened at 02:54 KST. No Beast external display detected then, so native external-display WebGL readiness and optical comfort remain pending. Camera has not been started.
- Browser pixel tests are not proof of phone WebView performance or see-through visibility. Verify `PARTS_READY` and `PARTS_DRAWN` on device, then user confirmation, before promoting this candidate.

## Device live trial

2026-11-21, user confirmed unchanged wearing/settings and independently started the trial. Log: `part-preview-live-20261121-0255.txt`.

- Full SBS 3840x1080 and `PARTS_READY` confirmed at 02:55:43 KST.
- Start 02:55:52.872; box part 0 drawn at 02:55:53.427.
- Box -> lid 02:56:08.137; lid part 1 drawn at 02:56:08.705.
- Lid -> A 02:56:14.835; screw part 2 drawn at 02:56:15.404.
- A/B/C/D green-to-transition delays: 3016/3017/3015/3016 ms.
- D -> inspection 02:57:13.098; closed assembly part 3 drawn at 02:57:13.666.
- All four part draw reports have a 3840x1080 canvas. No PARTS_ERROR, PARTS_RENDERER_GONE, PARTS_CONTEXT_LOST or FATAL event found in the captured app log.
- Camera automatically stopped at 02:57:23.129 (1636 camera frames). App subsequently force-stopped and absence of PID verified. Numeric logs only, no photo/video capture.
- These logs verify rendering code execution and stage progression, not optical comfort or perceived visibility. User feedback on binocular appearance, size, brightness, positioning and occlusion is pending.

## User-requested frame and smaller model

User reported that the 3D parts were visible, requesting a rounded rectangular outline and a slightly smaller preview. No explicit confirmation of all comfort/occlusion questions was given.

- Model viewport reduced by 20% in each dimension, same center and camera perspective.
- Added a 2 px pale-cyan outline at 55% opacity, 14 px rounded corners, no filled backdrop. The outline uses the same local Three.js canvas and clears together with the model on stop.
- Existing timings, calibration, native rings and text untouched.
- Prior candidate saved as `baseline/beast-gate-v05-part-preview-unframed.apk`.
- Build/lint and all 27 Android tests passed (`part-preview-framed-tests-device.txt`).
- All 12 Playwright part/viewport cases passed again, explicitly checking nonblank model AND frame pixels in both eyes, bounds, movement and stop clearing. At 3840x1080 each eye has 2174 outline pixels; no pixels outside the designated frame bounds.
- Inspected the updated box and screw close-ups. `part-preview-qa/framed-screw.png` is a uniquely named reference image; older same-path images may be cached by viewers.
- Revised APK installed; app stopped after tests. New framed/smaller layout has not yet had a wearing test.

## Green edge-only revision

User requested the 3D parts themselves be drawn only with green lines.

- Replaced colored surfaces with color-write-disabled depth faces plus green feature edges. Rear edges are occluded; faces contribute no visible fill. No triangle wireframe grids.
- Refined edge thresholds on rounded enclosure walls and cylinders so vertical contours remain legible. Screw threads, cross recess, lid thickness and enclosure depth remain visible.
- Part color `#6cff7a`; rounded frame uses the same green at 45% opacity. Model size/position and all native guidance unchanged.
- Prior solid/framed APK preserved as `baseline/beast-gate-v05-part-preview-framed-solid.apk`.
- Inspected rendered enclosure/screw close-ups after refining the contours. All 12 Playwright cases passed, now also asserting every visible colored pixel is green-dominant (`nonGreen=0`), both eyes nonblank, bounded, and cleared on stop. Evidence: `part-preview-green-v2-qa/`.
- Build/lint and all 27 Android instrumentation tests passed (`part-preview-green-tests-device.txt`). Installed on Fold7; app stopped after tests. No camera or wearing test started for this revision.

## Match the existing enclosure outline color

User requested the existing actual enclosure-overlay color instead of bright lime. Read the frozen Unity `client_unity/Assets/Scripts/SbsGuidancePresenter.cs:362` and the preparation build copy: normal level-2 strokes use RGB `(.55, .95, .85) * .55`, alpha 1.

- Preview feature edges now use the rounded sRGB byte equivalent `#4D8577` (77,133,119), with tone mapping disabled. Rounded frame uses the same hue at 45% opacity.
- Matching nominal RGB does not certify identical optical luminance across Unity and WebView; physical appearance still needs wearing confirmation.
- Geometry, size, position, timing and calibration untouched.
- Build/lint passed; all 12 Playwright combinations passed including hue and brightness checks (`nonMint=0`, max green <=134), both-eye geometry, animation and clearing. Evidence: `part-preview-mint-qa/`.
- Full Android suite was not rerun for this RGB-only change; the immediately preceding edge-only build passed all 27 tests. Camera remains off.

## Mint outline physical trial

2026-11-21, user confirmed wearing/settings. Initial display was 1920x1080, then the user switched Full SBS and 3840x1080 plus `PARTS_READY` were verified. Numeric log: `part-preview-mint-live-20261121-0312.txt`.

- Start 03:12:43.570 KST; box draw 03:12:44.137.
- Box -> lid 03:13:00.947; lid draw 03:13:01.518.
- Lid -> A 03:13:07.761; screw draw 03:13:08.328.
- A/B/C/D green-to-transition delays: 3033/3033/3015/3015 ms.
- Inspection 03:13:53.712; assembled-box draw 03:13:54.278.
- Automatic camera stop 03:14:03.759 (1553 frames). App subsequently force-stopped and absence of PID verified.
- All four part draws reported 3840x1080. No photos/video saved. User feedback on mint color, smaller size, outline brightness/thickness and binocular comfort requested and pending.

## Open-box clarity and further size reduction

User found the first box ambiguous and requested a slightly smaller preview. The rendered open box showed one conspicuous internal mounting post. Removed the internal posts from the illustrative preview, then added the rounded interior floor-wall junction after the user noted the unclear floor. Depth testing still hides lines behind the walls and the closed lid.

- Model viewport: 248x216 -> 224x194; frame: 288x256 -> 260x232 (about 10% smaller). Eye-local center remains (1635,270).
- Mint #4D8577, headlocked positioning, optical calibration, preparation timers and screw transitions unchanged.
- Prior APK retained at `baseline/beast-gate-v05-part-preview-mint-before-box-refine.apk`.
- Build/lint passed. All 12 Playwright cases passed with the new bounds, both-eye model/frame pixels, hue, entrance animation and stop clearing. Evidence: `part-preview-floor-qa/`. Inspected open-box floor junction in `detail-0.png`.
- Three calibration asset hashes remain identical to the verified reference. Full Android instrumentation suite was not rerun for this JS-only geometry/layout revision.
- Updated APK installed successfully on Fold7. Wearing comfort and final apparent size remain unverified; no camera session or recording started by this update.

User subsequently confirmed the refined preview works well ("잘 된다. 좋네"). Preserved this accepted revision at `baseline/verified-part-preview-20261121` before beginning the separate physical box-outline port. This acceptance does not validate the new spatial box outline.
