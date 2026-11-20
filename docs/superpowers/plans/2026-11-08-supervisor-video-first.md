# Supervisor Video-First Layout Implementation Plan

**Goal:** Implement the user's approved video-left/task-right layout and cursor-local highlight.
**Architecture:** Keep the existing HTML/controller contracts. Change candidate markup, CSS and pointer presentation only.
**Tech Stack:** Vanilla HTML/CSS/JS; existing Node and Playwright checks.
**Spec:** User-approved layout: video approximately two thirds, one task column at right, full sequence below; no large tracking/mode summary cards. Preserve fault guidance and confirmation boundaries.

## Constraints and Decisions

- No camera, Unity, calibration, recognition, state-machine or API changes.
- Keep mobile action-first order, video opt-in and uncropped source images.
- Keep the necessary camera-visible withdrawal instruction and recovery messages.
- Use pointer x/y, not a rotating gradient. Apply only to existing theme choices and clear command buttons, never to video or status text.
- Keep reduced-motion, highlight-off, disabled and touch states free of pointer effects.
- Prefer a focused CSS/markup change over importing the reference Next.js app. No dependencies installed, commits or deployment.

## Work

- [x] Reproduce reversed highlight with a screenshot-pixel regression in `tests/web/supervisor_pointer_browser.cjs`; add layout bounds to the existing shell browser check.
- [x] Update `web_overlay/supervisor_shell.js` pointer coordinates and `web_overlay/supervisor_demo.css` highlight, desktop proportions, height budget and typography.
- [x] Update `web_overlay/supervisor_demo.html` task order; keep the current target only in the right column. Preserve all shared controller IDs.
- [x] Run Node tests, pointer pixels, browser states/themes and real-controller synthetic rehearsal. Inspect desktop/mobile screenshots.
- [x] Open a fresh camera-free preview and report limitations.

## Review Focus

1. Cursor near either edge must brighten that edge, not the opposite one: pixel regression.
2. Disabled, touch, motion-off and reduced-motion must not suggest an active control: pointer browser check.
3. Small desktop displays must retain the sequence and current action: layout bounds.
4. Stale/disconnected inputs must retain stop/recovery guidance: existing state/browser checks.
5. Final confirmation and withdrawal camera visibility must survive presentation changes: existing workflow/release checks.

## Verification

Before the fix, the pointer pixel test failed: left cursor luminance 39.67 versus opposite edge 59.78. After the fix, left cursor 54.19 versus opposite 36.33; right cursor 54.22 versus opposite 36.33. This checks actual screenshot pixels, not just CSS variables. Touch, disabled controls, highlight-off and reduced-motion guards passed.

52 Node tests (including stored-session replay), 45 assembly/fault browser cases and 40 theme/navigation cases passed. The actual assembly-controller synthetic rehearsal passed S0-S1-A-B-C-D-S6-COMPLETED with three explicit confirmations. No browser page errors. Reviewed 1440px dark, 1280px light/disconnected and 390px release screenshots. First-viewport sequence, preserved video ratio and required withdrawal/recovery guidance passed.

Original supervisor controller/state/video and Unity GuidanceState file hashes are unchanged. No physical camera, Unity launch or recalibration was performed. This is UI verification, not a measured first-time-user study.

Artifacts: `C:/Users/fresh/Documents/Codex/supervisor-layout-review-20261108`.
The expired preview was replaced by a bounded 3600-second synthetic server and opened in Chrome at `http://127.0.0.1:50630/supervisor_demo.html?layout=video-first-20261108`, verified at S0.
