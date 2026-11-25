# Product Phone UI Implementation Plan

**Goal:** Replace the diagnostic-style phone launcher with a restrained, work-first Android interface suitable for exhibition use.
**Architecture:** Keep native Java Views and all existing camera, stereo, calibration, assembly and network lifecycles. A phone-only view class owns layout and presentation; MainActivity supplies existing state and actions.
**Tech Stack:** Android API 36, Java 17, native Views; existing Lucide icons converted to Android vectors.
**Spec:** User approved work-first UI and delegated detailed design; requested APK/build verification only, no phone installation.

## Design

- Charcoal background, near-white type, mint primary action, thin separators. No gradients, large slogans, decorative cards or nested cards.
- Work and Connection tabs. The work screen contains one current instruction, seven-step progress, task elapsed time, framed camera preview and persistent start/stop controls.
- Compact phone: vertical work surface. Wide Fold layout: work and preview side by side. Scroll content when font scale/height requires it; controls stay reachable.
- Connection: Beast output status, internet supervisor controls and visible consent. Local Wi-Fi and raw diagnostics remain available under a collapsed diagnostics section.
- Idle preview is an intentional camera-off state; no recordings, auto-camera launch or placeholder live state.
- Keep network configuration, consent, permission, invalid Full SBS and error feedback. Preserve current execution limits and show a concise five-minute session limit.
- Diagnostics modes retain their existing screen. No web/EC2 changes.

## Tasks

- [x] Read current launch/state flows and preserve original source/APK.
- [x] Add presentation policy tests (step titles, phase labels, responsive breakpoint, safe idle state).
- [x] Implement AssemblyScreen and connect existing callbacks without altering domain logic.
- [x] Style supervisor settings; hide diagnostics by default, never remove consent.
- [x] Compile instrumentation layout checks for folded/unfolded/landscape and font scaling.
- [x] Run JVM regression tests, assemble APK and instrumentation APK, lint; package candidate with hashes.

## Review Focus

- Disabled start must still explain missing Beast/Full SBS/permissions.
- Tab changes must not stop or start camera/remote link.
- Stop must be visible and immediate, including while viewing Connection.
- Long instructions and large fonts must scroll, not cover controls.
- No change to APK signing, applicationId, eye projection or frozen geometry.

## Verification Boundary

No device is attached, and user deferred device testing. Compile layout tests but do not claim screenshots or real-device verification. Do not commit, push, install or publish to a store as part of this task.

## Result

- JVM: 29 tests passed, zero failures/errors/skips.
- App and instrumentation APK builds passed; lint zero errors, 21 warnings.
- All 30 pre-existing packaged assets match the pre-redesign APK byte-for-byte.
- APK signature and applicationId unchanged; versionCode 8, versionName 1.3.
- Candidate: `releases/ar-assembly-1.3-ui-20261124/AR-Assembly-1.3.apk`.
- Instrumentation tests compiled only. Device installation, screenshots, fold/unfold behavior and camera/Beast workflow remain unverified for this candidate.
