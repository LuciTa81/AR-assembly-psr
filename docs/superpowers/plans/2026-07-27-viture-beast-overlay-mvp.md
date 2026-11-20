# VITURE Beast AR Guidance MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tethered Windows/VITURE Beast MVP that keeps S0-S6 procedure reasoning in Python and displays a safely registered screw target, instruction, warning, and completion UI on the glasses.

**Architecture:** A capacity-one capture buffer feeds an independent fast multi-marker pose worker and a slower ROI/YOLO/state worker. Python combines timestamped snapshots, performs the MVP workspace-to-display projection, and publishes schema-versioned messages to the existing browser fallback and a new Unity Windows client. Unity renders only; it never decides procedure state or screw completion.

**Tech Stack:** Python 3.11, OpenCV contrib, NumPy, PyYAML, Ultralytics YOLO, pytest, `websockets` 15.x, Unity Windows Standalone, C#/.NET `ClientWebSocket`, Unity UI Toolkit.

## Global Constraints

- Scope is one VITURE Beast, one Windows laptop, one assembly kit, one metric marker layout, and one calibrated primary user.
- MVP output is monoscopic or dominant-eye 2D guidance; independent per-eye stereo is deferred until Windows eye-image control is proven.
- Python is the source of truth for ArUco/PnP, ROI/YOLO evidence, S0-S6 state, target selection, and MVP workspace-to-display projection.
- Unity owns display selection, UI state presentation, interpolation, and animation only.
- SpaceWalker, Anchor, and device-side motion transformations remain disabled; use fixed direct 2D/0DoF output.
- Workspace units are millimetres. Use `camera_from_workspace` for the row-major 4x4 workspace-to-camera transform.
- Capture buffering has capacity one. New frames replace unprocessed frames; no unbounded frame queue is allowed.
- Fast pose target is at least 25 FPS with 30 FPS preferred; P95 pose capture-to-message latency is at most 75 ms with 50 ms preferred.
- Recognition/state processing target is 10-15 FPS; P95 state-guidance latency is at most 250 ms.
- Positional target graphics disappear when pose age exceeds 150 ms. Non-positional text may remain with a tracking warning.
- Wrong-screw guidance must be zero in the final evaluated runs.
- Preserve the current sequential browser harness until the threaded v2 path passes replay and camera smoke tests.
- Do not add MediaPipe to the MVP critical path.

---

### Task 1: Establish the Automated Test and Hardware-Gate Foundation

**Files:**
- Create: `server/realtime/requirements-dev.txt`
- Create: `tests/realtime/__init__.py`
- Create: `tests/realtime/test_probe_cameras.py`
- Modify: `server/realtime/probe_cameras.py:18-104`
- Create: `scripts/run_beast_hardware_gate.ps1`
- Create: `docs/beast_hardware_gate.md`

**Interfaces:**
- Produces: `probe_mode(index: int, backend: int, width: int, height: int, requested_fps: float, sample_seconds: float) -> dict`
- Produces: `outputs/realtime_camera_probe/beast_camera_modes.csv`
- Produces: a hardware report recording display/camera concurrency, camera/display FOV overlap, blur, tint, scaling, and USB connection.

- [ ] **Step 1: Add the realtime development dependencies**

Create `server/realtime/requirements-dev.txt`:

```text
-r requirements-realtime.txt
pytest==8.4.1
websockets==15.0.1
```

- [ ] **Step 2: Write the failing camera-probe tests**

Create `tests/realtime/test_probe_cameras.py` with a fake `cv2.VideoCapture` and tests that assert:

```python
def test_probe_mode_reports_requested_and_actual_mode(monkeypatch):
    row, frame = probe_mode(
        index=1,
        backend=700,
        width=1280,
        height=720,
        requested_fps=30.0,
        sample_seconds=0.05,
    )
    assert row["index"] == 1
    assert row["requested_width"] == 1280
    assert row["requested_height"] == 720
    assert row["requested_fps"] == 30.0
    assert row["actual_width"] == 1280
    assert row["actual_height"] == 720
    assert row["frames_read"] > 0
    assert row["measured_fps"] > 0
    assert frame is not None


def test_probe_mode_closes_failed_capture(monkeypatch):
    row, frame = probe_mode(7, 700, 640, 480, 30.0, 0.01)
    assert row["opened"] is False
    assert row["read_ok"] is False
    assert frame is None
```

- [ ] **Step 3: Run the tests and verify they fail**

Run:

```powershell
.\.venv_rt\Scripts\python.exe -m pip install -r server\realtime\requirements-dev.txt
.\.venv_rt\Scripts\python.exe -m pytest tests\realtime\test_probe_cameras.py -v
```

Expected: FAIL because `probe_mode` does not exist.

- [ ] **Step 4: Extend the camera probe**

Refactor `probe_index` to call `probe_mode`. Add CLI options:

```python
parser.add_argument("--modes", default="640x480@30,1280x720@30,1920x1080@30")
parser.add_argument("--sample-seconds", type=float, default=3.0)
```

Each CSV row must include:

```python
[
    "index", "backend", "opened", "read_ok",
    "requested_width", "requested_height", "requested_fps",
    "actual_width", "actual_height", "fps_property",
    "frames_read", "measured_fps", "read_failures",
    "mean_read_ms", "p95_read_ms", "preview_path",
]
```

- [ ] **Step 5: Add the repeatable hardware-gate script**

Create `scripts/run_beast_hardware_gate.ps1` to:

1. activate `.venv_rt` by calling its Python executable directly;
2. run the DirectShow and MSMF camera probes without opening two cameras concurrently;
3. save previews and CSV files;
4. print the manual checklist path.

