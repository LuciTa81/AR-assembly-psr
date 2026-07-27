# VITURE Beast Windows AR Guidance Design

## 1. Purpose

This document defines the second-semester design for extending the existing
assembly procedure recognition pipeline into a user-facing AR guidance system.

The target system uses:

- VITURE Beast glasses without a Pro Neckband
- a Windows laptop for camera capture, inference, state reasoning, and rendering
- the Beast forward RGB camera as the worker-view input
- ArUco markers for workspace-relative pose estimation
- the existing Python realtime recognition pipeline
- a Windows Unity client for user-facing guidance

The final user experience is not a video-see-through interface. The worker sees
the real workspace directly through the glasses. The system renders only
guidance graphics, such as a target ring, direction arrow, current step, next
instruction, warnings, and completion feedback.

## 2. Current Baseline

The repository already contains a functional realtime harness:

- `server/realtime/run_realtime_server.py`
- `server/realtime/aruco_tracker.py`
- `server/realtime/roi_realtime.py`
- `server/realtime/yolo_realtime.py`
- `server/realtime/online_state_filter.py`
- `server/realtime/overlay_http_server.py`
- `server/realtime/realtime_logger.py`
- `web_overlay/`

The current pipeline can:

1. capture a Windows camera stream;
2. detect ArUco markers and generate a workspace homography;
3. extract ROI evidence;
4. run asynchronous YOLO inference for `driver`, `handle`, and `screw`;
5. advance the ordered online procedure state from S0 to S6;
6. publish a browser overlay and save replayable logs.

The latest realtime test completed the ordered sequence S0 through S6 once.
Repeated-run validation, VITURE-native display integration, camera-to-display
calibration, and user evaluation are not complete.

`client_unity/` is currently an empty placeholder. The Unity client is therefore
a new second-semester component rather than an extension of existing Unity code.

## 3. Design Decision

### 3.1 Selected architecture

The selected architecture is:

> Python realtime recognition server + Unity Windows guidance client +
> ArUco/PnP workspace alignment + per-user display calibration.

Python remains responsible for vision and state reasoning. Unity is responsible
only for rendering user guidance on the Beast display. This boundary avoids
rewriting the verified Python pipeline and keeps UI failure independent from
inference failure.

### 3.2 Why Unity is selected

Unity is selected as the final renderer because it provides:

- a stable Windows standalone application;
- secondary-display and fullscreen rendering;
- responsive 2D Canvas rendering and animation;
- a future path toward stereo or 3D visualization;
- C# support for WebSocket communication;
- an optional native-plugin path for the VITURE Glasses SDK.

The official VITURE Unity SDK is not a required dependency because it is
primarily positioned around Neckband workflows. The Beast is initially treated
as a Windows display plus UVC camera. The cross-platform VITURE Glasses SDK is
added only if direct access to camera identity, device state, 3DoF orientation,
brightness, or display mode provides measurable value.

### 3.3 Alternatives and fallback

The existing browser overlay remains the reference and fallback client.

- Browser fullscreen: fastest integration and useful for protocol testing.
- Python/PySide: acceptable emergency fallback for 2D drawing.
- WinUI/WPF: a valid alternative if Unity display behavior is unreliable.
- C++/DirectX: rejected because it would require excessive rewriting for the
  current scope.

## 4. Scope

### 4.1 Required first release

The required release supports:

- one VITURE Beast device;
- one Windows laptop;
- one known assembly kit and marker layout;
- one calibrated primary user;
- a monoscopic 2D overlay;
- S0-S6 procedure guidance;
- target highlighting for screws A-D;
- marker-loss and low-confidence handling;
- logging, replay, and quantitative evaluation.

### 4.2 Explicit non-goals

The first release does not require:

- Pro Neckband or Android deployment;
- automatic calibration for arbitrary users;
- arbitrary workspaces or assembly products;
- true focal-depth 3D holograms;
- voice commands or hand-gesture UI;
- full spatial mapping without markers;
- production certification or industrial deployment;
- replacing the Python inference pipeline with Unity inference.

## 5. System Architecture

```text
VITURE Beast RGB Camera
        |
        v
Python Realtime Server
  - frame capture
  - camera undistortion
  - ArUco detection
  - board pose estimation
  - ROI and YOLO evidence
  - online S0-S6 state filter
  - target projection
  - tracking and confidence policy
        |
        | localhost WebSocket
        v
Unity Windows Guidance Client
  - Beast display selection
  - fullscreen black background
  - target ring and direction arrow
  - current and next instruction
  - confirmation, warning, completion UI
        |
        v
VITURE Beast Display
```

The Python server is the source of truth. Unity does not infer procedure states
or decide whether a screw is complete.

## 6. Coordinate Systems and Registration

### 6.1 Coordinate systems

The system maintains explicit coordinate systems:

