# AR Assembly for Fold7 + Beast

## Exhibition checkpoint: 2026-11-26

Current source: Android `1.4.2`, tracking candidate `1.4.2-partial-markers-c3.2`.
See [checkpoint and restoration notes](../../checkpoints/2026-11-26/README.md),
[partial-marker test history](docs/PARTIAL_TRACKING_C32_20261125.md), and
[internet supervisor](internet-supervisor/README.md).

The current runtime includes opt-in internet state/video sharing and server recording.
The work limit is ten minutes; final inspection ends earlier. Historical trial limits
below describe earlier builds, not the current exhibition configuration.
Private model weights, signing keys, APKs, raw recordings/logs and local SDKs are not
included. This is a source checkpoint, not a turnkey signed distribution.

## Historical standalone candidate (1.1)

The user-accepted functional baseline is frozen separately: [v1 checkpoint](V1_CHECKPOINT.md).
The current `1.1-candidate` launches full v1 guidance from the Android launcher without ADB extras. Camera capture still requires the Start button. Stop keeps the application open; a new Start begins at box placement. Display loss, backgrounding, camera errors and the existing five-minute limit stop capture without automatic restart. No camera/audio recording or network streaming is added.

Normal flow: connect Beast, choose Full SBS 3840x1080 with the unchanged wearing/display configuration, open **AR Assembly**, wait for readiness, and start. Refresh connection status using the refresh icon when needed. Detailed numeric tracking is collapsed by default. [Korean operating guide](SOLO_START.md).

An explicit diagnostic mode extra keeps the historical narrow probe behavior. Default full flow includes the physical box/lid outline, four screw reference rings with only the current screw colored, mint final-inspection rings, and the headlocked 3D part preview. Timing and calibration remain those of v1 (205/205mm, preparation 7s/6s tracked time, 800ms proximity, 4s working delay, then 3s after actual green presentation).

## Historical diagnostic releases

Independent test app; no changes to the Windows runtime or eye calibration.

- v0.5 adds an opt-in on-phone YOLO tool probe (`--ez tool_probe true`). Default optical probes are unchanged. The original v0.4 APK is saved in `baseline/beast-gate-v04-all-targets.apk`.
- Tool inference runs on a separate single worker with at most one pending/in-flight frame. Eye tracking does not wait for inference. Phone boxes, marker points and camera bitmap come from the same frame; boxes expire after 500 ms.
- The tool probe is detection only: it does not advance assembly steps or establish fastening completion. It still requires a button press and stops capture after 30 seconds.
- `--ez pose_probe true` enables a 30-second four-marker diagnostic (normally without `tool_probe`). `BeastPoseFrame` logcat entries contain numeric detected corners, rejection reason, available RMS/maximum residual, observation age and eye-pair readiness for each processed frame, not every UVC callback. No images are stored. Rejected poses never publish targets; thresholds and projection rules are unchanged. `pair_ready` is a diagnostic input state, not proof that a ring was seen on the physical display.
- The local YOLO11s model is exported to fixed-shape ONNX (640x384, CPU, two threads). The three classes remain `driver`, `handle`, `screw`. Model SHA256 is checked at load.

- v0.4: Android Presentation renders one selected screw with separate left/right projections on a 3840x1080 SBS surface. No rescaling or new calibration fit.
- Phone UVC preview shows detected marker outlines and camera-view A-D circles. Capture starts only from the button; the stereo trial stops after 30 seconds.
- Pose rejection, points outside either eye, or observations older than 500 ms hide both eye rings. Non-3840x1080 external output blocks the trial.
- v0.1 L/R connectivity and v0.2 camera-view APKs are preserved in `baseline/`.
- Only camera permission. No microphone, storage or Internet permission.
- Numeric frame counters in logcat; no frame files or audio recordings.
- USB filter: Sonix 0c45:6368, observed on the connected Beast.
- Dependency: com.herohan:UVCAndroid:1.0.13 (Apache-2.0 wrapper; native dependencies have their own notices).
- Not a full assembly app or fastening verifier. Existing eye projections are being tested on Android, not assumed validated there.

`RESULTS.md` records the completed gates and outstanding physical checks.

## Local model verification

`model-export/export_model.py` exports a copy of the existing model and compares
three frames from an existing recording against desktop PyTorch. It never opens
a camera. Test frames and float tensors live only in the instrumentation APK,
not the application APK. Dependencies are isolated in `model-export/deps`.

At exactly 1280x720 -> 640x360, Android uses area reduction to reproduce desktop
linear reduction bit-for-bit. ARM's linear implementation produced different
rounding; the full input-tensor regression check prevents recurrence. This is
specific to the fixed 2x scale, not a claim about arbitrary resize ratios.

Runtime references: [ONNX Runtime Java](https://onnxruntime.ai/docs/get-started/with-java.html),
[Android deployment](https://onnxruntime.ai/docs/tutorials/mobile/deploy-android.html),
[Ultralytics export](https://docs.ultralytics.com/modes/export/).

## Build and verify

Run `./build.ps1` for app APK, instrumentation APK and lint. Use this script so
`ANDROID_USER_HOME` and the debug signing key remain consistent for updates; do not
uninstall the app to work around a signing mismatch.

The device tests check camera XYZ/pixel parity against synthetic Windows fixtures,
eight frozen Unity eye-projection samples, invalid input rejection, and in-memory
stereo canvas pixels (left/right half mapping, stale frames, wrong surface size).
They do not measure physical binocular alignment.

The copied `eye-projection.json` is the unchanged joint A-D candidate selected by
the Windows console launcher, not the older baseline `candidate-probe.json`.
Its original candidate flags are preserved. Camera/workspace SHA256 bindings are
checked before any eye projection is enabled.

For sequential physical checks, launch a fresh activity with `--es probe_target B`
(or C/D). The target is fixed for that activity; omitted/invalid values select A.
Starting the activity does not start capture. The user must press the labeled
30-second button. The A-only v0.3 APK is preserved as `baseline/beast-gate-v03-A.apk`.