The script must not assume camera index `1` is permanently the Beast camera.

- [ ] **Step 6: Write the manual gate checklist**

Create `docs/beast_hardware_gate.md` with checkboxes for:

- Beast display visible in Windows;
- Windows scaling and resolution recorded;
- direct 2D/0DoF mode active, SpaceWalker/Anchor off;
- camera identity confirmed from preview, not index alone;
- chosen mode and measured FPS recorded;
- camera and fullscreen black/crosshair display run together for 30 minutes;
- all screw A-D positions lie inside both camera FOV and display-safe FOV;
- direct USB-C and adapter behaviour compared;
- blur during normal head movement recorded;
- brightness, minimum practical tint, and task lighting recorded.

- [ ] **Step 7: Verify**

Run:

```powershell
.\.venv_rt\Scripts\python.exe -m pytest tests\realtime\test_probe_cameras.py -v
.\scripts\run_beast_hardware_gate.ps1
```

Expected: tests PASS; the script creates camera-mode CSV and preview artifacts.

- [ ] **Step 8: Commit**

```powershell
git add server/realtime/requirements-dev.txt server/realtime/probe_cameras.py tests/realtime/__init__.py tests/realtime/test_probe_cameras.py scripts/run_beast_hardware_gate.ps1 docs/beast_hardware_gate.md
git commit -m "Add repeatable Beast hardware capability gate"
```

---

### Task 2: Define Realtime Overlay Protocol v2

**Files:**
- Modify: `server/realtime/schemas.py:17-54`
- Create: `tests/realtime/test_schemas_v2.py`
- Create: `docs/realtime_overlay_v2_schema.json`

**Interfaces:**
- Produces: `PoseSnapshot`
- Produces: `RecognitionSnapshot`
- Produces: `OverlayMessageV2.to_dict() -> dict`
- Preserves: `FramePacket.timestamp_ms` as a compatibility property returning `capture_timestamp_ms`.

- [ ] **Step 1: Write failing schema tests**

Create tests for:

```python
def test_frame_packet_timestamp_alias():
    packet = FramePacket(
        frame_id=8,
        capture_timestamp_ms=1200,
        source="camera",
        frame=None,
    )
    assert packet.timestamp_ms == 1200


def test_overlay_v2_serializes_pose_and_state_ages():
    message = OverlayMessageV2(
        pose_frame_id=11,
        pose_capture_timestamp_ms=1000,
        pose_computed_timestamp_ms=1030,
        state_frame_id=9,
        state_capture_timestamp_ms=900,
        state_computed_timestamp_ms=940,
        published_timestamp_ms=1050,
        calibration_profile_id="user01_direct",
        procedure_state="S3",
        target_id="screw_b",
        target_workspace_xyz_mm=(125.0, 80.0, 0.0),
        camera_from_workspace=IDENTITY_4X4,
        target_display_xy=(1240.0, 670.0),
        tracking_status="OK",
        tracking_quality=0.9,
        reprojection_error_px=1.8,
        marker_inlier_count=16,
    )
    data = message.to_dict()
    assert data["schema_version"] == "realtime_overlay_v2"
    assert data["pose_age_ms"] == 50
    assert data["state_age_ms"] == 150
    assert data["target_display_x"] == 1240.0
    assert data["camera_from_workspace"][3] == [0.0, 0.0, 0.0, 1.0]
```

Also test that non-finite display coordinates force `target_visible=False`.

- [ ] **Step 2: Run the tests and verify they fail**

```powershell
.\.venv_rt\Scripts\python.exe -m pytest tests\realtime\test_schemas_v2.py -v
```

Expected: FAIL because the v2 types are undefined.

- [ ] **Step 3: Implement the dataclasses**

Use immutable tuple-based matrix and coordinate fields in the public schema:

```python
Matrix4x4 = Tuple[
    Tuple[float, float, float, float],
    Tuple[float, float, float, float],
    Tuple[float, float, float, float],
    Tuple[float, float, float, float],
]


@dataclass(frozen=True)
class PoseSnapshot:
    frame_id: int
    capture_timestamp_ms: int
    computed_timestamp_ms: int
    tracking_status: str
    marker_count: int
    marker_inlier_count: int
    tracking_quality: float
    reprojection_error_px: float
    camera_from_workspace: Matrix4x4
    homography: Any = field(default=None, repr=False, compare=False)


@dataclass(frozen=True)
class RecognitionSnapshot:
    frame_id: int
    capture_timestamp_ms: int
    computed_timestamp_ms: int
    procedure_state: str
    current_label: str
    next_action: str
    target_id: str
    state_confidence: float
    held_reason: str = ""
    transition_event: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)
```

`OverlayMessageV2.to_dict()` computes ages from `published_timestamp_ms` and emits flat JSON-compatible lists.

- [ ] **Step 4: Add a machine-readable schema**

Create `docs/realtime_overlay_v2_schema.json` using JSON Schema draft 2020-12. Mark timestamps, ages, target identifiers, pose quality, visibility, warning, and projection coordinates as explicit properties. Set `additionalProperties` to `false` at the top level.

- [ ] **Step 5: Verify**

```powershell
.\.venv_rt\Scripts\python.exe -m pytest tests\realtime\test_schemas_v2.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add server/realtime/schemas.py tests/realtime/test_schemas_v2.py docs/realtime_overlay_v2_schema.json
git commit -m "Define timestamped realtime overlay protocol v2"
```

---

### Task 3: Add Capacity-One Capture and Snapshot Stores

