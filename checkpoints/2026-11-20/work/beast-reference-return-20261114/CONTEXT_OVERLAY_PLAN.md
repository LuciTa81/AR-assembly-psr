# Four-screw context overlay trial

- Preserve the protected baseline executable, joint A-D projection and all server policies.
- Opt-in `StageContext`: faint non-active rings and a thin A-B-D-C-A screw-center quad; existing active ring and blue/green cues remain unchanged.
- Screw stages S2-S5 only. All points use one fresh observation. Hide context on session/state/pose failure or any out-of-view corner; do not let context failure hide an otherwise valid active target.
- Reject legacy per-target offsets/depth records in this first shared-projection trial.
- Verify option parsing, fresh/session/state gates and active/context pixel identity; build in `context-overlay-build`, never over the successful player.
- Verify rendered output offline, then request readiness for a short live comparison. No camera/image recording during preparation.

## Result (2026-11-15)

- Implemented behind `--stage-context`; default off. Separate `context-overlay-build` produced successfully.
- C# tests: 410 passed, 3 optional replay tests skipped. Existing full-flow regression: 4 passed. Read-only review: no blocker found.
- Live session `viture_aruco_rt_20261115_144456_9d645343dc89`: 995 frames, 99.419 seconds; A-B-C-D automatic order and manual final completion recorded. Exact numeric replay matched all 995 frames.
- No OBSERVING re-entry after the first completed HOLD at any screw. Temporary PAUSED states remain; this does not establish tracking without interruption.
- User confirmed all four rings/lines were visible and active highlighting switched correctly. Requested brightness/thickness refinement; direction still pending.
- Actual optical visual verification was performed in this live trial, not an offline screenshot. Camera and player processes stopped; no images/video saved.
- Nine protected baseline/profile hashes and the previous successful checkpoint player remained unchanged. Candidate not promoted to default.
- Current faint rings: 36px, alpha .45; connecting lines: 2px, alpha .32; active ring remains the original 48px and cue-dependent color.

## Brightness follow-up

- User requested brighter/thicker context rings and lines; active target unchanged.
- Separate `context-overlay-brighter-build`: context ring diameter remains 36px, texture half-thickness 3.5 -> 4.5, alpha .45 -> .60. Lines 2 -> 3px and alpha .32 -> .45.
- Previous `context-overlay-build` remains selectable and unchanged. New brightness is not optically verified yet.
- Full box edges and S1 display were discussed, not implemented: workspace has A-D screw-center targets at z=60mm, but no physical outer-top/bottom vertices. Register box outline separately; preserve eye calibration and original targets.
