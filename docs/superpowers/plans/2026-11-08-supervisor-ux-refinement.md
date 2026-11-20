# Supervisor UX Refinement

## Scope and Evidence

User requested an overall usability review and restrained refinement, prioritizing users over technical display. Keep the established navigation, appearance settings and successful assembly controller. Change only the candidate presentation and its tests; no camera, Unity, calibration, recognition, completion gate or network API changes.

Evidence is heuristic inspection, browser screenshots, existing tests, and the user's prior reports of being unable to watch the notebook while wearing the glasses. This is not a new user study and does not establish a measured improvement.

## Findings

1. Large summary cards repeat the active target and elevate marker count and processing mode above the next action.
2. Internal S-codes and English phase names require interpretation even though the action is already in Korean.
3. Repeating normal feedback competes with the action; recovery reasons must remain immediately visible.
4. Video frame numbers and age change continuously but seldom help the operator act.
5. A hover highlight on a noninteractive metric suggests a control. Keep highlights on interactive theme choices instead.
6. The notebook is still needed for explicit setup/final confirmations. Visual polish does not make this a hands-free workflow.

## Decision

Refine the current single task view instead of adding operator/spectator modes or rebuilding navigation. Remove redundant overview cards, retain the camera and current action as the main content, and keep the complete sequence visible. Move internal state codes to diagnostics; translate displayed phase labels without changing their machine identifiers. Collapse video transport details but keep source/provenance and interruption warnings visible. On mobile, place action and sequence before video.

Preserve explicit manual confirmation, stale/disconnected gates, video opt-in and raw diagnostic access. Do not imply screw torque is automatically verified. Do not add cosmetic metrics, fake progress percentages, forced focus changes or persistent notifications.

## Sources

- NN/g, Progressive Disclosure: https://www.nngroup.com/articles/progressive-disclosure/
  Secondary information belongs behind a clear, discoverable detail entry.
- NN/g, 10 Usability Heuristics: https://www.nngroup.com/articles/ten-usability-heuristics/
  Use familiar language, preserve system status and recovery guidance, remove competing information.
- Design Council, Framework for Innovation: https://www.designcouncil.org.uk/resources/framework-for-innovation/
  Start from user needs and test small iterations, not visual assumptions.
- W3C, Understanding Status Messages: https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html
  Important status changes should be available without moving focus.

## Work

- [x] Add failing tests for plain-language phase labels and fault/recovery visibility.
- [x] Refine candidate markup, labels and responsive layout.
- [x] Verify units, source-session replay, browser states/themes and real-controller synthetic flow.
- [x] Inspect screenshots and leave a camera-free preview.

## Later User Check

Ask a first-time viewer to identify the active screw and next action without coaching; check that a pause is not mistaken for lost completion; ask what the final confirmation proves. Record errors and requests for help. These checks are proposed, not completed. Headset usability and motor workload remain separate physical tests.

## Review Details

Kept four navigation destinations and both themes. Removed the redundant overview, decorative clock, and noninteractive metric highlights. The camera source and interruption status remain visible. Video frame numbers/age are collapsed; internal stage codes and processing mode remain in diagnostics. Normal/confirmation feedback is suppressed only when the action or confirmation hint already carries the necessary instruction. Faults, retained progress, recheck and driver-acquisition guidance remain visible.

The target diagram now describes near/far and left/right from the established worker position, not a newly estimated position. Mobile order is action, full sequence, then video. No model, timing gate, confirmation semantics, overlay calibration or camera behavior changed.

Automated checks: 51 Node tests including stored-session replay; 45 assembly/fault browser cases; 40 theme/navigation browser cases. Zero browser page errors. Tested duplicate IDs, detail disclosure, first-viewport action visibility, keyboard routing, video opt-in/continuity and record export. Screenshots inspected at 320/390px and 1280/1440/2048px widths. Final real-controller rehearsal passed S0-S1-A-B-C-D-S6-COMPLETED with three explicit confirmations.

Evidence: `C:/Users/fresh/Documents/Codex/supervisor-ux-review-20261108`.
Camera-free preview verified at S0 and opened in Chrome: `http://127.0.0.1:61733/supervisor_demo.html?ux=20261108`.
This verifies implementation behavior, not measured usability improvement. No live camera, headset trial or screen-reader trial was conducted.

Follow-up priorities: observe a first-time user's three tasks above; align headset and supervisor wording; evaluate a low-workload explicit confirmation input without loosening safety gates.

## Camera-Free Walkthrough Follow-Up

Found a regression in the feedback reduction: the MOVE CLEAR action did not contain the essential requirement to keep the withdrawn driver visible to the camera. The detail containing that condition was hidden. A new unit test failed on this visibility rule before the one-line candidate fix; MOVE CLEAR now keeps the existing feedback visible. Stale, disconnected and invalid data still suppress actionable withdrawal guidance.

Added browser assertions for the release instruction and skip-link focus return. Full-page screenshots now start at scroll origin to avoid including an off-viewport fixed skip link in a scrolled full-page capture. The application skip-link behavior was not changed.

Verification after the fix: 52 Node tests including stored-session replay, 45 assembly/fault browser cases, 40 theme/navigation cases, and the real-controller synthetic S0-S1-A-B-C-D-S6-COMPLETED rehearsal all passed. No browser page errors. Inspected 1280px desktop and 390px mobile release screenshots. Updated the runbook with headset/supervisor terminology and the three-task camera-free walkthrough.

Preview was verified as synthetic input at S0 and reopened in Chrome. No camera, Unity, calibration, recognition thresholds, state-machine logic or confirmation API changes. An actual first-time-user observation and headset readability test remain outstanding.
