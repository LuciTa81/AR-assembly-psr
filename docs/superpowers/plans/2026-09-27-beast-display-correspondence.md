# Beast Display Correspondence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 수동 SBS 시험에서 눈별 화면 좌표와 최신 카메라 관측을 함께 저장하고, 실제 왼눈/오른눈 후보를 각각 한 개 이상 확인합니다.

**Architecture:** 기존 ArUco/PnP 카메라 worker는 영상 없이 관측 메타데이터만 선택적으로 전달합니다. 유한 수명의 loopback API를 Unity가 Enter마다 요청하고, 표시 조건과 관측 신선도를 확인한 뒤 후보 JSON을 저장합니다. 기존 카메라 없는 시험과 일반 인식 서버는 유지합니다.

**Tech Stack:** Python 3.12, OpenCV, multiprocessing, 표준 HTTP 서버, Unity 6000.3.25f1, UnityWebRequest/JsonUtility, NUnitLite/.NET 10, pytest, PowerShell.

**Spec:** `docs/superpowers/specs/2026-09-27-beast-display-correspondence-design.md`

상태: 설계/직접 구현 승인 완료. Tasks 1~3 구현 및 테스트 통과, Task 4 소프트웨어 연결/검사 완료. Task 5 리뷰 및 실제 착용 시험 대기.
권장 실행: 이 세션에서 직접 순차 구현하고 마지막에 독립 리뷰 한 번 수행합니다.

## Global Constraints

- Beast 0DoF + Full SBS. 렌더/실제 출력은 3840x1080 또는 3840x1200이며 시험 중 변경되면 종료합니다.
- 기존 2D/SBS 수동 시험은 카메라/HTTP 없이 계속 동작합니다. 선택적 수집 모드에서만 연결합니다.
- 일반 인식 서버, OnlineStateFilter, YOLO 및 기존 /state.json 계약을 바꾸지 않습니다.
- `target_id=A`, 눈별 좌표는 eye-local pixels/top-left, camera XYZ는 OpenCV(+X right,+Y down,+Z forward), mm입니다.
- `conservative_age_ms=age_ms+request_rtt_ms`가 0~150ms일 때만 허용합니다. 서로 다른 프로세스의 원시 monotonic 시각을 빼지 않습니다.
- 이는 소프트웨어 수신 나이 검사입니다. 센서 노출/광학 지연 또는 정밀 동기화를 보증하지 않습니다.
- 영상은 RAM에서만 처리합니다. 프로세스 간 영상 전송, 영상 HTTP endpoint, 영상 저장은 없습니다.
- `127.0.0.1` 임시 포트, 실행별 Bearer token, CORS 없음, 리다이렉트 거부. 토큰 로그 금지.
- 설정/후보/요약은 OneDrive 밖 `%LOCALAPPDATA%/ARAssembly/beast-mvp/display_correspondence`의 실행별 새 폴더에 저장합니다.
- `candidate_only=true`, `calibration_valid=false`, `display_alignment_verified=false`를 유지합니다.
- 서버/클라이언트 시험은 최대 300초입니다. 종료 지연 시 이번 실행이 소유한 카메라 자식만 정리합니다.
- 실제 촬영 전 착용/작업대 준비를 확인합니다. 클라우드, 보정 모델 fitting, 자동 추적 원은 이번 범위가 아닙니다.
- 기존 dirty worktree를 보존합니다. 커밋/푸시/배포는 하지 않습니다. 새 외부 패키지는 추가하지 않습니다.

## Review Focus

