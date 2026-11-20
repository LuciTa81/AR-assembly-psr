# A-to-B automatic interaction trial

## Scope

An opt-in bridge from the current metric workspace to the existing timed tool
evidence gate. The operator-confirmed A-D demo remains the default and fallback.
This is not a completed automatic assembly system or a torque measurement.

- `run_beast_demo.ps1 -ScrewAutoTrial -DurationSeconds 180` requires an explicit
  candidate projection and bounded duration. Other demo arguments stay the same.
- Starts at S2/A, with the lid already closed by the user. By default at most S3/B is reached.
  Add `-ScrewAutoEndState S6` explicitly for the full A-D interaction sequence.
  After D it stops at final confirmation, never automatic fastening certification.
  S0/S1 recognition and final completion are deliberately outside this trial.
- Uses one camera and the same metric pose for display and tool analysis. Disables
  old marker homography and ROI templates. Keeps existing auto mode unchanged.
- YOLO boxes are undistorted with camera intrinsics and mapped onto the common
  seated screw plane. All four target heights must agree within 0.5 mm.
- Distances are plane-projected mm, NOT measured 3D tool contact. Metric-only
  provisional score radius/softness are 12/4 mm. The legacy pixel screw-detection
  score is not mixed in. These trial settings need actual approach/release data.
- Keeps the existing 800 ms engagement, 400 ms visible withdrawal, fresh evidence,
  single-driver and target-dominance requirements. Loss or missing tool evidence
  disarms progression. No automatic torque/tightness claim is made.
- Unity and browser select A while observing A; only server transition selects B.
  Tool-only waiting can retain the spatial target using an independently fresh
  pose. Marker loss, stale state, stale pose or invalid data still hides it.
- No images/video are saved. Numeric results include source-bound detections
  (`yolo_frame_id`, `yolo_detections`) after the first trial; do not associate old
  boxes with the current image. Invalid/stale YOLO results have no detections.

## Verification

Before implementation, eight Python tests and seven C# automatic-display cases
failed. Implemented metric transforms, explicit trial configuration and stage
selection. Added a synthetic runtime test using real geometry, scoring, evidence
gate, logging and presentation with only camera input/neural predictions replaced.
It holds A while the tool is engaged, transitions exactly once after withdrawal,
and shows B in the same server snapshot. No image files are generated.

Pre-live: 632 Python realtime tests passed; 288 C# tests passed and one optional
offline-report test was skipped. Unity build succeeded:
`outputs/unity_p1/build-20261107-194950-614.log`.

The workspace profile had moved from Downloads into the graduation-project
folder. Updated only `outputs/demo/presentation.json` to its existing new path.
SHA256 still equals `5d4f4c6610af3264e0583eb64b038b3d66b12a9fc4844849d21d4f770d5c7acc`.
Camera/eye calibration, target coordinates and saved C/D records were not changed.

## First live result: not passed

Session: `viture_aruco_rt_20261107_195403_50cc6631a431`.
Runner: `outputs/demo/8509d125c468442ba82fb74c45f1cf23`.
Player: `outputs/unity_p1/player-20261107-195407-300.log`.

The user saw the A ring and performed approach/withdrawal with the same black/yellow
driver as before. 1,251 frames, 510 marker-valid frames, zero transitions. Only one
frame simultaneously had marker_ok, YOLO reason ok, one driver and a known tip.
That estimate was 63.28 mm from A. It does not establish the actual contact error.
Held reasons: marker_not_stable 741, invalid_observation 349, tool_not_visible 153,
tool_position_unknown 7, no hold 1. Tool-not-visible also includes multiple drivers.
The whole-run ratio is not a controlled stationary-tracking benchmark.

Stopped early after the user's report; camera/server/Unity exited. No media saved.
The first run lacks numeric detection boxes; added their logging for subsequent
diagnosis rather than guessing at confidence thresholds from counts alone.

Offline rereading of six existing Oct 6 photos with the same model reproduces the
previous driver counts (1,1,1,1,1,2) and confidences. Some boxes are on background
objects. This confirms the model still runs, not that current detection is correct.
Do not infer today's box locations from those older images.

