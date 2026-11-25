# Android A-to-B timed assembly probe

Date: 2026-11-21 (Asia/Seoul)

## Scope

- Opt-in `assembly_probe`, A only; B is the terminal preview.
- Existing camera, workspace and binocular calibration unchanged.
- Valid same-frame metric tool evidence requires at least five markers.
- Observed near-target hold: 800 ms; blue-to-green cue delay: 2000 ms.
- First fresh stereo green draw starts a latched 3000 ms advance timer.
- This is timed guidance, not a measurement of screw torque or fastening quality.
- No photos or video saved. Numeric logs only.

## Device evidence

Device: Samsung Z Fold7, Android 16, VITURE Beast Full SBS 3840x1080.

Log: `assembly-live-device-20261121-0222.txt`

| Session | Green draw | A-to-B transition | Delay | Automatic stop |
| --- | --- | --- | --- | --- |
| 1 | 02:20:58.621 | 02:21:01.630 | 3009 ms | 02:21:06.632 |
| 3 | 02:21:53.430 | 02:21:56.444 | 3014 ms | 02:22:01.476 |

The user confirmed that blue, green, then B appeared in order and that timing and position were acceptable. This is qualitative confirmation, not a numerical alignment measurement. Both runs reached B and stopped automatically five seconds later.

## Prior automated verification

- Debug build and Android lint passed.
- 19 Android instrumentation tests passed, including state timing and stereo draw acknowledgment.
- Tool geometry and selection matched 72 frozen Windows synthetic fixture cases.
- 17 offline Python regression tests passed.

## Remaining work

- A-through-D candidate passed one continuous physical trial (see below).
- Box/lid automatic progression remains unimplemented.
- Headlocked 3D part preview and wireless supervisor remain unimplemented.
- Four-marker robustness remains deferred; calibration and acceptance thresholds were not relaxed.
- A green `onDraw` acknowledgment is a rendering event; physical visibility was separately confirmed by the user.

## Full-sequence candidate, 2026-11-21 02:27 KST

- Separate intent flag `assembly_full=true`; original `assembly_probe=true` remains A-to-B.
- Each A/B/C/D stage requires its own 800 ms near evidence, 2000 ms cue delay, fresh stereo green draw, and 3000 ms timer.
- Stage transition clears partial/armed progress and rejects observation frames captured before the new stage began.
- D advances to a text-only inspection prompt, not an automatic claim of verified completion; stops 10 seconds later.
- Total camera session bounded to five minutes. No photo/video capture in this mode.
- Build and lint passed; 21 device instrumentation tests passed (`assembly-full-tests-device.txt`). New coverage exercises all four transitions, stale previous-stage evidence, all target/phase rendering, and final inspection without rings or green acknowledgment.
- Camera/workspace/eye calibration SHA256 hashes match the A-to-B baseline.
- Prior working APK retained at `baseline/beast-gate-v05-ab-verified.apk` (SHA256 `E50ADA92DA53AB515774FA9D104ACF7B9E0EE7F090C44ADD0E02725AF3F7D23D`).
- Installed and opened on Fold7. At launch no Beast external display was detected; camera remains off pending user readiness.

### Continuous physical trial

After connection and user readiness, Full SBS 3840x1080 was confirmed. The user started the trial at 02:28:00.758 KST.

Log: `assembly-full-live-device-20261121-0228.txt`

| Transition | First green draw | Transition time | Delay |
| --- | --- | --- | --- |
| A to B | 02:28:10.165 | 02:28:13.196 | 3031 ms |
| B to C | 02:28:19.713 | 02:28:22.727 | 3014 ms |
| C to D | 02:28:29.407 | 02:28:32.407 | 3000 ms |
| D to inspection | 02:28:39.038 | 02:28:42.053 | 3015 ms |

Camera automatically stopped at 02:28:52.100 after the inspection prompt (981 camera frames). The app was subsequently force-stopped and absence of its PID verified.

User confirmed A through D and the final inspection prompt were visible, with acceptable position and timing, including C/D. This establishes one successful qualitative continuous trial, not quantified accuracy, long-run reliability, or physical fastening verification. Calibration remained unchanged; no photos/video recorded.