1. 카메라 프로세스가 정상 프레임 뒤 죽거나 멎음: 이전 정상 관측으로 계속 저장되지 않아야 합니다. Task 2/4에서 검사합니다.
2. Enter 이후 응답 전에 디스플레이/눈 선택/종료 상태가 바뀜: 늦은 응답을 저장하지 않아야 합니다. Task 3/4에서 검사합니다.
3. JSON 필드 누락이 숫자 0으로 바뀜: 필수 필드를 누락한 응답은 유효 관측으로 취급하지 않아야 합니다. Task 3/4에서 검사합니다.
4. 한글/공백 경로, 파일 충돌 및 디스크 쓰기 실패: 기존 파일을 덮어쓰거나 SAVED를 표시하지 않아야 합니다. Task 3/4에서 검사합니다.
5. 화면 렌더 크기는 같고 물리 출력만 바뀜: 기존 SBS의 fail-closed 동작을 수집 모드에서도 유지해야 합니다. Task 4에서 검사합니다.

---

## File Map

| 파일 | 책임 |
| --- | --- |
| `server/realtime/workspace_live_preview.py` | 기존 worker의 선택적 영상 미전송 |
| `server/realtime/display_observation_server.py` (신규) | 최신 관측 API, 설정 생성, 유한 실행 및 정리 |
| `client_unity/Assets/Scripts/DisplayObservation.cs` (신규) | DTO, 후보 검증, 중복/저장 성공 규칙. UnityEngine 비의존 |
| `client_unity/Assets/Scripts/DisplayObservationRecorder.cs` (신규) | Unity 요청/JSON 변환/선택적 수집 수명 |
| `client_unity/Assets/Editor/DisplayObservationSmoke.cs` (신규) | 실제 JsonUtility 누락/오류 계약을 확인하는 batch 검증 |
| `client_unity/Assets/Scripts/StereoAlignmentState.cs` | 저장 전 스냅샷과 저장 후 확정 분리 |
| `client_unity/Assets/Scripts/StereoAlignmentProbe.cs` | 기존 키 조작에 선택적 눈별 수집 연결 |
| `scripts/run_beast_unity.ps1` | 수집 설정 경로 옵션 |
| `tests/realtime/test_display_observation_server.py` (신규) | 기하/HTTP/종료 검사 |
| `tests/realtime/test_workspace_live_preview.py` | 기존 worker 회귀 검사 |
| `tests/unity/DisplayObservationTests.cs` (신규) | 계약/신선도/중복/쓰기 실패 검사 |
| `tests/unity/StereoAlignmentStateTests.cs`, `GuidanceTests.csproj` | 상태 회귀 및 새 순수 C# 코드 포함 |
| `docs/beast_manual_alignment_probe.md` | 실행법, 실제 결과, 한계 기록 |

## Task 1: Metadata-Only Camera Worker

**Interfaces:** 기존 `camera_worker(queue, stop, camera_index, camera, workspace, errors)`에 마지막 인수 `include_image: bool = True`를 추가합니다. False일 때 packet에는 `frame_id`, `received_at`, `analysis`만 포함하며 `image` 키를 넣지 않습니다. 기존 `analyze_frame`, 오류 큐, release 및 stop_worker를 재사용합니다.

- [x] `test_camera_worker_metadata_only_omits_image`를 작성합니다. 합성 프레임으로 `image not in packet`, 기존 분석/프레임 ID/수신시각 보존, `cap.release` 호출을 확인합니다.
- [x] 대상 pytest를 실행해 새 옵션 미지원으로 실패하는 것을 확인합니다.
- [x] worker에 옵션만 추가합니다. 기존 미리보기 기본 경로와 이미지 분석 방식은 바꾸지 않습니다.
- [x] `test_workspace_live_preview.py` 전체를 실행합니다. 기본 영상 전달 및 metadata-only 두 경로가 모두 통과해야 합니다.

## Task 2: Local Observation API And Finite Runner

**Interfaces:** 새 `display_observation_server.py`가 아래 API를 제공합니다.

