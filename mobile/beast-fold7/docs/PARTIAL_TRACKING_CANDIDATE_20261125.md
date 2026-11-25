# Partial-marker tracking candidate C1

Date: 2026-11-25, Asia/Seoul.

## Status and priority

Candidate APK built; lint and 41 JVM tests passed. 31 Python regression tests
passed. Android instrumentation and wearer validation are pending: the previously
connected Fold7 became offline and reconnecting to 192.168.200.191:38811 timed out.
No candidate installation, camera start, recording, server update or web deployment
occurred. The installed v1 and its frozen archive remain untouched.

User clarified the primary occlusion: top-right and lower-right markers hidden.
Actual detector IDs are 2 and 5; remaining IDs are 0,1,4. The physical layout is:

```text
0       1       2
    4   box   5
3 (usually outside the view)
```

Do not confuse the user's ordinal 0-4 labels with detector IDs. Keep the physical
layout, 205/205 registration, camera profile and A-D binocular calibration unchanged.

## Implemented candidate

- Use OpenCV's CORNER_REFINE_APRILTAG path with the SAME DICT_4X4_50 markers.
  This does not require reprinting AprilTag markers or importing a learned model.
- Establish an image reference only after a valid >=5-marker pose. No cold start
  from three markers is claimed.
- Match current visible marker corners to the reference in undistorted image
  coordinates. Fit a planar homography with OpenCV, then transfer missing marker
  centers. Solve with the existing registered geometry and pose/error guards.
- Check corner RMS <=1.5 px, worst corner <=3 px, and whole-marker leave-one-out
  transfer spread <=3 px. Three-marker cases additionally reject collinear center
  layouts and require A-D pose sensitivity <=3 camera pixels and <=3 mm across
  the leave-one-out fits. Android also requires all four comparison targets on
  camera screen for this three-marker sensitivity check.
- Use CURRENT real corners on every displayed partial frame. A missing/invalid
  frame never republishes the previous pose. Reference data may remain cached for
  30 seconds, but partial frames never extend its expiry. Starting/stopping a
  session resets it; backward/duplicate timestamps invalidate it.
- If the precise path cannot produce a pose, run the unchanged v1 detector/pose
  path on that same frame. This recovers observations lost by precise detection.
- Keep actual detections in Result.markers; inferred centers do not inflate the
  displayed or transmitted detected-marker count.

Production/default builds keep PARTIAL_MARKER_CANDIDATE=false. The separate build
type uses application ID `com.lucita.beastgate.trackingcandidate`, app label
`AR Assembly Tracking`, and version `1.4.2-partial-markers-c1`. Its app data is
separate; it does not inherit v1's Internet-supervisor credentials or consents.

## What the evidence actually shows

The first center/corner-model methods failed and remain archived as experiments.
Replacing only the solver or relaxing the 3.2 px threshold was not adopted.

On the same 239 sampled video frames, adjacent-frame planar corner residual median:
SUBPIX 3.65 px, CONTOUR 4.34 px, APRILTAG 0.27 px. This is a temporal consistency
metric, NOT absolute accuracy. Precise detection saw >=5 markers in 130 frames
versus 156 for SUBPIX, motivating the unchanged-v1 fallback.

Chronological offline availability of the final candidate plus fallback:

| Dataset | Frames | v1 accepted | Candidate accepted | Gained | Lost |
| --- | ---: | ---: | ---: | ---: | ---: |
| Successful recording | 239 | 159 | 209 | 50 | 0 |
| Separate earlier photo retake | 46 | 19 | 43 | 24 | 0 |

Real missing-marker frames have no independent target ground truth. These numbers
mean returned valid poses, not proven physical alignment or measured Android FPS.
Video was compressed; photos were previously captured, not newly recorded.

For the user's priority case (hide IDs 2,5), chronological masked replay up to
30 seconds produced:

| Dataset | Trials | Returned | Within 5 camera px AND 5 mm | Camera difference p95 / max |
| --- | ---: | ---: | ---: | --- |
| Successful recording | 3263 | 1227 | 1223 | 1.99 / 3.79 px |
| Separate photo retake | 91 | 23 | 23 | 2.07 / 2.84 px |

The remaining trials are rejected by uncertainty checks, not treated as successes.
Four video cases exceeded the 5 mm consistency threshold (maximum 6.82 mm) despite
camera displacement staying below 5 px. This remains a limitation, not a pass.
After ten seconds the video returned 755/1950 compared cases; the photo dataset
returned only 6/48. Sustained three-marker availability needs a deliberate wearer
test and better view coverage before stronger claims.

These comparisons use the current precise five-marker estimate as reference,
not v1 and not independent physical truth. Overlapping windows are correlated.
All-five precise estimates can also differ from v1: on 127 common frames the
camera-target difference median/p95/max was 2.68/6.19/9.12 px, even with identical
calibration files. This change must be checked on the wearer; do not describe it
as bit-for-bit unchanged overlay alignment.

Reports under `../pose-comparison/`:
`refinement-audit.json`, `precise-only-bridge-report.json`,
`guarded-bridge-report.json`, `guarded-bridge-30000-report.json`,
`right-occlusion-retain-report.json`, `partial-candidate-fallback-availability.json`.

## Research used to choose the approach

- [OpenCV homography tutorial](https://docs.opencv.org/4.13.0/d9/dab/tutorial_homography.html):
  view-to-view transforms for planar surfaces. This supports the image-reference
  approach without guessing marker side length. It does not establish our accuracy.
- [IPPE authors' implementation](https://github.com/tobycollins/IPPE): planar pose
  ambiguity is a geometric issue; temporal filtering alone does not guarantee the
  correct solution. Existing ambiguity rejection therefore remains enabled.
- [Investigation of ArUco Marker Placement, Jan 2026 revision](https://arxiv.org/html/2509.17345v3):
  placement, viewing geometry and measurement reliability matter. Adaptive filtering
  is informative, but its robot experiments do not validate our eye overlay.
- [PACMAN, 2026 paper and authors' implementation](https://github.com/twpark97/PACMAN):
  useful alternative marker/detector research, but it uses a new patch-marker design
  and a TensorRT-oriented environment. Not a drop-in Fold7/printed-ArUco replacement.
  No PACMAN code or weights were incorporated.

## Next gates

1. Reconnect Fold7; install the candidate package and its test APK without replacing
   `com.lucita.beastgate`. Run WorkspaceTrackerTest and PartialMarkerBridgeTest.
   The latter contains 358 numeric replay fixtures with 207 expected valid cases,
   plus checks for cold start, loss/reacquisition, expiry and actual marker counts.
2. Run a short explicit diagnostic, not normal assembly. Initially show all five,
   then hide the top-right/lower-right pair without moving markers or box, then
   restore. Compare D first because its projection was most sensitive in this case;
   phone preview can show A-D. No screwdriver operation or recording is needed.
3. Compare all-five position with v1 as well as partial visibility. Confirm single
   binocular image, position, reacquisition, flicker, and processing time on Fold7.
4. Only then expand to the other likely hand/tool occlusions. Do not whitelist
   arbitrary IDs to force a pose or disable uncertainty checks for a demo.
5. Consider a small bank of validated reference views if one-reference coverage
   remains insufficient. That is not implemented in C1. For unlimited partial-only
   tracking or cold three-marker start, a validated board map is still a separate
   registration task. Current reference expires after 30 seconds without >=5 refresh.

Build: `scripts/build-tracking-candidate.ps1`.
No user camera permissions or server-storage consent should be bypassed for tests.