Post-live offline check reproduced a separate geometric issue: finding a minimum
rectangle endpoint AFTER plane projection changes the original image endpoint
(0.513 mm in the synthetic case). The metric path now estimates endpoints in the
camera image first, then undistorts/projects those points. Both handle-guided and
fallback cases have regression tests. This small synthetic error does not explain
the full live failure; the changed endpoint path has not been tested on the device.
Final build (common-stage log label only): `outputs/unity_p1/build-20261107-195945-177.log`.
After numeric-box logging and endpoint fixes, the full realtime suite passed
634 tests. No further hardware test was run. The successful pre-live C# run had
288 passing tests and one skipped optional offline-report test.

## Four-photo diagnosis, 2026-11-07

With explicit consent, captured two contact and two visible-withdrawal originals
only, plus derived previews, in `C:/Users/fresh/Downloads/AR_Beast_Tool_20261107`.
No Unity, state progression, or external upload. Each camera run ended normally.

- Contact: `at-A/ARAssembly/beast-mvp/workspace_registration/live-20261107T111047Z-da8e4246`, frames 1/31.
- Withdrawal: `clear-A/ARAssembly/beast-mvp/workspace_registration/live-20261107T111330Z-ee680bfb`, frames 1/32.
- Review: `tool-comparison.png`, `tool-comparison.json`, and per-frame
  `tool-analysis.png/json`. Original files remain untouched. Reports include
  source, weights and calibration hashes. Review uses conf 0.20 / imgsz 640,
  matching the configured model, and the current metric endpoint implementation.

| State/frame | Drivers | Driver confidence | A distance (projected mm) | A score |
| --- | --- | --- | --- | --- |
| Contact/1 | 1 | 0.860 | 5.99 | 0.818 |
| Contact/31 | 1 | 0.897 | 5.59 | 0.832 |
| Withdrawal/1 | 1 | 0.890 | 65.00 | 0.00000176 |
| Withdrawal/32 | 1 | 0.891 | 81.28 | 0.00000003 |

All four saved photos have a valid re-estimated marker pose. Visual inspection
shows the driver boxes on the actual shaft, not the background. One withdrawal
photo splits the actual handle into two boxes, but still has exactly one shaft.
The current tip fallback is used in all four; handle-plane intersection is absent.
Near scores exceed the configured 0.30 threshold and dominate the other targets;
withdrawal scores are below 0.15. These are planar proximity estimates, not measured
3D contact distances or proof of tightened screws.

The photos do NOT reproduce the earlier multiple-driver failure, and they do not
establish continuous 800 ms engagement / 400 ms withdrawal or end-to-end latency.
Do not duplicate these sparse frames to claim a successful temporal trial. No
production thresholds, eye calibration, target coordinates or model weights were
changed. Next: repeat the bounded A-to-B live trial with source-bound numeric
detection logging; investigate its hold reason if it still cannot progress.

## Second live result: A-to-B interaction passed once

Session: `viture_aruco_rt_20261107_201855_a5eb14487a43`.
Runner: `outputs/demo/77c98142a1c540e38136ff41ed810665`.
Player: `outputs/unity_p1/player-20261107-201859-580.log`.

Same profiles, weights, score thresholds and current endpoint implementation as
the four-photo review. No production code or calibration change between them.
The bounded automatic trial ran for approximately 79 seconds of recorded input,
then was stopped early through its own session-checked stop signal.

- Exactly one automatic transition: S2 -> S3 at frame 495, YOLO source frame 494.
- A engagement was observed first. Frames 491-495 then held valid visible tool
  withdrawal evidence; the transition frame had one driver and A distance
  55.27 projected mm (score approximately 0.00002).
- Unity logged S3 with visible candidate presentation. The user explicitly
  confirmed that both the B instruction and B ring appeared, without using the
  supervisor completion button.
- All 795 recorded filter inputs replay identically, including transition,
  guidance phase and target: `realtime_replay --validate-filter` passed.
- No image/video files were generated. Camera, server and Unity exited normally.

601/795 frames had valid marker evidence; the rest include startup and the user
moving away near the end. There were still marker, observation and tool holds.
This single run is not a stationary uptime benchmark or proof of robust operation
in every posture. It verifies the current A interaction -> server transition ->
SBS B guidance path, NOT fastening torque or final assembly correctness.

Next: opt-in B/C/D progression using the same evidence gate, with a bounded full
screw-sequence trial. Keep manual box/lid/final verification explicit and preserve
the current operator-confirmed fallback. No additional eye calibration is needed
just to connect the existing step-specific overlays.

## Full screw sequence extension

