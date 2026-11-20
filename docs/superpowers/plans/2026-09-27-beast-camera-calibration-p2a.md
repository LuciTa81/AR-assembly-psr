# Beast Camera Calibration P2a Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare a printable calibration target and a local capture/solve tool that produces a reviewable Beast camera-intrinsics candidate without altering the working P0/P1 pipeline.

**Architecture:** An explicit capture command records manually selected checkerboard images with actual image dimensions and camera-mode metadata. A separate offline command estimates intrinsics using OpenCV and reports held-out reprojection errors. The candidate is never automatically activated for Unity or described as eye/display calibration.

**Tech Stack:** Existing Python/OpenCV/NumPy, standard-library JSON, pytest. ReportLab is a development-only target-generation dependency, not a live-server dependency.

**Spec:** `docs/superpowers/specs/2026-09-26-beast-minimal-harness-design.md`, sections 3, 6 and 7.

**Status:** Capture/solve implementation, 21 tests and independent read-only review are complete. The user captured 25 initial plus 15 edge views. The combined candidate uses 32 fit / 8 hold-out views (0.377 px holdout RMS); the previous edge folding is absent in sampled mathematical checks. Further board capture is paused in favor of a controlled workspace-projection trial. Live activation, metric workspace PnP and wearer alignment remain pending. The original P0/P1 functionality remains unchanged.

**Target preparation evidence (2026-09-27):** `scripts/create_beast_calibration_target.py` generated `C:/Users/fresh/OneDrive/Desktop/Beast_camera_calibration_A4_25mm.pdf` using bundled ReportLab without installing live-server dependencies. PDF inspection confirmed one 297 x 210 mm page, 35 black 25 x 25 mm squares, two 100 mm reference rulers, and `PrintScaling=None`. Poppler rendering was visually inspected; installed OpenCV 4.14.0 detected all 54 inner corners. This verifies the file, not the physical printer scale or camera calibration. A printout and measured scale are still needed.

## Global Constraints

- Windows laptop + Beast, no Neckband, remote server, cloud upload or new model.
- Keep existing ROI homography, OnlineStateFilter and Unity P1 working unchanged.
- Use the real capture resolution; never invent intrinsics from product FOV.
- Camera index is not device identity. Require a preview confirmation before saving images and record the explicit index/backend plus available device inventory.
- A camera profile is a candidate, not proof of real-world millimetre accuracy or binocular alignment.
- Use a new output directory for each recording; never overwrite previous captures/profiles.
- Camera recording starts only when the wearer is ready. Store selected images locally, not in Git.
- Do not commit, push, deploy or change Windows security settings in this phase.

## Review Focus

1. A4 print scaling changes physical dimensions: include a 100 mm ruler, measured-square input and print instructions.
2. Index changes or negotiated resolution differs: confirm preview identity, record actual mode and reject mixed-size sets.
3. Near-identical views make calibration ill-conditioned: reject exact duplicate images, report view coverage and require tilted/varied-distance captures rather than claiming a low RMS is sufficient.
4. Training reprojection is not validation: reserve views before fitting intrinsics, label held-out pose fitting explicitly and retain per-view results.
5. Missing/corrupt frames or failed detection must not silently yield a supposedly valid profile: record failures, require enough usable fit/validation views, reject non-finite parameters.

## Task 1: Printable Target and Capture

**Files:**
- Create: `scripts/create_beast_calibration_target.py`
- Create: `server/realtime/camera_calibration.py`
- Create: `tests/realtime/test_camera_calibration.py`
- Create: `docs/beast_camera_calibration.md`

**Interfaces:**
- Target: A4 landscape PDF, 10 x 7 squares, nominal 25 mm sides, 9 x 6 inner corners. A clear white border remains around the pattern.
- `checkerboard_object_points(columns: int, rows: int, square_mm: float) -> np.ndarray`: row-major float32 XYZ, Z=0, physical millimetres.
- `detect_checkerboard(image: np.ndarray, pattern_size: tuple[int, int]) -> np.ndarray | None`: OpenCV `findChessboardCornersSB`, unresized original-image coordinates.
- CLI: `python -m server.realtime.camera_calibration capture --camera-index 1 --backend dshow --width 1280 --height 720 --square-mm 25`. Default capture root is LOCALAPPDATA, outside the OneDrive repository.
- Capture records: schema version, target geometry/measured square size, camera index/backend/inventory, requested/actual image size, capture timestamps, image hashes and relative paths.

- [x] Write failing tests for point ordering/metric scale, invalid dimensions/square size, rendered checkerboard detection and empty-image rejection.
- [x] Run `python -m pytest tests/realtime/test_camera_calibration.py -q`; confirm relevant failures before implementation.
- [x] Implement target generation and OpenCV detector. Keep PDF tooling outside live-server imports.
- [x] Implement capture with an explicit preview-confirm key, Space to save only a detected full pattern, Q/Esc to quit, and `finally` camera/window cleanup. Write Unicode paths via encoded image bytes and `Path` APIs.
- [x] Add tests with fake capture to cover read failure, unexpected resolution, cancellation, no saving before identity confirmation and no overwrite.
- [x] Generate and visually inspect the PDF; render it and verify 54 detected inner corners. Verify page dimensions and the ruler's PDF length, not only visual appearance.
- [x] Document actual-size printing, rigid flat backing, measured square size, varied tilt/position/distance and 20-25 usable views. Do not start physical recording yet.

