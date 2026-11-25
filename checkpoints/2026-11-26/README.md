# Exhibition source checkpoint (2026-11-26 KST)

## Scope

- Base: `dde9c62e7f08b77002a55fc1dba7edbd0a8fac8a` (existing public main).
- Backup branch: `backup/exhibition-20261126`. Main and deployments are unchanged.
- Added source root: `mobile/beast-fold7/`. Windows/Python/Unity history is retained.
- Includes Android source/tests, selected calibration and synthetic fixtures, relay and
  Next.js source/tests, deployment scripts, engineering notes and diagram generators.
- Runtime UI assets and their bundled licenses are included; captured photos are not.
- Excludes credentials, private keys, local databases, SDKs, dependency caches, model
  weights, APKs, PPTs, captured media, raw runtime logs and generated diagram exports.
- Notes preserve dated test history. Later entries can supersede earlier pending checks.

## Current configuration

- Fold7 / Android 16, VITURE Beast direct USB-C, Full SBS 3840x1080,
  0DoF, Extra Large, 4.5m; unchanged wearing position and fixed workspace.
- Android source version `1.4.2`; candidate package
  `com.lucita.beastgate.trackingcandidate`, suffix `-partial-markers-c3.2`.
- Keep the original v1 separately. Workspace registration remains 205/205mm;
  do not replace it with measured 200/205mm without recalibration and verification.
- C3.2 learns corner references with sufficient markers and permits validated 3/4-marker
  observations. It does not promise every subset or uninterrupted visibility.
- Box/lid preparation uses 7s/6s valid tracking time. Screw guidance retains orange,
  blue and green, 4s working delay and 3s after actual green presentation.
- Android performs OpenCV tracking and ONNX tool detection. Android Presentation/Canvas
  and a local Three.js HUD render the output. Python/Unity are the legacy desktop path.
- MediaPipe/HMM diagram extensions are design proposals, not implemented Android stages.
- Internet: Next.js/GitHub login, authenticated EC2 relay and PostgreSQL ownership,
  H.264 video, private S3 MP4 recordings. Consent is required; no audio recording.
- Recorded deployment limits: owner 10,000,000,000 bytes; file 300,000,000 bytes;
  600 seconds; retention seven days; one concurrent recording; `MULTI_USER=false`.
  These are usage limits, not a billing cap. This checkpoint does not enable services.

## Verification

On 2026-11-26, against the unchanged local source copied into this checkpoint:

- Relay: `node --test tests/*.test.ts`: 125 passed, zero failed.
- Relay TypeScript: `tsc --noEmit`: passed.
- Web TypeScript: `tsc --noEmit --incremental false`: passed.
- Gitleaks public-tree scan: no secrets found. The only new scoped exception is the
  public sample WebSocket nonce in a loopback protocol test, not a real credential.
- 333 copied files match their source SHA256 exactly. The copied README was updated;
  new checkpoint/ignore documentation is additional. No runtime code/calibration was edited.
- Diff whitespace check reports only the two verbatim bundled font-license lines
  with trailing spaces; third-party license text is preserved unchanged.
- No new hardware, camera, cloud recording or deployment test was started for Git backup.
- Earlier wearer and integration evidence is in
  [C3.2 history](../../mobile/beast-fold7/docs/PARTIAL_TRACKING_C32_20261125.md).
  The downloaded 121.437s file decoded all 819 frames; measured average was about 6.744fps,
  not 30fps. Long-duration stability and actual seven-day expiry remain separate checks.
- Visual guidance and tool proximity are not independent torque/fastening-quality measurements.

## Restoration

1. Use the matching source version, your own Android SDK/JDK/Gradle and Node toolchain.
   `build.ps1` and some diagram generators still contain original workstation paths.
2. Restore the private model to `app/src/main/assets/driver.onnx`; verify the checksum
   against `driver-model.json`. Do not substitute another model silently.
3. Provision your own local signing keystore. Updating an existing installed APK requires
   its original signing identity; no private signing material is published here.
4. Install relay/web dependencies from their lockfiles. The relay declares Node >=24.22.
   Configure `.env` from examples with fresh credentials. Examples must not be deployed as-is.
5. Deployment scripts are historical operator scripts, not an automatic deployment request.
   Review target host, storage limits, backup/rollback and authorization before use.
6. Diagnostic Python experiments reference private captured inputs not shipped here.
   Generated figures require external assets/runtime setup described in their sources.

Local supplemental backup is separate from this public repository. APK/model/media/PPT
checksums and raw diagnostic files must never be committed as a substitute for these notes.

## Release identity (SHA256)

| Artifact | SHA256 |
| --- | --- |
| C3.2 APK (local only) | `043D51AF0C709AF7BD24C3539E0B3084E9458154754E12BD208B85B41DE79F15` |
| camera-profile.json | `25F025BC5C2F71E4C83E6645E5CDC742BDA81CD75D30C55FF7E5ACA99924872E` |
| workspace-profile.json | `5D4F4C6610AF3264E0583EB64B038B3D66B12A9FC4844849D21D4F770D5C7ACC` |
| eye-projection.json | `1127D29FB5022D005373D12EB0A8886FABAFA53C852AC4BB3FD281CCD10904F3` |