The user requested the same proven A interaction path for B/C/D. Added only
`-ScrewAutoEndState S6` / `--screw-auto-end-state S6`, with S3 retained as the
default. The option requires the explicit auto-trial flag. Model weights, tip
geometry, timing thresholds, profiles, C/D depth corrections and Unity code are
unchanged. No Unity rebuild is needed for this server-side sequence extension.

The bounded launcher checks the requested terminal state in its own session's
metadata. S2/A -> S3/B -> S4/C -> S5/D -> S6/final confirmation uses the existing
gate and stage-target selection. Each target needs separate fresh engagement and
visible withdrawal; the final phase remains `AWAITING_CONFIRMATION`.

Regression verification: six failing cases before implementation, then 16 metric
trial cases passing. The new synthetic full-sequence integration test checks all
four transitions, their targets in browser messages, no premature progression
during engagement, final confirmation, no image saving and exact filter replay.
Full Python realtime suite: 639 passed. Targeted NUnitLite guidance/projection
suite: 135 passed, one optional offline-report test skipped. Launcher preflight
with S6 passed. These automated checks do not substitute for the live sequence.

### First full-sequence live run: blocked at B

Session: `viture_aruco_rt_20261107_202719_df9f6bbb1210`.
Runner: `outputs/demo/1b9f5139fe6f416c8f479b447ba87ab1`.
Player: `outputs/unity_p1/player-20261107-202723-496.log`.
1,416 frames; automatic A -> B at frame 415 only. User reported holding the driver
at B without progression. Stopped the owned run early; no photos/video captured.
Original exact filter replay passed for all 1,416 frames.

Source-frame-bound numeric analysis reconstructed each pose from that same
frame's logged marker corners. Among 431 unique valid YOLO observations, 302 B
observations had multiple raw driver boxes but only one intersecting the existing
metric work area. For example frame 1413 / source 1412 had a B distance of 7.40 mm,
with two extra driver boxes entirely to the left of that work area. Their actual
appearance is unknown because this run intentionally saved no images.

Root cause: global driver counting and highest-confidence selection ran before
the existing workspace intersection check. An irrelevant outside detection could
block or shadow the valid in-workspace driver.

Metric-trial-only fix: apply the existing work-area intersection before both
driver counting and selection. Preserve all raw boxes and `driver_count_raw` for
diagnosis. Multiple candidates inside the work area still block progression;
outside-only observations cannot count as withdrawal. Legacy geometry, model,
confidence thresholds, interaction timings and eye calibration are unchanged.

Three new regression cases failed before the fix; four cases now cover zero,
one and two in-area candidates, outside high-confidence distractors, raw evidence
retention and unchanged legacy behavior. Focused geometry/YOLO/timing suite:
72 passed; full realtime suite after the fix: 643 passed. Numeric counterfactual
replay, using the saved boxes and original
timestamps (no repeated or invented observations), advances A -> B at frame 415
and B -> C at frame 580. This is NOT a new live success or proof of C/D accuracy.
Analysis artifacts: `outputs/tool_review_20261107/scope-audit.json` and
`scope-replay.json`. Original session logs were not changed.

### Scoped-detector live run: reached D, final confirmation not passed

Session: `viture_aruco_rt_20261107_203717_9961750bb3c6`.
Runner: `outputs/demo/1dca0aa4456b496b8a1860851785656a`.
Player: `outputs/unity_p1/player-20261107-203721-899.log`.
Stopped by the 300-second launcher limit. 2,945 recorded frames (294.58 seconds
between first/last input timestamps); zero photos/video files. Camera/server/player
exited. Exact filter replay matched all 2,945 frames.

Automatic transitions, with no supervisor completion commands:
- Frame 354: A -> B (S2 -> S3).
- Frame 578: B -> C (S3 -> S4); two raw boxes, one in-workspace driver.
- Frame 1409: C -> D (S4 -> S5).
- No S5 -> S6 transition. Do NOT report the complete screw sequence as passed.

The user reached D, physically tightened it, and did not notice the withdrawal
instruction. Server logs contain 12 D engagement confirmations (`OBSERVED`, 144
frames total); Unity logs also enter `SBS_GUIDANCE_OBSERVED_screw_d`. This confirms
receipt/state handling, not that the user perceived a usable, steady instruction.

Replaying the exact state machine reveals 11 D engagement resets: five from two
in-workspace driver candidates, two from no in-workspace driver, and four from
invalid marker pose. The last engagement remained armed when the time limit ended.
Maximum accumulated valid withdrawal evidence was 208 ms versus the unchanged
400 ms requirement. No threshold was relaxed to turn this into a pass.

