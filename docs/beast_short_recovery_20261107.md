# Short observation-loss recovery trial

## Scope and baseline

Preserve the successful configuration, eye/workspace profiles, YOLO settings,
800ms engagement, 400ms release, and visual freshness rules. Default recovery
grace is zero, keeping old sessions and commands reproducible. The optional
trial uses 600ms, measured from the last usable source observation to the
recovered observation's receipt, not from repeatedly renewed pause events.
No camera/Unity run is part of offline implementation.

The latest live session had 30 completed PAUSED runs during S2-S5; 18 lasted
at most 600ms. This measures displayed pause duration, not recoverable work or
proof that a 600ms grace is optimal. Recovery also requires fresh evidence.

## Rules

- Only S2-S5 engagement progress can be suspended. Never advance during loss.
- Freeze time at the last valid source observation; exclude the entire gap.
- Resume only on a new, valid, single-tool observation near the same target.
- Preserve an already observed engagement, but clear partial release time.
- Recovery away from the target, ambiguous/other targets, multiple tools,
  malformed data, or an expired grace discards suspended progress.
- Late pre-loss observations remain rejected. Repeated pauses/cached frames
  cannot extend grace or accumulate work.
- Stage/session boundaries clear all suspended work. Long loss restarts only
  the current screw, not completed stages.
- Existing PAUSED/hidden-ring presentation remains; no stale MOVE CLEAR cue.

## Verification

Reproduce reset with tests, add opt-in recovery tests, run the complete realtime
suite, replay the successful sessions exactly with the default, then compare
counterfactual trial outputs on the same numeric logs. Earlier hypothetical
transitions are not live accuracy or proof of faster task completion because
the user's actions followed the original instructions. Live confirmation is
separate and requires readiness. No imagery or new dependency is required.

## Offline results (2026-11-07)

- Final realtime regression suite: 686 passed in 46.30s.
- Unit cases cover partial HOLD, already observed engagement, repeated gaps,
  stale/cached evidence, wrong or ambiguous targets, malformed data, the 600ms
  boundary, and release requiring fresh observations after recovery.
- The synthetic full-runtime test drops one detection during each screw's
  HOLD. With recovery enabled, S0/S1 manual confirmation, A-D automatic
  transitions, and S6 manual confirmation complete; recorded inputs replay
  exactly. The camera and neural detector are substituted, not the metric
  scoring, evidence gate, session controller, or logger.
- Exact baseline replay: 1743 + 2245 + 2727 = 6715 frames matched across the
  three successful live sessions from 21:25, 21:38, and 21:57.
- Counterfactual 600ms replay: 19/11/10 frames changed from OBSERVING to
  OBSERVED. Transition order AND transition frames stayed identical. PAUSED
  frame counts did not improve; no task-time improvement is claimed.
- Both original and recovery-enabled launcher commands passed `-CheckOnly`.
  Existing profile compatibility passed; hardware and optical alignment were
  not tested. Unity binaries and calibration files were not modified.

Report: `outputs/recovery_trial_20261107/comparison-600.json`.
Pre-edit source/config copies and hashes:
`outputs/recovery_trial_20261107/baseline-222029/`.
The original realtime YAML SHA256 remains
`69FED607A6149D2B487F00124E78E84C5C7113979FA4159E1BE5B296657034C2`.

## Trial and rollback

Keep the existing successful command as the baseline. For a bounded live
comparison, add only `-ScrewResumeMs 600` to the `-AssemblyFlow` command.
Omit it (or use zero) to restore the original immediate-reset policy.
The Python equivalent is `--screw-resume-ms 600`; the chosen timing is recorded
in each session's `config_used.yaml` for exact replay.

Further live comparison requires readiness. Check a brief interruption during
HOLD and recovery at the same screw, then normal visible withdrawal. Confirm
that no step advances during loss. Long loss should restart the current HOLD
without clearing completed steps. Do not tighten screws further for this test.

This change does not preserve state across server/process restarts, improve
tracking availability, or verify screw torque. It also deliberately discards
engagement if the first valid recovery is already away from the target: return
to the same screw before continuing. The 600ms receipt-based budget includes
inference delay, so it is not a promise to preserve every 600ms visible pause.

## First live trial: partial benefit, not acceptance

Session: `viture_aruco_rt_20261107_224042_f3e0abced7e0`.
Runner: `outputs/demo/e1f0ce7d90ad445d84cd7d38fd2549a9/`.
Unity: `outputs/unity_p1/player-20261107-224046-161.log`.

- Isolated A-to-B mode, 600ms recovery, same profiles/thresholds, no manual
  confirmation. Unity selected Beast 3840x1080. Input initially saw only one
  marker, then tracked five. Stopped after A-to-B instead of using all 3 minutes.
- 904 logged frames / 90.316s input span; exact filter replay matched.
  The sole transition was S2->S3 at frame 619. The user saw B but reported
  a remaining feeling of having to restart partway through.
- Before that transition, A had five suspended-engagement episodes. One
  resumed (frames 552->555, 511ms from last usable source to recovery receipt),
  restoring an already completed HOLD. Four discarded the stored engagement.
