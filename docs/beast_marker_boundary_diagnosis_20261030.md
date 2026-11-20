# Marker boundary diagnosis (2026-10-30)

## Scope and measurement

The user measured the black outer square of marker ID 3 as 69 mm. The earlier
report was that all six prints have the same size. A 69 x 69 mm square for all
markers is therefore a candidate assumption, not an independently measured
per-marker layout. Width and height were not separately reported this time.

No camera was opened for this investigation. Existing camera/workspace profiles,
eye calibration, recognition thresholds, exposure and Unity behavior were not
changed. No corner-pose candidate was activated.

Local evidence is under
`C:/Users/fresh/Downloads/AR_Beast_Diagnostics_20261030` (outside OneDrive).
Images and numerical reports remain local, not committed with the source.

## Reproduction

- Changing the old 70 mm corner candidate to 69 mm alone did not resolve its
  poor fit: accepted counts across four recordings changed from 2/16/12/5 to
  2/18/10/5, respectively. The reference still lacks ID 3 orientation.
- Inspecting `capture-01/frame-000042/raw.png` showed that the existing SUBPIX
  detector follows the white paper perimeter for IDs 0, 3, 4 and 5. ID 2 mostly
  follows the black square. See `marker-corners-inspection.png`.
- A synthetic ArUco ID 3 with a 100 px black square, 5 px white margin and dark
  background reproduced the paper-boundary error on OpenCV 4.14.0.
- OpenCV `CORNER_REFINE_APRILTAG` recovered the black boundary while retaining
  `DICT_4X4_50`. This does not require new printed AprilTag markers or VITURE SDK.

## Offline comparison

`detector-boundary-comparison.json` contains image hashes, numeric corners,
profile hashes, individual outcomes and timing for 24 saved photos.

| Method | Center solver accepted | 69 mm corner candidate accepted |
| --- | ---: | ---: |
| SUBPIX | 14/24 | 1/24 |
| APRILTAG | 14/24 | 13/24 |

The corner candidate still uses inferred orientations from the old reference,
not fully measured world corners. These counts are solver gate outcomes, not
physical accuracy, continuous tracking rates or eye alignment measurements.
The same pose gates were used. Blurred photos with no detections stayed lost;
some grazing-angle detections were lost with APRILTAG. Do not describe this as
a universal improvement in marker detection rate.

Offline median detector time was about 10.44 ms vs 39.68 ms on these 24 photos.
This is not an end-to-end latency or live FPS measurement. Decimation screening
is recorded separately in `detector-decimation-comparison.json`; no speed/quality
tradeoff from that screening was adopted.

## Minimal implementation

- `detect_markers(..., corner_refinement="subpix")` keeps the existing default.
  Explicit `"apriltag"` uses the alternative corner detector. Unknown modes and
  unavailable APRILTAG support are not silently substituted.
- Only the finite local `workspace_live_preview` diagnostic exposes
  `--corner-refinement {subpix,apriltag}` for live and saved-image input.
- The chosen method is written to session and per-frame/sample evidence.
- The diagnostic continues to use the existing center-based pose solver, its
  quality gates and freshness rules. The 69 mm candidate is offline only.
- Presentation, observation collection and real-time recognition default paths
  remain SUBPIX. Existing optical observations are not rebound to new geometry.

With the repository Python environment active, append
`--corner-refinement apriltag` to an existing `workspace_live_preview` command.
For example, after confirming camera index and user readiness:

```powershell
python -m server.realtime.workspace_live_preview `
  --camera-profile <camera-profile.json> --workspace <workspace-candidate.json> `
  --camera 0 --duration 15 --assembly-overlay --target A `
  --corner-refinement apriltag --no-image-saving
```

This is a local camera projection check, not a Unity/eye-overlay validation.
Camera index 0 must be rechecked if devices have been reconnected. Omit the new
option to return to the unchanged diagnostic default.

## Verification and next gate

- Red tests failed before implementation on the missing optional arguments/CLI.
- 220 tests passed across marker boundaries, preview, workspace projection and
  overlay, display observation, presentation bridge and offline corner reports.
- Synthetic black-boundary checks cover detection scales 1.0 and 1.5. Worker,
  saved-image, CLI and session provenance tests cover the new option.
- All 24 saved images matched the prior comparison's IDs and new corner
  coordinates after routing through the implemented helper. Center pass counts
  remained 14/24 for each method. Active profile hashes were unchanged.

Next: a bounded live diagnostic under the same auto exposure and comfortable
view, comparing black-boundary consistency, center pose continuity and processing
age. Then inspect candidate corner geometry and independent A-D projection error
before any live solver switch. Eye/display calibration remains a separate gate.

Reference: [OpenCV DetectorParameters](https://docs.opencv.org/4.13.0/d1/dcd/structcv_1_1aruco_1_1DetectorParameters.html).