**Files:**
- Create: `server/realtime/latest_value.py`
- Create: `server/realtime/runtime_workers.py`
- Modify: `server/realtime/frame_source.py:17-98`
- Create: `tests/realtime/test_latest_value.py`
- Create: `tests/realtime/test_capture_worker.py`

**Interfaces:**
- Produces: `LatestValue[T].publish(version: int, value: T) -> None`
- Produces: `LatestValue[T].wait_for_newer(last_version: int, timeout_s: float) -> Optional[Tuple[int, T]]`
- Produces: `CaptureWorker(source: BaseFrameSource, frames: LatestValue[FramePacket])`
- Produces: `TrackedFrame(packet: FramePacket, pose: PoseSnapshot)`
- Guarantees: no collection stores more than one frame.

- [ ] **Step 1: Write failing latest-value tests**

```python
def test_publish_replaces_unconsumed_value():
    latest = LatestValue[str]()
    latest.publish(1, "old")
    latest.publish(2, "new")
    assert latest.snapshot() == (2, "new")


def test_wait_for_newer_ignores_same_version():
    latest = LatestValue[str]()
    latest.publish(3, "same")
    assert latest.wait_for_newer(3, timeout_s=0.01) is None


def test_close_releases_waiter():
    latest = LatestValue[str]()
    latest.close()
    assert latest.wait_for_newer(-1, timeout_s=0.01) is None
```

- [ ] **Step 2: Run and verify failure**

```powershell
.\.venv_rt\Scripts\python.exe -m pytest tests\realtime\test_latest_value.py tests\realtime\test_capture_worker.py -v
```

Expected: FAIL because `LatestValue` and `CaptureWorker` do not exist.

- [ ] **Step 3: Implement `LatestValue` with one condition variable**

`LatestValue` stores only `_version`, `_value`, and `_closed`. Publishing replaces `_value` and calls `notify_all()`. It must not use `queue.Queue`.

- [ ] **Step 4: Implement `CaptureWorker`**

The worker iterates the existing `BaseFrameSource` in one daemon thread and publishes each `FramePacket` by `frame_id`. It records:

```python
captured_frames
replaced_frames
last_capture_error
```

Update `FramePacket` construction in all frame sources to use `capture_timestamp_ms`.

- [ ] **Step 5: Verify**

```powershell
.\.venv_rt\Scripts\python.exe -m pytest tests\realtime\test_latest_value.py tests\realtime\test_capture_worker.py -v
```

Expected: PASS, including a fake source that produces three frames before one read and returns frame 3.

- [ ] **Step 6: Commit**

```powershell
git add server/realtime/latest_value.py server/realtime/runtime_workers.py server/realtime/frame_source.py tests/realtime/test_latest_value.py tests/realtime/test_capture_worker.py
git commit -m "Add latest-frame capture primitives"
```

---

### Task 4: Create Metric Workspace and Camera-Intrinsic Artifacts

**Files:**
- Create: `server/realtime/workspace_geometry.py`
- Create: `server/tools/build_metric_workspace.py`
- Create: `server/tools/generate_charuco_board.py`
- Create: `server/tools/calibrate_camera_charuco.py`
- Create: `tests/realtime/fixtures/marker_layout_pixels.yaml`
- Create: `tests/realtime/fixtures/roi_layout_pixels.yaml`
- Create: `tests/realtime/test_workspace_geometry.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `WorkspaceGeometry.load(path: Path) -> WorkspaceGeometry`
- Produces: `WorkspaceGeometry.marker_corners_mm: Dict[int, np.ndarray]`
- Produces: `WorkspaceGeometry.targets_mm: Dict[str, np.ndarray]`
- Produces: `configs/calibration/workspace_metric_v1.yaml`
- Produces: `configs/calibration/beast_camera_intrinsics.yaml`

- [ ] **Step 1: Write a synthetic conversion test**

The fixture uses a 100-pixel marker declared as 50 mm. Assert:

```python
def test_build_metric_workspace_scales_and_flips_y(tmp_path):
    output = build_metric_workspace(
        pixel_layout_path=PIXEL_LAYOUT,
        roi_layout_path=ROI_LAYOUT,
        marker_size_mm=50.0,
        output_path=tmp_path / "workspace.yaml",
    )
    geometry = WorkspaceGeometry.load(output)
    assert geometry.units == "mm"
    assert geometry.axis_convention == "x_right_y_away_z_up"
    assert np.isclose(
        np.linalg.norm(
            geometry.marker_corners_mm[0][1]
            - geometry.marker_corners_mm[0][0]
        ),
        50.0,
        atol=0.5,
    )
    assert set(geometry.targets_mm) == {
        "screw_a", "screw_b", "screw_c", "screw_d"
    }
```

- [ ] **Step 2: Run and verify failure**

```powershell
.\.venv_rt\Scripts\python.exe -m pytest tests\realtime\test_workspace_geometry.py -v
```

Expected: FAIL because the geometry loader and builder do not exist.

- [ ] **Step 3: Implement metric workspace generation**

`build_metric_workspace.py` must:

1. calculate median marker side length in pixel-layout coordinates;
2. derive millimetres per warp pixel from the measured black-square side;
3. set origin at the bottom-left outer workspace anchor;
4. set +X right, +Y from the bottom marker row toward the top row, and +Z above the work plane;
5. convert every marker corner and screw ROI centre to `[x_mm, y_mm, 0.0]`;
6. write dictionary name, source layout hashes, axis convention, markers, and targets.

Measure the printed black-square side and run:

```powershell
$M = Read-Host "Enter the measured black-square side in millimetres"
.\.venv_rt\Scripts\python.exe server\tools\build_metric_workspace.py `
  --pixel-layout configs\marker_layout_v2_session_17.yaml `
  --roi-layout configs\roi_layout_v2.yaml `
  --marker-size-mm $M `
  --output configs\calibration\workspace_metric_v1.yaml
