# EC2 / Vercel deployment checkpoint

## Current Storage Limits (2026-11-25)

- Current relay: `/opt/ar-assembly/releases/20261125-07-storage-10gb`.
- Owner total: 10,000,000,000 bytes (10GB); one recording: 300,000,000 bytes (300MB).
- Duration remains 600 seconds; retention remains seven days; concurrency remains one.
- `MULTI_USER=false`: applies to the existing owner, not a newly opened public service.
- 125 Node tests and TypeScript passed. Production process environment, authenticated
  recording-list API, public HTTPS health and unchanged recording/account rows verified.
- Backup: `/var/backups/ar-assembly/pre-storage-10gb-20261125T143016Z`.
- Details: `../docs/STORAGE_LIMITS_20261125.md`. Older limits below are historical.

Production relay and Vercel web are deployed. Owner login, authenticated
web-to-relay access, Fold7 cellular idle-state reception and toggle reconnection
are verified. Active assembly and long-duration phone testing remain pending.
NOVA remains unchanged/inactive. Earlier checkpoints below are historical.

## Reliability Update 2026-11-24

- Current relay release: `/opt/ar-assembly/releases/20261124-02`.
  Previous `/opt/ar-assembly/releases/20261124-01` preserved unchanged.
- Added protocol-level ping every 20 seconds; an unanswered probe is terminated
  at the next interval (about 40 seconds maximum from the last successful cycle,
  excluding event-loop delays). No application state, credentials or media in pings.
  Existing three-second stale-state handling is unchanged.
- Reproduced missing heartbeat with a real WebSocket client with autoPong=false;
  after the fix, silent publisher eviction, healthy observer survival, saved
  credential reuse and recovery gap history passed.
- Node tests: 72/72; TypeScript passed. Android JVM tests: 25/25, including five
  server disconnect/reconnect cycles, offline snapshot discard, saved credential
  restoration in a new transport and cancellation during retry. No APK changed.
- Production DB backup before update:
  `/var/backups/ar-assembly/pre-reliability-20261124T080326Z.dump` (root-only).
  Deployment script's final NOVA status exit-code assertion returned nonzero after
  successful switch/health verification. Corrected that diagnostic locally;
  independently verified active AR service, Result=success, NRestarts=0 and journal.
- Production TLS/WSS smoke with a separate synthetic idle device passed for 45
  seconds: two heartbeat cycles, ordered updates, no duplicate step events,
  revocation and unauthenticated rejection. Only its own temporary rows removed.
- Browser reconnected automatically after server replacement. Real Fold7 was not
  sending (last observed phone update 16:55:22 KST before restart); do not claim
  live phone recovery across this restart. Earlier cellular and toggle tests passed.
- AR v1, marker geometry, A-D calibration, Android production code and Vercel web
  code were not changed. Camera/video/audio were not started by this task.
- Remaining: actual phone recovery across restart; app background/screen-off,
  prolonged network outage and long-duration operation; active assembly isolation
  test; separate session-secret rotation. See `../CONNECTION_RELIABILITY.md`.

## Current Status 2026-11-24

- Production: `https://ar-assembly-supervisor.vercel.app`.
- Ready deployment: `a1NaadfFP2Wyi37n5yRZeczqFXff`, build duration 26 seconds.
- All seven environment variables verified as Production only. `NEXTAUTH_SECRET`,
  `RELAY_SERVICE_KEY` and `GITHUB_SECRET` are Secret; remaining four are Config.
  User explicitly approved retaining existing values after the conversion warning.
  Values were not rotated. A tooling redaction failure exposed NEXTAUTH_SECRET
  in a local tool response during verification; do not copy that response to docs
  or source. Future rotation remains a separate credential-handling task.
- Existing GitHub OAuth app retains localhost callback and adds
  `https://ar-assembly-supervisor.vercel.app/api/auth/callback/github`.
  Actual owner login reached the production dashboard successfully.
- Authenticated browser GET `/api/observer/devices` returned `{"devices":[]}`;
  this verifies the Vercel server-to-EC2 relay connection with production settings.
- Unauthenticated curl to the same endpoint returned HTTP 401, TLS verification 0.
  EC2 HTTPS `/health` returned 200 with certificate verification enabled.
- No real phone pairing, camera, recording or media transmission in this check.
  Local Fold7 approval does not carry over to the production database.
- Next: phone relay URL `https://54.116.139.37`, explicit production pairing,
  then phone cellular / PC Wi-Fi status and reconnection tests. Video is not yet
  implemented in this internet deployment. Preserve AR v1 and calibration files.

## Verified 2026-11-24

- User confirms Elastic IP `54.116.139.37`. SSH known-host match successful.
- NOVA inactive; no Docker containers; only SSH and local DNS listeners.
- Ubuntu 24.04.4; Node 22.23.2, below project's minimum 24.22.
- About 6.9 GB available RAM, 9.4 GB free disk (81% used).
  `/opt/nova` is 17 GB; do not modify or delete it.
- UFW allows only SSH. AWS security group remains to be checked.
- Real Fold7 reconnected after graceful relay restart without a new code.
  This is camera-off USB reverse verification, not public internet verification.

