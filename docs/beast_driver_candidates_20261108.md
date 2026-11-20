# Conservative driver candidate trial

## Scope

Opt-in `-NestedDriverDedup` in `scripts/run_beast_demo.ps1`, or
`--nested-driver-dedup` in the Python server. Only the metric screw trial and
hybrid assembly flow accept it. The default is off; successful calibration,
camera settings, detector confidence, HOLD/release timing and recovery budgets
are unchanged. No camera, real Unity player, model inference or optical test
was started for this change.

Baseline source copies: `outputs/driver_candidate_trial/baseline-20261107-235307/`.
The existing player is unchanged and accepts the server's new pause instruction.
Default camera YAML SHA256 remains
`69FED607A6149D2B487F00124E78E84C5C7113979FA4159E1BE5B296657034C2`.

## Rule

After existing workspace filtering and NMS, retain the stronger driver box and
remove a weaker overlapping shaft candidate only when all conditions hold:

- Both select the same existing handle detection.
- Both have aspect ratio >= 2.5 and the same major axis.
- Shaft widths differ by at most a factor of two.
- Confidence differs by at least 0.15.
- Intersection covers at least 75% of the smaller box.
- Image-space handle-guided tips differ by at most min(6px, 30% of shaft width).

Comparison is with retained boxes, not transitive groups. Do not average or
modify retained geometry. Keep raw detections and pre-dedup counts in logs;
record `nested_driver_dedup` and `driver_nested_duplicates` in filter inputs.
These are conservative trial thresholds derived from observed failures, not
a validated detector improvement or proof of physical tool identity.

Multiple remaining candidates still clear the current HOLD and block progress.
With the option on, they now report `multiple_tool_candidates` and ask the user
to recheck the target with one driver. The supervisor distinguishes that from
a missing driver. Old inputs without the option keep their exact prior reason.
Missing-tool recovery, wrong-target rejection and completed-stage history are
unchanged. Read-only retained-HOLD versus recheck feedback was added separately;
see [HOLD progress feedback](beast_hold_progress_20261108.md). Its live check is pending.

## Evidence

Source: `viture_aruco_rt_20261107_232856_18e5b58b699d`.
Audit: `outputs/driver_candidate_trial/offline-audit-20261108.json`.

| HOLD reset frame | Raw boxes after existing NMS | After new rule |
|---|---:|---:|
| 318 | 2 | 1 |
| 400 | 2 | 1 |
| 981 | 2 | 2 |
| 1111 | 2 | 2 |
| 1465 | 5 | 5 |

This audit uses saved numeric boxes only. It does not rerun YOLO or workspace
projection. Frame 1465's runtime count was 2 after workspace filtering; the
raw audit's five boxes include outside-workspace detections. The first two
frames have agreeing tips; the remaining cases are not merged. This is not
evidence of two avoided resets in a new live flow or a task-time improvement.

Verification on 2026-11-08:

- Reproduced new behavior failures before implementing the rule and reason.
- Python realtime suite: 738 passed, including the metric runtime's complete
  synthetic S0-S6 hybrid flow with duplicate boxes and short observation loss.
- C# suite: 320 passed, 1 existing optional projection-report test ignored.
  The new reason stays PAUSED, hides the target and preserves the instruction.
- Web state/feedback suites: 25 passed. Explicit multiple-candidate feedback
  remains blocked and requests rechecking rather than claiming no driver.
- Six saved real sessions, 10,552 frames: exact filter replay matches state,
  transitions, guidance and instructions. This checks compatibility with old
  filter inputs, not neural detector reproducibility.
- Runner `-CheckOnly` passes both with and without the new option. Hardware
  capture and model inference are explicitly not checked by this command.

## Next live check

After fresh readiness confirmation, repeat the same bounded A-D trial with
`-ScrewResumeMs 600 -CompletedHoldResumeMs 2000 -NestedDriverDedup`.
Keep optical settings, workspace and other parameters unchanged. No further
tightening, supervisor advancement or media recording is needed.

Check actual HOLD/MOVE CLEAR/withdrawal order and final-check arrival. Inspect
logged duplicate suppression and remaining multiple-candidate pauses separately
from marker loss. Do not claim improved comfort until the wearer confirms it.
Omit `-NestedDriverDedup` to return to the prior successful behavior.

## First bounded live comparison (2026-11-08 00:17 KST)

- Session: `viture_aruco_rt_20261108_001713_3f831d54f740`.
- Runner: `outputs/demo/ebae4e04e87a4bf28b9211eaa38a168a/`.
- Unity: `outputs/unity_p1/player-20261108-001717-983.log`.
- Report: `outputs/driver_candidate_trial/live-audit-20261108.json`.
- User confirmed the same wearing/workspace settings, followed MOVE CLEAR and
  withdrawal at A-D, saw final check, and reported less restarting discomfort.
- Compared saved configs with the previous 23:28 trial: the only change was
  `yolo.nested_driver_dedup: true`. Unity selected Beast at 3840x1080; existing
  A offset and C/D depth profiles were loaded. No calibration was changed.
- 1,528 frames / 152.928s input span replayed exactly. Automatic transitions:
  A->B frame 700, B->C 920, C->D 1058, D->S6 1286. Final release evidence spans
  were 401/609/593/400ms, each with valid evidence, five markers and one driver.
  No manual advancement or backwards stage transition occurred. Unity logged
  FINAL CHECK. S6 is a request for final inspection, not certified tightening.
- Completed HOLD resumed nine times (A five, B three, C one), with gaps of
  511..1601ms. Missing time was not counted as work. One suspended completed
  HOLD was discarded at A frame 481 after 2097ms without sufficient evidence;
  the returning sample still had no driver. D frame 1184 directly cleared
  completed HOLD because two driver candidates remained ambiguous.
- **New-rule suppression count was zero.** The option was active and recorded,
  but no valid nested pair met its criteria during this run. A count-only
  counterfactual without the option gives identical state/phase frames and
  transition frames. The user-reported improvement cannot be attributed to
  the new dedup rule. Existing recovery did operate; no new-rule live efficacy
  claim or faster-task claim is supported.
- Active S2-S5 had 1285 frames, 772 PAUSED: marker instability 421, invalid or
  in-flight observations 280, missing tool 68, unknown position 1, multiple
  candidates 2. Startup included a one-marker view before the user adjusted
  gaze; these totals are not matched-window flicker or accuracy measurements.
- Stopped early after final check using this session's own stop signal.
  Camera/server/Unity exited; server-error log 0 bytes, image/video files 0.
  Default YAML hash remains unchanged. No follow-up trial was started.

Keep the option experimental and off by default. This run establishes a
successful bounded flow with no observed regression, not overall reliability
or dedup effectiveness. Preserve the known good configuration; distinguish
retained progress from a genuine recheck in future UX without widening the
evidence gate just to hide remaining pauses.