```

- [ ] **Step 4: Implement ChArUco intrinsic calibration tools**

`generate_charuco_board.py` writes a printable board PDF or PNG plus metadata. `calibrate_camera_charuco.py` captures accepted views only when board coverage and corner count pass configured limits, then writes:

```yaml
schema_version: camera_intrinsics_v1
image_width: 1280
image_height: 720
camera_matrix: [[1000.0, 0.0, 640.0], [0.0, 1000.0, 360.0], [0.0, 0.0, 1.0]]
dist_coeffs: [0.0, 0.0, 0.0, 0.0, 0.0]
reprojection_error_px: 0.42
camera_mode: "1280x720@30"
```

The block above defines the tested file shape only. The tracked project artifact
must contain numeric values generated from the Beast camera and must never reuse
the illustrative matrix.

- [ ] **Step 5: Protect replaceable personal calibration artifacts**

Add to `.gitignore`:

```text
configs/calibration/user_profiles/
outputs/beast_calibration/
```

Keep the workspace metric artifact and the selected Beast camera intrinsic artifact tracked because the project uses one fixed device and board. Recalibration changes must be committed with a reason.

- [ ] **Step 6: Verify**

```powershell
.\.venv_rt\Scripts\python.exe -m pytest tests\realtime\test_workspace_geometry.py -v
.\.venv_rt\Scripts\python.exe server\tools\build_metric_workspace.py --help
.\.venv_rt\Scripts\python.exe server\tools\calibrate_camera_charuco.py --help
```

Expected: tests PASS; both tools show usage without opening the camera.

- [ ] **Step 7: Commit**

```powershell
git add .gitignore server/realtime/workspace_geometry.py server/tools/build_metric_workspace.py server/tools/generate_charuco_board.py server/tools/calibrate_camera_charuco.py tests/realtime/fixtures/marker_layout_pixels.yaml tests/realtime/fixtures/roi_layout_pixels.yaml tests/realtime/test_workspace_geometry.py
git commit -m "Add metric workspace and Beast camera calibration tools"
```

After real calibration:

```powershell
git add configs/calibration/workspace_metric_v1.yaml configs/calibration/beast_camera_intrinsics.yaml
git commit -m "Record measured Beast workspace calibration"
```

---

### Task 5: Add Robust Multi-Marker Pose and Projection

**Files:**
- Modify: `server/realtime/aruco_tracker.py:12-176`
- Create: `server/realtime/projection.py`
- Create: `tests/realtime/test_aruco_pose.py`
- Create: `tests/realtime/test_projection.py`
- Modify: `configs/realtime_viture_beast_aruco.yaml`

**Interfaces:**
- Produces: `ArUcoRealtimeTracker.process(frame_bgr, capture_timestamp_ms) -> PoseSnapshot`
- Produces: `DisplayCalibrationProfile.load(path) -> DisplayCalibrationProfile`
- Produces: `project_target(pose, target_workspace_xyz_mm, intrinsics, profile, display_size) -> ProjectionResult`

- [ ] **Step 1: Write a synthetic pose-estimation test**

Generate known marker image points using `cv2.projectPoints`, inject them through a fake detector, and assert:

```python
assert result.tracking_status == "OK"
assert result.marker_inlier_count >= 12
assert result.reprojection_error_px < 0.5
assert np.allclose(
    np.asarray(result.camera_from_workspace)[:3, 3],
    expected_translation,
    atol=2.0,
)
```

Add rejection cases for too few inliers, excessive reprojection error, and an excessive frame-to-frame pose jump.

- [ ] **Step 2: Write projection tests**

Test:

- target centre projection;
- physical ring radius projection from a second workspace point;
- off-screen edge-arrow direction;
- non-finite input rejection;
- pose older than 150 ms hides the positional target.

- [ ] **Step 3: Run and verify failure**

```powershell
.\.venv_rt\Scripts\python.exe -m pytest tests\realtime\test_aruco_pose.py tests\realtime\test_projection.py -v
```

Expected: FAIL because pose and projection interfaces are missing.

- [ ] **Step 4: Extend the ArUco tracker without breaking homography**

Keep current homography output for ROI/YOLO. Add:

- camera intrinsic loading;
- metric marker correspondences;
- `cv2.solvePnPRansac`;
- optional `cv2.solvePnPRefineLM`;
- reprojection-error calculation;
- inlier count and normalized tracking quality;
- configurable translation and rotation jump limits;
- a fresh-pose timestamp separate from homography fallback age.

A previous homography may support ROI briefly, but a previous pose beyond 150 ms must never keep the target ring visible.

- [ ] **Step 5: Implement the MVP projection**

`projection.py` performs:

```text
target_workspace_xyz_mm
-> camera pixel through camera_from_workspace and intrinsics
-> display pixel through the saved display_from_camera_px homography
-> safe-region clipping and edge-arrow metadata
```

Python owns these output pixels for the MVP. Return workspace target and pose as diagnostics as well.

- [ ] **Step 6: Add pose and projection configuration**

Extend `configs/realtime_viture_beast_aruco.yaml`:

```yaml
pose:
  enabled: true
  workspace_geometry: configs/calibration/workspace_metric_v1.yaml
  camera_intrinsics: configs/calibration/beast_camera_intrinsics.yaml
  min_inlier_corners: 12
  max_reprojection_error_px: 4.0
  max_translation_jump_mm: 45.0
  max_rotation_jump_deg: 15.0
  stale_after_ms: 150

