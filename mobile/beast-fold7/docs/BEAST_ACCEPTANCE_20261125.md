# Beast verification 2026-11-25

## Observed

- Installed APK: 1.4.1 / versionCode 11. Beast output 3840x1080.
- AR session 1 reached BOX -> LID -> A -> B -> C -> D -> INSPECT, then stopped automatically.
- Rendered-green transition delays: A 3012ms, B 3032ms, C 3048ms, D 3032ms.
- User initially reported lower C/D alignment, then corrected that alignment was broadly acceptable.
- Pulled APK camera/workspace/eye/outline profiles and three colored marker textures match frozen v1 by SHA256. No calibration changed.
- Browser production login succeeded. Real workbench video was visible, state updated through at least 35 seconds, and marker count changed from 1 to 5. This is a live-video smoke check, not a measured 30fps or prolonged AR/video performance result.
- User stopped the phone session. Browser removed the live image and returned to waiting; browser video toggle was also turned off.
- No audio or video recording was enabled during that test.

## Storage preflight

- EC2 service active, production release `/opt/ar-assembly/releases/20261124-03`.
- No recording configuration entries were returned from the production environment whitelist check.
- Authorized EC2-role list under the private bucket's `recordings/` returned zero objects and no remaining page.
- EC2 role cannot read bucket lifecycle configuration. This is not evidence of missing Put/Get/Delete permissions and does not justify broadening the shared NOVA role.
- Existing S3 browser object listing returned an error; use verified EC2 results rather than interpreting that page as an empty bucket.

## Authorized next scope

User approved: one tiny synthetic S3 upload/download/delete, AR server/DB backup and recording candidate rollout, own account only, one concurrent recording, maximum 30 seconds and 15MB, no audio. Real camera recording still requires explicit phone consent. No public recording rollout or NOVA changes.

## Restricted recording rollout

- Synthetic S3 test passed: 68-byte verification file uploaded with AES256 encryption, downloaded with identical bytes, deleted, then absence verified. No verification objects remain.
- Server tests: 108 passed; TypeScript passed. Next.js production build passed.
- Deployment first stopped before service/config changes because its PATH omitted `/usr/sbin` and could not find `runuser`. Corrected only the script PATH; backup and rollout then succeeded.
- Database/config/service backup: `/var/backups/ar-assembly/pre-recordings-20261125T055020Z/`. PostgreSQL custom-format dump is 20KB. This is a created backup, not a restore rehearsal.
- Active server release: `/opt/ar-assembly/releases/20261125-01-recording-check`; previous: `/opt/ar-assembly/releases/20261124-03`.
- Production smoke checks passed: TLS, authorization, WSS state, PostgreSQL history, revocation, blocked remote stop; 30 ordered synthetic video packets, consent stop, state isolation. No camera used by these checks.
- Restricted configuration verified: `MULTI_USER=false`, recording enabled, 30 seconds, 15000000 bytes per file and owner, one concurrent recorder. Separate phone consent remains required.
- SDK S3 listing also succeeded as the actual `ar-supervisor` OS account; zero objects before real recording. The AWS snap CLI cannot run with that account's `/opt` home, so SDK verification was used without changing account permissions.
- Web production deployment: `dpl_3X7zHww6Auk4bjvw3VYDHPpYUZ5K`; rollback deployment: `dpl_Fm1dMTVkZH4wtdSju55aqr8KrJZt`. Existing Production credentials unchanged; `PUBLIC_GITHUB_LOGIN` remains unset (owner-only default).
- Browser authenticated production page loaded the new Work history / Work videos section and received the empty recording list successfully.
- Candidate APK SHA256 `3EC8F7F7F1E6A946A3F204282ECC32B3C765D04197E139183F43FED2E035EEC0` installed with `adb install -r`; app opened without camera activation. Existing app data retained.
- Candidate camera, workspace, eye projection and box outline assets match frozen v1 by hash. Version remains 1.4.1 / code 11; identify this candidate by hash and installation time, not version alone.
- NOVA remained inactive and was not modified.

## Actual recording result