- `make_observation(packet: dict | None, now: float, session: dict, camera: CameraModel, workspace: MetricWorkspace) -> dict`: age, 상태, target A 좌표를 생성합니다.
- `ObservationStore(session: dict, camera: CameraModel, workspace: MetricWorkspace)`, `update(packet)`, `invalidate(reason: str)`, `snapshot(now: float) -> dict`: lock으로 최신 메타데이터 하나만 보관합니다.
- `start_server(store: ObservationStore, token: str) -> tuple`: `(ThreadingHTTPServer, Thread)` 반환. 주소는 127.0.0.1:0, GET /observation만 허용합니다.
- `run_collection(camera_path: Path, workspace_path: Path, camera_index: int, seconds: float, root: Path | None = None) -> Path`: 기존 프로필 검증, metadata worker, API, deadline, 종료 및 요약을 소유하고 실행 폴더를 반환합니다.
- CLI: `python -m server.realtime.display_observation_server --camera-profile PATH --workspace-profile PATH --camera-index 1 --seconds 300`.

**Wire decisions:** 응답 `schema_version=beast_display_observation_v1`. 배열은 rvec/tvec/world_xyz/camera_xyz 각 길이 3, image_size/target_pixel 길이 2입니다. 프로필 ID/hash는 `camera_profile_id`, `camera_profile_sha256`, `workspace_profile_id`, `workspace_profile_sha256`로 평탄화합니다. 성공 status는 tracking. JSON은 allow_nan=False로 생성합니다.

설정 `schema_version=beast_display_collection_config_v1`에는 `session_id`, `observation_url`, `token`, 예상 프로필 ID/hash, `image_size`, `target_id=A`, 실행 `directory`를 넣습니다. 새 실행은 새 session_id/token/폴더를 사용합니다. 설정은 원자적으로 완성한 뒤 경로만 stdout에 출력합니다.

- [x] `test_observation_preserves_geometry_and_age` 작성: 합성 pose에서 camera XYZ가 `Rodrigues(rvec) @ xyz + tvec`와 일치하고 픽셀은 기존 `project_targets`와 같습니다. 수신 10.0, now 10.1이면 age 약100ms입니다.
- [x] invalid/future/stale, target behind/off-image, duplicate marker rejection, 정상 뒤 유실/worker 오류/worker 종료에 대한 테스트를 작성합니다. 이전 정상 target이 되살아나지 않아야 합니다.
- [x] 실제 ephemeral HTTP 테스트를 작성합니다. Bearer 없거나 다르면 401, 다른 경로는 404, CORS/image 없음, snapshot마다 age 증가, 서로 다른 실행의 token/session 분리, 비유한 JSON 미출력을 확인합니다.
- [x] 위 pytest를 실행해 신규 모듈/기능 부재로 실패함을 확인합니다.
- [x] 기존 load_profiles/analyze_frame을 사용해 구현합니다. 별도 모델/추적 알고리즘은 만들지 않습니다. producer 오류 큐와 생존 상태를 프레임과 별도로 확인하며 오류 상태에서는 재사용을 차단합니다.
- [x] 가짜 worker와 짧은 deadline으로 실행 수명 테스트를 추가합니다. 정상/예외/멎은 read 모두 API close와 소유 자식 종료, 폴더 내 영상 없음, 요약 기록을 확인합니다. HTTP 요청도 연결 timeout으로 유한 처리합니다.
- [x] `test_display_observation_server.py`와 기존 camera/projection 관련 테스트를 실행해 모두 통과시킵니다.

## Task 3: Unity Contract And Transactional Candidate Save

**Interfaces:** 새 `DisplayObservation.cs`는 `[Serializable]` DTO `DisplayCollectionConfig`, `DisplayObservation`, `DisplayCorrespondenceCandidate`를 선언합니다. JSON 이름은 Task 2와 동일하게 사용합니다. 후보는 원본 관측, `StereoAlignmentPoint`, 선택 눈, 출력 크기, `request_started_seconds`, `response_received_seconds`, `request_rtt_ms`, `conservative_age_ms`를 포함합니다.

