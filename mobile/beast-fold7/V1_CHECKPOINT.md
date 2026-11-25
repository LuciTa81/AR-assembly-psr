# Fold7 + Beast v1 (2026-11-21)

## Frozen checkpoint

`baseline/v1-frozen-20261121/` contains the unmodified v1 APK, instrumentation APK, application source/assets/tests, Gradle build configuration, local debug signing key when present, and development/test reports. All 90 archived files were SHA256-verified against `sha256-manifest.json` before standalone-launch work began. Do not overwrite this directory or publish its signing key or test images.

APK SHA256: `43F7DE01B3E7CCEA603DCC59551136B9091AB5A19FCABE1DAA0042F1FA44BC7B`.

This is the user's functional v1 checkpoint. Its APK's historical package metadata is still versionName 0.5 / versionCode 5. It needs the existing `screw_context` launch option; the subsequent standalone-launch candidate removes that requirement for normal launcher entry.

## Frozen behavior

- Fold7 Android 16, Beast Full SBS 3840x1080, 0DoF / Extra Large / 4.5m.
- Workspace top-row centers stay x=0,205,410mm (205/205 spacing). Camera/workspace/eye profiles unchanged.
- Body 7s, lid 6s of valid tracked guidance time; not object placement/closure detection.
- Screw proximity accumulation 800ms, then working cue delay 4s with fresh valid near evidence required for green. Actual green presentation starts a 3s next-target timer.
- Four screw rings, inactive neutral and active orange/blue/green; final inspection rings mint #4D8577. Physical body/lid outlines and headlocked 3D part preview included.
- Full flow stops after final inspection (10s), or at the existing five-minute bound. User stop and connection-loss stop remain available.
- No camera video/photo/audio recording in normal assembly mode; numeric diagnostic logs only.
- Does not verify fastening torque/quality. Qualitative alignment/appearance feedback does not establish numerical optical accuracy.
- 42 device tests passed with the 4s setting; that last one-second adjustment has not received separate wearer timing feedback.

## Restore

Install `v1.apk` as an update with the same package/signing identity (do not uninstall to resolve signature problems), then launch `com.lucita.beastgate/.MainActivity --ez screw_context true`. Launch alone does not open the camera; press the phone's start button.

For source rebuild, use the archived source's `build.ps1`. Its SDK/JDK/Gradle paths refer to this laptop. Maven dependencies and toolchain caches are external prerequisites, not an offline reproducible toolchain archive. The APK is the exact runnable fallback.

## Next candidate scope

Default launcher entry uses the frozen full-flow options. Explicit diagnostic intents retain their narrower modes. Start remains user-triggered; display/model/camera-device readiness controls buttons. Stop leaves the phone app open for a fresh session; backgrounding and disconnects stop capture without resuming automatically. Keep the five-minute bound and all vision/timing/geometry untouched. Rename the app to AR Assembly, keep the live preview and actionable connection state, and put numeric tracking details behind a toggle. No wireless supervisor or recording in this change.
