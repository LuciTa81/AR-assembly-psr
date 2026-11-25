# Connection Reliability - 2026-11-24

## Verified

| Check | Evidence | Result |
| --- | --- | --- |
| Owner-only web login and relay access | Production browser + unauthenticated curl | Passed |
| Phone cellular state reception | User confirmed cellular; browser receive time advanced | Passed, idle camera-off state |
| Phone internet toggle off/on | User action; browser receive time resumed without new code | Passed |
| Silent publisher / responsive observer | Real local WebSockets, disabled automatic pong | Passed after heartbeat fix |
| Server restart | Same test DB and credential, new relay process instance | Registration/history preserved; no old live snapshot replay |
| Five reconnect cycles | Android JVM MockWebServer, close 1001 | Credentials and stream preserved, sequence increases, offline samples discarded |
| New phone transport instance | Android JVM, same credential store | No new enrollment; new stream starts at sequence 1 |
| Stop during backoff | Android JVM | No background reconnect; saved approval retained |
| Revocation, expiry, temporary auth failure | Existing Node/Android regression tests | Passed |
| Production update | Separate release, DB backup, service status/journal | Active; normal shutdown/start; no restart loop |
| Web recovery after production restart | Existing browser tab, no manual reload | Reconnected; waiting for phone |
| Production TLS/WSS keepalive | Synthetic idle device, 45 seconds | Two ping cycles, ordered updates, one step event |

Tests: Node 72/72; Android policy/transport 25/25; TypeScript passed.
No Android production or AR calibration changes; no APK installation required.

## Connection Rules

- Phone performs network/credential I/O on its own worker. The supervisor UI only
  reads snapshots; it does not advance assembly stages or control the camera.
- Phone keeps at most the latest outgoing snapshot. Disconnected samples are not
  replayed as new events after reconnect.
- Transient failures back off up to 30 seconds. Authorization expiry/revocation
  stops transmission and asks for new approval; invalid TLS is never bypassed.
- Phone WebSocket ping interval: 20 seconds. Server now independently probes every
  20 seconds and terminates unanswered connections on the following interval.
- Server state becomes stale after three seconds without new publisher data;
  browser stops treating a live packet as current after 3.5 seconds without receipt.
- Protocol keepalive does not reset application freshness or add history events.
- Browser reconnects with a new short-lived observer ticket. Browser login may
  need renewal after its one-hour session expires; this does not revoke the phone.
- Phone enrollment lasts 30 days; pairing request codes last at most 12 hours.

## Not Yet Verified on the Real Phone

1. Recovery from this production restart: the phone had stopped sending before it.
2. Full assembly while toggling internet or during server restart.
3. Screen lock/background behavior, process recreation and OS battery restrictions.
4. Prolonged outage and multi-hour thermal/network operation.

Do not treat a user's decision to defer assembly testing as a recorded pass.
No video/audio is sent. Recording and streaming are separate future features.

## Rollback

Release `20261124-01` and the pre-update PostgreSQL dump remain on EC2.
To roll back code, repoint `/opt/ar-assembly/current` to that release and gracefully
restart only `ar-supervisor`; do not reset DB, revoke Fold7 or change NOVA.
No schema migration was introduced by this update.
