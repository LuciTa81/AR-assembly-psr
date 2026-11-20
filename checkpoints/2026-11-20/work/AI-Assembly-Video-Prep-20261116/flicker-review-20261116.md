# Recorded flicker review

## Scope

Offline replay only. No camera was opened. No application, threshold, workspace
coordinate, or eye calibration was changed. Protected file hashes were unchanged.
The production pose solver reproduced every recorded acceptance/rejection reason
in both samples (80 + 1699 unique observations).

## Findings

1. In the 10-second verification recording, all 80 unique observations contained
   five markers. The current 3 px RMS / 5 px maximum gates accepted 47 and rejected
   33. There were 41 changes between accepted and rejected observations. This is
   pose-quality boundary chatter, not missing marker detection in this sample.
2. Marker 1 had the largest residual in 30 of those 33 rejected observations.
   Its median horizontal residual across solved observations was -4.70 px.
   This does not establish that marker 1 physically moved: workspace registration,
   intrinsics, and detection bias remain possible causes. Do not move the marker
   or adjust its registered position from this residual alone.
3. The longer take shows a different D-stage bottleneck. Of 269 observations,
   108 failed the marker-geometry check and 50 had insufficient visible markers.
   Of the 108 geometry failures, 107 showed IDs 0,1,2,4 and one showed 0,1,2,5.
   The existing center-based IPPE solver rejects these four-center configurations
   because three of the centers are collinear. Four detected markers is therefore
   not, on its own, enough for this solver.
4. The Korean action-text display retains brief soft-loss text for screw stages
   S2-S5 only. Box/lid stages S0/S1 lack that display-level retention. The Unity
   log confirms repeated S0 guiding/tracking-lost changes and attention messages.
   Changing this text policy would reduce instruction flicker, not repair poses.

## Diagnostic threshold comparison

These are accepted *observations*, not measured Unity display uptime.

| Sample | Current RMS 3 / max 5 | Diagnostic RMS 3.5 / max 6 |
| --- | ---: | ---: |
| 10-second verification | 47/80 (58.8%) | 79/80 (98.8%) |
| Full take, first 205 seconds | 1171/1699 (68.9%) | 1274/1699 (75.0%) |
| D stage in that take | 105/269 (39.0%) | 111/269 (41.3%) |

For newly admitted observations with a baseline-accepted neighbor within 250 ms,
the maximum A-D eye-projection displacement had median/p95/max values of
9.30/20.68/31.44 px in the short sample and 23.02/66.32/153.85 px in the long take.
These differences include actual head motion and are NOT optical registration
errors. They cannot establish that relaxed gating is safe. No relaxation applied.

## Minimal next step

- Address S0/S1 instruction churn separately, preserving only the text through a
  bounded soft-loss interval; do not advance stages, retain stale spatial geometry,
  suppress disconnects, or display successful confirmation from that retention.
- For recording, preserve the marker layout and calibration. Keep lower/side
  markers visible together with the upper row, especially while working at D.
- Do not attempt a new marker layout, corner solver, or calibration replacement
  solely to rescue this recording. Those require separate validation.

## Evidence

- `recordings/20261116_010232_wgcverify2/states.jsonl`
- `recordings/20261116_005052_take02/states.jsonl` (through 205 s; excludes subsequent headset put-down)
- `flicker-offline-audit-20261116.json`: full measurements and source hashes
- `audit_recorded_flicker.py`: offline reproduction, profile bindings, and hash checks
- Unity log: `../beast-action-guide-20261115/player-v2/player-20261116-005848-912.log`

HTTP sampling can miss camera observations. Durations are sample spans, not
frame-perfect display-loss measurements. Actual optical accuracy was not measured.
