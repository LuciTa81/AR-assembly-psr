# Next.js Supervisor and GitHub Login Implementation Plan

Execution: native, user authorized continuous local implementation. No external deployment or APK changes. Follow existing Internet supervisor spec.

## Scope
- Separate web/ Next.js App Router, NextAuth 4 stable GitHub provider, one immutable GitHub numeric ID allowlist.
- Keep black UI/colors/font/layout; React state replaces DOM polling script. No marketing page.
- Login protects page and every BFF API. Secrets stay server-side. GitHub access token is not sent to browser or relay.
- HTTP-only session JWT, one-hour max age, opaque viewer session ID; logout revokes active observer sockets and outstanding tickets via relay without stopping phone publisher.
- Relay API adds safe device list and viewer revoke. Web acquires 30s one-use ticket, subscribes directly, clears current cues on stale/disconnect, retries with bounded jitter. Browser fallback watchdog handles silent network loss.
- History is loaded from relay DB, default stage events, all option includes phase/gap/stop. No invented completion or video preview.
- Device pairing and Android sender remain next milestone. Existing provisioned devices can be observed; UI shows truthful empty state if none.

## Tasks / Checks
- [x] Owner policy, session-scoped tickets and logout revocation: tests fail first, SQL + real sockets, no cross-owner leaks.
- [x] Web auth + BFF endpoints: NextAuth GitHub stable provider; reject unapproved profile ID, CSRF Origin check on BFF POST, timeout/no-store, typed validation.
- [x] React dashboard preserving existing CSS/assets: live/history/device views, responsive buttons and accessible controls, stale/empty/error states. Visual verification below remains separate.
- [ ] Browser integration: real Next server + real relay + PostgreSQL engine + synthetic publisher; session cookies signed using test-only runtime secret, no application auth bypass.
- [ ] Typecheck/build, auth policy tests, unauth and other owner API denial, phase/history/offline/recovery/logout, screenshots desktop/mobile, independent review.
- [x] Leave local UI server for user review; actual user-authorized GitHub OAuth callback and dashboard entry verified separately from synthetic sessions.

## Review Focus
1. Logout must revoke in-flight auth and pending tickets without revoking the phone.
2. Service credentials must never appear in HTML/client JS/logs or go to user-provided hosts.
3. Expired/wrong-owner cookies cannot access relay via BFF.
4. A lost WebSocket without close event must not leave green/live guidance visible.
5. Old socket/ticket/history responses cannot repaint a different selected device.

## Ledger
- Prior milestone: relay 37 tests/typecheck/demo passed; Android and successful baselines unchanged.
- Current GitHub connector reports immutable owner ID 101696460 (LuciTa81). No email copied into web config.
- Next 16.4.6 / next-auth 4.24.15 registry peer compatibility confirmed. User provided local OAuth configuration without disclosing secrets in chat. User authorized read:user consent. First callback failed with missing State cookie; a fresh login request succeeded without weakening verification. Real dashboard entry and empty-device state visually verified on 2026-11-23.
- 49 automated tests and production build pass. Live local BFF rejects anonymous, wrong-owner and expired cookies, cross-origin mutation and revoked-session read requests. Built-in NextAuth signout checked via its CSRF-protected route.
- Independent review found swallowed signout failure and pending-publisher logout race. Both reproduced RED then fixed GREEN. Default signout route now gates cookie clearing on successful revoke; viewer revocation generation does not invalidate pending publishers.
- Local Next.js :3000 and relay :8787 running on loopback. Local relay uses persistent PGlite with no synthetic device. No Android/EC2/Vercel changes.