projection:
  display_width: 1920
  display_height: 1200
  safe_margin_px: 80
  target_radius_mm: 25.0
  user_profile: configs/calibration/user_profiles/user01_direct.json
```

The display dimensions are updated to the hardware-gate result before the config is committed.

- [ ] **Step 7: Verify**

```powershell
.\.venv_rt\Scripts\python.exe -m pytest tests\realtime\test_aruco_pose.py tests\realtime\test_projection.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add server/realtime/aruco_tracker.py server/realtime/projection.py tests/realtime/test_aruco_pose.py tests/realtime/test_projection.py configs/realtime_viture_beast_aruco.yaml
git commit -m "Add robust multi-marker pose and target projection"
```

---

### Task 6: Implement Nine-Point Display Calibration and Four-Point Recenter

**Files:**
- Create: `server/realtime/display_calibration.py`
- Create: `server/tools/run_display_calibration.py`
- Create: `web_overlay/calibration.html`
- Create: `web_overlay/calibration.js`
- Create: `web_overlay/calibration.css`
- Modify: `server/realtime/overlay_http_server.py:35-77`
- Create: `tests/realtime/test_display_calibration.py`

**Interfaces:**
- Produces: `fit_display_profile(samples: Sequence[CalibrationSample], metadata: ProfileMetadata) -> DisplayCalibrationProfile`
- Produces: `quick_recenter(profile, four_samples) -> DisplayCalibrationProfile`
- Persists: `configs/calibration/user_profiles/user01_direct.json`

- [ ] **Step 1: Write failing calibration tests**

Use nine synthetic points transformed by a known homography:

```python
def test_nine_point_fit_recovers_display_transform():
    profile = fit_display_profile(samples, metadata)
    predicted = profile.camera_to_display((640.0, 360.0))
    assert np.allclose(predicted, expected_display_point, atol=0.5)
    assert profile.residual_p95_px < 1.0
    assert profile.sample_count == 9


def test_profile_invalidates_on_display_mode_change():
    assert profile.is_compatible(
        display_size=(1920, 1200),
        windows_scale=1.0,
        display_mode="direct_0dof",
        camera_mode="1280x720@30",
        marker_layout_version="workspace_metric_v1",
    )
    assert not profile.is_compatible(
        display_size=(1920, 1200),
        windows_scale=1.25,
        display_mode="direct_0dof",
        camera_mode="1280x720@30",
        marker_layout_version="workspace_metric_v1",
    )
```

- [ ] **Step 2: Run and verify failure**

```powershell
.\.venv_rt\Scripts\python.exe -m pytest tests\realtime\test_display_calibration.py -v
```

Expected: FAIL because calibration types are undefined.

- [ ] **Step 3: Implement profile fitting and validation**

Fit a RANSAC homography from projected camera pixels to accepted display pixels. Store:

- profile id and user id;
- dominant-eye/display mode;
- display resolution and Windows scale;
- camera mode and marker-layout version;
- nine accepted pairs;
- 3x3 `display_from_camera_px`;
- median and P95 residual;
- creation timestamp.

Reject save when fewer than nine valid samples exist or P95 residual exceeds the configured limit.

- [ ] **Step 4: Implement the technical calibration UI**

`calibration.html` is a fullscreen black page with:

- one hollow crosshair/ring;
- current sample number `1/9`;
- arrow-key movement;
- Shift+arrow coarse movement;
- Enter to accept;
- Backspace to repeat the previous point;
- residual/error status;
- no camera video.

The server exposes narrowly scoped calibration POST endpoints and rejects them outside an active calibration session.

- [ ] **Step 5: Implement four-point recenter**

Four-point recenter composes a corrective homography with an existing valid nine-point profile. It cannot create a new profile from nothing.

- [ ] **Step 6: Verify**

```powershell
.\.venv_rt\Scripts\python.exe -m pytest tests\realtime\test_display_calibration.py -v
.\.venv_rt\Scripts\python.exe server\tools\run_display_calibration.py --help
```

Expected: PASS and the CLI displays required camera, display, and profile arguments.

- [ ] **Step 7: Commit**

```powershell
git add server/realtime/display_calibration.py server/tools/run_display_calibration.py server/realtime/overlay_http_server.py web_overlay/calibration.html web_overlay/calibration.js web_overlay/calibration.css tests/realtime/test_display_calibration.py
git commit -m "Add nine-point Beast display calibration"
```

---

### Task 7: Split Fast Pose from Recognition and Publish WebSocket v2

**Files:**
- Modify: `server/realtime/runtime_workers.py`
- Create: `server/realtime/snapshot_publisher.py`
- Create: `server/realtime/overlay_websocket_server.py`
- Modify: `server/realtime/run_realtime_server.py:51-320`
- Modify: `server/realtime/realtime_logger.py:13-108`
- Modify: `server/realtime/requirements-realtime.txt`
- Create: `tests/realtime/test_runtime_workers.py`
- Create: `tests/realtime/test_snapshot_publisher.py`
- Create: `tests/realtime/test_overlay_websocket_server.py`

**Interfaces:**
- Produces: `PoseWorker`
- Produces: `RecognitionWorker`
- Produces: `SnapshotPublisher.build_message(now_ms: int) -> OverlayMessageV2`
- Produces: `OverlayWebSocketServer.publish(message: dict) -> None`
- Preserves: legacy sequential execution through `runtime.mode: sequential_v1`.

- [ ] **Step 1: Write the concurrency contract tests**

Use fake processors where recognition sleeps 200 ms and pose sleeps 5 ms. Assert:

```python
def test_slow_recognition_does_not_block_pose_updates():
    runtime = make_fake_runtime(recognition_delay_s=0.2, pose_delay_s=0.005)
    runtime.run_for(0.5)
    assert runtime.pose_worker.processed_count >= 10
    assert runtime.recognition_worker.processed_count <= 4
    assert runtime.frame_buffer_depth == 1
