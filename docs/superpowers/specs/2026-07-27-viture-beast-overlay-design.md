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
> multi-marker ArUco/PnP workspace alignment + per-user display calibration.

Python remains responsible for vision and state reasoning. Unity is responsible
only for rendering user guidance on the Beast display. This boundary avoids
rewriting the verified Python pipeline and keeps UI failure independent from
inference failure.

The Python runtime separates fast workspace-pose updates from slower recognition
updates. A slow YOLO inference must never delay the latest ArUco/PnP pose.

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
- a monoscopic or dominant-eye 2D overlay;
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
- independently calibrated stereo rendering unless the Windows display mode is
  first verified to expose controllable left-eye and right-eye images.

## 5. System Architecture

```text
VITURE Beast RGB Camera
        |
        v
Latest-Frame Capture Buffer
        |
        +------------------------------+
        |                              |
        v                              v
Fast Pose Worker                 Recognition Worker
  - camera undistortion            - ROI evidence
  - multi-marker ArUco              - asynchronous YOLO
  - board pose and quality          - online S0-S6 filter
  - target projection               - target_id selection
  - target visibility policy
        |                              |
        +---------------+--------------+
                        v
Python Realtime Message Publisher
  - synchronized pose and state snapshots
  - calibration profile
  - logging and quality metrics
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

The capture buffer has capacity one: a new camera frame replaces an unprocessed
frame instead of extending a queue. The pose worker runs at the highest stable
rate supported by the selected camera mode. Recognition may run at a lower rate
and publishes its latest valid result with its own timestamp. The publisher
combines only timestamped snapshots and reports their ages explicitly.

The pose worker also publishes a capacity-one `TrackedFrame` containing the
source frame and the pose/homography calculated from that exact `frame_id`.
Recognition consumes this matched object rather than applying a pose from one
frame to pixels from another frame.

The MVP uses a fixed direct 2D or 0DoF display mode. SpaceWalker, Anchor, and
other device-side motion modes remain disabled so that they cannot apply a
second transformation to an already registered target.

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

Workspace geometry is stored in millimetres. The metric marker-layout artifact
defines its axis convention, marker corner order, and screw A-D positions.
Transformation matrices are named by direction, such as
`camera_from_workspace`, and serialized as row-major 4x4 arrays.

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
2. the existing asymmetric six-marker layout is represented as one metric
   `cv2.aruco.Board`;
3. marker dimensions and positions are stored in metric workspace coordinates;
4. detected marker corners are matched to known workspace points;
5. robust PnP estimates `camera_from_workspace`;
6. marker inliers, reprojection error, pose age, and pose jumps determine whether
   the pose is usable;
7. the known 3D position of the next target screw is projected into the camera;
8. the per-user display correction transforms it into Beast display coordinates;
9. Unity renders the target ring at the final display coordinate.

A ChArUco board is used for camera intrinsic calibration when practical. It does
not automatically replace the runtime marker layout, because the existing
distributed markers provide better visibility around the physical assembly
workspace.

Although the Beast provides native 3DoF, the marker board supplies
workspace-relative camera pose evidence. Device IMU fusion is not part of the
MVP because it adds clock synchronization and sensor-fusion risk before the
camera-only registration baseline is measured.

### 6.4 User calibration

The primary MVP calibration uses nine reference points distributed across the
safe display and workspace overlap:

1. the user wears the Beast in the normal working position;
2. the system projects a crosshair for each known workspace reference point;
3. the user adjusts the crosshair until it visually overlaps the real point;
4. the system fits the monoscopic or dominant-eye display correction using all
   accepted points;
5. the resulting correction and residual errors are saved as a named user
   profile.

Four points are retained only as a quick recenter workflow after a valid
nine-point profile already exists. Nine points improve robustness but do not by
themselves remove camera-eye parallax. The MVP therefore restricts the user,
glasses fit, work plane, and normal working distance. Calibration must be
repeatable in under 60 seconds after the initial profile is created.

The profile is invalidated when:

- display resolution or scaling changes;
- direct/0DoF display mode or eye-side mode changes;
- the user changes;
- the glasses fit or nose pad changes enough to create visible error;
- the marker board geometry changes.

Each profile records the user identifier, dominant-eye mode, display resolution,
Windows scaling, device display mode, camera mode, marker-layout version, and
creation timestamp.

### 6.5 Distance and target size

The target ring can represent a physical radius on the workspace. The system
projects the target center and one or more radius reference points, allowing the
ring to appear larger when the user is closer and smaller when the user is
farther away.

The first release remains monoscopic. It aligns a 2D graphic with a point on the
known assembly plane but does not claim true optical depth placement.

The target is drawn as a comparatively large hollow ring with a contrasting
outline. The real screw remains visible through the centre.

### 6.6 Deferred per-eye projection

Independent left-eye and right-eye projection is a second-stage experiment, not
an MVP dependency. It begins only after a hardware spike verifies that the Beast
Windows mode exposes independently controllable eye images with repeatable
geometry.

If supported, the experiment may estimate per-eye projection parameters and
compare binocular, dominant-eye, and stereo target rendering. A nine-point
single-pose calibration is not treated as proof of full head-motion or
multi-depth accuracy; the experiment must include multiple normal head poses and
an explicit camera-eye model.

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
- If marker pose becomes stale, hide positional target graphics within 150 ms.
- If state confidence is low, hold the current instruction.
- If the procedure is out of order, do not advance the target.

Non-positional text may remain briefly after target graphics are hidden so that
the worker understands why guidance paused.

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
  "pose_frame_id": 1234,
  "pose_capture_timestamp_ms": 123456700,
  "pose_computed_timestamp_ms": 123456730,
  "state_frame_id": 1228,
  "state_capture_timestamp_ms": 123456620,
  "state_computed_timestamp_ms": 123456650,
  "published_timestamp_ms": 123456750,
  "pose_age_ms": 50,
  "state_age_ms": 130,
  "calibration_profile_id": "user01_beast_1920x1200_direct",
  "ui_state": "GUIDING",
  "procedure_state": "S3",
  "target_id": "screw_b",
  "target_workspace_xyz_mm": [125.0, 80.0, 0.0],
  "camera_from_workspace": [
    [1.0, 0.0, 0.0, 12.0],
    [0.0, 1.0, 0.0, -35.0],
    [0.0, 0.0, 1.0, 540.0],
    [0.0, 0.0, 0.0, 1.0]
  ],
  "target_display_x": 1240.0,
  "target_display_y": 670.0,
  "target_radius_px": 34.0,
  "target_visible": true,
  "target_offscreen": false,
  "tracking_quality": 0.91,
  "reprojection_error_px": 1.8,
  "marker_inlier_count": 16,
  "state_confidence": 0.78,
  "instruction": "Fasten screw B",
  "event": ""
}
```

