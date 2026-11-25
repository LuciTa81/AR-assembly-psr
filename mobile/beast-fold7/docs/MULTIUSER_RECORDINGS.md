# Internet recordings implementation

## Scope

- Preserve AR v1, calibration, and the current production deployment.
- Public GitHub login is an explicit opt-in configuration; numeric GitHub IDs own devices and recordings.
- Browser identity comes from the verified session through the trusted BFF, never a browser-supplied owner field.
- Recording requires separate phone consent. No audio, no automatic activation on existing installations.
- Private bucket: `safeops-aiserver-706762893591-ap-northeast-2-an`, region `ap-northeast-2`, prefix `recordings/`.
- Access ends seven days after completion. Storage cleanup retries independently; an expired file is never downloadable while deletion is pending.
- Paid recording activation, quotas, production migration, and real-device capture remain deployment gates.

## Progress

- [x] Existing source backup: `baseline/internet-supervisor-before-multiuser-20261125.zip`.
- [x] Private bucket policy saved; EC2 list succeeds within `recordings/`, outside-prefix listing denied. No files uploaded.
- [x] Tenant-safe HTTP, pairing, session revocation, state/video sockets and opt-in login.
- [x] Recording storage adapter, expiry, download authorization and bounded upload (local tests; no real S3 upload).
- [x] Phone capture consent and server remux; web recording library.
- [x] Automated tests, build, local UI checks.
- [ ] Approved production rollout and actual Fold7/Beast test.

## Verification gates

Cross-owner list/read/ticket/revoke/download must fail. Logout must not affect another owner. Disabled recording must reject uploads. Failed uploads cannot appear ready. Expired or deleted recordings cannot issue download URLs. Cleanup failure must retain retry state. Existing tests must continue to pass.

## Infrastructure caveats

The EC2 role is shared with NOVA; the bucket policy only grants that role access to the recording prefix and does not change existing IAM policies. The S3 seven-day lifecycle rule was prepared but has NOT been saved yet. Do not describe retention as deployed until verified.

## Implementation checkpoint 2026-11-25

- Node: 108 tests passed; TypeScript passed. Includes actual authenticated WebSocket AVC packets -> MP4 -> fake private object storage -> owner-only access. Both I-only and I/P-frame MP4 samples passed FFmpeg decoding. Storage mocks do not prove AWS Put/Get/Delete permissions.
- Android: 39 JVM tests passed, `assembleDebug` and `lintDebug` succeeded. Analytics-settings permission and existing deprecated API warnings remain non-fatal. No device installation or camera capture performed.
- Next.js production build passed. Headless Chrome checked desktop 1440px/mobile 390px, download response, delete confirmation, empty list, visible actions and no page overflow/JS errors using isolated synthetic fixtures. No production login was bypassed.
- Candidate APK: `releases/ar-assembly-recordings-candidate-20261125/AR-Assembly-recordings-candidate.apk`.
- SHA256: `3EC8F7F7F1E6A946A3F204282ECC32B3C765D04197E139183F43FED2E035EEC0`.
- Existing AR assembly state machine, calibration and frozen v1 sources were not edited.

## Recording semantics

The phone independently opts into live video and recording. Consent is not persisted across an off/on cycle. New recording consent is sent only when the relay's authenticated ready message advertises support. Legacy relays keep receiving their original state shape.

The relay remuxes existing silent 1280x720 H.264 into fragmented MP4 without decoding/re-encoding. It starts on a key frame and accepts at most 16 queued frames. Sequence/timestamp gaps, state staleness, consent withdrawal, disconnection, configured duration/byte limits or server shutdown finalize only the accepted segment. One device/work-session can create only one recording, including after restart/deletion; a new work session is required to record again. The web labels interrupted segments as partial.

Review fixes: a per-job wall-clock timer enforces duration even after codec changes or missing AVC frames; failed DB transitions retain a bounded recovery slot and are retried before normal object cleanup; S3 signature time is anchored to the post-DB authorization time and rechecked after signing so lookup/credential delays cannot extend the retention cutoff. Regression tests reproduce all three cases.

Follow-up review caught a delayed-unlink/recovery race. Recovery now waits for the previous finalizer, and slot deletion/deadline callbacks verify job identity so old cleanup cannot remove a newer session. Both failing regressions now pass; the reviewer reran the delayed-unlink reproduction and found no remaining blocker in the reviewed fixes. This does not replace actual AWS/device validation.

Per-owner quota is reserved atomically before file creation and adjusted only after upload completes. Failed uploads never become ready; failed object deletion retains both retry metadata and quota. Temporary files are under a dedicated private spool. Server restart abandons unfinished records and retries cleanup, never presenting them as completed.

Download authorization is checked against the verified GitHub owner and active viewer session. Object keys never come from the browser. Signed URLs expire within 60 seconds and cannot extend beyond the seven-day cutoff. An already-issued URL is a bearer link until expiry or actual object deletion; logout alone cannot revoke it instantly. Keep links private and do not log them.

Application cleanup runs each minute. Expired files cannot receive new download URLs even if S3 deletion fails. Physical deletion is retry-based, not a guarantee of exact-to-the-second removal. Keep bucket configuration when disabling new capture so cleanup continues. Lifecycle remains an additional deployment safeguard, not the authorization boundary.

## Deployment gates (not applied)

1. Confirm permitted storage/transfer cost, file/owner quotas and concurrency. Add an aggregate service budget/rate guard before opening paid recording to unrestricted new accounts; per-user storage limits are not a billing cap.
2. Review existing production-secret rotation checkpoint before public login; do not copy secret values into documentation.
3. Back up PostgreSQL and current release; provision a dedicated writable spool with owner-only permissions. Existing service has `ProtectSystem=strict`: explicitly allow only the spool path. Check shutdown grace against upload/deletion deadlines and disk headroom. Run exactly one recorder process against this DB/spool.
4. Apply additive schema and server with capture off, deploy web with owner-only login, verify existing phone compatibility. Then separately enable `MULTI_USER=true` and `PUBLIC_GITHUB_LOGIN=true` and verify two actual accounts.
5. With cost approval, test one tiny synthetic S3 upload/read/delete using the EC2 role; save/verify retention lifecycle and incomplete multipart cleanup. Do not alter NOVA or other bucket policies.
6. Configure explicit capture limits, enable recording, install candidate APK with approval, and test Fold7/Beast opt-in -> recording -> download/playback -> deletion. Check concurrent users, network failure and server restart with real Postgres/S3 before public rollout.
