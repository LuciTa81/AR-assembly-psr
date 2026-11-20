# P2b Live Camera Projection Check

Spec: `../specs/2026-09-26-beast-minimal-harness-design.md`.

Scope: a finite laptop camera diagnostic using the saved camera/target candidates.
No runtime activation, Unity eye alignment, state estimation changes, or upload.

## Tasks

1. Validate the target candidate's camera ID/hash and A-D targets before opening
   a device. Reuse metric PnP; reject duplicate known markers and resolution changes.
2. Render targets only on the same fresh source frame. A 150 ms receive-age limit
   is experimental, not a sensor-to-display latency guarantee. Invalid/lost/stalled
   input hides all rings. Camera/PnP run in a separate owned process so a blocked
   native camera read does not prevent the UI watchdog or bounded shutdown.
3. Add a bounded preview with Q/window-close exit, local metadata logs and optional
   limited screenshots. Capture remains outside OneDrive. Test before live use.
4. Review, then ask the wearer to test left/right/near/far and marker occlusion.
   Record actual results without claiming eye alignment or mm accuracy.

## Verification

- Unit tests: profile binding, valid/invalid pose, duplicate markers, frame-size
  mismatch, stale/future timestamps, stale ring pixels, latest-only transport,
  camera release/error, owned worker shutdown, local evidence persistence.
- Run full Python suite, CLI help and a finite synthetic subprocess smoke test.
- Live validation requires the wearer's readiness; it is not replaced by tests.

## Execution Record

- Pre-flight: projection produces raw-camera pixels; preview consumes exactly the
  same frame and dimensions. Candidate stores calibration byte hash and ID.
- Ruling: this is a separate diagnostic, not main runtime integration. This keeps
  unverified physical geometry out of the current guidance. Integration remains P2.
- Ruling: use the existing isolated dirty worktree; no automatic commit/cleanup.
- Task 1-3: implemented; 18 new tests and complete Python suite 147 passed.
  Missing module RED -> GREEN; GUI failure incorrectly marked duration_limit was
  reproduced and fixed. Actual Windows spawn IPC tested with synthetic packets.
  Saved real candidates load with matching hashes. CLI help and diff checks pass.
- Task 4: user-approved 60s live run completed:
  565 received packets, 272 tracking / 293 rejected, 12 local samples. Different
  views visually show approximate screw alignment, not measured mm accuracy.
  Laptop preview was re-observed by the camera, producing duplicate marker IDs
  (134 rejections). Keep rejection; move laptop screen outside view and recheck.
- Ruling: repeated screen markers are an environmental ambiguity, not grounds
  to loosen thresholds or accept duplicate IDs. User asked to turn screen away.
- Second approved run: 40s, 357 packets (191 tracking,166 rejected),9 samples.
  Duplicate-ID rejections fell to1. Low marker count/degenerate subsets/motion
  still limit stability. These mixed-motion runs are not accuracy measurements.
- Final review: five important findings fixed. Native HighGUI Ctrl+S modal path
  replaced by own Tk window; no disk I/O during display; bounded evidence writer
  starts after window/camera cleanup; separate terminal camera-error channel;
  only acknowledged sample writes appear as saved. Stale transitions are logged.
  Regression tests observed failing then passing; new Tk pixel and finite spawn
  integration tests pass. No second hardware capture after UI lifecycle changes.
- Ruling: recordings buffered in RAM, maximum12 image pairs/300s of metadata.
  Unexpected process death can lose diagnostic evidence; this is documented.
  Avoids adding a durable streaming recorder to this temporary diagnostic.
- P2b diagnostic implementation complete; physical accuracy, stable operating
  range and P2c eye alignment remain unverified. No commit/push or activation.
- Final verification: full `python -X utf8 -B -m pytest -q` completed with
  153 passed in 12.93s; focused preview suite24 passed; `git diff --check` passed
  (existing LF/CRLF conversion warnings only). Reviewer closed after fixes.