- `DisplayCorrespondenceRules.Create(config, observation, point, outputWidth, outputHeight, requestStarted, responseReceived) -> DisplayCorrespondenceCandidate`: 잘못된 입력은 ArgumentException, 성공은 후보를 반환합니다. 필수 숫자 DTO 초기값은 NaN/-1 등 검증에서 거부되는 값으로 두고, 누락은 0으로 성공 처리하지 않습니다.
- `DisplayCorrespondenceStore.Save(candidate, string json) -> string`: 실행 폴더에 FileMode.CreateNew로 기록한 최종 경로 반환. 같은 눈/프레임 중복 및 다른 세션 거부, 파일 성공 후에만 중복 집합/Count 변경. JSON은 Recorder가 JsonUtility로 생성합니다. 쓰다 실패한 파일은 후보 확장자로 남지 않도록 임시 파일을 완료 후 rename합니다.
- `StereoAlignmentState.PreviewMark(double now) -> StereoAlignmentPoint`: 변경 없는 후보. `CommitMark(StereoAlignmentPoint point, double now) -> void`: 동일 상태/좌표/다음 index/유효 수명일 때만 확정. 기존 `Mark(now)`는 두 메서드를 즉시 호출하여 기존 동작을 보존합니다.

- [x] NUnit에 fresh 성공, age+RTT=150 허용/150 초과 거부, 음수/NaN/Infinity/역전 시각, 잘못된 세션/hash/해상도/target/XYZ 길이/뒤쪽/화면 밖, Channels/Both 거부 테스트를 작성합니다. 요청과 응답의 Unity 시각 차이만 RTT에 사용합니다.
- [x] `PreviewMark`가 상태를 바꾸지 않고, 이후 좌표/눈/수명이 달라지면 `CommitMark`가 거절하는 회귀 테스트를 작성합니다.
- [x] 저장 테스트에 한글/공백 임시 경로, 동일 눈+frame 중복 거부, 다른 눈은 별도 기록, 기존 파일 충돌, 쓰기 실패 시 Count=0 및 재시도 가능을 포함합니다.
- [x] csproj에 신규 순수 코드/테스트를 연결하고 `dotnet run --project tests/unity/GuidanceTests.csproj -- --noresult`로 실패를 확인합니다.
- [x] 위 DTO/검증/파일 저장/상태 분리를 구현하고 전체 NUnit을 통과시킵니다. 점수/기하 보정 모델은 추가하지 않습니다.

## Task 4: Optional Unity Collector Integration

**Interfaces:** `DisplayObservationRecorder`는 MonoBehaviour입니다. `Initialize(string configPath)`, `bool Pending`, `string Status`, `Collect(StereoAlignmentPoint point, Func<bool> stillValid, Action<StereoAlignmentPoint> onSaved)`, `Cancel()`을 제공합니다. Collect가 pending이면 중복 요청을 시작하지 않습니다. 설정 경로는 `--display-observation-config PATH`로 전달합니다.

Recorder는 GET의 timeout=1초, redirectLimit=0, 제한된 응답 크기(64KiB)를 적용합니다. 종료/disable 시 Abort/Dispose하고 늦은 callback은 무시합니다. 로컬 주소/설정 스키마와 프로필을 시작 시 검사합니다. 기록 시 표시 조건을 다시 검사하고, 파일 저장 및 CommitMark 성공 뒤에만 SAVED를 표시합니다. 저장/확정은 Unity 메인 스레드의 동일 callback에서 처리합니다.