- User confirmed phone opt-in and work start. Recording `3cd7c716-a111-43d7-a0d8-0c1df800af28` reached `ready` with reason `duration_limit`.
- S3 HeadObject confirmed `video/mp4`, AES256 encryption and 7581678 bytes. Temporary recording spool was empty after upload.
- Authenticated owner browser displayed the recording and downloaded it through the production download button to `C:/Users/fresh/Downloads/AR-Assembly-3cd7c716-a111-43d7-a0d8-0c1df800af28.mp4`.
- Download SHA256: `484E91EEA113F138C482276D8A6A425F4E8B9C2BB7DAE2492F84EBED92162EC5`.
- FFprobe: H.264, 1280x720, 29.986337 seconds, 259 decoded frames, no audio stream. Average recorded frame rate is approximately 8.64fps, NOT 30fps. Maximum packet timestamp gap was 195ms; all DTS values strictly increased.
- Full FFmpeg decode passed with timestamp-preserving output (`-fps_mode passthrough -enc_time_base 1:1000000`). Default null output initially warned about duplicate DTS after coarse output time-base quantization; direct input packet checks and timestamp-preserving decode did not reproduce an input timestamp error.
- Three sampled video frames showed actual workbench motion. This proves saved-video content, not eye-display alignment or precision.
- Completion-to-expiry interval is exactly 604800000ms (7 days). Web shows December 2, 2026, 14:59 KST. Actual seven-day deletion has not yet elapsed or been observed.
- User was asked to stop work and internet sharing after the 30-second clip. Camera stop has not yet been independently confirmed at this checkpoint.
- At 15:03 KST, new recording was disabled (`RECORDING_ENABLED=false`); owner-only login retained, file preserved, S3 configuration and expiry cleanup retained. Service restarted and authenticated health probe passed. The finish script's initial untrusted local health probe was rejected; corrected to the existing trusted proxy header and verified healthy separately. No real recording was deleted.

Pending: recorded-frame-rate investigation, redundant S3 lifecycle safeguard, deletion of the actual test recording only with separate authorization, real multi-user/security/network-failure checks before any public recording rollout. Synthetic upload/download/delete passed previously; it is not a substitute for an end-to-end owner deletion test. Public/multi-account recording remains disabled.

## Five-minute limit requested after the test

- User requested a five-minute ceiling, accepting earlier finalization. Changed only `RECORDING_MAX_SECONDS=30` to `300` in production; prior configuration backed up to `before-five-minute-limit.env` in the same private backup directory.
- Validated enabled-capture configuration in memory without enabling recording. Service restart and health check passed. `RECORDING_ENABLED=false`, file and owner quotas of 15000000 bytes, concurrency and all other settings remain unchanged.
- This is a maximum duration, not a guaranteed five-minute clip. At the measured test bitrate, the 15MB file limit would be reached in approximately one minute.
- The retained 7581678-byte clip plus the next 15000000-byte reservation exceeds the unchanged owner quota. Before another capture, separately authorize deletion of that clip or a quota increase; do not silently remove data or raise cost limits.

## 100MB limit requested afterward

- User requested 100MB. Updated production file and owner quotas to exactly 100000000 bytes, retaining the 300-second ceiling and recording-off state. A proposed 200MB owner allowance was explicitly withdrawn before any change; it was not applied.
- Config equality assertions verified that only the two byte limits changed. Enabled-capture validation was performed in memory, service restarted, and health returned OK. Prior settings backed up as `before-100mb-limit.env`; no actual 5-minute/100MB capture was performed.
- Existing recording remains intact. Current reservation logic reserves the entire per-file maximum, so the retained file still prevents another full 100MB reservation within the 100MB owner quota. Before the next test, obtain deletion approval or separately agree a higher aggregate quota; do not silently delete the test recording.

## Five-minute attempt and remaining-quota correction

