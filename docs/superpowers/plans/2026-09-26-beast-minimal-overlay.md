# Beast + Laptop Minimal Overlay Implementation Plan

> **Historical plan:** 브라우저 중심의 이전 계획입니다. 현재 범위는
> `../specs/2026-09-26-beast-minimal-harness-design.md`를 따르며,
> 첫 실행 순서는 `2026-09-26-beast-harness-p0.md`를 사용합니다.
> 아래 작업 지시는 이력 보존용이며 새 계획과 충돌하면 실행하지 않습니다.
> Preserve the current worktree and user changes. Commit/push only when requested.

**Goal:** 고정된 인클로저의 다음 나사 위치에 실제 착용 시 원을 겹쳐 표시하고,
기존 실시간 조립 상태에 따라 안내를 바꿉니다.

**Architecture:** Windows 노트북의 기존 Python 인식 서버와 브라우저 화면을 재사용합니다.
ArUco/PnP와 착용자 보정을 추가하고, 위치 안내의 신선도와 상태 안내를 따로 관리합니다.
Beast는 USB 카메라와 외부 디스플레이로 사용합니다.

**Tech Stack:** Python, OpenCV, 기존 YOLO 가중치, 기존 OnlineStateFilter, HTTP,
HTML/CSS/JavaScript. 기본 구현에 VITURE Unity SDK, Unity 프로젝트, Neckband는 필요하지 않습니다.

**Spec:** ../specs/2026-07-27-viture-beast-overlay-design.md
작성 당시의 브라우저 우선 범위입니다. 현재는 위 최소 하네스 설계로 대체됐습니다.

## 범위와 현재 코드

- Neckband는 이후에도 전제로 두지 않습니다.
- 사용자 1명, 인클로저 1종, 고정 지그/위치, 알려진 마커 배치부터 검증합니다.
- 사용자는 실제 작업대를 렌즈 너머로 봅니다. 안경에는 원과 짧은 안내만 표시합니다.
- 기존 브라우저 카메라 영상은 노트북 디버그 용도로 유지합니다.
- 원은 알려진 나사 좌표를 마커 자세로 투영합니다. 임의 위치로 옮긴 상자를 자동 추적한다고 주장하지 않습니다.
- 책상 평면과 뚜껑의 나사 높이는 다릅니다. 실제 나사 높이를 측정해 XYZ에 넣습니다.
- 현재 실시간 추론은 server/realtime/online_state_filter.py의 인과적 순차 필터입니다.
  Session17의 offline Viterbi HMM 성능을 실시간 성능으로 인용하지 않습니다.
- 실시간 entry point는 ROI와 YOLO를 사용합니다. MediaPipe 재통합은 현재 필수 기능이 아닙니다.
- server/realtime/yolo_realtime.py의 stale-result 처리와 기존 전이 확인 표시를 우선 재사용합니다.
- IMU fusion, 별도 Unity UI, SBS 양안 보정, WebSocket 전면 전환, SLAM,
  markerless 추적, 음성/손동작 UI, 대규모 grid search는 초기 범위에서 제외합니다.
- 공식 Glasses SDK는 기존 UVC 경로의 장치 접근/표시 모드 문제를 해결할 때만 adapter로 추가합니다.
  SDK를 넣는 것 자체는 완료 조건이 아닙니다.

## 기대 결과

1. 시작 후 연결/보정 상태를 확인합니다.
2. 박스 배치와 뚜껑 닫기를 인식하고 짧은 안내를 표시합니다.
3. S2에서는 실제 나사 A 주위에 빈 원과 "Fasten screw A"를 표시합니다.
4. 작업 증거가 들어오면 확인 표시를 잠시 유지합니다.
5. 대상 도구가 충분히 머물렀다가 이탈한 뒤 다음 나사를 안내하도록 검증합니다.
6. 마커/프레임/연결이 유효하지 않으면 위치 원을 숨기고 안내를 유지합니다.
7. 마지막 단계 이후 사용자가 전체 조립을 확인하고 세션을 종료합니다.

나사 접근/작업 관찰은 체결 토크나 기계적 완료의 증명이 아닙니다.
숫자 confidence를 보정된 성공 확률처럼 사용자에게 표시하지 않습니다.
9점 2D 보정은 제한된 작업 거리와 자세에서 검증하며, 자유로운 머리 이동/깊이 변화나
양안 정합을 자동 해결하지 않습니다.

## 구현 순서

### Task 0: 기존 코드 재개 및 장치 확인

**Files:** server/realtime/beast_device_check.py, scripts/check_beast_device.ps1,
tests/realtime/test_beast_device_check.py, 기존 probe_cameras.py / frame_source.py.

**Interfaces:** inspect_devices(devices: list[dict]) -> dict.
실제 Windows 장치 조회 결과를 받아 camera_status, ready_for_capture_probe,
capture_verified, display_alignment_verified를 구분합니다.