Next work is limited to D source-bound duplicate/missing-tool diagnosis and
legible, stable action/status feedback. Preserve the successful A/B/C path and
existing eye calibration. Tightening again is not needed to diagnose this:
the system observes visual interaction, not torque. If images become necessary,
request fresh explicit permission; this run has numeric evidence only.

### Duplicate shaft suppression and explicit action cues (2026-11-07)

Numeric source-frame review of the five D duplicate resets found overlapping
shaft boxes with IoU 0.549-0.697. This is evidence of overlapping candidates,
not image-based proof of two distinct physical tools; no new photos were taken.

The metric trial now applies OpenCV NMS at IoU 0.5 after the existing workspace
intersection test. It retains raw detections, `driver_count_raw`, and the
pre-NMS `driver_count_in_workspace` for diagnosis. Spatially separate in-area
tools still block progression. Legacy scoring, model weights, tip geometry,
confidence thresholds, engagement/release times and optical profiles are unchanged.
This remains a single-tool demo: highly overlapping real tools cannot reliably
be distinguished using these boxes alone.

Counterfactual replay uses original logged detections, their own source-frame
marker pose, and original timestamps, without new inference or invented frames:
- Previously successful A run: A -> B remains at frame 495.
- Last D-blocked run: A -> B 354, B -> C 451, C -> D 709, D -> S6 1923.
- S6 is `AWAITING_CONFIRMATION`, NOT fastening verification or automatic completion.
- These are offline counterfactuals, not a new successful live sequence. User
  behavior could differ when seeing earlier transitions. Live confirmation remains.

Artifacts: `outputs/tool_review_20261107/nms-a-regression/` and `nms-latest/`.
Original exact filter replays still match 795 and 2,945 frames respectively.
No source session files were modified.

Unity now titles the current target explicitly (`SCREW D | 4 / 4`) rather than
showing a preceding state's observed-event label. Large cues and ring colors are:
cyan `WORK AT X`, amber `HOLD AT X`, green `MOVE CLEAR`, and amber `PAUSED`.
The detailed server instruction remains visible; recognition loss clears the
withdrawal cue immediately rather than latching a misleading success message.
The instruction band moves above low targets, with a 100-pixel deadband and
position retention during pose loss. Both eyes use the same text layout.

Verification:
- New metric duplicate test failed before the fix; legacy and two-tool separation
  regressions remain covered. Full realtime suite: 645 passed.
- First full run had an intermittent existing Tk resource lookup failure;
  isolated retry and the complete rerun passed without code/environment changes.
- NUnitLite: 294 passed, one optional offline-projection-report test skipped.
- Unity build: `outputs/unity_p1/build-20261107-211849-937.log`.
- Synthetic laptop-only rendered captures: 46 normal-target frames and 52 final
  low-target frames passed pixel checks for A-D, eye separation, hidden rings
  during tracking loss/pause/disconnection and final confirmation. Captures are
  Unity-generated synthetic output, not desktop/camera recordings.
- Final captures: `outputs/unity_p1/cue-capture-final-20261107/`.
  An initial hidden-window run produced blank captures and an intermediate low
  run had incomplete renders; neither is counted as a passed visual check.
- Launcher `-CheckOnly` passed; no camera/optical test is implied by preflight.

Next live run must use fresh readiness confirmation, no supervisor completion
buttons, no new photos/video, and the same bounded five-minute launcher. The user
need not tighten the screws again: observe HOLD/MOVE CLEAR and visible withdrawal.
Do not claim automatic torque, rotation, seating-height or fastening-quality checks.

### First complete live A-D interaction sequence (2026-11-07 21:25 KST)

Session: `viture_aruco_rt_20261107_212521_29900053454b`.
Runner: `outputs/demo/fa363ef0941746659c63e02e114ded38`.
Player: `outputs/unity_p1/player-20261107-212524-409.log`.
The user confirmed readiness before capture, then reported that the ring and
large instructions were readable. No supervisor completion commands were sent.

Automatic transitions from actual input, not counterfactual replay:
- Frame 621, YOLO source 620: A -> B.
- Frame 918, YOLO source 916: B -> C.
- Frame 1069, YOLO source 1068: C -> D.
- Frame 1296, YOLO source 1294: D -> S6 / `AWAITING_CONFIRMATION`.

