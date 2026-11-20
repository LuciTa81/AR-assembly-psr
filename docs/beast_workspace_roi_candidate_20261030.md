# Saved-image workspace ROI candidate (2026-10-30)

## Scope

User approved a minimal saved-image candidate, not runtime activation. Moving the
entire table does not change marker-to-box geometry. Keep the current metric
profile and estimate camera-to-workspace pose separately for each source image.
The legacy recognition warp still assumes the earlier marker 4/5 positions.

## Design

- Reuse load_profiles, analyze_frame, and OpenCV projection/remap APIs.
- Four provisional 18 mm square screw regions at the registered target height
  (currently 60 mm); a central lid region inset 10% from the screw quadrilateral.
- These are inspection regions, not measured screw diameters or a new box outline.
- Project at lid height with calibrated lens distortion. Sample each region into
  a 64x64 inspection crop. Do not reuse old mat-plane ROI templates or thresholds.
- Reject invalid poses and incomplete/offscreen regions. Never reuse a prior pose.
- Save source hashes, profile hashes, world geometry, previews, crops and reports
  in a new output folder. Do not overwrite inputs or an existing output folder.
- No camera, Unity, SDK, exposure, state transitions, or active configuration edits.

Updating static image rectangles is insufficient when the head moves. Updating
only the old marker layout would leave height/parallax and template coordinates
unresolved. A metric surface candidate is the smallest isolated comparison here.

## Implementation and checks

1. Add regression tests for height, lens distortion, changed camera pose, invalid
   geometry, failed tracking, partial visibility, provenance and no camera access.
2. Add one offline-only module with a saved-image CLI, no live runtime imports of it.
3. Inspect current photos and additional saved views, including a blurred failure.
4. Record visual findings separately from physical accuracy and recognition claims.

The existing metric target positions are inherited registration, not independent
ground truth. Successful crops do not establish lid state, screw completion, or
eye/display alignment. New open/closed/tool evidence is needed before activation.

## Results

- Added `server/realtime/workspace_roi_candidate.py` and 19 focused tests.
  Initial 17 tests failed before implementation and passed after it. Two later
  edge-case tests cover partial visibility and valid-then-rejected input.
- Final related suite: 180 passed. Full suite before those two test-only additions:
  554 passed on rerun. The first full run had 553 passes and a pre-existing Tk
  initialization test failed with `invalid command name "tcl_findLibrary"`.
  That test passed independently and in the unchanged full rerun. This intermittent
  initialization failure was not fixed or suppressed by this change.
- Independent read-only review found no concrete defect. Its two coverage gaps
  were covered by the additional tests; production code was unchanged afterward.
- Seven saved images, no fitting to their pixels: six produced all five regions;
  the blurred image failed pose estimation and produced no crops. This is not a
  measured accuracy rate or an independently annotated holdout evaluation.
- Visually inspected the current and earlier views and all 30 generated crops.
  Screw regions follow the vicinity of A-D instead of the prior front-face ROI.
  Exact centering, occlusion, loose-screw height and state discrimination remain
  unverified. A 64x64 crop only resamples source detail; it does not add resolution.
- All seven input-image hashes and both profile hashes still match. No camera,
  Unity, SDK setting, active config, original photo or calibration was modified.

Artifacts: `C:/Users/fresh/Downloads/AR_Beast_Diagnostics_20261030/roi-candidate-01/`.
`candidate.json` describes the geometry, `image-*/report.json` binds each source
and pose, and `crop-contact-sheet.png` compares the extracted regions.
`full-tests.xml`, `full-tests-rerun.xml`, and `related-final-tests.xml` retain all
test outcomes, including the initial Tk failure.

Reproduction interface (saved images only, output directory must not exist):

```powershell
python -m server.realtime.workspace_roi_candidate --camera-profile <camera.json> --workspace <workspace.json> --images <saved1.png> <saved2.png> --output <new-directory>
```

Next: connect these candidate regions to diagnostic preview only. Once their
coverage is checked under a small head movement, collect labelled lid open/closed
and tool engagement/release samples in the new crop coordinates. Do not reuse
the old mat-warp templates or claim automatic screw completion from this step.

## Optional live diagnostic (2026-10-30)

Added `workspace_live_preview --roi-candidate`, mutually exclusive with
`--assembly-overlay`. Default preview and production recognition remain unchanged.
The shared projector/drawing helper produces the same geometry as saved images,
without crop generation on the live display path. Stale/future/invalid poses hide
regions; partially offscreen patches are not shown. The existing 150 ms check is
unchanged and evaluates age before rendering, not physical display/exposure age.
Live session and saved-image CLI reports record 18 mm / 10% / metric quads.

Verification:
- Eight new cases failed before the implementation. The one initial assertion
  that included the header's last row was corrected from row 40 to row 41.
- Full suite then passed 564 tests. Read-only review found a missing metric
  definition in the saved-image CLI report; a new regression reproduced it and
  the shared definition was added to that report.
- Final related run: 141 passed, one existing Tk initialization test failed
  intermittently (`tk.tcl`/`spinbox.tcl` lookup). That test and the new metadata
  regression passed together in a fresh process (2 passed). Do not report the
  final related run as all-green. Tk reliability remains a separate issue.
- Three saved-image results match offline ROI reports exactly. Normal-image
  rendering p50 was about 8.6-8.9 ms; this is not a live throughput guarantee.

After explicit readiness and permission for at most 20 saved images, ran the
camera-only diagnostic for 23 seconds including startup. SUBPIX, camera 0,
original exposure and profiles, no Unity/state recognition. Saved eight raw and
eight annotated photos (16 total) to `capture-07-live-roi` in the Downloads
diagnostic root; all 27 copied evidence files match their source SHA256.

199 incoming frames: 95 tracking, 104 rejected (93 insufficient markers, 10
degenerate center combinations, one reprojection rejection). Zero logged stale
events. Of the tracked frames, 90 showed all five regions; five hid screw C
because its patch was not fully inside the image. Source interval p50/p95/max
was 96.55/113.02/114.47 ms. Age at event recording was 29.52/41.52/53.89 ms.
Event recording is after projection but before the Tk display update; it is not
exposure-to-eye latency. These timings are not directly comparable across
different postures and motion in earlier captures.

Inspected all eight saved views. Successful examples cover the intended screw
vicinities/lid center; failed samples contain visible directional blur despite
markers remaining in view. Not all unsaved failures are attributed to blur.
This validates diagnostic wiring, not motion robustness, state recognition, or
eye alignment. Profile hashes and metric ROI geometry match the saved candidate.

Next: a short, separately authorized open/closed lid comparison with a steady
comfortable view, before new recognition references or thresholds are adopted.
Motion-blur handling remains an independent tracking task; do not keep stale
geometry visible merely to make this preview appear stable.