- [x] 이동된 기존 저장소와 feature/viture-beast-overlay-mvp worktree를 찾습니다.
- [x] git worktree repair로 오래된 계정 경로를 복구합니다.
- [x] 알려진 Beast UVC ID, 장치 오류, 잘못된 이름/유사 PID, 조회 실패 테스트를 추가합니다.
- [x] 표준 라이브러리 진단 모듈과 PowerShell 실행기를 구현하고 8개 테스트를 통과합니다.
- [x] 실제 장치를 조회합니다. 이번 실행은 Beast camera/control 미감지입니다.
- [ ] 새 PC의 Python 실행환경을 준비하고 기존 realtime 테스트/재생을 확인합니다.
- [ ] Beast 연결 후 preview와 하드웨어 ID를 대응시킵니다. camera index만 믿지 않습니다.
- [ ] 기존 UVC capture의 실제 해상도, format, 수신 FPS를 측정합니다.
- [ ] 기존 probe에 필요할 때만 MJPEG 요청/actual format 기록을 추가하고 모의 capture로 테스트합니다.
- [ ] 직접 표시 모드와 고정 Windows 배율로 카메라/화면 동시 동작을 확인합니다.

현재 복사된 .venv_rt/pyvenv.cfg는 C:/Users/user의 Python을 가리킵니다.
이를 동작하는 새 환경으로 오인하지 않습니다.
진단 도구는 Python 표준 라이브러리만 필요합니다.
실행: scripts/check_beast_device.ps1 -PythonExe "<working-python.exe>".
종료 코드 0은 capture 검사 후보 발견, 1은 미감지/장치 오류, 2는 조회/환경 오류입니다.
어느 경우도 화면 정합 성공을 뜻하지 않습니다.

### Task 1: 실제 나사 위치 계산

**Files:** 새 server/realtime/workspace_projection.py,
configs/beast_workspace_metric.yaml, configs/beast_camera_calibration.yaml,
tests/realtime/test_workspace_projection.py; 기존 aruco_tracker.py 연결.

**Interfaces:** estimate_board_pose(corners, ids, board, camera_matrix, distortion) -> pose result;
project_screw(pose, screw_xyz_mm, camera_matrix, distortion) -> camera pixel or invalid.

- [ ] 실제 marker 모서리 배치, 인쇄 길이, 나사 A-D XYZ를 측정해 기록합니다.
- [ ] 카메라 intrinsic/distortion을 실제 사용 모드에서 보정합니다.
- [ ] 알려진 합성 자세를 복원하는 테스트와 잘못된/부족한 marker에서 invalid를 반환하는 테스트를 작성합니다.
- [ ] OpenCV Board/PnP와 projectPoints로 구현합니다. ROI용 기존 homography는 유지합니다.
- [ ] 디버그 영상에서 나사 A-D와 투영점이 맞는지 여러 정상 자세로 확인합니다.

카메라에서의 reprojection error와 사용자가 보는 실제 overlay 오차는 따로 기록합니다.

### Task 2: 착용자 보정과 안경 원 표시

**Files:** 새 server/realtime/display_calibration.py,
tests/realtime/test_display_calibration.py; 기존 overlay_http_server.py,
web_overlay/index.html, style.css, app.js.

**Interfaces:** fit_display_mapping(camera_points, display_points, profile_metadata) -> profile;
map_to_display(profile, camera_xy) -> display_xy or invalid.

- [ ] 9개 분산된 참조점과 별도 검증점으로 보정합니다. 나사 높이/작업 거리를 기록합니다.
- [ ] 부족한 점, 일직선 점, non-finite 값, 모드/배율 불일치, 나쁜 검증 오차를 거부하는 테스트를 작성합니다.
- [ ] 기존 HTTP 서버에 로컬 보정 시작/점 입력/저장 기능만 추가합니다.
- [ ] 기존 UI에 안경 모드를 추가합니다. 검은 배경, 빈 원, 한 줄 안내, 일시정지만 표시합니다.
- [ ] 노트북 화면에는 기존 카메라/진단 패널을 유지합니다.
- [ ] 실제 안경 착용 후 A-D의 정합과 양안 불편 여부를 확인합니다.

보정에 쓴 점에서만 잘 맞는 결과는 통과가 아닙니다.
한 자세에서만 맞으면 사용 범위를 그 자세/거리로 제한해 표시합니다.
화면 밖 target은 처음에는 원을 숨기고 작업공간을 바라보라는 문구만 표시합니다.
방향 화살표와 세밀한 윤곽선은 원의 정합이 통과한 뒤 추가할 수 있습니다.

### Task 3: 최신 위치로 표시하고 유실 시 숨기기

**Files:** 기존 frame_source.py, schemas.py, run_realtime_server.py,
overlay_http_server.py, realtime_logger.py, web_overlay/app.js;
필요 시 작은 server/realtime/latest_frame.py; 관련 tests/realtime 테스트.

**Interfaces:** 같은 frame_id의 영상과 pose를 묶어 recognition에 전달합니다.
기존 OverlayMessage를 확장해 pose_frame_id, pose_age_ms, target_display_xy,
target_visible, calibration_profile_id를 전달합니다.

