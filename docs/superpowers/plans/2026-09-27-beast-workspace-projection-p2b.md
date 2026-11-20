# Beast Metric Workspace P2b Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 실측 마커 중심 좌표로 카메라 기준 작업대 자세와 높이가 있는 목표점을 계산하는 독립 진단 도구를 만든다.

**Architecture:** 기존 ROI용 homography와 상태 서버는 변경하지 않는다. 실측한 평면 마커 중심을 OpenCV IPPE/PnP에 입력하고, 원본 영상에만 진단점을 표시한다. 눈/Unity 정합은 P2c에서 별도로 진행한다.

**Tech Stack:** 기존 Python, NumPy, OpenCV, pytest. 새 의존성 없음.

**Spec:** docs/superpowers/specs/2026-09-26-beast-minimal-harness-design.md

## Global Constraints

- Windows, Beast 1280 x 720 촬영 및 일치하는 카메라 후보 사용.
- 좌표는 mm, ID 3 중심 원점, +X 오른쪽, +Y 벽 쪽, +Z 매트 위쪽.
- 입력하지 않은 물리 좌표를 과거 ROI 픽셀이나 사진 눈금으로 채우지 않는다.
- 프로필/입력 해상도 불일치, 비정상 좌표, 4개 미만 마커, 평면 자세 모호성은 거부.
- 최신 프레임마다 독립 계산. 이전 pose fallback 없음. 이번 도구는 저장 사진 진단이며 실시간 신선도 통합은 하지 않는다.
- 원본 사진/진단 이미지는 LOCALAPPDATA 아래 새 디렉터리. 자동 런타임 활성화, 클라우드, Unity 변경, 커밋/푸시 없음.
- 재투영 오차는 mm 정답 또는 눈 정합 성능이 아니다.
- 사용자가 이번 단계 진행을 승인했다. 별도 재승인 질문 없이 이 범위만 구현한다.

## Review Focus

1. 기울어진 마커 네 코너 평균은 중심이 아니다: 왜곡 보정 후 대각선 교점으로 계산하고 합성 투영 시험.
2. 평면 PnP 두 후보가 비슷하게 맞으면 잘못된 높이 투영 가능: 후보 간 오차/자세 차이 검사, 모호하면 출력 거부.
3. ID 순서/알 수 없는 ID/중복 또는 불완전 코너: ID별 대응, 미등록 ID 무시, 형상/범위 검사.
4. 잘못된 렌즈 모델/해상도/단위 또는 빈 실측값: 입력 단계에서 설명 가능한 오류.
5. 카메라 뒤쪽/작업대 아래/영상 밖 목표점: 표시하지 않고 이유를 기록.

## Task 1: Geometry Core

**Files:** Create server/realtime/workspace_projection.py; tests/realtime/test_workspace_projection.py.

**Interfaces:**
- CameraModel.from_profile(data: dict) -> CameraModel
- MetricWorkspace.from_dict(data: dict) -> MetricWorkspace
- marker_center_px(corners, camera) -> ndarray(2) (undistorted pixel coordinates)
- estimate_pose(detections: dict[int, ndarray], workspace, camera, image_size) -> WorkspacePose
- project_targets(pose, workspace, camera) -> dict[str, dict]
- pixel_to_plane(pixel, height_mm, pose, camera) -> ndarray(3)

- [x] Write synthetic distorted/tilted scene tests including target height, ID order, missing/degenerate markers, malformed profiles, failed/ambiguous poses and offscreen targets.
- [x] Run tests; observe missing implementation failures.
- [x] Implement with OpenCV solvePnPGeneric(SOLVEPNP_IPPE) and projectPoints. Require physical camera above board and all observed points in front. Initial diagnostic maximum RMS 3 px, max per-point error 5 px. These are trial gates, not final accuracy targets.
- [x] Run focused tests and full tests/realtime suite.

## Task 2: Offline Registration Diagnostic

