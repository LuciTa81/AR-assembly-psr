# Fold7 + Beast direct connection gate

Observed 2026-11-20, SM-F966N / Android 16. Windows runtime and A-D calibration unchanged.

## Confirmed

- Wireless ADB works while Beast occupies the phone USB-C port.
- Android enumerates VITURE Beast and Sonix USB camera (0c45:6368).
- Switching the glasses to Full SBS exposes a 3840x1080, approximately 60 Hz external display.
- The separate test app creates a 3840x1080 Presentation surface.
- UVCAndroid 1.0.13 opens `Size(1920x1080@30,type:7)`.
- At 23:56:08-23:56:27, frame count increases from 19 to 432. One-second callback rates are mostly around 20 fps initially, reaching about 30 fps for the final three samples.
- Display remains 3840x1080 @ 60 Hz while camera callbacks arrive.
- User confirms increasing frame counter.
- User confirms live workbench imagery is visible on the phone.
- User confirms L is visible in the left eye and R in the right eye.
- Build succeeds; Android lint: 0 errors, 7 warnings. Packaged permissions include CAMERA and an app-private signature receiver permission, not microphone/storage/Internet permissions.

## Initially unverified (v0.1)

- Preview orientation, aspect ratio, sharpness, and suitability for marker detection have not been quantitatively checked.
- Sustained performance, thermal behavior, USB reconnection, inference speed, and marker tracking.
- Real eye-projection calibration on Android. This test pattern is not calibrated AR.

No camera frame files, audio, or screen recordings were captured. Frame counters are numeric logcat diagnostics only. The camera preview stops automatically at 120 seconds or when the app leaves the foreground.

The initial simultaneous camera/display connectivity gate passed with user visual confirmation. The test app was explicitly stopped afterward; this result does not establish full application portability or calibrated AR accuracy.

## Camera-space tracking gate (v0.2, 2026-11-21)

- Build and lint tasks succeeded. Three Android instrumentation tests passed on the Fold7 after installing the updated APK.
- Synthetic front/near/side projections match the frozen Windows reference within 0.05 pixels; this is numerical parity, not measured physical accuracy.
- The camera negotiated `Size(1280x720@30,type:7)`, matching the copied camera profile resolution. NV21 frames are analyzed on-device with OpenCV 4.14.0, at most once every 200 ms.
- Live logs contain accepted 4-6-marker poses. For example, at 00:18:45-00:18:49 all six markers were detected, RMS ranged from 1.47 to 3.00 pixels, processing latency was 24-31 ms, and camera callbacks were about 20 fps. These are sampled diagnostics, not a sustained benchmark.
- The user first reported video without A-D circles, then confirmed circles were visible when holding the view steady, and finally confirmed all four circles roughly aligned with the screw heads in the phone video.
- Marker counts repeatedly fell below four, including zero; the exact cause of each loss was not established. No thresholds or calibration were changed to mask these losses.
- This passes a qualitative camera-view alignment check only. Eye-space projection, binocular alignment, depth/angle accuracy, and sustained tracking remain unverified on Android.
- No photos, videos, or audio were saved. The app was explicitly force-stopped after feedback; `pidof com.lucita.beastgate` returned no process.
- Windows runtime and original A-D calibration remain unchanged. The external glasses display still uses the L/R diagnostic pattern, not the tracked A-D overlay.

## A-only binocular candidate (v0.3, 2026-11-21)

- Copied the joint candidate actually selected by `scripts/run_beast_console_session.ps1`; SHA256 `1127d29fb5022d005373d12eb0a8886fabafa53c852ac4bb3fd281ccd10904f3` matches the existing local Windows file. No matrix, target, or profile bytes were changed.
- Camera-space XYZ now feeds the same row-major 3x4 homogeneous projection formula as Unity `CandidateProjection.TryProject`. No per-stage offsets or C/D depth adjustments are added.
- Five tests passed on the Fold7 (`stereo-tests-device.txt`): prior detector/rejection checks, synthetic camera XYZ/pixel parity, eight saved eye-projection replay points within 1e-7 pixels, and canvas checks for separate eye halves, stale data, and incorrect output size.
- `build.ps1` succeeded including both APKs and lint (0 errors, 10 warnings). Installed v0.3 without uninstalling the previous app. A first signing mismatch was corrected by using the existing project-specific Android user home; the build script now includes the instrumentation APK to keep signing consistent.
- At 00:29:57 the actual Presentation reported 3840x1080 at 60 Hz and its drawing surface reported 3840x1080. Camera remained idle awaiting the user's button.
- This candidate draws only A, clips each ring to its eye half, hides invalid/stale (>500 ms) observations and stops capture after 30 seconds. Only camera and the app-private receiver permissions are packaged; no image/audio recordings.
- Physical binocular alignment on Android is pending user confirmation. Successful numeric/rendering tests are not a physical accuracy result.