1. `camera_raw`: pixels from the Beast RGB camera;
2. `camera_undistorted`: pixels after lens correction;
3. `workspace`: metric coordinates on the marker-defined assembly plane;
4. `warp`: stable analysis coordinates used by ROI and YOLO features;
5. `display`: Unity pixel coordinates on the Beast display;
6. `user_profile`: per-user eye/display correction parameters.

No component may silently mix these coordinates. Every projected target carries
its source coordinate type and timestamp.

### 6.2 Existing homography role

The existing homography and warp remain in use for:

- stable ROI crops;
- YOLO-to-workspace association;
- screw A-D region definitions;
- state observation features.

The warp is an internal analysis image and is never shown to the worker.

### 6.3 PnP registration role

The AR overlay uses a pose-based projection:

1. camera intrinsics and distortion are calibrated once;
2. marker dimensions and positions are stored in metric workspace coordinates;
3. detected marker corners are matched to known workspace points;
4. `solvePnP` estimates the camera pose relative to the workspace;
5. the known 3D position of the next target screw is projected into the camera;
6. the camera projection is transformed into Beast display coordinates;
7. the per-user eye/display correction is applied;
8. Unity renders the target ring at the final display coordinate.

Although the Beast provides native 3DoF, the marker board supplies full
workspace-relative pose evidence for the current camera view. Beast 3DoF is
optional supporting evidence, not the primary registration method.

### 6.4 User calibration

The first calibration method uses four reference points:

1. the user wears the Beast in the normal working position;
2. the system projects a crosshair for each known workspace reference point;
3. the user adjusts the crosshair until it visually overlaps the real point;
4. the resulting display correction is saved as a named user profile.

If four-point calibration does not meet the error target, the workflow expands
to nine points. Calibration must be repeatable in under 60 seconds after the
initial camera calibration.

The profile is invalidated when:

- display resolution or scaling changes;
- glasses size or eye-side mode changes;
- the user changes;
- the glasses fit or nose pad changes enough to create visible error;
- the marker board geometry changes.

### 6.5 Distance and target size

The target ring can represent a physical radius on the workspace. The system
projects the target center and one or more radius reference points, allowing the
ring to appear larger when the user is closer and smaller when the user is
farther away.

The first release remains monoscopic. It aligns a 2D graphic with a point on the
known assembly plane but does not claim true optical depth placement.

## 7. Procedure State and UI State

Procedure state and UI runtime state are separate.

### 7.1 Procedure states

| Procedure state | Meaning | Next guidance target |
| --- | --- | --- |
| S0 | Empty workspace | Place enclosure box |
| S1 | Box placed | Close lid |
| S2 | Lid closed | Fasten screw A |
| S3 | Screw A complete | Fasten screw B |
| S4 | Screw B complete | Fasten screw C |
| S5 | Screw C complete | Fasten screw D |
| S6 | Screw D complete | Assembly complete |

### 7.2 UI runtime states

| UI state | User-visible behavior | Entry condition |
| --- | --- | --- |
| `STARTING` | Device and service connection status | Application launch |
| `CALIBRATION_REQUIRED` | Guided display alignment | Missing or invalid profile |
| `READY` | Initial assembly instruction | Tracking stable before guidance |
| `GUIDING` | Target ring, arrow, and next instruction | Valid target and stable pose |
| `EVIDENCE_PENDING` | Ring progress animation | Candidate action seen but not confirmed |
| `STEP_CONFIRMED` | Green ring and detected message | Procedure transition confirmed |
| `TRACKING_DEGRADED` | Hide target and request workspace view | Pose quality below threshold |
| `PAUSED` | Hold guidance and state | User pause or recoverable stop |
| `COMPLETED` | Completion and elapsed time | Procedure state S6 |
| `ERROR` | Device or service recovery message | Non-recoverable runtime failure |

UI priority is:

```text
ERROR / PAUSED
-> CALIBRATION_REQUIRED
-> TRACKING_DEGRADED
-> STEP_CONFIRMED
-> EVIDENCE_PENDING
-> GUIDING
-> READY
```

This priority prevents a stale target from remaining visible during marker loss
or a device error.

### 7.3 Transition presentation

Example:

1. Procedure state S2 and UI state `GUIDING` highlight screw A.
2. Driver evidence changes UI state to `EVIDENCE_PENDING`.
3. The online filter confirms S2 -> S3.
4. UI state becomes `STEP_CONFIRMED` for approximately 1.5 seconds.
5. Procedure state remains S3 and UI state returns to `GUIDING`.
6. The new target is screw B.

## 8. User-Facing UI

### 8.1 Beast display

The Beast display shows only:

- a pulsing ring over the current target;
- an edge arrow when the target is outside the safe overlay area;
- a compact current-step indicator;
- a one-line next instruction;
- a green confirmation state;
- short marker or alignment recovery messages;
- a completion screen.