- User deleted the authorized old 30-second recording through the web. Database status was `deleted`, account usage was zero, and S3 HeadObject returned 404. The downloaded local MP4 was retained. This verifies owner web deletion through physical S3 removal.
- Recording was temporarily enabled for the approved five-minute check. First AR run initially had internet supervision off. The user later enabled it and stopped that run; a real 2269ms / 329241-byte clip was saved as `5b45d1f9-bcc1-45ea-9320-14ebaf631e9c`.
- The subsequent run sent state, video availability and recording consent, but could not reserve another full 100000000 bytes. The actual root cause was full-file quota reservation while aggregate quota equalled the per-file cap, not late connection itself. User stopped the run. The five-minute recording test did not pass and remains pending.
- Fixed quota reservation under an owner-row lock: the recorder can reserve the smaller of the per-file maximum and the remaining owner balance. Minimum reservation is 2MiB (or the lower configured file maximum), including 1MiB mux overhead allowance. Actual queued frame writes and final MP4 size are checked against the reserved amount, not the original file cap.
- Added separate `quota_full` state; the web shows recording consent separately from actual recording, warns explicitly when space is insufficient or storage fails, and no longer labels every preview as "not saved". AR/state/video channels remain independent. Connecting midway is still allowed; recording cannot include frames from before sharing/consent.
- Regression checks: 113 server tests passed, server TypeScript passed, Next.js production build passed. Tests include partial reservation with the exact 329241-byte existing clip, concurrent quota attempts, late consent, queued-frame size limits, quota failure distinct from connection failure, and existing permission/retention/recovery tests.
- Desktop (1440x1000) and mobile (390x844) Playwright checks passed for quota warning, consent versus capture, continued live state, transition to recording, download and delete confirmation, no overflow and no JS errors. Test media/data were synthetic. Screenshots: `internet-supervisor/.local/recording-ui/`.
- Production web: `dpl_FdsA4K9URGjYwMyRR2k3rYaqw1BW`, alias `https://ar-assembly-supervisor.vercel.app`. Previous web deployment retained: `dpl_3X7zHww6Auk4bjvw3VYDHPpYUZ5K`.
- Production server: `/opt/ar-assembly/releases/20261125-02-quota-fix`; previous release retained. DB/env backup: `/var/backups/ar-assembly/pre-quota-fix-20261125T065657Z/`.
- Real PostgreSQL smoke used transaction-local temporary tables, verified 99670759-byte remaining reservation and unused quota release, then rolled back without touching real recordings or S3. Production TLS/auth/state/video-channel smoke checks also passed. NOVA unchanged.
- Final configuration: `RECORDING_ENABLED=false`, `MULTI_USER=false`, maximum 300 seconds, file and owner limits both 100000000 bytes, one concurrent recorder. S3 configuration and expiry cleanup retained. The 2-second real clip and its 329241-byte account usage remain intact; no new actual capture was started.
- No Android APK, AR guidance, eye calibration or marker geometry changed. Next gate: explicitly re-enable owner recording, reconnect phone supervision with consent, start a fresh work session, and verify `capturing` immediately before continuing the bounded five-minute test. Actual long-run frame rate, battery/network recovery and elapsed seven-day deletion are still not verified.

## Retest after quota fix

- New real recording `5ce1e2a4-262a-4749-b136-253b6e6008cf` successfully reserved 99670759 bytes while retaining the prior 329241-byte clip. This verifies the quota fix on the real phone/server path.
- Capture finalized early with reason `stale`: 78586ms, 19774786 bytes, DB status `ready`. The web showed a 1:18 partial recording. This is NOT a successful five-minute recording.
- The relay stops recording when state age exceeds 3000ms or media age exceeds `VIDEO_STALE_MS`; the shared `stale` reason does not identify which occurred. The exact transport/root cause remains unverified. State subsequently continued through C, D and inspection.
- Corrected prior operator instructions: `MainActivity.assemblyTick` intentionally stops a full session 10000ms after `assembly.finished()`, in addition to the 300000ms overall ceiling. D -> INSPECT was logged around 128s (green delay 3030ms), and the final state was `running=false`, message `안내가 끝났어요 | frames=2271`, around 138s. Do not instruct the user to expect five minutes at inspection with this build.
- At approximately 66s, battery was 20%, temperature 36.1C; camera callbacks were approximately 16-17fps. This is not encoded/recorded frame-rate evidence.
- Owner web download was attempted, but Chrome navigated to an `ERR_BLOCKED_BY_CLIENT` page for the signed S3 URL. No completed local file was observed. Do not mark download/playback verified for this clip; do not bypass browser security controls.
- Recording was disabled afterward by restoring the pre-retest environment backup only after asserting all non-recording-enable lines were identical. Service health passed. No recordings were deleted and no AR code or calibration changed.

## Stale investigation