```

Also assert:

- publisher chooses latest pose and latest recognition independently;
- pose age over 150 ms sets `target_visible=False`;
- low state confidence keeps instruction but does not advance target;
- WebSocket client receives `realtime_overlay_v2`.

- [ ] **Step 2: Run and verify failure**

```powershell
.\.venv_rt\Scripts\python.exe -m pytest tests\realtime\test_runtime_workers.py tests\realtime\test_snapshot_publisher.py tests\realtime\test_overlay_websocket_server.py -v
```

Expected: FAIL because worker and publisher interfaces are incomplete.

- [ ] **Step 3: Implement pose and recognition workers**

`PoseWorker` consumes every newer latest frame it can obtain and publishes both
`PoseSnapshot` and a capacity-one `TrackedFrame` containing the same source
packet and its exact pose/homography.

`RecognitionWorker` consumes the newest `TrackedFrame` at its configured maximum
rate, uses only that same-frame homography for ROI/YOLO association, and is the
only worker allowed to call `OnlineStateFilter.update`. It must not combine a
raw frame with a pose produced for a different `frame_id`.

Neither worker calls Unity/browser/network code.

- [ ] **Step 4: Implement the publisher**

The publisher:

1. reads latest pose and recognition snapshots under short locks;
2. resolves `ui_state` priority;
3. maps S2-S5 to screw A-D targets;
4. calls the Python projection module;
5. hides positional output when pose is invalid or stale;
6. emits source timestamps and calculated ages;
7. logs the exact message sent to clients.

- [ ] **Step 5: Implement WebSocket broadcast**

Use `websockets.sync.server.serve` in a daemon thread. Each client receives the newest message; slow clients do not create an unbounded per-client queue. Keep `/state.json` and `/frame.jpg` for the browser fallback.

- [ ] **Step 6: Refactor the entry point behind a config switch**

Add:

```yaml
runtime:
  mode: threaded_v2
  pose_publish_hz: 30
  recognition_max_hz: 12
  websocket_port: 8766
```

Keep the current loop in a callable `run_sequential_v1(args, config)` until
threaded replay and camera smoke tests pass. Add
`run_threaded_v2(args, config)` as the selected Beast path.

- [ ] **Step 7: Extend logging**

Add CSV/JSON fields for:

- capture, pose, state, and publish timestamps;
- pose and state source-frame ids;
- pose and state ages;
- pose FPS and recognition FPS;
- replaced frame count;
- reprojection error and inlier count;
- calibration profile id;
- projected target and visibility reason.

- [ ] **Step 8: Verify**

```powershell
.\.venv_rt\Scripts\python.exe -m pytest tests\realtime -v
.\.venv_rt\Scripts\python.exe server\realtime\run_realtime_server.py --source dummy --max-frames 120
```

Expected: all realtime tests PASS; dummy run serves both HTTP and WebSocket and exits cleanly.

- [ ] **Step 9: Commit**

```powershell
git add server/realtime/runtime_workers.py server/realtime/snapshot_publisher.py server/realtime/overlay_websocket_server.py server/realtime/run_realtime_server.py server/realtime/realtime_logger.py server/realtime/requirements-realtime.txt tests/realtime/test_runtime_workers.py tests/realtime/test_snapshot_publisher.py tests/realtime/test_overlay_websocket_server.py configs/realtime_viture_beast_aruco.yaml
git commit -m "Split realtime pose and recognition pipelines"
```

---

### Task 8: Turn the Browser Overlay into the Technical Beast Fallback

**Files:**
- Modify: `web_overlay/index.html`
- Modify: `web_overlay/style.css`
- Modify: `web_overlay/app.js`
- Create: `tests/realtime/test_overlay_http_server.py`
- Modify: `docs/beast_hardware_gate.md`

**Interfaces:**
- Consumes: `/state.json`, `/frame.jpg`, and protocol v2 fields.
- Produces: fullscreen black technical overlay with ring, edge arrow, instruction, warnings, and diagnostics toggle.

- [ ] **Step 1: Write HTTP server tests**

Assert:

- `/state.json` returns protocol v2 unchanged;
- static paths cannot escape `web_overlay`;
- calibration POST is unavailable without an active session;
- `/frame.jpg` returns 503 before a frame exists.

- [ ] **Step 2: Run and verify the current behavior**

```powershell
.\.venv_rt\Scripts\python.exe -m pytest tests\realtime\test_overlay_http_server.py -v
```

Expected: at least the protocol-v2 and calibration-session tests FAIL.

- [ ] **Step 3: Implement the technical overlay**

Default Beast view:

- black background;
- hollow cyan/white target ring;
- edge arrow when `target_offscreen=true`;
- next instruction at a stable lower-safe-region position;
- green transition acknowledgement;
- amber tracking warning;
- red blocking error;
- positional elements hidden when `target_visible=false`.

Pressing `D` toggles laptop-only diagnostics. The default Beast view must not show the raw camera frame or engineering metrics.

- [ ] **Step 4: Add stale-message handling in JavaScript**

Use `published_timestamp_ms`, `pose_age_ms`, and the local receive time. Hide the ring after 150 ms of stale pose even if HTTP polling itself has not failed. Keep the instruction with “Tracking paused”.

- [ ] **Step 5: Run the hardware fallback gate**

```powershell
.\.venv_rt\Scripts\python.exe server\realtime\run_realtime_server.py --config configs\realtime_viture_beast_aruco.yaml
```

On the Beast display:

1. place and move a technical crosshair;
2. keep camera capture active;
3. verify ring hide/recovery under marker occlusion;
4. run for 30 minutes;
5. record screenshots and observations in `docs/beast_hardware_gate.md`.

- [ ] **Step 6: Verify and commit**

```powershell
.\.venv_rt\Scripts\python.exe -m pytest tests\realtime\test_overlay_http_server.py -v
git add web_overlay tests/realtime/test_overlay_http_server.py docs/beast_hardware_gate.md
git commit -m "Add Beast technical browser overlay fallback"
```

---

### Task 9: Build the Unity Windows Guidance Client

**Files:**
- Delete: `client_unity/.gitkeep`
- Create: `client_unity/Packages/manifest.json`
- Create: `client_unity/ProjectSettings/ProjectVersion.txt`
- Create: `client_unity/Assets/UI/Guidance.uxml`
- Create: `client_unity/Assets/UI/Guidance.uss`
- Create: `client_unity/Assets/Scripts/Protocol/OverlayMessageV2.cs`
- Create: `client_unity/Assets/Scripts/Networking/OverlayWebSocketClient.cs`
- Create: `client_unity/Assets/Scripts/Display/BeastDisplayRouter.cs`
- Create: `client_unity/Assets/Scripts/UI/GuidancePresenter.cs`
- Create: `client_unity/Assets/Scripts/Runtime/GuidanceRuntime.cs`
- Create: `client_unity/Assets/Editor/CreateGuidanceScene.cs`
- Create: `client_unity/Assets/Scripts/BeastGuidance.Runtime.asmdef`
- Create: `client_unity/Assets/Tests/EditMode/BeastGuidance.EditModeTests.asmdef`
- Create: `client_unity/Assets/Tests/EditMode/OverlayMessageTests.cs`
- Create: `client_unity/Assets/Tests/EditMode/GuidancePresenterTests.cs`

**Interfaces:**
- Consumes: WebSocket `ws://127.0.0.1:8766` protocol v2 JSON.
- Produces: Unity Windows fullscreen guidance on selected display.
- Guarantees: Unity cannot advance or infer S0-S6.