**Files:** Create server/realtime/workspace_registration.py; tests/realtime/test_workspace_registration.py; configs/beast_workspace_metric.example.json; docs/beast_workspace_registration.md.

**Interfaces:**
- inspect_image(image_path, camera_profile_path, workspace_path, output_root) -> Path
- CLI python -m server.realtime.workspace_registration --image ... --camera-profile ... --workspace ... [--out-root ...]

- [x] Test synthetic PNG end-to-end with detector boundary injected, fresh outputs, immutable source, profile/geometry hashes and absence of eye-registration claims.
- [x] Observe RED, implement using existing marker detector and calibration JSON/write helpers.
- [x] Report pose, observed/projected marker centers, known target projections and explicit unregistered targets when absent.
- [x] Unfilled example has null coordinates and is rejected until measurements are supplied; never fabricate actual board.
- [x] Inspect recorded image with supplied measurements if available. Otherwise record actual-data validation pending, not passed.

### Task 2b: User Target Selection

Same registration module/tests. Required continuation of target registration, without auto-activation.

- [x] Add RED tests for `register_target_points(clicks, pick_height_mm, target_height_mm, pose, camera)` and `collect_target_clicks(image)`.
- [x] Implement ray/height-plane intersection, A/B/C/D winding and 110 mm side/diagonal check (10 mm initial sanity tolerance); preserve observed XY.
- [x] Add RED tests and implement `pick_workspace_targets(...)`: user-only OpenCV window, cancel without candidate, explicit Enter, source hashes, immutable input, unactivated candidate.
- [x] Actual user selection; saved candidate and reprojected onto two other stored views. Visual check only, no mm accuracy claim.
- [ ] Wider new-view physical target error measurement and live pose integration before P2 is considered complete.

## Task 3: Verification and Handoff

- [x] Run full realtime tests and CLI help: 126 passed before independent review. Import/CLI checks execute both modules.
- [x] One fresh scoped code review of these additions; fix material findings with regression tests.
- [x] Record completion/remaining real measurements and physical validation in this plan and usage doc.

## Execution Ledger

- Start: existing isolated feature/viture-beast-overlay-mvp worktree; unrelated P0/P1/P2a changes preserved.
- Ruling: measured centers replace measured corners for initial P2b; avoids needing all corner orientations. Cost: only 4-6 point correspondences, less redundancy than a measured 24-corner board. Reprojection gates and later held-out checks are required.
- Ruling: registration is independent offline tooling first; no automatic live activation before real metric input and held-out checks. Cost: actual glasses output requires follow-on P2c.
- Task 1 complete: 28 RED missing implementation -> 28 GREEN, full suite 111 passed.
- Task 2 complete: 5 RED -> GREEN; actual photo pose RMS 2.201/2.579/2.074 px under unchanged diagnostic gates. This is fitting error, not held-out physical accuracy.
- Task 2b software complete: 15 registration tests (including cancel/order/height/immutable candidate), focused total 43, full suite 126 passed. Physical selection pending.
- Ruling: user initially reported unequal screw heights, then clarified heads are effectively near the lid and about 60 mm, only not tightly fastened. Use 60 mm for an initial candidate only; do not require extra torque. Cost: small unmeasured height differences bias XY and must be checked on an independent view.
- Actual registration: user clicked 4 heads in reference-02; candidate saved, original layout untouched. Other reference-01/03 target projections visually coincide with screws; limited view difference, no quantitative physical validation.
- Final review: fresh reviewer Lagrange found cyclic A/B/C/D label assignments could pass square shape checks. No other material findings reported.
- Final fixed: cyclic label shifts BDAC/CADB/DCBA reproduce failure, then explicit workspace XY ordering rejects them; 3 RED -> GREEN. Full realtime suite 129 passed, focused new tests 46. Actual user candidate revalidated unchanged.
- Final: CLI help and compile checks pass; user picker exited normally, no capture/registration process left. No runtime activation, commit or push. No deferred minor findings.