The user explicitly confirmed seeing D's MOVE CLEAR, withdrawing the driver,
and seeing the final-check instruction. Unity logs contain both D OBSERVED and
AWAITING_CONFIRMATION. This is the first full live interaction sequence passed
under this configuration, not proof of repeatability or actual screw tightness.
No `COMPLETED`/operator final confirmation was performed.

After final check, tracking loss produced PAUSED while the logical state stayed
S6; it did not rewind the sequence or generate extra transitions. Future final
confirmation UX may need to distinguish this from an unfinished screw interaction.

Stopped the owned session early using its session-verified stop file. Server,
camera and Unity exited; server-error.log is empty. 1,743 frames are logged, no
photos/videos were saved, and exact filter replay matched every frame. Keep the
same model, profiles, stage offsets, NMS and timings for the next repeatability
check rather than tuning after a successful single run.

### Same-configuration live repeat (2026-11-07 21:38 KST)

Session: `viture_aruco_rt_20261107_213813_9e374993e7ad`.
Runner: `outputs/demo/6c760fb5ed1a4eff95faafd8ddd006f2`.
Player: `outputs/unity_p1/player-20261107-213817-678.log`.
The user confirmed readiness and then explicitly reported A-D in order and the
final-check instruction. No supervisor advancement, new photos or video.

| Transition | Frame | YOLO source frame |
|---|---:|---:|
| A -> B | 761 | 760 |
| B -> C | 982 | 980 |
| C -> D | 1398 | 1396 |
| D -> S6 | 1736 | 1734 |

Exact filter replay matched 2,245 frames. Camera/server/Unity were stopped.
This is a second same-configuration live interaction pass, not a broad reliability
measurement and not torque/rotation/tightness verification. The user did not
perform an explicit final `COMPLETED` confirmation in this isolated screw trial.

### Minimal full-flow integration

Opt-in `-AssemblyFlow` / `--guidance-mode hybrid` wraps the unchanged metric timed
S2-S6 filter with explicit box, lid and final operator confirmations. It does not
re-enable unvalidated box/lid ROI scoring or let manual commands skip screw steps.
S6 final text and human confirmation no longer require visible markers; current
camera/server input and the existing 500ms freshness budget are still required.
The final confirmation says operator-confirmed completion, not automatic quality.

Recorded confirmation inputs are replayed along with numeric filter inputs.
Synthetic runtime tests use the actual scoring/geometry/filter and check full
S0-S6/COMPLETED sequencing and exact replay. Browser tests use the real controller
and local HTTP API, with synthetic evidence, not a camera.
See [current integration and command](beast_integrated_v1_20261104.md).
After offline/build/browser verification, one full live hybrid sequence passed:
`viture_aruco_rt_20261107_215714_e5592e580a6e` (21:57 KST).
Manual setup confirmations: frames 709 and 846. Automatic A->B, B->C, C->D,
D->S6: frames 1445/1630/2167/2382, using YOLO sources 1444/1628/2166/2380.
Explicit human final confirmation: frame 2456, revision 6 -> 7, phase COMPLETED.
The user confirmed sequential targets/instructions and the final completion
message in the glasses. Marker loss after completion did not hide that message.
Exact replay matched all 2,727 frames, including the three consumed confirmation
inputs. No photos/video, server-error.log empty, camera/server/player stopped.
This is a full-flow live pass under the current setup, not unrestricted tracking
or a claim of physical fastening quality. Startup tracking loss and intermediate
observation pauses still occurred; do not claim uninterrupted rendering.

## Completion order (historical plan)

1. Diagnose current driver boxes and tip at A (near vs clear) using numeric source
   records and, only with consent, a few labelled images. Separate detection noise
   from marker loss and plane geometry. Do not change eye alignment to fix it.
2. Pass A-to-B with sustained engagement, visible withdrawal and no hand-only or
   tracking-loss transitions. Then reuse the same flow for B-D and verify once.
3. Restore box/lid automatic evidence on current metric regions; otherwise label
   those steps as operator-confirmed. Never disguise manual steps as AI results.
4. Freeze a reproducible demo configuration, complete a full run, keep logs and
   document valid distance/posture limits and manual fallback.

Today/tomorrow is a delivery target, not a guarantee of unrestricted registration
or fully automatic fastening verification. Current reliable fallback is the
operator-confirmed stage-linked SBS demo.