## Infrastructure Applied 2026-11-24

- Console verified Elastic IP association to Nova `i-0e207133be009b32b` in Seoul.
  Existing `sg-0eeb91e20667d75ce` already allowed IPv4 TCP 22/80/443; no console
  rule changes were made. User explicitly approved adding IPv4 80/443 to UFW.
- Installed nginx 1.24.0 (Ubuntu security build), PostgreSQL 16.15 and official
  Certbot snap 5.10.0. PostgreSQL listens only on `127.0.0.1:5432`.
  No AR DB/role or phone credentials have been provisioned yet.
- Separate `/opt/ar-assembly/runtime` is Node 24.22.3; archive SHA256 matched
  Node's official HTTPS checksum list. Existing `/usr/bin/node` is unchanged.
- Created non-login system user `ar-supervisor`; no app service installed yet.
- User approved Let's Encrypt subscriber agreement and email-free registration.
  Staging validation and production IP certificate issuance succeeded.
  Certificate SAN is `54.116.139.37`, expiry 2026-11-30 18:47:54 UTC.
- nginx TLS template passed `nginx -t` on this server and was applied. Original
  newly installed default site symlink retained at `/etc/nginx/default-site.before-ar`;
  AR bootstrap config retained at `/etc/nginx/ar-bootstrap.before-tls`.
- Automatic renewal timer active. `certbot renew --dry-run --run-deploy-hooks`
  succeeded, including nginx validation/reload. The hook prints nginx's successful
  validation to stderr; this is not a hook failure.
- External curl with certificate verification enabled: HTTPS `/health` returned
  502 with TLS verify result 0 (expected: no relay running); `/__local/stop` 404.
  Do not describe the 502 endpoint as a working supervisor.
- Final inspection: NOVA inactive; SSH/80/443 public, PostgreSQL loopback only,
  no 8787 listener; disk about 8.8 GB free. No recordings or app data uploaded.
- Vercel CLI 66.6.0 `whoami`: logged out. `login` fails before displaying an
  approval URL with a ByteString error (character 52572). Official CLI OAuth
  source places `os.hostname()` in the User-Agent header. The local hostname
  contains non-ASCII characters; header construction reproduces the error.
  No OS rename, TLS bypass, custom token flow or modification of the CLI was made.
  Next step: signed-in Vercel browser dashboard, isolated AR project, then decide
  an official CLI/runtime path or Git deployment without this hostname issue.
  Source: https://github.com/vercel/vercel/blob/main/packages/cli/src/util/oauth.ts

## Deployment Order

### Vercel environment handoff follow-up (2026-11-24)

- User saved all seven expected variable names. Browser shows they were imported
  as **Config**, applied to **Production and Preview**, not requested Secret /
  Production-only. This historical scope issue is resolved in Current Status.
- Editing requires Vercel email re-verification. Initial verification dialog
  was cancelled without revealing values. Redeploy was rejected by safety review
  because the broader Preview scope was not authorized; do not bypass that block.
- Returned to NEXTAUTH_SECRET Edit and requested the verification email. Chrome
  now waits for the user to enter the six-digit code directly and verify.
- Next: narrow all seven variables to Production, mark NEXTAUTH_SECRET,
  RELAY_SERVICE_KEY and GITHUB_SECRET as Secret without changing values, verify
  scopes, then redeploy and test owner OAuth login + relay access.
- EC2 HTTPS health rechecked: 200, TLS verify result 0. No phone/camera used.

### Production connection checkpoint (2026-11-24, after browser deploy)

- User deployed `ar-assembly-supervisor` in Vercel scope `luci-ta81-s-projects`.
  Canonical URL: `https://ar-assembly-supervisor.vercel.app`.
- With explicit approval, added the exact production OAuth callback to existing
  GitHub app `AR Assembly Local` (4045741). Localhost callback remains unchanged;
  wildcard matching and Device Flow remain off. No client secret rotated.
- AR relay release: `/opt/ar-assembly/releases/20261124-01`; `current` symlink.
  Frozen pnpm lockfile production install, with lifecycle scripts disabled.
  Separate `ar_supervisor` PostgreSQL database/role; no superuser/create roles.
  Root-only `/etc/ar-assembly/relay.env` and `vercel-runtime.env` contain fresh
  production secrets; never copy these into source archives or output logs.
- `ar-supervisor.service` validated, enabled and running under `ar-supervisor`.
  Public HTTPS `/health` 200 with TLS verification enabled; `/devices` 401
  without credentials. Vercel `/api/observer/devices` also rejects with 401.
- `deploy/smoke-production.ts` passed real HTTPS/WSS publisher + observer,
  PostgreSQL event history, revocation and blocked `/__local/stop`. It used only
  synthetic idle state and removed its own temporary test rows afterward.
  No real phone, camera, video or microphone was started or transmitted.
- Root-only initial backup under `/var/backups/ar-assembly` restored successfully
  into separate `ar_restorecheck_20261124` database (five tables). Both preserved.
  AR service graceful restart passed: Result=success, NRestarts=0, active.
  PostgreSQL 5432 and relay 8787 listen only on 127.0.0.1; NOVA stays inactive.