Unity rejects:

- unknown schema versions;
- pose snapshots older than the positional stale threshold;
- non-finite coordinates;
- target coordinates without a valid tracking status.

Unity renders at display refresh rate and interpolates only visual movement.
It never extrapolates procedure state transitions.

For the MVP, Python remains the reference implementation of
workspace-to-display projection and `target_display_x/y` are authoritative.
Workspace targets and pose matrices are also transmitted for diagnostics,
recording, and the deferred per-eye experiment.

Pose and state ages are calculated from their source-frame capture timestamps,
not from inference-completion timestamps. This exposes sensor-to-message delay
instead of hiding processing time.

## 10. Error Handling

### 10.1 Device startup gate

Before feature development, the system must verify:

1. Windows identifies the Beast as a display;
2. a fullscreen test crosshair appears on the Beast;
3. Windows identifies the Beast forward camera;
4. the camera is identified by a stable device descriptor rather than an
   assumed camera index alone;
5. supported resolution and FPS combinations are enumerated;
6. OpenCV or the Glasses SDK captures frames from that camera;
7. camera capture and display output work simultaneously for at least 30 minutes;
8. camera FOV and display-safe FOV overlap across the screw A-D work area;
9. head movement, motion blur, exposure, direct USB-C, and adapter behaviour are
   recorded;
10. direct 2D/0DoF mode, fixed Windows scaling, brightness, and tint produce
    repeatable calibration.

Failure at this gate triggers a hardware-specific investigation before Unity
feature work continues.

### 10.2 Marker loss

- short loss: retain pose for smoothing but stop updating the target;
- pose age beyond 150 ms: hide physical target graphics;
- recovery: require several stable frames before restoring the target;
- prolonged loss: show a fixed request to bring workspace markers into view.