- Discards occurred at frames 289/357/389/572 with source ages
  704/703/703/608ms. Three involved continued tool/marker/input loss; at 357
  the fresh tool was already away from A. That last recovery fails the
  same-target condition even when the grace is increased.
- Same-input counterfactuals at 0/600/800/1000ms all transitioned at frame 619.
  At 600ms, eight guidance-phase frames differed from 0ms. This demonstrates
  limited state recovery, not faster completion or overall interruption relief.
- Camera/server/Unity ended; server-error log was empty and no image/video
  files were saved in the session. No calibration, detector, default config,
  or timing implementation was changed during this live trial.

Next design question: distinguish completed engagement from pending withdrawal.
Increasing grace alone did not resolve this recording. A future opt-in change
could retain bounded completed-HOLD memory while requiring fresh valid release
evidence; unknown input must never count as withdrawal or advance a step.
Wrong-target, long-loss, and stage/session-boundary resets still need explicit
tests before changing that rule. The optional variant below addresses this;
the original successful command remains unchanged.

## Completed-HOLD variant

Use `-ScrewResumeMs 600 -CompletedHoldResumeMs 2000` for the next bounded
trial. The new option defaults to zero, with a validated range of 0..3000ms.
Python/config names are `--completed-hold-resume-ms` and
`timing.completed_hold_resume_ms`. The 2000ms trial budget is an engineering
choice to test, not a measured optimum. Prior implementation copies are in
`outputs/recovery_trial_20261107/before-completed-hold/`.

- Partial HOLD still uses only the old 600ms same-target budget.
- Completed HOLD can survive recoverable observation loss for up to 2000ms
  from the last usable source to recovery receipt, without renewed deadlines
  from missing/cached samples. Long loss still clears it.
- New valid single-tool evidence at the same target restores completed HOLD.
  Alternatively, evidence clearly away from ALL four targets starts a new
  release interval. The missing interval and any pre-loss release time do not
  count toward the required 400ms visible release.
- Wrong/ambiguous target, multiple tools, and malformed evidence discard the
  memory. Another target detected during a resumed release also discards it.
  Returning to the current target cancels partial release as before.
- No advancement during loss, no memory across stages/sessions, no automatic
  change to S0/S1/S6 human confirmations. PAUSED/visibility rules are unchanged.

Behavior was reproduced with failing tests before implementation. Unit tests
cover completed vs partial HOLD, deadline boundaries, stale/malformed inputs,
repeated pauses, target changes, and new-stage isolation. A synthetic runtime
test now drops detections after HOLD and recovers during withdrawal, completes
the hybrid A-D flow, and validates exact log replay.

Four real logs (7619 frames total) still replay exactly with their own saved
settings. Counterfactual report:
`outputs/recovery_trial_20261107/completed-hold-2000.json`.
All event sequences are unchanged; some transition frames become earlier.
The latest A-to-B recording would transition at frame 313 instead of 619.
This is NOT a measured speedup or ground-truth correctness: the user's actions
followed the earlier UI, and real intent/withdrawal must be confirmed live.
Launcher `-CheckOnly` passed; no Unity rebuild or calibration changes needed.

## Completed-HOLD live check (22:57 KST)

Session: `viture_aruco_rt_20261107_225704_d576986da57f`.
Runner: `outputs/demo/bdeb96c2ade24cf4896565a51fd9dad3/`.
Unity: `outputs/unity_p1/player-20261107-225708-103.log`.

- Final realtime regression: 714 passed in 49.35s. The preceding run had
  713 passes and one existing Tk preview file-read failure; its isolated
  rerun and then the complete rerun passed without a code workaround.
- 1013 frames / 101.325s input span, exact replay matched. A->B at frame 620.
  User confirmed MOVE CLEAR, visible withdrawal, B text/ring, and less of
  a restarting feeling. Camera/Unity stopped; server-error bytes=0, media=0.
- A's final release used distinct source frames 614,616,618 spanning 401ms.
  These had markers, one visible driver, and A scores below release threshold.
  No stage transition occurred during missing input.
- A had two suspended completed-HOLD episodes, both discarded when loss
  exceeded 2000ms (frames 414/487, source ages 2001/2111ms). There was no
  recovery in the A->B portion, and its phases/event frame match a replay
  with completed-HOLD recovery disabled. Therefore the subjective improvement
  is NOT evidence that the new feature caused faster A completion.
- After B was displayed, completed-HOLD memory resumed twice at frames
  963 and 1013, both at 1904ms source-to-receipt gap, with fresh clear-tool
  evidence starting a new release interval. This supports actual-input recovery
  operation. B was the trial's terminal state; B->C and full A-D usability
  were not validated, and this tail was not a controlled B task comparison.
- Counterfactual report `outputs/recovery_trial_20261107/completed-live-vs-600.json`
  has the same A->B event at frame 620 and 35 changed phase frames AFTER it.
  Default config SHA256 is unchanged. Both recovery options remain opt-in.

Next: controlled B-C-D flow with the same options, checking that each MOVE CLEAR
is followed by the user's actual withdrawal, while separating input loss from
completed-HOLD memory. Do not increase the retention budget merely to improve
the completion count. Current evidence is a functioning trial, not broad
tracking or automatic assembly-quality acceptance.