- Fresh local checks: 70/70 Node tests, TypeScript passed.
- Prepared seven Vercel Production variables in access-restricted local
  `.local/production-handoff/vercel-production.env`; user is entering/saving
  them through the browser. No values printed or placed in upload ZIP.
  Await actual save, redeploy, owner login and web-to-relay validation.
  Cross-network Fold7 pairing and reconnection are still pending; phone can
  remain disconnected until that test. Local phone approval is not production
  approval and is not copied into the production database.

### Vercel browser checkpoint (2026-11-24)

- Confirmed signed-in Chrome account `LuciTa81`, scope `luci-ta81-s-projects`,
  Hobby plan. Existing `youtube-daily-mind-map` project was not modified.
- Opened New Project. No AR project or deployment has been created yet.
- `scripts/prepare-vercel-upload.ts <new-directory>` makes a web-only upload
  copy and an adjacent SHA-256 manifest. Only that copy rewrites two imports
  to its bundled `shared/protocol.ts`; original application files are unchanged.
- Prepared `../vercel-upload/ar-assembly-supervisor` and adjacent ZIP: 29 files,
  1,779,577 uncompressed bytes. No environment files, local DB, SSH keys or logs.
  Checked against local secret values and private-key markers: zero matches.
- Separate `../vercel-build-check-20261124` installed the frozen lockfile and
  passed Next.js production build including TypeScript, without credentials.
  Do not upload this build-check directory (it contains dependencies/artifacts).
- Browser file chooser accepted calls for both directory and ZIP, but the page
  stayed unchanged. Requested extension file-URL access or manual file selection.
  No production credentials entered, no Git repository created or pushed.
- Read-only EC2 recheck: NOVA inactive, only postgres default database exists;
  AR runtime is present but AR relay/database deployment remains pending.

1. Confirm AWS security group and UFW allow TCP 80/443 when ready. Never expose
   8787 or PostgreSQL. Preserve SSH access and NOVA configuration.
2. Use separate `/opt/ar-assembly`, OS user `ar-supervisor`, AR-only DB and role.
   Install a separate official Node >=24.22 runtime with checksum verification;
   keep existing Node unchanged. Install nginx, PostgreSQL and Certbot >=5.4.
3. Test TCP PostgreSQL, graceful restart, persistence and backup/restore before
   public exposure. Do not copy the local PGlite DB or phone credentials.
4. Select final Vercel URL and exact `WEB_ORIGIN`. Create new production secrets
   in root-protected `/etc/ar-assembly/relay.env`, never in a public variable.
   Set `HOST=127.0.0.1`, `PORT=8787`, `TRUSTED_PROXY=127.0.0.1`.
5. Bootstrap HTTP with only `/.well-known/acme-challenge/` under
   `/var/lib/ar-acme`; return 404 elsewhere. Obtain staging then production IP
   certificates. Never bypass TLS validation or send credentials to staging TLS.
6. Validate nginx template using `nginx -t`, then install. It requires a single
   directly exposed nginx overwriting `X-Real-IP`. Additional proxy/CDN layers
   require a new trust-boundary review. Production runs `server/main.ts`, not
   `scripts/local-relay.ts`; `/__local/` is also blocked at nginx.
7. Configure and test certificate auto-renewal with a deploy hook running
   `nginx -t && systemctl reload nginx`. IP certificates last six days.
8. Validate/install the systemd template with actual user/runtime/env paths.
   Test valid public TLS, unauthenticated API rejection, spoofed IP headers,
   WebSocket operation and graceful restart before phone approval.
9. Deploy only `web` to a separate Vercel project. Server-only environment:
   `NEXTAUTH_URL`, `NEXTAUTH_SECRET`, `GITHUB_ID`, `GITHUB_SECRET`,
   `OWNER_GITHUB_ID=101696460`, `RELAY_HTTP_URL=https://54.116.139.37`,
   `RELAY_SERVICE_KEY`. Add production GitHub callback:
   `https://<final-project>.vercel.app/api/auth/callback/github`.
10. Approve Fold7 for the production destination. Test phone cellular + PC Wi-Fi,
    disconnect/reconnect, server restart, logout and revocation. Camera remains
    off until user readiness. Video/storage is a separate later feature.

Never upload `.local`, `.env*`, SSH keys, local DB or existing device credentials.
No installation script may silently accept certificate subscriber terms.

## Certificate Reference

Official Certbot example: `certonly --staging --preferred-profile shortlived
--webroot --webroot-path /var/lib/ar-acme --ip-address 54.116.139.37`.
Production requires omitting staging after successful validation; account/contact
and subscriber agreement must be handled intentionally.

- https://letsencrypt.org/2026/03/11/shorter-certs-certbot
- https://nginx.org/en/docs/http/websocket.html

## Rollback

Gracefully stop only `ar-supervisor`, disable only AR nginx configuration, validate
and reload. Preserve DB and backups. Do not delete volumes, reset DB, modify NOVA
or change SSH rules as rollback.