### A live feedback

- User subsequently confirmed A appears as one binocular ring and remains roughly aligned when moving closer. This is a qualitative user check, not a quantified accuracy measurement or validation of B/C/D.
- Logs include accepted A left/right projections with 4-5 markers, e.g. 00:33:16-00:33:22, RMS 1.45-2.16 pixels and processing latency 21-28 ms. Marker loss and hidden rings also occur; continuous tracking stability is not established.
- Two 30-second run endings are recorded at 00:33:11 (489 frames) and 00:33:43 (488 frames). The app was explicitly force-stopped after feedback; no process remained.
- Next physical gate: B, C and D using the same unchanged joint eye projection, followed by modest side-view checks.

## Selectable single-target probe (v0.4, 2026-11-21)

- Added a validated launch-time `probe_target` (A/B/C/D, default A) used consistently by the phone label, camera target selection, and numeric eye logs. Capture remains explicitly user-started and bounded to 30 seconds.
- Build/lint succeeded; all six device tests passed (`target-tests-device.txt`), including target selection and the existing projection/rendering regression tests.
- Camera, workspace, and eye-projection asset hashes are unchanged from v0.3. A-only APK preserved locally. No Windows files or calibration values changed.
- B physical check is pending; C and D are also not yet physically verified on Android.

### B live feedback

- User confirmed one binocular B ring, roughly aligned with the screw at both the nearer and original distances.
- The 30-second run ended at 00:42:27 with 555 camera callbacks. Sampled accepted projections at 00:42:22-00:42:26 had RMS 2.05-2.60 px and latency 16-28 ms.
- Reprojection-limit, degenerate-geometry and insufficient-marker rejections also occurred. This is a qualitative alignment pass, not proof of uninterrupted tracking.
- Calibration and thresholds unchanged. C and D physical checks remain pending.

### C live feedback

- User confirmed C appears as one binocular ring and roughly aligns at both nearer and original distances.
- The 30-second run ended at 00:43:56 with 529 camera callbacks. At 00:43:48, five markers supported an accepted pose (RMS 1.80 px, 26 ms) with C left/right pixels reported.
- Insufficient-marker intervals and accepted poses without a visible C projection also occurred. The qualitative alignment check does not establish continuous visibility or the cause of every hidden interval.
- Calibration and thresholds unchanged. D physical check remains pending.

### D live feedback and distance-check summary

- User confirmed D appears as one binocular ring and roughly aligns at both nearer and original distances.
- The 30-second run ended at 00:44:51 with 581 camera callbacks. Its final sampled accepted D pair was L (1255.5,166.7), R (1022.3,166.0), RMS 1.41 px, processing latency 34 ms.
- Hidden intervals occurred both with insufficient markers and with an accepted pose but no drawable D pair. No claim of uninterrupted tracking is made.
- A/B/C/D now have qualitative user confirmation of binocular fusion and approximate screw alignment at two distances on Android. This is not a numerical physical-accuracy measurement, side-view validation, or a complete assembly workflow test.
- The app was force-stopped after D feedback; `pidof` returned no process. Calibration, thresholds and the Windows successful runtime remain unchanged.
- Remaining gates: modest lateral-view checks; then on-phone tool observation / workflow integration before validating 3-second automatic screw advancement and box/lid automation. The current Android diagnostic does not yet implement YOLO, assembly step decisions, or laptop supervision.

### A lateral-view check

- User confirmed approximate binocular alignment after a small lateral move and again on returning to the frontal position.
- The 30-second run ended at 00:47:39 with 565 camera callbacks. Accepted A left/right pairs were logged, including RMS 2.03 px and processing latency 29 ms at the final sample.
- An insufficient-marker rejection also appeared near the end. This records qualitative alignment in the tested movement, not uninterrupted tracking or a quantified angular operating range.
- No calibration or thresholds changed. B/C/D lateral checks remain pending.

### B lateral-view check