- [ ] **Step 1: Create the minimal Unity project**

Pin the installed local Unity LTS version in `ProjectVersion.txt`. Use UI Toolkit and the Unity Test Framework packages only; do not add an inference or XR package.

- [ ] **Step 2: Write EditMode tests**

Test JSON parsing and UI policy:

```csharp
[Test]
public void StalePoseHidesTargetButKeepsInstruction()
{
    var message = OverlayMessageV2.ValidGuidance();
    message.pose_age_ms = 151;
    var state = GuidancePolicy.Resolve(message);
    Assert.IsFalse(state.TargetVisible);
    Assert.AreEqual("Tracking paused", state.WarningText);
    Assert.AreEqual("Fasten screw B", state.Instruction);
}


[Test]
public void UnknownSchemaIsRejected()
{
    Assert.Throws<UnsupportedSchemaException>(
        () => OverlayMessageV2.Parse("{\"schema_version\":\"v99\"}")
    );
}
```

- [ ] **Step 3: Run tests and verify failure**

Run Unity EditMode tests from the Unity Test Runner or batch mode. Expected: FAIL because protocol and policy classes do not exist.

- [ ] **Step 4: Implement protocol and WebSocket reception**

`OverlayWebSocketClient` uses `System.Net.WebSockets.ClientWebSocket`. Background receives enqueue the newest parsed message into a capacity-one `ConcurrentQueue` replacement; the Unity main thread consumes it in `Update()`.

Reject:

- unknown schema;
- non-finite coordinates;
- incompatible calibration profile id;
- invalid target plus visible flag;
- pose older than 150 ms.

- [ ] **Step 5: Implement display routing**

`BeastDisplayRouter`:

1. lists Unity displays;
2. activates the configured secondary display when present;
3. falls back visibly to display 0 for laptop debugging;
4. records selected display index, resolution, and refresh rate;
5. never invokes SpaceWalker or applies device-side 3DoF.

- [ ] **Step 6: Implement the UI**

`Guidance.uxml` and `Guidance.uss` contain:

- hollow target ring with fixed pixel bounds;
- edge arrow;
- current state;
- next instruction;
- confirmation;
- tracking warning;
- completion;
- connection status.

`GuidancePresenter` positions only the ring/arrow from authoritative Python display coordinates. It may visually interpolate between recent valid points but cannot extrapolate state transitions.

- [ ] **Step 7: Generate the scene through an editor script**

`CreateGuidanceScene.cs` creates one camera, one UIDocument, display router, WebSocket client, presenter, and runtime root. Save `Assets/Scenes/Guidance.unity`. This avoids undocumented manual scene setup.

- [ ] **Step 8: Verify**

1. Run Python dummy mode with WebSocket v2.
2. Run Unity Play Mode on the laptop.
3. Confirm connection, ring movement, warnings, and completion.
4. Build Windows Standalone.
5. Select Beast display and confirm fullscreen black output.
6. Disconnect Python and verify target hides while reconnect remains bounded.

- [ ] **Step 9: Commit**

```powershell
git add client_unity
git commit -m "Add Unity Windows guidance client"
```

---

### Task 10: Integrate S0-S6, Quantify Registration, and Package the MVP

