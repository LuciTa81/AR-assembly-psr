# Tracking-gated preparation instructions

Date: 2026-11-21 (Asia/Seoul)

## Decision and limits

The bundled detector (`YoloDetector.LABELS` and `driver-model.json`) only covers driver, handle and screw. Workspace pose comes from fixed table markers, not the box/lid. Neither signal establishes actual box placement or lid closure.

The user's requested fallback is therefore implemented as timed instructions, not object verification. The initial duration was eight seconds per stage. Following the first physical trial, the user requested seven seconds for box instructions and six for lid instructions; these are guidance durations, not measured assembly-time requirements.

## Candidate

- Opt-in intent `preparation_probe=true`; existing `assembly_full` and `assembly_probe` modes retain their prior flows.
- Box instruction -> lid instruction -> unchanged A/B/C/D timed guidance -> final inspection text.
- Box instructions need 7000 ms and lid instructions 6000 ms of eligible tracking intervals while text is drawn on the 3840x1080 SBS surface.
- Accepted pose with at least five markers; observation age <=500 ms, interval <=350 ms. Duplicate, out-of-order, future, stale and pre-stage frames cannot add time.
- Tracking loss pauses accumulation without erasing prior progress. A long gap cannot count as instruction time.
- Both eyes show the current Korean instruction. Preparation is text-only, with no new box geometry or recalibration.
- No preparation evidence carries into the screw gate: a new `AssemblyProbe` begins on entry to A.
- Total session max five minutes, final inspection ten seconds, background/disconnect/stop cancels the session.
- No photos/video saved. Logs explicitly say `mode=tracked_instruction_time` and `object_verified=false`.
- This can advance even if a box/lid is absent while the table markers remain tracked. It must not be presented as an automatic placement/closure detector.

## Verification

- Debug build and lint passed.
- 26 device instrumentation tests passed (`preparation-tests-device.txt`).
- Preparation tests cover eight-second boundaries, interrupted tracking, old-stage frames, restart, and no screw evidence inheritance.
- Render tests cover both eye text regions, no ring in preparation, stale/invalid pose, wrong surface size, and callback cleanup when switching/clearing.
- Initial integration test incorrectly assumed the lid could reuse the box transition frame. Corrected the test to require a new stage baseline frame, then reran all tests successfully.
- Camera, workspace and eye-projection SHA256 hashes unchanged from the verified A-to-D candidate.
- Previous A-to-D APK: `baseline/beast-gate-v05-ad-verified.apk`, SHA256 `E8D3E56DE24E042018FCC496B0FFD676DB44FF77D7B514759F63A9B33B5590C0`.

## Physical trial

Candidate installed and opened at 02:35 KST. The user subsequently connected Beast, confirmed readiness, and started the trial. Full SBS 3840x1080 confirmed before start.

Log: `preparation-live-device-20261121-0236.txt` (numeric app log only).

| Event | Time (KST) | Interval |
| --- | --- | --- |
| Start | 02:36:39.562 | - |
| Box -> lid | 02:37:13.762 | 34.200 s wall time from start |
| Lid -> A | 02:37:25.158 | 11.396 s wall time |
| A -> B | 02:37:38.955 | 3016 ms after green draw |
| B -> C | 02:37:49.483 | 3048 ms after green draw |
| C -> D | 02:38:07.226 | 3048 ms after green draw |
| D -> inspection | 02:38:22.304 | 3065 ms after green draw |
| Automatic camera stop | 02:38:32.353 | 1850 camera frames |

The time-gated preparation stages and all screw transitions reached final inspection. Box instruction took substantially longer than eight seconds of wall time because only eligible drawn tracking intervals count (startup and rejected/gapped observations do not count). Per-frame preparation timer increments are not separately logged, so the exact split of excluded intervals has not been quantified.

After automatic stop, the app was force-stopped and absence of PID verified. User confirmation of actual visibility and subjective timing is pending; logs alone do not establish comfort or successful physical assembly.

## User timing adjustment

The user's response to the trial was to shorten box/lid instructions to 7/6 seconds. No separate explicit confirmation of all visuals was supplied in that response.

- Updated stage thresholds, remaining-time display, start and transition logs together.
- Original eight-second APK retained as `baseline/beast-gate-v05-preparation-8s.apk`.
- Build/lint passed; all 26 device instrumentation tests passed again (`preparation-7s-6s-tests-device.txt`), including exact seven/six-second boundaries, interrupted timing and stage isolation.
- Updated APK installed on Fold7; app stopped after tests. No live camera trial started for these new durations.
- A-to-D three-second transitions, tracking acceptance, and calibration unchanged.

## Seven/six-second live trial

2026-11-21, Full SBS 3840x1080, user confirmed unchanged wearing/settings and started the trial. Numeric log: `preparation-7s-6s-live-20261121-0242.txt`.

| Event | Time (KST) | Interval |
| --- | --- | --- |
| Start | 02:42:58.331 | box_ms=7000, lid_ms=6000 |
| Box -> lid | 02:43:13.554 | 15.223 s wall time |
| Lid -> A | 02:43:24.101 | 10.547 s wall time |
| A -> B | 02:43:34.230 | 3031 ms after green |
| B -> C | 02:43:43.012 | 3000 ms after green |
| C -> D | 02:43:55.058 | 3000 ms logged after green |
| D -> inspection | 02:44:07.335 | 3016 ms after green |
| Automatic stop | 02:44:17.365 | 1549 camera frames |

All transitions reached inspection; no photo/video recording. App force-stopped after automatic camera stop, PID absence verified. The user confirmed that the entire flow through final inspection was visible and that both waiting time and screw guidance were acceptable. This is one successful qualitative trial of the seven/six-second candidate, now the working reference for subsequent feature work; it is not evidence of actual box/lid detection or quantified long-run reliability. Shorter wall time than the previous trial is not an isolated timing-policy comparison because tracking and user motion differed.