- User confirmed approximate binocular alignment after a small lateral move and on frontal return.
- The 30-second run ended at 00:49:02 with 583 camera callbacks. The ending samples had insufficient markers and hidden B rings; the user's alignment feedback applies to the visible portions.
- User noted that rings are mostly visible with five detected markers. No detection thresholds or calibration were changed. C/D lateral checks remain pending.

### C lateral-view check

- User confirmed C roughly aligned binocularly from the lateral position and after frontal return.
- The 30-second run ended at 00:50:31 with 582 camera callbacks. Visible C pairs at 00:50:27-00:50:29 had RMS 1.61-2.65 px and latency 28-34 ms; the final samples were hidden due to insufficient markers.
- Calibration and thresholds unchanged. D lateral check remains pending; tracking continuity is still a separate limitation.

### D lateral-view check and optical gate summary

- User confirmed D roughly aligned binocularly from the lateral position and after frontal return.
- Logs show a 30-second run ending at 00:54:28 (473 callbacks), followed by another run ending through the user's stop at 00:54:49 (294 callbacks). Accepted D eye pairs were recorded in both runs; insufficient-marker intervals also remained.
- After feedback the app was force-stopped and no process remained. No camera frames, videos or audio were saved.
- All A-D targets now have qualitative user confirmation at nearer/original distances and during a small lateral move with frontal return, using the unchanged Windows joint projection on Fold7/Beast. This does not establish a quantified accuracy envelope or uninterrupted tracking.
- Optical diagnostic gate is sufficient to proceed to a separate workflow candidate. Next: on-device tool inference and assembly state integration, then a clearly labeled 3-second timed screw advance option and box/lid advancement. Automatic fastening verification is not established by this optical gate.

### On-device YOLO numerical gate (2026-11-21)

- Copied the frozen `best-3.pt` model without modifying its source. Exported YOLO11s to ONNX opset 17, input `[1,3,384,640]`, output `[1,7,5040]`; classes driver/handle/screw, confidence 0.20, class-aware NMS IoU 0.70.
- Source SHA256: `a69070553f50eb124896f237107db9ff5653b19d0f1869fd5e01573ccbb34efe`.
- ONNX SHA256: `a44d5a558d6e3a693df2df92f80f1b7c4c89f84ef9531af0431b4f5429e4f179`.
- Existing take4 camera frames at 10/35/65 seconds yielded 1/1/3 detections. Desktop PyTorch versus ONNX comparisons passed at <0.2 px coordinate difference and <0.002 confidence difference. These are regression samples, not a detection-accuracy dataset.
- First Fold7 parity test failed. Full input comparison isolated 141,288 differing channel values in the first frame (maximum 1/255), before model inference. ARM OpenCV linear downsampling rounded differently from desktop. Exact 2x area reduction matched all input values for all three frames; raw-head and decoded-box comparisons then passed without relaxing tolerances.
- Fold7 instrumentation completed `OK (8 tests)` at 01:07:55: six existing optical tests plus two tool tests. The three measured preprocessing/inference intervals were 321/240/231 ms; the measurement also includes test fixture input comparison overhead. This is a short CPU sample, not a sustained camera throughput, thermal or battery benchmark.
- Model runs locally through ONNX Runtime CPU with two intra-op threads. No camera was opened for these checks. Existing camera/workspace/eye asset SHA256 values remain unchanged.
- v0.4 installed APK was saved before update. v0.5 live tool probe is opt-in, keeps optical tracking separate, and preserves frame/time correspondence for phone detection boxes. Actual camera-tool detection, combined tracking load and workflow remain to be checked.
- Final v0.5 build/lint succeeded. Fold7 instrumentation reported `OK (9 tests)` including phone overlay pixel checks for fresh, stale and cleared detections (`tool-tests-device.txt`). The app and test APK installed successfully.
- Launched the tool probe in waiting state at 01:11:18; model initialization reported `YOLO_READY`. Camera was not started. External display reported 1920x1080 at 01:11:31, so Full SBS must be reselected before a physical trial.

### Live tool probe feedback (2026-11-21)

