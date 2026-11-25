# Internet Camera Preview

## Goal and Scope

Implement authenticated Fold7 camera preview on the existing owner-only web dashboard. The user deferred live camera testing: do not start the camera or send real images in this task. Preserve v1, calibrations, assembly rules, existing app data and deployed working releases. No audio, recording, public feeds or camera remote-start.

## Design Decision

Use a separate WSS `/video` channel with bounded JPEG frames at 640x360, at most 5 fps. Existing ws/OkHttp/JPEG codecs avoid a new paid service, TURN deployment or camera ownership changes. This is a low-frame-rate supervisor preview, not a 30fps WebRTC stream. State and media have independent sockets and backpressure; drop media instead of queuing. The phone must explicitly consent per connection. Stop/background/disconnect invalidates in-flight frames. No frames enter the database or disk.

Reuse current publisher authentication and single-use owner observer tickets, expiry, allowed Origin, revocation and heartbeat. Limit frames to 100 KiB, validate JPEG dimensions, do not retain latest image server-side. Browser clears stale frames after 3s and closes decoded ImageBitmaps (no object URLs). Separate recording remains unavailable.

Reference review: prior source audit found SafeOps liveSnapshot is polling and IVS Stage media is separate; it is not a ready-made Android Beast transport. This task's repeat public GitHub fetch failed; do not claim a fresh successful code read or copy company code.

## Tasks

- [x] Media protocol validation and relay channel; auth/isolation/consent/revocation/stale tests; bounded queue handling.
- [x] Android opt-in encoder/transport separated from tracking; transport consent/reset/failure tests and NV21 downsampling tests.
- [x] Web preview, stale/offline states and explicit viewer toggle.
- [x] Build, typecheck, tests and synthetic frame end-to-end rendering.
- [x] Package APK and deployment source changes separately. Preserve production rollback.
- [ ] Production deployment and actual Fold7-to-web camera/cellular validation: deferred by user, not claimed complete. Encoder CPU/thermal effects and congested-network behavior require a real device trial.

## Completion Evidence

Report implemented/build-tested separately from deployed and real-camera-tested. Never describe synthetic fixture rendering as actual camera/AR validation. Existing calibration and model assets must match the previous APK. Media cannot affect stage advancement or imply fastening verification.
