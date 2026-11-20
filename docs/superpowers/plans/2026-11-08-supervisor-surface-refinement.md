# Supervisor Surface Refinement

Goal: Match the approved reference application's dark surfaces and cursor-local light, while retaining the video-first assembly workflow.

## Boundaries

- Candidate UI only; no camera, Unity, calibration, recognition, state-machine or API changes.
- New visitors default to dark. Explicit saved light/system choices remain valid.
- Frame only the video tool and current-action tool. Keep sequence/history unframed; no extra summary cards.
- Pointer light follows actual coordinates on tool chrome and controls, never camera imagery or fault text. Preserve disabled, reduced-motion and touch guards.
- Claude receives only a separate UI review bundle. CLI authentication expired (401), but the desktop review was subsequently completed using current UI code, screenshots, and SafeOps source excerpts. No experiment logs or calibration files were included.

## Work

- [x] Add default-theme, surface bounds and pointer isolation regression checks.
- [x] Update candidate surfaces, density and hover presentation.
- [x] Verify unit tests, desktop/mobile states and themes, screenshot pixels, and synthetic controller flow.
- [x] Open a fresh local camera-free preview and report results.

## Review And Verification

- Claude review: https://claude.ai/chat/67fff65a-49f4-4650-9f94-10c721c81c4c
- Accepted three small CSS changes: keep the screw map near the action, retain it on 720p/768p desktop layouts, and reduce duplicated status color while preserving caution/error emphasis.
- Reproduced the excessive map gap with a failing browser assertion before changing CSS. Added 1366x768 and 1280x720 coverage.
- Unit tests: 52 passed. Shell/theme checks: 48 passed. State/layout cases: 54 passed across six viewports. No page errors.
- Pointer pixel checks passed in both directions; camera imagery and warning interiors stayed unchanged. Touch, disabled controls, and reduced-motion guards passed.
- Camera-free rehearsal used the real assembly controller with synthetic observations: S0 -> S1 -> A -> B -> C -> D -> S6 -> COMPLETED, with three operator confirmations.
- Protected supervisor controller/state/video and Unity GuidanceState hashes were unchanged.
- Opened and retained the updated Chrome preview at http://127.0.0.1:58090/supervisor_demo.html?review=20261108-final. This is a bounded local synthetic preview, not a hardware test; camera and Unity remain off.
- Evidence: C:/Users/fresh/Documents/Codex/supervisor-surface-review-20261108.

## Presentation Follow-up

- Shortened the video caption to distinguish test input from the camera viewpoint without a long negative disclaimer. Only the synthetic source label changed in supervisor_video.js; polling and validation are unchanged.
- Tool pointer light: radius 416px -> 280px, center color mix 13% -> 24%. Kept video and warning isolation. Pixel regression failed before the change and passed afterward.
- Fullscreen scrollbar keeps a stable native gutter and becomes visible within 28px of the right edge. Keyboard scrolling also reveals it; forced-colors retains native colors. No custom scroll physics or overflow suppression.
- Fullscreen API and display-mode media query drive the shell state. Reference: https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/%40media/display-mode
- Verification: 52 unit tests, 54 browser state/layout cases, pointer pixel guards, fullscreen edge visibility, stable layout width, and PageDown scrolling passed. Browser fullscreen-button checks ran in automated Chrome; native F11 was not separately exercised.
- Refreshed the user's existing Chrome preview with the new caption and video enabled. Camera and Unity remain off.