- User confirmed that phone detection boxes generally followed the driver.
- Full SBS 3840x1080 and 1280x720 MJPEG camera opening were logged. Two runs auto-ended at 01:12:24 (524 callbacks) and 01:12:59 (611 callbacks). Numeric logs only: `tool-live-device.txt`.
- Across both runs, 249 YOLO results had inference duration mean 148 ms, range 83-230 ms; frame-receipt-to-result age mean 177 ms, range 96-266 ms. These are short-run measurements, not thermal or battery endurance results.
- The 58 one-second tracking samples included 12 accepted poses and 46 `need_four_markers` rejections. Sampling is not a frame-by-frame acceptance metric. Tool detection continued without a valid workspace pose, as intended for the diagnostic; it must not independently authorize assembly progress.
- Multiple driver/handle candidates and duplicate-looking detections occur in raw output. No ground-truth images were saved, so this feedback is not a quantitative precision/recall result. Next: port the existing tool/handle association and tip-to-target distance calculation with same-frame pose validity before connecting hold/advance logic.
- App was force-stopped after feedback; `pidof` returned no remaining process. Calibration and Windows runtime unchanged. Three-second auto-advance, box/lid automation, part preview and laptop supervision are not implemented in this probe.

### Four-marker investigation (2026-11-21)

- User observed that four visible markers often seemed insufficient. Existing live logs demonstrate two accepted four-marker samples (`[1,2,3,5]`, RMS 0.89/0.91 px, visible A left/right coordinates at 01:12:13/14). The implementation requires at least four registered markers, not five.
- Added an instrumentation audit of all 15 four-marker subsets at each of three noiseless synthetic poses (middle/near/side). All 45 cases matched the expected behavior: 36 accepted; 9 rejected before reprojection checking with `degenerate_ippe_geometry`. The rejected subsets are `[0,1,2,3]`, `[0,1,2,4]`, `[0,1,2,5]` at each pose; registered centers 0/1/2 share the same y coordinate.
- This confirms a structural limitation of the current center-based IPPE support rule, not the cause of every live disappearance. Other combinations can still fail due to noisy detections, reprojection error, ambiguity, stale data or eye bounds. Existing live tracking logs are sampled once per second and cannot reconstruct every rejected frame.
- Build/lint and `OK (10 tests)` passed on Fold7. See `four-marker-tests-device.txt` and `four-marker-audit.txt`. No camera was opened, runtime rules were not changed, and no calibration/marker placement changes were made.
- Order of work: investigate live four-marker rejection reasons before enabling automatic step transitions; tool-tip/distance port can proceed with valid poses only. Do not increase the 3.2 px limit to bypass geometry rejection. Corner-based or alternate-solver candidates require separate offline/physical accuracy checks and must remain isolated from the verified baseline.

### Per-processed-frame diagnostic candidate

- Added opt-in `pose_probe` logging: marker IDs and numeric corner coordinates, pose rejection reason, RMS/max residual when a physical candidate exists, observation age and eye-pair readiness. No images/audio are saved. Geometry rejection may still have null residuals because it occurs before solving; ambiguity rejection reports pre-refinement residuals.
- Rejected observations retain diagnostic residuals only; targets and camera XYZ remain empty. The 3.2 px RMS, 5 px point limit, geometry/ambiguity checks and eye projections were not changed.
- New regression verifies a noisy rejected pose retains residuals but never publishes targets. Existing four-marker subset, projection, detector and drawing tests remain passing: `OK (11 tests)` on Fold7 (`pose-diagnostic-tests-device.txt`). Build/lint succeeded and camera/workspace/eye asset hashes were unchanged.
- Saved the previous installed tool-probe APK as `baseline/beast-gate-v05-tool-probe.apk`. Opened the diagnostic at 01:31:01 in waiting state; no camera was started by the assistant. Live four-marker trial is pending user readiness and button press.

### Live four-marker diagnosis result (2026-11-21)

- User reported that the A ring disappeared with four markers and returned on returning to the original posture.
- Run ended automatically at 01:32:08 with 563 camera callbacks. Captured 129 processed-frame diagnostic entries in `pose-live-device.txt`; this is not 129 raw camera frames. App was force-stopped after log collection and no PID remained.
- Four markers: 70 entries. `[0,1,2,4]` was rejected 35 times and `[0,1,2,5]` 34 times, all `degenerate_ippe_geometry` before solving/reprojection checks. One `[0,2,4,5]` entry was accepted with RMS 1.918 px, maximum residual 2.207 px and `pair_ready`.
- Five markers `[0,1,2,4,5]`: 48 accepted / pair-ready entries and 2 reprojection-limit rejections. Fewer than four markers: 9 entries. Observation ages were 18-51 ms (mean 36.38 ms); no logged eye-bound or stale-data rejection explained the four-marker failures.
- The four-marker symptom in this trial is predominantly the center-based support geometry guard, not the RMS threshold. Raising 3.2 px would not address those 69 rejected entries. Guard removal without a validated alternative is not a fix.
- Next candidate evaluation can replay the saved numeric corners without another camera session. Keep successful 5-marker processing/calibration unchanged; separately assess an alternative observation/pose method for degenerate 4-center cases. Any corner-based approach requires validated physical corner geometry, not assuming the approximate 70 mm marker size is exact. Candidate acceptance needs target XYZ / eye-projection consistency and physical alignment checks, not merely more accepted poses.