## Task 2: Offline Intrinsics Candidate and Validation Report

**Files:**
- Extend: `server/realtime/camera_calibration.py`
- Extend: `tests/realtime/test_camera_calibration.py`
- Extend: `docs/beast_camera_calibration.md`

**Interfaces:**
- `calibrate_views(views: list[np.ndarray], image_size: tuple[int, int], pattern_size: tuple[int, int], square_mm: float) -> dict`.
- CLI: `python -m server.realtime.camera_calibration solve --session <capture-directory>`.
- Require at least 15 usable, distinct images; reserve every fifth accepted view before fitting (at least 12 fit and 3 hold-out). This is a minimum dataset size, not an accuracy guarantee.
- Fit via `cv2.calibrateCamera`; evaluate held-out views with fixed K/distortion and `solvePnP` + `projectPoints`.
- Candidate JSON: schema/profile ID, provenance, image size, K, five distortion coefficients, measured square size, train/holdout membership, per-view pixel RMS, aggregate metrics, `status=candidate`, `display_alignment_verified=false`.
- The held-out pose is fitted from its corners; its residual checks consistency with fixed intrinsics, not absolute pose/mm accuracy. Do not auto-load the candidate into any live pipeline.

- [x] Add failing tests for recovery of known synthetic intrinsics from varied poses, exclusion of held-out views from calibration, duplicate/non-finite inputs, too few views and mixed image dimensions.
- [x] Implement load/validate/detect/split/fit/report; fail explicitly on unusable datasets or invalid numerical results. List every rejected image and reason.
- [x] Store fresh candidate/report files under the session with unique names; preserve selected images and capture metadata for reproduction.
- [x] Run synthetic end-to-end solve and verify recovered focal lengths/principal point within test tolerance; label all generated data synthetic.
- [x] Run the whole realtime Python test suite and Unity pure-state tests; record results without claiming physical calibration succeeded.
- [x] Perform one read-only review of the new files and fix material findings before handoff.

## Physical Follow-Up (Not Yet Done)

1. User confirms A4 printing or describes an existing board. Print at actual size, measure the ruler/squares and mount flat.
2. Confirm Beast preview and record varied calibration views with the capture tool. Review fitted candidate and held-out errors; recapture if necessary.
3. P2b: measure the six marker corners and screw A-D positions/heights in a consistent workspace frame. Implement metric PnP and verify camera-image projections while preserving the ROI warp.
4. P2c: collect wearer-specific display correspondences in 0DoF/default 2D, then test held-out physical targets, head motion and re-wearing. Assess monocular/binocular mismatch explicitly.
5. Only after those checks connect moving target coordinates to Unity. Tracking loss/stale pose must hide positional graphics.

## Primary References

- https://docs.opencv.org/4.x/dc/dbb/tutorial_py_calibration.html
- https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html

Checked 2026-09-27. Installed OpenCV API signatures must also be checked during implementation.

## Execution Record

- Task 1: software complete; user print/scale/flat-mount confirmation received. Tests were observed RED (missing module), then GREEN.
- Task 2: software and synthetic integration tests complete; independent read-only review found no material findings. Physical capture launched with the user's measured/flat-mounted board ready; no physical solve result yet.
- Verification: 21/21 new Python tests; 83/83 realtime suite; 25/25 Unity pure-state suite.
- Ruling: changed the default capture root from repository outputs to LOCALAPPDATA because this repository is in OneDrive. This preserves the local-only photo promise; cost is that users must follow the printed session path rather than look under repository outputs.
- No commit/push or changes to active recognition/display settings.
- Physical capture process started 2026-09-27 15:34 KST, requested Beast index 1 / DirectShow / 1280x720, manual save only. Session: `%LOCALAPPDATA%/ARAssembly/beast-mvp/camera_calibration/beast-calibration-20260927T063458Z-6e9910e4`. Launch is not proof of saved images or a valid camera profile.
- Physical capture ended normally with 25 saved views at 15:47 KST; camera process exited. All saved views passed hash/size/detection checks. Fit/holdout RMS 0.299132/0.304811 px. Candidate retained but NOT activated. See `docs/beast_camera_calibration_result_20260927.md` for edge coverage, non-monotonic radial extrapolation and the targeted extra-capture request.
- Additional 15-view capture ended normally. Combined 40-view audit: all inputs passed; 32 fit / 8 holdout, RMS 0.285371 / 0.377395 px; sampled minimum radial derivative 0.982610, Jacobian determinant 0.965879. Candidate `beast-combined-20260927T065914Z-89414bbe` retained for a controlled PnP trial, NOT activated. See the report's latest section; no further capture requested at this point.