- [ ] 설정 주소 검사에 localhost 유사 이름, 외부 IP, userinfo, redirect, 누락 URL/token/session을 거부하는 테스트를 추가합니다. 허용 URL은 생성된 `http://127.0.0.1:<port>/observation` 형식뿐입니다.
- [ ] 수집 옵션이 없는 기존 SBS 경로는 Recorder/HTTP를 만들지 않는 것을 검사합니다. 옵션은 `-Beast -StereoAlignmentProbe`와 함께만 허용하며 파일 없음/충돌 인수는 Player 실행 전에 거절합니다.
- [ ] Recorder/Probe를 연결합니다. Enter는 PreviewMark를 고정하고 Collect, 성공 콜백은 CommitMark입니다. Pending 동안 이동/눈 전환/중복 Enter는 막고 Q/Esc는 즉시 종료합니다. Both Enter는 저장하지 않습니다.
- [ ] 진단 표시는 CAPTURING / SAVED / STALE / NO POSE / CONNECTION ERROR 정도로 제한합니다. NOT CALIBRATED는 유지합니다. 수집 모드에는 일반 안내용 화면 좌표를 공급하지 않습니다.
- [ ] `client_unity/Assets/Editor/DisplayObservationSmoke.cs`의 `ARAssembly.DisplayObservationSmoke.Run()`으로 실제 JsonUtility 파싱 smoke test를 작성/실행합니다. Unity `-batchmode -nographics -executeMethod ARAssembly.DisplayObservationSmoke.Run`에서 정상 fixture는 통과하고 필드 누락, 깨진 JSON, 비유한 수치, 잘못된 스키마는 모두 저장 전에 거절되어야 합니다. 테스트 실패 시 Editor exit code=1, 모두 통과하면 0입니다.
- [ ] 합성 HTTP endpoint로 build된 Player를 검사합니다. 정상/401/redirect/stale/응답 지연/종료 중 응답/marker 유실 모두 예상 상태가 되고, 해상도 및 물리 출력 변경 시 저장과 원 표시가 중지되어야 합니다. 장치가 없으면 하드웨어 항목은 미검증으로 남깁니다.

## Task 5: Regression, Review, And Short Hardware Pilot

- [ ] PowerShell에서 `& (Join-Path $env:LOCALAPPDATA 'ARAssembly/beast-mvp/.venv/Scripts/python.exe') -m pytest tests/realtime -q` 전체 통과. 기존 실행 전 기준은 153 tests이며 늘어난 테스트 수를 기록합니다.
- [ ] `dotnet run --project tests/unity/GuidanceTests.csproj -- --noresult` 전체 통과. 기존 기준 52 tests를 유지합니다.
- [ ] `scripts/build_beast_unity.ps1` 실행 후 Unity build 성공/오류 유무를 로그에서 확인합니다. 새 인수의 PowerShell negative test도 실행합니다.
- [ ] 새 변경에 대해 독립 리뷰를 한 번 요청합니다. 특히 stale/clock/domain mismatch, 표시 변경, 쓰기 성공 표시, 소유 process 정리 및 기존 카메라 없는 경로를 확인합니다.
- [ ] 사용자에게 카메라 실행 준비를 확인합니다. 상자/마커 고정, 노트북 화면은 카메라 시야 밖, 0DoF+Full SBS를 유지합니다. 양쪽 원이 전에 같은 자세에서 겹쳤다는 기존 결과를 보존합니다.
- [ ] 최대300초 서버 및 Unity를 실행합니다. 눈별 원을 나사 A에 맞춘 뒤 Enter부터 저장 응답까지 자세를 유지해 각각 최소1개를 저장합니다. 이전 성공 좌표를 카메라 관측 없이 자동 후보로 가져오지 않습니다.
- [ ] 종료 후 실제 후보에서 세션/hash/카메라 XYZ/눈별 좌표/age/RTT와 수락/거절 수를 확인합니다. 양안 비교는 사용자 관찰과 파일 증거를 구분해 기록합니다. 관련 세션이 실행 중이면 최종 응답 전에 종료/확인합니다.
- [ ] 문서에 실행법/결과/미검증 범위를 업데이트합니다. 아직 보정 fitting이나 자동 추적이 완성되지 않았음을 명시합니다. 하드웨어 시험이 어려우면 소프트웨어 검증 완료와 실기기 대기를 분리해 보고합니다.

## Self-Review

- Spec의 흐름/좌표/거절/수명/저장/검사는 Tasks 1~5에 대응합니다.
- 일반 인식 API, 자동 정합, cloud/dashboard 및 추가 모델은 포함하지 않았습니다.
- 기존 성공은 양안 단일점 수동 관찰이며, 이번 후보 한 쌍도 보정 정확도 검증을 대체하지 않습니다.
- 실행 절차의 approval은 설계 승인과 별도입니다. 계획 검토 후 선택된 방법으로 구현합니다.