### Offline fallback comparison decision

- Completed `pose_replay_compare.py`; details in `pose-comparison/REVIEW.md` and `report.json`. Replayed all 129 Android accept/reject outcomes with zero mismatches; all protected input hashes unchanged.
- SQPnP produced 68/69 actual geometry-rejected candidates, but those observations lack independent reference poses. Masking ID 4/5 from 48 accepted five-marker frames preserved prior target position in only 29/48 and 1/48 cases respectively (report-only 5px camera AND 5mm XYZ criteria). Worst eye-coordinate differences were 465.10/61.17 px.
- Historical 300ms temporal candidate also failed to consistently preserve target positions (22/42 and 24/42), contributing only two actual fallback poses. Its original 3.0px RMS policy was not modified; no lifetime extension was tried.
- Six camera-free analysis regression checks passed. No Android build/install/runtime change, camera activation, marker movement or calibration edits in this comparison. Neither fallback is approved for live use. Next requires trustworthy corner geometry/observation validation, not accepting more solves by lowering guards.

### 69/70 mm corner hypothesis sensitivity

- User confirmed six equal-size markers and currently estimates the black outer side at approximately 69 mm; historical 70 mm was explicitly approximate. Neither is promoted to an exact calibrated value.
- Completed `corner_size_compare.py`: first eight accepted five-marker observations fit orientation only; later 110 observations evaluate fixed 69/70 mm square hypotheses. Registered centers and A-D coordinates unchanged; missing marker 3 orientation not invented.
- On 40 held-out full-five-marker references, corner hypotheses returned only 5/6 poses. Mask ID 4: preserved 1/40 for each size; mask ID 5: 0/40 for each. Neither candidate is approved for live use.
- On the 31 observations where both sizes passed, maximum side-change differences were 1.69 camera px, 1.16 mm camera XYZ, 3.69 eye px. These are hypothesis-to-hypothesis differences, not true-size or physical accuracy measurements. A side-length adjustment alone did not fix baseline inconsistency.
- Details: `pose-comparison/CORNER_SIZE_REVIEW.md`, `corner-size-report.json`. Ten combined offline checks passed, including synthetic known geometry and no fit/evaluation overlap. No camera, phone install, runtime modification or calibration changes.

### Step 1 complete: per-marker inconsistency audit

- Used the 40 held-out accepted five-marker observations; no fitting on evaluation frames. `marker_observation_audit.py` separates center residual, full corner residual and corner-shape residual after removing common image translation.
- At 69mm, median shape residuals for IDs 0/1/2/4/5 were 2.03/1.82/1.64/3.03/6.14 px. IDs 4 and 5 had the highest shape residual in 20 and 18 of 40 observations, respectively; the same dominance counts held at 70mm.
- ID1 center residual pointed left in 40/40 observations, median horizontal residual -3.03 px. ID4 center residual was modest (median 0.70px) despite corner-shape peaks of 10.20px. These are consistency differences against a pose fitted from the same observations, not proof of misplacement or a particular detector failure.
- ID3 could not be assessed. Without images, boundary selection, physical paper/registration and camera-model effects cannot be separated.
- Next necessary input narrowed to one visual check of ID4/5 detected boundaries against the actual black square at a steady and slightly changed viewpoint. Images would require separate user consent. Only if boundaries are correct, prioritize measuring top-row center distances 0-1 and 1-2 (both currently registered 205mm), then ID4/5 flatness/dimensions. Do not move markers.
- Korean report: `pose-comparison/MARKER_AUDIT.md`; complete data: `marker-audit.json`. Thirteen combined offline checks passed. Protected hashes unchanged; no camera, Android install or calibration/runtime changes.
