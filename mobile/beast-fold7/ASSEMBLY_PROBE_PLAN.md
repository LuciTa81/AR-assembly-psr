# Android A-to-B candidate

Scope: separate opt-in `assembly_probe`; existing camera/workspace/eye assets and pose acceptance unchanged. No camera frame recording in this mode. Maximum 90 seconds, end five seconds after B is reached.

1. Expose copies of accepted pose rotation/translation without modifying target projection.
2. Port metric tool-plane evidence from frozen Windows `yolo_realtime.py`: undistortion, screw-plane intersection, workspace ROI, driver NMS, nested duplicates, unique handle association, image long-axis tip and 12mm/4mm distance score. Keep .30 current-target threshold and target dominance. Require at least five detected markers for this first assembly probe.
3. Candidate timing: 800ms observed near-target HOLD, 350ms maximum consecutive evidence interval, 600ms incomplete-progress retention without counting gaps. Completed HOLD checkpoint survives gaps until session end but needs fresh near-target evidence before release cue. Keep 2000ms display delay after HOLD. First actually drawn stereo green cue starts a latched 3000ms wall-clock timer. No withdrawal requirement in this explicitly timed candidate, and no claim of torque/fastening verification.
4. A-to-B only in live pilot. B does not start another hold. Stop/restart resets the session. No old inference result can count after a step transition. No green timer starts from a hidden/offscreen/stale ring or wrong display dimensions.
5. Numeric golden fixtures and Android tests for tool geometry, ambiguity, stale/out-of-order inputs, missing markers, HOLD gaps, actual draw acknowledgment, exact 3000ms boundary and reset. Existing regression tests must stay green.

This is a native Java candidate using the existing Android app, not a wholesale Unity port. Box/lid automation, all-step workflow, part preview and laptop dashboard remain later steps. Camera start requires the user's button after readiness confirmation. Preserve installed diagnostic APK in baseline before replacement.