The UI uses a black background and renders only luminous guidance elements.
The worker views the real workspace directly rather than a camera feed.

### 8.2 Visual semantics

- cyan or white: current target;
- green: confirmed action;
- amber: tracking degraded or action not yet confirmed;
- red: blocking error or incorrect-order warning.

Animated elements have stable bounds so that animation cannot move layout.
Target animation is subtle and stops during degraded tracking.

### 8.3 Off-screen and unsafe conditions

- If the target is outside the display-safe region, show an edge arrow.
- If the target is behind the user or projection is invalid, hide the target.
- If marker pose becomes stale, hide target graphics within 300 ms.
- If state confidence is low, hold the current instruction.
- If the procedure is out of order, do not advance the target.

### 8.4 Laptop debug display

The laptop debug display may show:

- raw camera frame;
- marker corners and board axes;
- estimated screw coordinates;
- YOLO boxes and driver tip;
- pose and reprojection error;
- state confidence and transition evidence;
- FPS, latency, and dropped-frame counts.

These diagnostics are not shown in the Beast user interface.

## 9. Server-Client Contract

The realtime protocol uses localhost WebSocket communication. Messages are
versioned and timestamped.

Required fields:

```json
{
  "schema_version": "realtime_overlay_v2",
  "frame_id": 1234,
  "timestamp_ms": 123456789,
  "ui_state": "GUIDING",
  "procedure_state": "S3",
  "target_id": "screw_b",
  "target_display_x": 1240.0,
  "target_display_y": 670.0,
  "target_radius_px": 34.0,
  "target_visible": true,
  "target_offscreen": false,
  "tracking_quality": 0.91,
  "state_confidence": 0.78,
  "instruction": "Fasten screw B",
  "event": ""
}
```

Unity rejects:

- unknown schema versions;
- messages older than the configured stale threshold;
- non-finite coordinates;
- target coordinates without a valid tracking status.

Unity renders at display refresh rate and interpolates only visual movement.
It never extrapolates procedure state transitions.

## 10. Error Handling

### 10.1 Device startup gate

Before feature development, the system must verify:

1. Windows identifies the Beast as a display;
2. a fullscreen test crosshair appears on the Beast;
3. Windows identifies the Beast forward camera;
4. OpenCV or the Glasses SDK captures frames from that camera;
5. camera capture and display output work simultaneously;
6. direct 2D/follow display mode produces repeatable calibration.

Failure at this gate triggers a hardware-specific investigation before Unity
feature work continues.

### 10.2 Marker loss

- short loss: retain pose for smoothing but stop updating the target;
- loss beyond 300 ms: hide physical target graphics;
- recovery: require several stable frames before restoring the target;
- prolonged loss: show a fixed request to bring workspace markers into view.

### 10.3 Communication loss

- Unity keeps the last non-positional instruction briefly;
- target graphics are hidden immediately after the stale threshold;
- reconnect occurs automatically with bounded retry;
- procedure state is resynchronized from the Python server after reconnect.

### 10.4 Calibration failure

Calibration is rejected when reprojection or alignment error exceeds its
threshold. The user is asked to repeat only the failed points rather than the
entire process.

## 11. Performance and Acceptance Targets

Initial project targets:

| Metric | Target |
| --- | --- |
| Median registration error on workspace | <= 15 mm |
| P95 registration error on workspace | <= 25 mm |
| P95 end-to-end guidance latency | <= 150 ms |
| Vision/state processing rate | 10-15 FPS |
| Unity rendering rate | 60 FPS |
| Marker availability in normal posture | >= 95% |
| Stale target removal after tracking loss | <= 300 ms |
| Repeat calibration time | <= 60 s |
| Full-sequence completion | 10 successful evaluated runs |
| Unsafe premature guidance | zero in final evaluated runs |

Targets may be tightened after the first calibrated prototype. They must not be
relaxed silently; changes require a documented reason and before/after result.

## 12. Testing Strategy

### 12.1 Automated tests

- coordinate conversion and finite-value checks;
- protocol serialization and compatibility;
- UI priority resolution;
- stale-message handling;
- state-to-target mapping;
- replay determinism for recorded sessions.

### 12.2 Calibration tests

- camera reprojection error;
- target alignment at center and corners;
- alignment at three normal head positions;
- repeated fit/remove/wear test;
- direct display mode versus optional 3DoF mode comparison.

### 12.3 End-to-end tests

- S0-S6 successful sequence;
- marker temporary occlusion;
- marker prolonged loss and recovery;
- wrong screw/tool approach;
- communication interruption and resynchronization;
- user pause and restart;
- target leaving and returning to the field of view.

### 12.4 User evaluation

Record:

- task completion time;
- per-step transition delay;
- false or premature instruction count;
- registration error at each screw;
- marker availability;
- user correction count;
- post-task usability feedback.

