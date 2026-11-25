# Device Pairing and Android Sender Implementation Plan

**Goal:** Owner-approved phone enrollment and optional, foreground-only status publication without changing AR behavior.
**Spec:** `../specs/2026-11-23-internet-supervisor-design.md`. User authorized continuous execution. No deploy, push, phone install or camera activation in this task.
**Architecture:** Existing Next.js owner session approves a short-lived phone code. Relay persists approval and hashed credentials. Android uses OkHttp, Keystore AES-GCM storage and a bounded latest-state sender. Production requires HTTPS/WSS; debug loopback may use HTTP through a later explicit adb reverse test.

## Contract
- Phone `POST /pairing/request`, JSON `{name}` (1..64 trimmed chars); returns `{code,poll_token,expires_ms,interval_ms:2000}`. Code is 8 unambiguous uppercase base32 characters, expires in 5 minutes. No camera/state is sent for enrollment.
- Phone `POST /pairing/poll`, `Authorization: Bearer <poll_token>`, no body; returns `{status:"pending",expires_ms}` or `{status:"approved",device_id,device_token,expires_ms}`. Approved `expires_ms` is device credential expiry (30 days). Expired/revoked pairing => HTTP 410. Credentials never appear in URLs/logs.
- Next server only `POST /pairing/lookup` JSON `{code}` -> `{request_id,name,expires_ms}`; then `POST /pairing/approve` JSON `{code,request_id}` -> `{device_id,name}`. Require service key + unrevoked `X-Viewer-Session`. UI confirms displayed name before approval. Approval is atomic once.
- Existing WebSocket `/ws`: first message `{role:"publisher",token:<device_token>}`. Wait for `{type:"ready"}` before sending protocol-1 state wrappers. Close 4401 with reason `Reauthenticate` means reconnect; other unauthorized failures require new enrollment. Reconnect sequence does not rewind.
- Polling response is retryable with the same high-entropy secret until pairing expires, to survive a lost HTTP response. DB stores hashes only; token is HMAC-derived using server service key and poll hash. Revoked devices can never be recovered through old pairing.

## Constraints / Review Focus
- Preserve all v1 calibration, 205/205 geometry, thresholds/timings and rendering. Preserve LAN option. No auto-enable, no background service or camera change.
- Validate HTTPS endpoint, no credentials/query/hash/path, no redirect following or insecure trust managers. HTTP only debug localhost/127.0.0.1; Android backup already disabled.
- Off/on/onStop and late network callbacks must not reactivate sending. Network/Keystore I/O off main thread. Latest-only bounded send; no offline replay. Snapshot sampling <=4Hz and idle heartbeat 1Hz. Retry jitter capped 30s.
- Server body <=2KiB, pending requests <=128, request/approval/poll rate limits, origin/owner checks, expiry, repeated/concurrent approve, forged poll token and DB errors covered.
- Web empty/error/pending/expired states, keyboard labels, no fake phone completion. No claims of physical device testing based on simulator checks.

## Tasks
- [x] Preserve pre-change source/APK checkpoint and verify frozen manifests.
- [x] Server: tests RED; pairing SQL/service + bounded HTTP routes; tests GREEN including actual WS authentication with approved credential.
- [x] Android: separate `RemoteSupervisor*` Java classes and tests, Keystore storage, optional UI hook only in MainActivity; build/lint/tests, no install.
- [x] Web: owner/Origin-protected BFF lookup+approve, code/name confirmation UI in device tab; regression tests and Next build.
- [x] Integration: synthetic phone request/approval/poll/publish, BFF auth, revoked/expired behavior; screenshot check where available.
- [x] Independent security/lifecycle review, baseline hash checks, documentation of verified vs pending physical/network tests.

## Ledger
- Current accepted app and both frozen baselines remain immutable. Workspace is not a Git repository; no commit requested.
- Existing actual GitHub OAuth login to localhost:3000 verified. Phone upload, deployment and internet/device tests remain separate.
- 2026-11-23: server/web tests 64/64; root and web typechecks; Next production build; running local BFF auth and synthetic pairing/7-stage/history/revoke checks passed. Revoked synthetic entries remain intentionally labeled in local DB.
- Desktop and 390x844 browser checks passed for code/name preview and unavailable code error; viewport restored. UI preview was cancelled, not approved with the real user's session.
- Frozen manifests: 90 + 61 files, 0 mismatches. Existing app/src checkpoint: 70 files checked, only MainActivity lifecycle/UI hook changed; new remote classes are separate.
- Android JVM 22/22, candidate and instrumentation APK builds passed; lint 0 errors/20 warnings. Keystore and lifecycle instrumentation tests were compiled, not run on Fold7.
- Independent review found approval/logout race and transient authentication DB failure clearing phone credentials. Both were reproduced RED and fixed GREEN: viewer row lock within atomic approval, retryable WS1013 for server failure; Android token preservation regression added.
- Follow-up review found delayed DB auth timeout and unrelated device revocation could also clear a valid phone token. Both reproduced RED and fixed GREEN: pending-auth timeout WS1013, generation mismatch WS4401 Reauthenticate. Truly invalid/expired credentials remain Unauthorized; unauthenticated sockets still time out.
- Final independent follow-up: five focused regression/auth-boundary tests passed, no additional defect reported in this scope. Actual multi-connection PostgreSQL contention and Android network failure/recovery remain unverified.