- Around 16:00:45-16:00:54 KST, phone camera callbacks continued each second (approximately 15.7-16.9fps), and B -> C occurred locally at 16:00:53.038. Available logs contain no encoder exception or app crash in that interval.
- Server state event seq 373 arrived at 16:00:52.359 with about 3765ms additional receive delay relative to the median pre-gap phone-monotonic/server-time offset. Seq 380 still had about 2086ms excess delay; seq 389 had returned to baseline. This is relative delay evidence, not synchronized absolute one-way latency.
- A `gap` state event confirms the state path experienced a receive gap. The persisted shared `stale` recording reason still cannot establish whether state or video timeout fired first. No server service restart occurred at the recording cutoff. Available evidence does not distinguish Wi-Fi/carrier latency, phone transport scheduling or a server event-loop stall.
- Direct cause of lost remainder: the relay finalizes a recording on a three-second state or media stale interval, while Recorder.attempted prevents restarting the same device/work session after recovery. Thus restored live state/video does not imply restored recording. This is independent of the fixed quota issue and the later normal D/inspection auto-stop.
- Added `tests/recording-stale.test.ts`, reproducing a 3101ms receive pause, partial MP4 finalization, recovery on the same open sockets, and no resumed same-session recording. Characterization test and TypeScript passed. No production behavior or APK changed during this diagnosis; actual camera was not restarted.
- Recommended follow-up, not implemented: explicit interrupted-recording status and bounded recovery into a new segment after fresh consented state and a decodable keyframe; preserve per-work duration/aggregate byte limits across segments and expose gaps rather than hiding them. Avoid simply raising the stale threshold for live guidance.

## Bounded segment recovery deployed

- Implemented the follow-up after user approval. A recoverable receive/transport gap preserves the finished clip, then waits for fresh running state, video sharing, recording consent and an H.264 keyframe before starting a separate segment. The live-guidance stale threshold was not increased. State and video timeout reasons are now distinct (`state_stale`, `video_stale`).
- Segment rows retain their work session, ordinal, approximate preceding wall-time gap and a durable resume block. A work's deadline is its first recording start plus 300 seconds, not 300 seconds per segment. The sum of all prior segment bytes, including deleted segments, is deducted from its 100000000-byte budget. Owner quota remains 100000000 bytes; no user file is automatically deleted to make room. Minimum reservation/mux overhead checks remain in force.
- Normal stop, session change, withdrawn consent, duration/size limits, storage failure and server shutdown do not automatically resume that work. A consent withdrawal while a segment upload is pending also blocks recovery, even if consent is later restored in that same work. Starting a new work session is separate from reconnecting the old one.
- Web now accepts and shows `interrupted` / `recovering`, and saved videos display their segment number and approximate preceding gap. Clips are not falsely presented as one continuous video. No Android APK, AR logic, calibration, marker layout, OAuth setting or public-user permission was changed.
- Verification: all 119 server tests passed; server TypeScript and Next.js production build passed. New tests cover fresh-state/keyframe gating after a 3101ms state pause, real state-socket disconnect/reconnect, consent withdrawal during upload, preserved deadline, and cumulative byte limits after deletion. Real PostgreSQL verification used temporary tables and rollback; no S3 calls or real camera capture.
- Desktop/mobile Playwright checks passed: segment/gap labels, interrupted/recovering/capturing transitions, continued live connection, quota warnings, download/delete controls with synthetic data, no page overflow or JS errors. Mobile screenshots were visually inspected under `internet-supervisor/.local/recording-ui/`.
- Web production: `dpl_8j4mJ5tARWPink1TC199FSrS8QaS`, alias `https://ar-assembly-supervisor.vercel.app`. Previous deployment `dpl_FdsA4K9URGjYwMyRR2k3rYaqw1BW` retained. Production login HTTP 200 verified.
- Server production: `/opt/ar-assembly/releases/20261125-03-segment-recovery`. Backup: `/var/backups/ar-assembly/pre-segment-recovery-20261125T072414Z/` (DB custom dump, environment, previous release and recording inventory). TLS/auth/WSS/history/revocation/video smoke checks passed. Existing recording inventory and environment were byte-compared before/after and unchanged; NOVA remained inactive.
- The PowerShell stdin wrapper appended a trailing CR after all deployment checks and the success message, producing exit 1 outside the script body. Independent follow-up verified the active release, running service, exact SHA256 matches for all four changed server files, unchanged safety limits and production web health. No rollback was triggered by that trailing wrapper character.
- Final state: `RECORDING_ENABLED=false`, `MULTI_USER=false`, 300-second work ceiling, 100000000-byte work/file and owner limits. Existing real clips remain preserved. No live recording was started by this change.
- Rollback caution: the unique index is now `(device_id, session, segment)`. Once real multiple segments exist, do not blindly run the previous release's schema, which would recreate a one-row-per-session index. Use a reviewed schema-compatible rollback; do not delete recordings to make an old migration succeed. This deployment's automatic rollback was safe only while recording remained disabled and existing sessions had one segment each.
- Still pending: real Fold7/Beast interrupted-recording recovery, real long-run performance/5-minute ceiling, and playback/download verification of the retained 1:18 clip (earlier browser download was blocked). This change does not claim to solve network latency, improve frame rate or remove the intentional 10-second post-inspection AR stop.