**Files:**
- Create: `server/realtime/evaluate_overlay_run.py`
- Create: `server/realtime/registration_sampling.py`
- Create: `tests/realtime/test_evaluate_overlay_run.py`
- Modify: `server/realtime/realtime_replay.py`
- Create: `scripts/run_beast_mvp.ps1`
- Create: `scripts/check_beast_mvp.ps1`
- Modify: `README.md`
- Modify: `docs/realtime_harness_plan.md`
- Create: `docs/beast_mvp_evaluation_protocol.md`

**Interfaces:**
- Consumes: realtime session logs, manual transition GT, and registration samples.
- Produces: `registration_metrics.csv`, `latency_metrics.csv`, `state_metrics.csv`, `wrong_target_events.csv`, and summary JSON/PNG.
- Produces: one-command MVP startup and package verification.

- [ ] **Step 1: Write failing evaluator tests**

Use fixture logs and assert:

```python
def test_summary_separates_pose_and_state_latency():
    summary = evaluate_session(FIXTURE_SESSION)
    assert summary["pose_latency_p95_ms"] == 48.0
    assert summary["state_latency_p95_ms"] == 210.0


def test_wrong_target_is_counted_as_safety_failure():
    summary = evaluate_session(WRONG_TARGET_SESSION)
    assert summary["wrong_target_count"] == 1
    assert summary["safety_pass"] is False


def test_repeated_replay_is_labeled_determinism_only():
    summary = compare_replays([RUN_A, RUN_B])
    assert summary["evaluation_kind"] == "determinism"
```

- [ ] **Step 2: Run and verify failure**

```powershell
.\.venv_rt\Scripts\python.exe -m pytest tests\realtime\test_evaluate_overlay_run.py -v
```

Expected: FAIL because the evaluator does not exist.

- [ ] **Step 3: Implement objective registration sampling**

At centre, corners, screws A-D, and three normal head positions:

1. save predicted display point;
2. let the user align an evaluation crosshair with the physical point;
3. inverse-project the corrected display point to the workspace plane;
4. calculate millimetre error from the known target;
5. save fit/remove/wear repetition id and pose quality.

This produces measured error rather than a subjective “looks aligned” label.

- [ ] **Step 4: Implement session metrics**

Calculate:

- registration median and P95 in mm;
- error relative to minimum adjacent-screw spacing;
- pose update FPS and P95 capture-to-message latency;
- state update FPS and P95 state-guidance latency;
- marker availability;
- stale-target violations;
- wrong-target count;
- premature transition count against manual GT;
- full S0-S6 completion.

- [ ] **Step 5: Define the physical evaluation set**

`docs/beast_mvp_evaluation_protocol.md` requires:

- 5-10 distinct Beast-camera assembly sessions;
- manual state-transition GT per session;
- normal head movement;
- temporary and prolonged marker occlusion;
- wrong-screw approach;
- glasses remove/refit trials;
- direct mode, fixed display scaling, fixed lighting;
- no claim of generalization from replaying one recording repeatedly.

- [ ] **Step 6: Add one-command run and package checks**

`scripts/run_beast_mvp.ps1`:

1. validates the Python environment;
2. validates camera, workspace, and user calibration files;
3. starts Python threaded v2;
4. starts the Unity Windows build if present;
5. prints log and WebSocket locations.

`scripts/check_beast_mvp.ps1` verifies required configs, YOLO weights, ROI references, Unity build, schema, and test status without modifying files.

- [ ] **Step 7: Run full verification**

```powershell
.\.venv_rt\Scripts\python.exe -m pytest tests\realtime -v
.\scripts\check_beast_mvp.ps1
.\scripts\run_beast_mvp.ps1
```

Then perform the defined physical sessions and run:

```powershell
.\.venv_rt\Scripts\python.exe server\realtime\evaluate_overlay_run.py `
  --sessions outputs\realtime_sessions `
  --output outputs\beast_mvp_evaluation
```

Expected: metrics, failure CSVs, and summary figures are generated; wrong-target guidance is zero in the final accepted run set.

- [ ] **Step 8: Update documentation**

README and realtime docs must state:

- the exact tethered Windows architecture;
- setup and run commands;
- calibration prerequisites;
- Python/Unity ownership boundary;
- browser fallback;
- current measured hardware mode;
- known one-user/one-workspace limitations;
- evaluation results without claiming stereo or arbitrary-workspace AR.

- [ ] **Step 9: Commit**

```powershell
git add server/realtime/evaluate_overlay_run.py server/realtime/registration_sampling.py server/realtime/realtime_replay.py tests/realtime/test_evaluate_overlay_run.py scripts/run_beast_mvp.ps1 scripts/check_beast_mvp.ps1 README.md docs/realtime_harness_plan.md docs/beast_mvp_evaluation_protocol.md
git commit -m "Integrate and evaluate Beast AR guidance MVP"
```

---

## Execution Order and Review Gates

1. **Hardware gate:** Task 1 must pass before Unity work.
2. **Deterministic core:** Tasks 2-3 establish protocol and queue behavior.
3. **Registration gate:** Tasks 4-6 must project and calibrate screws A-D in the browser technical overlay.
4. **Concurrency gate:** Task 7 must prove slow recognition does not delay pose.
5. **Fallback gate:** Task 8 must run on the Beast display before Unity is treated as critical.
6. **Unity gate:** Task 9 adds the user-facing client without moving inference into Unity.
7. **Evidence gate:** Task 10 requires distinct physical sessions and quantitative error/latency results.

Do not begin deferred per-eye projection, IMU fusion, arbitrary-workspace mapping, or MediaPipe reintegration until the Task 10 MVP evidence is complete.