## 13. One-Month MVP

| Week | Scope | Exit criterion |
| --- | --- | --- |
| 1 | Beast display/camera gate and camera calibration | Beast display and forward camera operate simultaneously; calibration file saved |
| 2 | Marker-board PnP and target projection | Python test view projects screws A-D and follows normal head movement |
| 3 | Unity Windows client and WebSocket | Beast displays target ring, arrow, instruction, and tracking warning |
| 4 | S0-S6 integration and error handling | One complete assembly demonstration with synchronized logs |

The one-month MVP is limited to one user, one assembly kit, one marker layout,
monoscopic 2D guidance, and a tethered Windows laptop.

## 14. Second-Semester WBS

| ID | Period | Work item | Deliverable and completion criterion |
| --- | --- | --- | --- |
| 1 | Late July | Preserve realtime baseline | Dedicated development history, reproducible command, baseline log |
| 2 | August week 1 | Beast device integration | Display, UVC camera, resolution, and latency report |
| 3 | August week 2 | Camera and workspace calibration | Intrinsics, marker layout, metric screw coordinates |
| 4 | August week 3 | PnP registration | Stable projected coordinates for screws A-D |
| 5 | August week 4 | User display calibration | Four-point workflow and persisted user profile |
| 6 | September weeks 1-2 | Unity client foundation | Display selection, fullscreen mode, WebSocket connection |
| 7 | September weeks 3-4 | Guidance UI | Ring, arrow, instruction, warning, confirmation, completion |
| 8 | October weeks 1-2 | S0-S6 integration | Online state and target mapping connected end to end |
| 9 | October weeks 3-4 | Runtime stabilization | Smoothing, marker-loss handling, stale-target prevention |
| 10 | November weeks 1-2 | Realtime data collection | 5-10 full sessions with manual transition ground truth |
| 11 | November week 3 | State parameter retuning | Realtime-FPS transition/filter parameters and comparison report |
| 12 | November week 4 | User evaluation | Registration, latency, error, completion time, usability results |
| 13 | December weeks 1-2 | Final integration | Ten repeatable runs and deployable demo package |
| 14 | December week 3 | Documentation and presentation | GitHub history, WBS, UML, results, demo video, final report |

Additional data collection and HMM/transition parameter retuning occur after
the calibrated overlay path is stable. The online state filter is not redesigned
from zero; it is integrated and retuned for the Beast camera frame rate.

## 15. Risk Register

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Beast camera is not exposed as expected | Blocks head-view input | Verify official Glasses SDK and UVC path in the first hardware gate |
| Camera and display cannot run together | Blocks integrated setup | Test USB mode, firmware, direct connection, and supported adapters early |
| Camera-eye parallax causes large error | Misaligned target | Per-user calibration, metric PnP, restricted working depth |
| Native 3DoF conflicts with marker overlay | Drifting or doubled motion | Begin in direct 2D/follow mode; compare modes after baseline |
| Marker occlusion by hands | Missing target | Multiple markers, pose quality gate, short fallback, quick hide |
| UI appears correct but state advances early | Unsafe instruction | Keep state authority in Python and require ordered evidence |
| Unity schedule expands | Delays core demonstration | Maintain browser overlay as a working fallback |
| Single-session overfitting | Weak evidence | Collect repeated realtime sessions and manual transition ground truth |

## 16. Implementation Boundary

The implementation plan must preserve these ownership boundaries:

- Python vision modules produce observations and workspace pose.
- Python state modules own S0-S6 transitions.
- A projection module owns workspace-to-display target conversion.
- A protocol module owns message validation and versioning.
- Unity owns presentation and local UI animation only.
- Logging records raw evidence, projected target, UI message, and transition event
  using synchronized frame and timestamp identifiers.

These boundaries allow the browser fallback, Unity client, and future clients to
consume the same server contract without duplicating procedure logic.

## 17. Definition of Done

The second-semester AR guidance system is complete when:

1. a user connects the Beast to the Windows laptop;
2. the application validates camera and display availability;
3. the user loads or completes calibration;
4. the system detects the marker-defined workspace;
5. S0-S6 guidance is shown on the Beast;
6. screw targets A-D are visually aligned with the real screw positions;
7. lost tracking removes stale physical guidance safely;
8. the full assembly completes repeatedly;
9. results are logged and reproduced through replay;
10. registration, latency, transition, and usability results are documented.

## 18. References

- VITURE XR Glasses SDK:
  <https://www.viture.com/developer/glasses-sdk/glasses>
- VITURE Developer:
  <https://www.viture.com/developer>
- Unity multi-display:
  <https://docs.unity3d.com/Manual/MultiDisplay.html>
- Unity native plugins:
  <https://docs.unity3d.com/Manual/NativePlugins.html>
