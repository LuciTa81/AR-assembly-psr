# Web supervision layout, 2026-11-25

## Scope

- User requested a more compact operational layout inspired by SafeOps, no transition countdown, and stable geometry when video display is toggled. App UI is deferred.
- Visually inspected the supplied SafeOps insights page and live-page loading layout, plus the existing AR production dashboard. Existing browser session was already authenticated; no account/settings/data changes were made on SafeOps.
- Adopted compact navigation, consistent spacing, restrained section titles, fixed primary viewport and scannable secondary statuses. Did not copy unrelated charts, metrics, private assets or data.

## Changes

- Main toolbar combines page title, connection status and device selection.
- Desktop: camera viewport left, current instruction right, work sequence and six status fields below. Mobile: the same sections stack in a stable order.
- Video off keeps the viewport and shows an off state. Removed both the hidden viewport attribute and toggle-dependent column reflow. Video decoding/subscription still stops when the display switch is off; the switch does not stop the phone camera or server recording.
- Removed the `remaining_ms` countdown from the web. Current action/phase and elapsed work duration remain. Actual AR step timers and the wire protocol are unchanged.
- Inactive screw-phase indicators reserve their space without appearing or being exposed to assistive technology. Detailed tracking metrics remain collapsible. Waiting, stale, live and offline connection states have distinct treatments.
- Existing recording consent/status distinction, interrupted-recording warnings, segment gaps, download/delete controls, login and ownership rules remain intact.

## Verification

- Regression reproduced against the previous build: disabled video slot was not visible.
- New production build and TypeScript checks passed.
- Playwright passed at 1920x1080, 1440x900, 820x1180, 390x844 and 320x740: exact camera/instruction/sequence/status bounds unchanged on/off; no countdown despite positive remaining time; synthetic H.264 decoded to nonblank canvas; no horizontal overflow or JS errors.
- Checked box, lid, screw, final inspection, idle and stale states, dark/light themes, recording recovery states and synthetic download/delete flow. Screenshots under `internet-supervisor/.local/recording-ui/`; these use synthetic state/video, not an actual phone capture.
- Eight focused state/auth/signout regression tests passed. No backend behavior changed in this task.

## Deployment and rollback

- Production web: `dpl_HHoJGaV8vfB23ZQXAfa4WpAEn12L` at https://ar-assembly-supervisor.vercel.app.
- Previous deployment retained: `dpl_8j4mJ5tARWPink1TC199FSrS8QaS`.
- Source backup: `internet-supervisor/.local/web-before-layout-20261125.tar.gz`.
- Only web source uploaded, through `vercel-upload-layout-20261125`; credentials and environment settings unchanged. Production login and new layout CSS delivery verified separately.
- No EC2, database, S3, APK, AR calibration or recording-enable changes. No real camera started. Real-device video rendering after this UI deployment remains a follow-up check.

## Overlay follow-up

- Current remote payload has work state and camera video, not a synchronized eye-render capture or camera-projected contour geometry. It cannot reproduce the real headset overlay merely by drawing the current stage onto arbitrary video coordinates.
- Camera-view overlays need per-frame projected points/contours or compositing at the phone encoder, with frame/timestamp alignment and stale-data hiding. A mirrored eye render is a separate view, not an accurately aligned camera composite. Both require phone-side work; neither was added or simulated here.