- [ ] 느린 YOLO가 위치 갱신을 막지 않도록 latest-frame 방식으로 구성합니다.
- [ ] FIFO 적체, 영상과 pose의 frame_id 불일치, stale HTTP 결과에 대한 테스트를 작성합니다.
- [ ] 기존 HTTP의 순차 polling을 먼저 측정합니다. 요청 중첩은 막고 완료 후 다음 요청을 보냅니다.
- [ ] JavaScript는 수신 후 경과시간과 서버가 계산한 pose age를 합쳐 원을 숨깁니다.
- [ ] pose age 150 ms 초과, 연결 끊김, 보정 무효, non-finite 좌표에서 원이 남지 않게 합니다.
- [ ] HTTP가 측정된 지연 요구를 만족하지 못할 때만 전송 방식 변경을 검토합니다.

Python monotonic timestamp와 브라우저 Date.now를 직접 빼지 않습니다.
렌더 프레임률, pose 갱신률, recognition 갱신률을 혼동하지 않습니다.

### Task 4: 자동 단계와 안내 연결

**Files:** 기존 online_state_filter.py, state_definitions.py,
run_realtime_server.py, configs/realtime_viture_beast_aruco.yaml;
tests/realtime/test_online_state_filter.py.

**Interfaces:** 기존 StateEstimate.state / target / transition_event를 UI에 연결합니다.
나사 단계는 접근/머무름/이탈 관측을 내부 후보로 관리하고 확인 전에는 다음 target으로 바꾸지 않습니다.

- [ ] 손만 통과, 다른 나사 접근, 도구 오검출 잔존, 작업 중 마커 가림의 회귀 테스트를 만듭니다.
- [ ] dwell과 유효 증거의 만료는 경과시간 기준으로 바꿉니다.
- [ ] 마커 유실은 도구의 정상 이탈로 처리하지 않습니다.
- [ ] 확인 후 약 1.5초 동안 해당 나사의 확인 표시를 유지합니다.
- [ ] S0-S6 순차 작업을 새 영상에서 재생하고 조기/지연 전이를 기록합니다.

초기 overlay 디버깅 중 target 선택은 수동으로 가능하지만,
수동 선택 데모를 자동 상태 인식 성공으로 기록하지 않습니다.

### Task 5: 실행과 시연 확인

**Files:** scripts/run_beast_mvp.ps1, 기존 realtime_logger.py,
docs/beast_minimal_evaluation.md 및 기존 README 실행 섹션.

- [ ] 하나의 실행 명령으로 환경/보정 파일 확인과 서버 시작을 지원합니다.
- [ ] 서로 다른 실제 조립 3회 이상에서 target 선택, 상태 전이, 위치 안내를 확인합니다.
- [ ] marker 가림, 정상 머리 이동, 안경 다시 착용, 카메라/서버 끊김을 확인합니다.
- [ ] 정합 오차는 사용하지 않은 참조점에서 측정하고 median/P95와 최대 오차를 기록합니다.
- [ ] 합격 오차의 초깃값은 최소 나사 간격의 1/4 미만으로 두고 실제 작업 요구에 따라 조정합니다.
- [ ] p95 처리 지연과 실제 capture-to-display 지연을 구별합니다.
- [ ] 현재 UI 영상, 실행 명령, 측정 결과, 알려진 제한을 한곳에 저장합니다.

10 mm/20 mm 같은 정확도나 30 FPS를 보장하지 않습니다.
카메라 모델/SDK 문서에 쓰인 수치는 입력 설정의 참고이고 실제 측정으로 판단합니다.

## 검토할 실패 조건

| 조건 | 기대 동작 | 담당 |
| --- | --- | --- |
| 노트북 webcam만 있음 / 다른 VITURE 기기 | Beast 후보 발견으로 표시하지 않음 | Task 0 |
| marker board와 상자 상대 위치/높이 변경 | 기존 target 좌표를 그대로 신뢰하지 않음 | Task 1, 2 |
| DPI/해상도 변경 / 안경 재착용 오차 | 보정 재검증, 무효면 원 숨김 | Task 2 |
| 느린 inference / 오래된 응답 | 최신 pose 우선, stale 원 숨김 | Task 3 |
| 나사를 돌리는 중 / marker 가림 | 작업 이탈로 오인해 다음 나사를 안내하지 않음 | Task 4 |

## 현재 작성/실행 결과

2026-09-26 이번 작업은 Task 0의 경로 복구, 진단 구현/테스트와 최소 계획 작성까지입니다.
실제 Beast 카메라 캡처와 착용 정합은 수행하지 않았습니다.
기존 main의 docs/session17_hmm_v2_status.md 수정은 사용자 작업으로 유지합니다.
이번 변경의 commit/push는 하지 않았습니다.

## 참고

- [VITURE Glasses C SDK](https://www.viture.com/developer/glasses-sdk/glasses):
  Windows 및 Beast UVC 장치 식별/제어의 참고.
- [VITURE Unity XR SDK](https://www.viture.com/developer/unity-sdk/unity):
  Marker Tracking Demo 구조 참고. Neckband 실행 경로는 본 구현의 의존성이 아닙니다.
