# Internet Supervisor Foundation Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans. User requested continuous execution; do not add redundant approval gates for local implementation. No deployment, push, APK install, or camera activation in this milestone.

**Goal:** Build and verify the Internet supervisor's isolated state relay and durable event store before changing the working Android app.

**Architecture:** TypeScript HTTP/WebSocket server with strict shared state validation, one owner, scoped device credentials and one-use observer tickets. PostgreSQL persists devices/events; latest snapshots stay in bounded memory. Browser and phone adapters follow this verified protocol.

**Tech Stack:** Node.js, TypeScript, ws, Zod, pg; node:test and PGlite (actual embedded PostgreSQL engine, test-only).

**Spec:** ../specs/2026-11-23-internet-supervisor-design.md

## Global Constraints
- Preserve all existing Android code, calibration, v1/standalone archives and NOVA. New code only under internet-supervisor.
- No public unauthenticated endpoint may return state; 16KiB messages, 10 messages/s, bounded queues.
- State is stale after 3s, never infer fastening verification or absent intermediate events.
- No secrets in source, query strings, logs. Local development binds 127.0.0.1. Real TLS and OAuth deployment remains separate.
- User has Vercel account/GitHub login; OAuth app and project authorization still need interactive setup later.
- No commits or pushes without request. New isolated directory provides change boundary; preserve baseline manifests.

## Review Focus
- Replaced publisher's delayed message must not overwrite a new publisher: relay generation test.
- Device reconnect with same stream and lower seq must not rewind state: ordering test.
- Phone monotonic time is not Unix time: stale uses server monotonic receipt, not updated_ms.
- Unauthorized/slow clients must not consume unlimited resources: auth deadlines, payload/rate/client/queue tests.
- DB failure must not block active guidance or expose stale records as complete: event failure and gap tests.

### Task 1: Contract
Files: shared/protocol.ts, tests/protocol.test.ts, tests/fixture.ts, package.json, tsconfig.json.
Interface: parseSnapshot(input: unknown): Snapshot, parsePublish(input: unknown): Publish; strict Zod schema rejects invalid stages/phases, unsafe integers, forged capability flags, unknown fields.
- [x] Write positive real-shaped snapshot and negative schema/phase/size tests.
- [x] Run tests against minimal exported stubs and observe assertions fail.
- [x] Implement validation and run tests/typecheck.

### Task 2: Durable ownership and records
Files: server/store.ts, server/schema.sql, tests/store.test.ts.
Interface: Store backed by query(text,values); device token hashes, 30s single-use tickets, revoked devices, idempotent stage events.
- [x] Test SQL on test-only PGlite, including persistence on reopen, wrong owner, expiration/reuse, token revocation and event duplication.
- [x] Implement schema and store queries; never accept owner supplied by phone state.
- [x] Run tests/typecheck; document PostgreSQL TCP connection remains separate deployment verification.

### Task 3: WebSocket relay
Files: server/relay.ts, server/http.ts, tests/relay.test.ts.
Interface: createRelay(store, config) returns HTTP server + close(); /ws first message authenticates publisher or observer. Owner HTTP API requires server-only key, never browser-delivered.
- [x] Test real loopback HTTP/WebSocket connections for unauthorized, origin, tickets, publish/observe, stale, takeover, seq, limits, revoke, DB failure.
- [x] Implement bounded latest-state relay, heartbeat/disconnect, event writes with bounded per-device queue.
- [x] Run full suite and typecheck.

### Task 4: Reproducible local operation
Files: server/main.ts, scripts/demo.ts, README.md, .env.example, .gitignore.
- [x] Test invalid/missing config fails closed; dev loopback no camera.
- [x] Add local synthetic demonstration that never reads phone/camera and exits, real DB deployment instructions, test results ledger.
- [x] Fresh independent review, fix significant findings with regression tests, full verification.

## Following Milestones (separate detailed plans)
- Next.js: existing black UI, GitHub allowlisted login, device pairing UI, tickets, stored history, browser QA.
- Android: opt-in upload transport and Keystore, no calibration/timing changes, APK tests before wearer test.
- Deploy: user-assisted Vercel/OAuth setup, NOVA audit, EC2 TLS/DB/network and phone 5G comparison.
- Video/recording: separate consent and WebRTC/TURN/storage design.

## Execution Ledger
- Design approved; implement natively in this session, final independent review. No extra methodology approval needed after user's continuous execution request.
- Starting baseline: v1 90 files and standalone 61 files hashes match. Prior observer browser suite passes.
- Task 1 RED: schema stub accepted invalid messages (13 failed assertions); GREEN: strict schema 15 tests passed.
- Task 2 RED: missing ownership/event behavior; GREEN: real embedded PostgreSQL token/ticket/revocation/idempotency tests, plus disk close/reopen persistence passed.
- Task 3 RED: unauthenticated HTTP response mismatch; later replay test reproduced retired stream overwrite. GREEN: authenticated loopback sockets, retired stream guard, stale/gap, record outage, bounded pending writes.
- Task 4: synthetic seven-stage demo passed, 7 stored events. Missing environment startup exits 1 without opening a listener. No phone installed/connected by this work.
- Verification before independent review: 34 tests passed, TypeScript check passed, dependency audit zero known vulnerabilities. Baseline 151 archived files still match; no app/src/main files modified.
- Ruling: use Node 24 built-in TypeScript execution instead of tsx/esbuild; avoids unnecessary build scripts. Requires Node 24.22+ documented in README; deployment runtime must satisfy that version.
- Ruling: foundation contains Store.provision for local tests only, no public pairing/login yet. Those follow with web/phone adapters; deploying this milestone alone is not approved production authentication.
- Ruling: split HTTP API remains in relay.ts (small shared ownership boundary); no empty http.ts abstraction.
- No git commit/push: user requested implementation, not publication; parent working directory is not a Git repository.
- Final independent review found 4 issues. Fixed pending-auth/revoke race with auth generation (both roles tested), rejected half-open upgrades with explicit socket destruction and shutdown tracking, history overflow with durable gap repair before ok, and idle stop classification before stage comparison. All reproduced RED then verified GREEN.
- Final verification: 37/37 tests, TypeScript noEmit check, seven-stage loopback demo (7 records) passed. DB disk restart persistence tested. No deferred review findings.
- Scope still pending: Next.js/OAuth, phone pairing and remote sender, PostgreSQL TCP server integration, EC2/Vercel production deployment, real phone cross-network test, video and recording.