A pose is also rejected when reprojection error, inlier count, or frame-to-frame
pose jump exceeds its configured limit. Marker count alone is insufficient.

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
| Correct target identification | P95 error <= one third of minimum adjacent-screw spacing |
| Wrong-screw guidance | zero in final evaluated runs |
| Precision-ring registration, stretch goal | median <= 8 mm and P95 <= 15 mm |
| Fast pose update rate | >= 25 FPS, with 30 FPS as the preferred target |
| P95 pose capture-to-message latency | <= 75 ms, with <= 50 ms as the preferred target |
| Recognition/state processing rate | 10-15 FPS |
| P95 state-guidance latency | <= 250 ms |
| Unity rendering rate | 60 FPS |
| Marker availability in normal posture | >= 95% |
| Stale positional target removal | <= 150 ms |
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
- latest-frame replacement without queue growth;
- pose and state snapshot age calculation;
- pose rejection using reprojection error, inliers, and jump limits.

### 12.2 Calibration tests

- camera reprojection error;
- target alignment at center and corners;
- alignment at three normal head positions;
- repeated fit/remove/wear test;
- direct display mode repeatability;
- camera/display FOV overlap and safe-region clipping.

### 12.3 End-to-end tests

- S0-S6 successful sequence;
- marker temporary occlusion;
- marker prolonged loss and recovery;
- wrong screw/tool approach;
- communication interruption and resynchronization;
- user pause and restart;
- target leaving and returning to the field of view.
- camera-display simultaneous operation for 30 minutes;
- five to ten distinct Beast-camera sessions with manual transition ground truth.

Repeated playback of the same recording verifies determinism, not recognition
generalization. Accuracy and premature-transition claims use distinct physical
sessions.

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
| 1 | Beast hardware, FOV, direct-display, and camera-intrinsic gate | Stable camera mode, simultaneous display/capture, FOV report, and calibration file saved |
| 2 | Fast multi-marker pose path and target projection | Latest-frame PnP projects screws A-D with timestamped pose quality and no recognition-induced delay |
| 3 | Unity Windows client and WebSocket | Beast displays target ring, arrow, instruction, and tracking warning |
| 4 | Nine-point display calibration, S0-S6 integration, and error handling | One complete assembly demonstration with synchronized logs and measured registration error |

The one-month MVP is limited to one user, one assembly kit, one marker layout,
monoscopic 2D guidance, and a tethered Windows laptop.

## 14. Second-Semester WBS

| ID | Period | Work item | Deliverable and completion criterion |
| --- | --- | --- | --- |
| 1 | Late July | Preserve realtime baseline | Dedicated development history, reproducible command, baseline log |
| 2 | August week 1 | Beast device integration | Display, UVC camera, resolution, and latency report |
| 3 | August week 2 | Camera and workspace calibration | Intrinsics, metric multi-marker board, metric screw coordinates |
| 4 | August week 3 | Fast PnP registration | Latest-frame pose worker, quality gate, stable projected coordinates for screws A-D |
| 5 | August week 4 | User display calibration | Nine-point monoscopic/dominant-eye workflow, four-point recenter, persisted profile |
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
| Native 3DoF conflicts with marker overlay | Drifting or doubled motion | Disable SpaceWalker/Anchor and use fixed direct 2D/0DoF mode for the MVP |
| Marker occlusion by hands | Missing target | Multiple markers, pose quality gate, short fallback, quick hide |
| Slow recognition delays target motion | Ring lags during head movement | Latest-frame buffer and independent fast pose worker |
| Camera and display FOV do not overlap | Target cannot be shown where the user works | Measure overlap before Unity work and restrict the safe work region |
| UI appears correct but state advances early | Unsafe instruction | Keep state authority in Python and require ordered evidence |
| Unity schedule expands | Delays core demonstration | Maintain browser overlay as a working fallback |
| Single-session overfitting | Weak evidence | Collect repeated realtime sessions and manual transition ground truth |

## 16. Implementation Boundary

The implementation plan must preserve these ownership boundaries:

- Python vision modules produce observations and workspace pose.
- Python state modules own S0-S6 transitions.
- A Python projection module owns the MVP workspace-to-display target conversion.
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
5. fast pose updates continue independently of slower recognition;
6. S0-S6 guidance is shown on the Beast;
7. screw targets A-D are visually aligned with the real screw positions;
8. wrong-screw guidance is absent from the final evaluated runs;
9. lost tracking removes stale physical guidance within 150 ms;
10. the full assembly completes repeatedly in distinct Beast-camera sessions;
11. results are logged and reproduced through replay;
12. registration, latency, transition, and usability results are documented.

## 18. References

- VITURE XR Glasses SDK:
  <https://www.viture.com/developer/glasses-sdk/glasses>
- VITURE Developer:
  <https://www.viture.com/developer>
- Unity multi-display:
  <https://docs.unity3d.com/Manual/MultiDisplay.html>
- Unity native plugins:
  <https://docs.unity3d.com/Manual/NativePlugins.html>
