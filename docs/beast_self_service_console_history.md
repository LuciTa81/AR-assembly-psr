# Laptop self-service console

## Scope

Keep calibration, detection, FSM and the protected successful build unchanged.
Reuse supervisor_demo.html and the last reviewed A-to-B candidate launcher.
The candidate is not promoted to the protected baseline. Full-flow verification
of that candidate is still pending.

## Design

A loopback-only Python controller serves the existing supervisor even when the
camera is off. Fixed launch arguments, no browser-supplied commands or paths.
Proxy only state.json, frame.jpg and operator/confirm to the owned live session.
Check Host and Origin; require same-origin custom headers for mutations.

The controller owns one launch at a time. Start performs a fresh read-only
preflight, then starts the existing launcher. Stop signals the owned launcher,
waits for cleanup, and uses an owned Windows job as the final cleanup boundary.
Reloading a browser must not stop/reset a running session. Starting again after
stop creates a new session. Closing Unity also releases the camera.

The managed launcher disables only the trial deadline and automatic completed
exit; the operator explicitly stops it. The original bounded invocation remains
unchanged. Shutdown, startup failure and controller loss must clean up children.

## Implementation and verification

1. Add offline lifecycle/HTTP tests first (duplicate start, stop during startup,
   error cleanup, fresh restart, CSRF/Host checks, endpoint allowlist).
2. Add local controller and minimal managed-launcher flags.
3. Add compact controls to existing UI, retaining video opt-in and themes.
4. Add one-click local opener, no camera on opening/checking.
5. Run Python and browser tests, desktop/mobile screenshots and protected hashes.
6. Leave the camera off; live start/stop and full-flow headset acceptance remain
   an explicit next test with the wearer ready.

## Verification record (2026-11-15)

- Active project suite: `pytest tests -q`, 1056 passed.
- Console tests include real Windows job descendant cleanup, unrelated-process
  survival, stale-session rejection, confirmation forwarding and malformed upstream JSON.
- Existing supervisor browser regression: 54 checks, six viewports, no page errors.
- Console desktop/mobile lifecycle and real idle page verified separately.
- Actual read-only preflight passed: protected files, Beast device, extended
  3840x1080 display and no conflicting session. Camera capture was not opened.
- All nine protected hashes unchanged; three PowerShell files parse successfully.
- A plain repository-root `pytest -q` also collected an old copied test under
  outputs/driver_candidate_trial and failed its relative import. The active
  tests/ tree above passes; the saved artifact was not changed.

Windows PowerShell now imports its own Utility module explicitly. The trial
launcher uses UTF-8 for JSON reads and a UTF-8 BOM for Korean path literals.
This fixes startup from a desktop shortcut without depending on Codex's shell.
The same defaults and bounded lifetime apply when Managed is omitted.
