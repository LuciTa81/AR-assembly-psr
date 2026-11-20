# 코드 지도와 검토 순서

경로는 모두 `source/` 기준이다. 기존 코드의 책임 구분이며, 파일 수가 곧 완성도를 뜻하지 않는다.

## 1. 빠른 진입점

| 목적 | 먼저 읽을 파일 |
| --- | --- |
| 실제 실시간 입력과 분기 | `server/realtime/run_realtime_server.py` (`run_session`) |
| 현재 활성 옵션 | `configs/realtime_viture_beast_aruco.yaml` |
| 최신 추적 후보와 한계 | `server/realtime/workspace_projection.py`, `corner_tracking_report.py` |
| 오버레이와 서버 연결 | `server/realtime/presentation_bridge.py` |
| Unity SBS 동작 | `client_unity/Assets/Scripts/StereoAlignmentProbe.cs`, `CandidateProjection.cs` |
| 원 정렬/저장 의미 | `StereoAlignmentState.cs`, `DisplayObservationRecorder.cs` |
| 상태 안내 | `server/realtime/online_state_filter.py`, `guidance_timing.py` |

## 2. Python: 입력과 작업 단계

| 파일 | 책임 / 검토 관점 |
| --- | --- |
| `server/realtime/frame_source.py` | 카메라·리플레이·dummy 입력. frame/session/시간 의미 |
| `server/realtime/aruco_tracker.py` | 인식용 homography, 이전 H fallback. metric pose와 혼동 금지 |
| `server/realtime/roi_realtime.py` | box/lid 등 ROI 특징. 조명/투명 뚜껑/warp 의존성 |
| `server/realtime/yolo_realtime.py` | 도구·handle 결과, `long_axis_endpoints`, `handle_guided_tip`, 근접 점수 |
| `server/realtime/online_state_filter.py` | S0-S6와 정책 분기, 대상 선택, 전이/보류 이유 |
| `server/realtime/guidance_timing.py` | `TimedEvidenceGate.evaluate`: 접근·이탈·유효 시간·ack |
| `server/realtime/state_definitions.py` | 단계 이름, 다음 작업, target ID |
| `server/realtime/schemas.py` | 결과 snapshot 데이터 구조 |
| `server/realtime/overlay_http_server.py` | 상태/선택적 영상/관제 제공 |
| `server/realtime/realtime_logger.py` | 수치 결과, 진단·전이 로그 |
| `server/realtime/realtime_replay.py` | 저장 기록을 현재 정책으로 재생·비교 |

리뷰할 질문: 손/팔/도구 오검출로 전이하는가? 검출 유실을 이탈로 오인하는가? 비동기 YOLO 결과가 다른 frame/target/session에 적용되는가? 오래된 pose와 최신 stage가 섞이는가? UI의 OBSERVED가 실제 체결 완료로 읽히지 않는가?

## 3. Python: 공간 추적과 눈별 보정

| 파일 | 책임 / 검토 관점 |
| --- | --- |
| `server/realtime/camera_calibration.py` | 카메라 내참수/왜곡 보정 후보 |
| `server/realtime/workspace_registration.py` | 나사 영상 클릭과 높이 평면으로 작업대 XYZ 등록 |
| `server/realtime/workspace_projection.py` | `CameraModel`, `MetricWorkspace`, `estimate_pose`, `estimate_corner_pose`, `project_targets`, `pixel_to_plane` |
| `server/realtime/workspace_live_preview.py` | `analyze_frame`, `camera_worker`, 프로필 로딩/진단 창 |
| `server/realtime/workspace_overlay.py` | `world_segments`, `project_overlay`: 카메라상의 나사 둘레/화살표 |
| `server/realtime/display_observation_server.py` | 최신 관측 저장소, 로컬 인증된 수치 API, 수집 세션 |
| `server/realtime/presentation_bridge.py` | 기존 카메라 입력을 공간 관측/관제와 공유 |
| `server/realtime/display_calibration.py` | 정합 계약과 synthetic 자료 검증. 실측 합격과 구분 |
| `server/realtime/display_fit.py` | 눈별 DLT 데이터 검증/계산/시험 후보 export |
| `server/realtime/display_joint_fit.py` | PD soft prior를 포함한 단순 양안 모델, 오프라인 비교 전용 |
| `server/realtime/tracking_report.py` | 수치 관측의 거절 원인/연속 구간 분석 |
| `server/realtime/corner_tracking_report.py` | 기준 fixture의 가정 geometry로 같은 trace에서 중심/모서리 비교 |

리뷰 우선순위: 좌표축/단위/왜곡 사용 -> 공선·평면 모호성 -> 실측 geometry -> timestamp/신선도 -> 모델 자유도/독립 검증 -> 착용 변화. 후보가 총 통과율만 높였는지, 기존 정상 조합을 왜 잃는지도 확인한다.

## 4. Unity: Windows standalone, SDK 기반 XR 앱이 아님

아래 파일은 `client_unity/Assets/Scripts/` 아래에 있다.

