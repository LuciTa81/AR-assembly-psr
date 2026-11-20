# Beast SBS text stability: 2026-11-07

## Scope

Presentation-only follow-up to the short-loss HOLD recovery trial. The user
reported brief changes in the lower text. Guidance and position reasons were
rendered directly from each current sample, even when the underlying stage had
not changed. Do not interpret a text change as a completed-stage reset.

`GuidanceTextStability` is applied by `SbsGuidancePresenter` to two independent
channels: the action/cue and the position footer. It never caches an old action.

- Soft input loss immediately replaces actionable text with `PAUSED` and
  `Checking input. Guidance paused.` Position uncertainty shows
  `Checking position` instead of rapidly alternating detailed reasons.
- A specific soft-fault reason must persist for 500ms before its detail appears.
  Changing the reason restarts that interval.
- After a soft/hard interruption, healthy input must persist for 250ms before
  restoring the CURRENT action. Intermittent healthy frames do not restart it.
- Normal healthy phase changes remain immediate. New session/stage/target
  contexts do not inherit the previous target's pending text state.
- Connection, invalid-data, profile/display errors and unknown hard faults are
  immediate. Explicit final confirmation and completed status are immediate.
- Ring position, visibility gates and ring color still use the unfiltered state.
  Text recovery does not make an uncertain target visible or delay its hiding.
- Both eyes use the same filtered instruction. `[SBS TEXT]` records changes to
  the actual displayed cue/instruction/footer; existing raw-state logs remain.

No changes to Python recognition, state transitions, HOLD/release timers,
recovery settings, calibration, camera options, or supervisor actions.
The 500/250ms display intervals are initial UX choices, not measured optima.

## Verification

- Regression reproduced before implementation: 8 failing behavioral cases.
- New C# cases: 23 passed. Complete C# suite: 319 passed, 0 failed, 1 ignored.
  The existing optional projection-report test requires an external report.
- Unity build succeeded: `outputs/unity_p1/build-20261107-231444-558.log`.
- First hidden-window synthetic run did not render UI and failed the nonblank
  capture assertion. It is NOT counted as a successful screen test.
- Visible laptop-only R4 fixture: 59 checked frames, A/B/C/D per-eye rings and
  loss/final/disconnection hiding checks passed. A second comparison using
  Direct3D 11 passed 51 frames. Production renderer settings were not changed.
- All 41 screw-stage PNGs from the default visible run and all 33 from the
  renderer comparison had cue, instruction and footer pixels after capture
  completion. Representative pause, MOVE CLEAR, final-check and disconnect
  images were inspected. These are synthetic UI captures, not camera images
  or a recording of the user's through-glasses view.
- The fixtures/players exited. At this offline checkpoint no real camera or
  Beast trial had run. The subsequent live check is recorded below.

Artifacts under `outputs/unity_p1/`:

- `text-stability-visible-preview-20261107.json`
- `text-stability-visible-player-20261107.log`
- `text-stability-visible-capture-20261107/`
- `text-stability-dx11-player-20261107.log`
- `text-stability-dx11-capture-20261107/`

Prior complete player distribution is preserved at
`outputs/unity_baselines/before-text-stability-20261107/`.
Default camera config SHA256 remains
`69FED607A6149D2B487F00124E78E84C5C7113979FA4159E1BE5B296657034C2`.

## Planned bounded live check

After fresh readiness confirmation, use the same optical/workspace settings
and the opt-in 600ms partial / 2000ms completed-HOLD recovery settings for one
A-D trial. No further tightening or media recording is needed. Check:

1. WORK AT / HOLD AT / MOVE CLEAR correspond to the user's actual actions.
2. Brief uncertainty shows neutral text, without a stale MOVE CLEAR command.
3. Recovery restores the current instruction; completed stages remain complete.
4. Each stage advances only after visible withdrawal, ending at final check.

Review logs and the user's experience separately. Do not claim this removes
tracking loss, establishes torque/tightness detection, or proves broad accuracy.

## A-D live check (23:28 KST)

Session: `viture_aruco_rt_20261107_232856_18e5b58b699d`.
Runner: `outputs/demo/de921cb2ba9b4605abed544f84ad35ef/`.
Unity: `outputs/unity_p1/player-20261107-232900-387.log`.

- Same profiles, Full SBS 3840x1080, 600ms partial and 2000ms completed-HOLD
  recovery; isolated S2->S6 automatic trial, no supervisor advancement.
- User confirmed following MOVE CLEAR and withdrawal at each screw, A-D in
  order, and seeing final confirmation. Text was better, but a restarting
  feeling remained. This is one successful bounded flow, not full UX acceptance.
- 1920 frames / 192.044s input span replayed exactly. Transitions were
  A->B frame 495, B->C 817, C->D 1175, D->S6 1509. Their final release source
  spans were 400/400/607/401ms, with valid evidence, five markers and one driver.
  No backwards stage transition occurred. S6 is final-check, not a completed
  assembly-quality decision or manual CONFIRMED result in this isolated mode.
- Active S2-S5: 1508 frames, including 710 PAUSED frames. Reasons: marker
  instability 386, invalid/in-flight observation 221, tool-not-visible 101,
  unknown tool position 2. These include startup and are raw input states,
  NOT a measured on-screen flicker rate or a camera-accuracy benchmark.
- Replay inspection found 12 resolutions of suspended completed-HOLD memory
  that restored the prior HOLD: A once, C five times, D six times. Source-to-
  receipt gaps were 496..1904ms. The missing interval was not added to work.
- Three suspended completed HOLDs were discarded: B frame 574 at 2002ms,
  D frame 1335 at 2096ms (marker loss beyond budget), and A frame 252 at
  1599ms (fresh recovery classified the tool near B, score 0.889, not A).
- Five additional direct completed-HOLD resets occurred at frames
  318/400/981/1111/1465. Each had `driver_visible=1`, `driver_count=2`, valid
  evidence and markers. The first four have substantially overlapping driver
  boxes; the last includes separate left-side boxes. Numeric logs suggest
  duplicate/background detections but, without saved imagery, do not establish
  physical object identity. Never simply accept every multiple-tool sample.
- All five use `tool_not_visible`, whose displayed instruction is "Tool not
  visible. Keep the driver in view." The explanation is misleading for multiple
  candidates. A follow-up should distinguish missing, ambiguous and multiple
  tool evidence, and retained HOLD from genuinely cleared HOLD.
- Disabling only completed-HOLD recovery in same-input replay changes 57 phase
  frames but leaves all four transition frames identical. No faster task-time
  claim is supported. Report:
  `outputs/recovery_trial_20261107/text-stability-live-vs-600.json`.
- Camera/server/Unity stopped; server-error log 0 bytes; image/video files 0.
  Unity logged FINAL CHECK. Later S6 tracking-loss text occurred after the final
  transition in isolated auto mode; no assembly-stage rollback occurred.

Next: preserve this successful build/config. First examine overlapping driver
candidates offline and separate the ambiguity message from missing-tool text;
keep genuinely distinct tools blocked. Do not widen HOLD retention or lower
recognition thresholds merely to remove pauses. No detector/state-machine
implementation was changed during this live check.