| 파일 | 책임 |
| --- | --- |
| `DisplayBootstrap.cs` | 디스플레이/모드/실행 옵션 초기화 |
| `GuidanceSnapshot.cs`, `GuidanceReceiver.cs`, `GuidanceState.cs` | Python 단계 수신 및 연결/신선도 상태 |
| `GuidancePresenter.cs`, `SbsGuidancePresenter.cs`, `SbsGuidanceOptions.cs` | 일반 2D 또는 SBS 단계 안내 |
| `ManualAlignmentState.cs`, `StereoAlignmentState.cs` | 좌표 조절, 눈별 확인/저장, 양안 PAIR 상태 |
| `StereoAlignmentProbe.cs` | 수동 정렬/수집/후보 추적 시험 UI |
| `DisplayObservation.cs`, `ObservationHttpTransport.cs` | 관측 계약/HTTP와 수신 시점 |
| `DisplayObservationRecorder.cs` | 최신 관측에 화면 좌표를 묶는 저장 경로 |
| `CandidateProjection.cs` | 후보 행렬의 Python/C# 투영 일치와 표시 유효성 |
| `SpatialGuidanceState.cs` | 공간 안내 유효성/상태 계약 |

`Assets/Editor/AssemblyGuideBuilder.cs`가 씬/Player 생성 경로이며, 나머지 Editor smoke는 실제 Unity JSON/계약 검사를 제공한다. `tests/unity`의 순수 .NET 테스트 성공과 실제 Player/안경 검증은 별도다.

## 5. 브라우저와 실행 도구

- `web_overlay/supervisor.html`, `supervisor.js`, `supervisor_state.js`, `supervisor_video.js`, `supervisor.css`: 현재 관제. 영상 opt-in, 단계·보류 이유·공간 진단.
- `web_overlay/index.html`, `app.js`, `style.css`: 이전 카메라 overlay 화면. supervisor와 역할을 구분한다.
- `scripts/run_beast_harness.ps1`: 입력/프로필/실행 조합.
- `scripts/build_beast_unity.ps1`, `run_beast_unity.ps1`: Player 빌드/기기 및 시험 모드 실행.
- `scripts/check_beast_device.ps1`, `server/realtime/beast_device_check.py`: 장치 확인.
- `server/realtime/harness_check.py`: 최소 구성 점검.

검토 목적만으로 카메라/Unity/서버 실행 스크립트를 자동 실행하지 않는다.

## 6. 테스트와 증거

| 범위 | 파일 |
| --- | --- |
| 단계·타이밍 | `tests/realtime/test_timed_guidance.py`, `test_guidance_sequence.py`, `test_online_state_filter.py` |
| 비동기 입력·서버 | `test_runtime_lifecycle.py`, `test_presentation_bridge.py`, `test_yolo_realtime.py`, `test_overlay_http_server.py` |
| pose/보정/후보 | `test_workspace_projection.py`, `test_corner_tracking_report.py`, `test_display_fit.py`, `test_display_joint_fit.py` |
| 수집/미리보기 | `test_display_observation_server.py`, `test_workspace_live_preview.py` |
| 숫자 fixture | `tests/realtime/fixtures/workspace_pose_comfort.json`, `tests/fixtures/spatial_guidance_v1.json` |
| C# | `tests/unity/GuidanceTests.csproj` 및 해당 `*Tests.cs` |
| 브라우저 | `tests/web/*.test.cjs`, 별도 Playwright `*_browser.cjs` |
| 기존 실제 수치 보고서 | 패키지 루트 `evidence/corner-report.json` |

환경이 준비된 검토자가 명시적으로 테스트하기로 결정한 경우의 예시다. 이번 자료 정리에서는 아래를 실행하지 않았다.

```powershell
# source/에서, 프로젝트 전용 Python 환경을 선택한 뒤 실행
python -m pytest tests/realtime/test_workspace_projection.py tests/realtime/test_corner_tracking_report.py -q
# .NET 10 / NUnitLite. 패키지 복원이 필요할 수 있음
dotnet run --project tests/unity/GuidanceTests.csproj -- --noresult
# Node의 순수 상태 검사. 브라우저 실기동 테스트와 별개
node --test tests/web/supervisor_state.test.cjs tests/web/supervisor_feedback.test.cjs tests/web/supervisor_pose.test.cjs
```

`requirements-dev.txt`의 의존성 설치, Unity 라이선스/Editor 실행, 장치 사용, 로컬/외부 서버 기동은 자동 승인된 것으로 간주하지 않는다. snapshot에는 가중치/이미지/개인 프로필이 없어 전체 실행이 제한된다.

## 7. 1학기 코드와 외부 참고

- `server/state/run_state_baseline_v2.py`, `build_hmm_input_v2.py`: 오프라인 HMM v2 계열.
- `server/vision/`: warp, YOLO/MediaPipe/ROI 특징 추출.
- `server/pipelines/`: 세션 검증과 오프라인 재생.
- `README.md`: 주로 1학기 구조/평가. 현재 live `timed_v1` 설명으로 읽지 않는다.
- SafeOps 저장소는 영상/비동기 분석/관제 구조 참고 대상으로 검토했던 별도 프로젝트다. 이 코드 묶음의 의존성이나 현재 활성 운영 서버가 아니다.
- VITURE SDK는 확인 결과 문서만 포함한다. 배포 ZIP/헤더/바이너리를 넣지 않았다.

## 8. 더 깊은 검토에 필요한 원자료

이 패키지만으로 원자료를 새로 측정한 것처럼 결론 내리지 않는다. 정량 재분석 시에는 사용자가 선택한 동일 착용 세트의 PAIR JSON, camera/workspace profile, 숫자 pose trace와 실행 로그가 추가로 필요할 수 있다. 원본 영상이 필요한 분석과 숫자만으로 가능한 분석도 구분한다. 토큰이 들어 있는 `client-config.json`이나 전체 런타임 폴더를 통째로 전달할 필요는 없다.
