# Beast Harness P0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> for native execution, or superpowers:subagent-driven-development only if the
> user selects it. Execute task-by-task; do not treat this plan as approval to
> build Unity or deploy a server. Commit/push only when explicitly requested.

**Goal:** 기존 실시간 코드를 새 PC에서 실행하고, 중복/만료 관측과 재생·로그의
확인된 결함만 고쳐 다음 Unity 작업의 기준선을 만듭니다.

**Architecture:** 기존 Python entry point와 모듈을 수정합니다. 한 프로세스에
한 세션을 사용하고 재생은 EOF에서 끝납니다. 범용 메시지 버스, 새 상태 엔진,
플러그인 프레임워크, 자동 재시작 관리자는 만들지 않습니다.

**Tech Stack:** Python 3.12, 기존 OpenCV/Ultralytics/PyYAML, pytest/unittest, PowerShell.

**Spec:** `../specs/2026-09-26-beast-minimal-harness-design.md`

**Status:** 사용자 승인 후 P0 코드/전체 테스트 59개/실제 영상 119프레임 재생을 검증했습니다.
OpenCV 차단은 해소됐으며, Beast 실카메라 150프레임 실행과 로그 재생도 검증했습니다.
P0 실행 기준선은 확보했습니다. 추적 안정성/표시 정합은 다음 단계이며 제어 USB Code 10을 기록했습니다.
현재 실행 결과는 ../../beast_harness_p0_status.md에 기록합니다.

## Global Constraints

- Windows 노트북 + Beast, Neckband/JEV/운영 SafeOps 의존성 없음.
- 기존 worktree와 사용자 변경을 보존하며 가중치와 과거 가상환경을 삭제하지 않습니다.
- 신규 서버/영상 업로드/카메라 상시 녹화/commit/push는 이 단계에서 하지 않습니다.
- 한 실행에 한 session_id, 자동 반복 재생 없음. 재실행은 모든 객체를 새로 생성합니다.
- YOLO 만료 초깃값은 `max_age_ms=800`; pose 150 ms 기준은 P1-P2의 별도 항목입니다.
- S0-S6 의미/YOLO 가중치/점수 임계값은 변경하지 않습니다. 인식률 튜닝은 하지 않습니다.
- 모의 검사 통과와 실제 영상·장치 검증 결과를 별도로 보고합니다.
- 계획 검토 후 Native 방식으로 제가 순서대로 구현하는 것을 권장합니다.

## Review Focus

- 다른 cwd에서 실행하거나 옛 Python/가중치 경로가 남아 있음: 시작 전에 설명 가능한 실패. Task 1.
- 마커가 복구된 뒤 유실 이전/유실 중 결과가 늦게 옴: 전이 증거로 거부. Task 2.
- 처리 속도는 높은데 새 검출이 없음: 캐시 재조회로 확인 횟수를 늘리지 않음. Task 2.
- 임계값 바로 아래 feature를 저장·재생함: 반올림으로 결과가 바뀌지 않음. Task 3.
- 파일 충돌/전이 기록 실패/재실행: 기존 로그를 보존하고 미기록 상태를 성공으로 게시하지 않음. Task 3.

## Files

| 책임 | 파일 |
| --- | --- |
| 준비 검사 | 새 `server/realtime/harness_check.py`; 기존 장치 진단 재사용 |
| 실행 진입점 | 새 `scripts/run_beast_harness.ps1`; 기존 `run_realtime_server.py` |
| 관측 수용/전이 | 기존 `yolo_realtime.py`, `online_state_filter.py`, `schemas.py`, runtime/config |
| 유한 입력/재생/기록 | 기존 `frame_source.py`, `realtime_replay.py`, `realtime_logger.py`, runtime |
| 회귀 검사 | `tests/realtime/test_harness_check.py`, `test_online_state_filter.py`, `test_yolo_realtime.py`, `test_replay.py`, `test_realtime_logger.py` |

기존 파일명만 표시한 Python 파일은 모두 `server/realtime/` 아래입니다.
이름만을 위해 새 모듈을 추가하지 않으며, helper는 소유 모듈 안에 둡니다.

## Task 1: 환경과 단일 실행 경로

**Files:** 새 `harness_check.py`, `scripts/run_beast_harness.ps1`,
`tests/realtime/test_harness_check.py`; 수정 `run_realtime_server.py`.

**Interfaces:**
- `build_effective_config(base: dict, args: argparse.Namespace) -> dict`
  를 runtime에 둡니다. CLI override와 절대 경로를 합쳐 실제 사용한 설정을 만듭니다.
- `check_runtime(config: dict, *, source: str, session_path: Path | None) -> dict`
  는 `ready: bool`, `checks: list[dict]`를 반환합니다. 각 check는 name/status/detail입니다.
- PowerShell `-Mode doctor|replay|live-local`, `-PythonExe`, `-Config`,
  `-Session`, `-Weights`를 받습니다. repo root는 `$PSScriptRoot` 기준입니다.
- 준비 검사의 종료 코드: 0 준비됨, 1 필수 항목 누락, 2 조회/설정 오류.
  장치 미검사나 모델 미추론은 별도 상태이며 하드웨어 성공으로 합치지 않습니다.

- [x] **환경 준비:** `%LOCALAPPDATA%/ARAssembly/beast-mvp/.venv`에 새 환경을 준비합니다.
  기존 경로가 있으면 먼저 확인하고 삭제하지 않습니다. 기존 requirements-dev.txt를
  사용하고 설치 결과/version을 기록합니다. main의 가중치는 명시적 경로로 참조하며
  모델 복사/다운로드나 GPU 프레임워크 교체를 추가하지 않습니다.
- [x] **실패 검사 작성:** 선택 모드별 의존성 누락, weights/fixture 누락,
  잘못된 config, CLI override 보존, 다른 cwd, 준비 실패 후 camera/server 미시작을 검사합니다.
  예: `assert report['ready'] is False`; camera factory와 server start mock은 미호출이어야 합니다.
- [x] **실패 확인:** `& $Py -B -m pytest tests/realtime/test_harness_check.py -q`.
- [x] **최소 구현:** 준비 검사 뒤 리소스를 열고 실패 경로에서도 열린 카메라/worker/server를
  정리합니다. feature-log 검사에는 카메라나 YOLO 모델을 요구하지 않습니다.
  `doctor`는 카메라를 자동으로 열지 않습니다. 실제 캡처 검사는 기존 probe를 사용합니다.
- [x] **통과 확인:** 위 pytest 및
  `& $Py -B -m unittest discover -s tests/realtime -p test_beast_device_check.py -v`.
  성공한 doctor와 고의로 잘못된 weights 경로의 실패 출력을 각각 기록합니다.

`$Py`는 새 환경의 `Scripts/python.exe` 절대 경로입니다. 설치 실패 시 남은 검사를
성공으로 표시하지 않으며, 임의의 다른 Python으로 조용히 전환하지 않습니다.

## Task 2: 새롭고 유효한 관측만 전이에 사용

**Files:** 수정 `yolo_realtime.py`, `online_state_filter.py`,
`run_realtime_server.py`, `configs/realtime_viture_beast_aruco.yaml`;
새 `tests/realtime/test_yolo_realtime.py`, `test_online_state_filter.py`.

**Interfaces:**
- `YoloRealtimeResult`에 `session_id: str=''`, 원본 `timestamp_ms: int=-1`,
  `source_marker_ok: bool=False`를 추가합니다. `frame_id`는 기존 원본 ID를 그대로 사용합니다.
- analyzer 생성자에 `session_id: str`, `max_age_ms: int=800`을 전달합니다.
  runtime이 만든 세션 ID를 결과까지 보존하고 다른 세션의 결과는 거부합니다.
- `submit(frame_id, frame_bgr, homography, *, timestamp_ms: int, marker_ok: bool) -> None`.
  marker invalid 입력은 추론에 제출하지 않습니다. worker는 영상/H/원본 시각을 함께 보존합니다.
- `get_result(current_frame_id: int, *, now_ms: int, min_valid_frame_id: int = 0)
  -> YoloRealtimeResult`. 만료/미래 ID/유실 이전 결과를 전이용으로 사용하지 않습니다.
  유효 조건은 `0 <= now_ms - timestamp_ms <= max_age_ms`이며 다른 invalid 조건도 없어야 합니다.
- 필터 `update(frame_id, marker_ok, features=None, *, observation_id: int | None = None,
  evidence_valid: bool = True) -> StateEstimate`.
  YOLO를 요구하는 나사 단계에서만 새 observation_id가 확인 횟수를 늘립니다.
  마지막 소비 ID는 단계 전이 때 지우지 않습니다. S0/S1 ROI와 dummy 경로는 유지합니다.

- [x] **실패 검사 작성:** 동일 관측 세 번으로 전이하지 않음; 서로 다른 정상 관측은
  기존 조건을 충족하면 전이함; 후보 두 번 -> marker invalid -> 한 번으로는 전이하지 않음;
  frame ID 차이가 작아도 800 ms 초과는 만료; 다른 세션/유실 이전 늦은 응답/미래 ID는 거부.
  같은 캐시를 읽을 때 원본 결과 객체/시각이 바뀌지 않는 대조 검사도 넣습니다.
- [x] **실패 확인:**
  `& $Py -B -m pytest tests/realtime/test_online_state_filter.py tests/realtime/test_yolo_realtime.py -q`.
  실제 GPU 대신 모델 대역을 사용해 검출 정책만 검사합니다.
- [x] **최소 구현:** runtime이 마지막 marker invalid 프레임을 기록하고 그보다 이전/같은
  결과를 거부합니다. marker invalid 또는 검출 만료에는 미확정 후보/latch를 지웁니다.
  같은 관측의 재조회는 누적도 갱신도 하지 않습니다. 현재 확정 상태는 유지합니다.
  `yolo_age_ms`는 실제 경과시간으로 바꾸고 frame 나이는 진단값으로만 남깁니다.
- [x] **통과 확인:** 상태/YOLO 정책 및 장치 진단 단위 검사는 통과.
  Beast 연결 후 camera probe와 실카메라 150프레임 실행/입력 재생을 확인했습니다.
  회귀 검사에서 실제 재현한 두 결함이 막혔음을 보고합니다.

P0는 현재 확인 횟수 규칙을 새로운 관측에만 적용하는 단계입니다.
시간 기반 연속 dwell과 도구 이탈은 P3에서 구현하며 P0 완료를 작업 완료 판정의
정확성 확보로 보고하지 않습니다. 검출 만료 시간은 성능 평가 후에만 조정합니다.

## Task 3: 유한 재생과 판단 입력 기록

**Files:** 수정 `frame_source.py`, `realtime_replay.py`, `realtime_logger.py`,
`run_realtime_server.py`, `schemas.py`; 새 `tests/realtime/test_replay.py`,
`test_realtime_logger.py`, 작은 `tests/realtime/fixtures/filter_input.jsonl`.

**Interfaces:**
- `SessionFrameSource.__iter__()`는 한 번만 순회하고 끝납니다. 원본 ID/시간은
  `FramePacket.source_frame_id: int | None`와 `source_timestamp_ms: int | None`에 보존합니다.
  timestamp_ms는 현재 실행의 로컬 시각과 혼동하지 않습니다.
- 기존 `results.jsonl`에 `filter_input`을 추가합니다. 내부에는 update에 실제 전달한
  `frame_id`, `marker_ok`, `features`, `observation_id`, `evidence_valid`를 그대로 저장합니다.
- `replay_filter_inputs(rows: Iterable[dict], filter_config: dict) -> list[dict]`
  를 `realtime_replay.py`에 둡니다. 결과 항목은 frame_id/state/transition_event입니다.
  과거 log 조회 CLI는 유지하고 `--validate-filter`를 추가합니다.
- 새 session_id는 시각+UUID suffix로 만듭니다. 기존 session 디렉터리는 덮어쓰지 않습니다.
  이 단계의 replay는 저장된 필터 입력을 재현하며 실시간 GPU 실행 순서의 동일성을 보장하지 않습니다.

- [x] **실패 검사 작성:** 두 입력 이미지가 정확히 두 번 yield된 뒤 종료;
  빈/읽을 수 없는 입력은 실패; 새로운 실행은 S0 또는 설정된 초기 상태에서 시작;
  `0.5499996` 저장/재입력 후 상태 동일; CLI override를 포함한 config_used 일치;
  같은 session 디렉터리 재사용 거부; 최초 이벤트 from_state가 실제 초기 상태와 일치.
  로그의 이미지 경로는 image_path/path뿐 아니라 현재 logger의 saved_frame도 읽습니다.
- [x] **실패 확인:**
  `& $Py -B -m pytest tests/realtime/test_replay.py tests/realtime/test_realtime_logger.py -q`.
- [x] **최소 구현:** filter_input의 float는 JSON 원정밀도로 기록하고 표시용 반올림과
  분리합니다. filter 검증은 저장된 입력 순서/유효성을 사용하고 실행 속도로 판단을 바꾸지 않습니다.
  실효 설정과 모델 hash/code revision을 저장합니다. 미측정 시각은 0 ms 성능처럼 표시하지 않습니다.
- [x] **전이 저장 정책:** 결과 입력/전이 이벤트를 flush/fsync한 뒤 새 상태를 게시합니다.
  기록 실패 시 중단합니다. mock으로 저장 실패가 상태 게시보다 먼저 중단되는지 검사합니다.
  강제 전원 차단/저장장치 손실 보장, 자동 세션 복원, P4 outbox는 이 단계에서 만들지 않습니다.
- [x] **통과 확인:** 로그를 새 필터에 넣어 state/transition_event 목록을 비교하고
  저장 당시 결과와 일치해야 합니다. 재생용 필드가 없는 과거 로그는 열람만 가능하다고 알립니다.
- [x] **최종 확인:** 전체 `pytest -q` 59개(기존 장치 unittest 8개 포함)가 통과했습니다.
  feature fixture 및 확보된 실제 영상 fixture를 구분해 결과를 남깁니다.
  영상이 없으면 실제 영상 재현은 미검증으로 남기고 실기기 준비 완료라고 보고하지 않습니다.

## P0 종료와 다음 순서

P0 산출물은 실행기 하나, 환경 검사, 재현 가능한 필터 입력/로그, 위 결함의 회귀 검사입니다.
실제 카메라는 기존 probe로 하드웨어 ID/preview를 대응시키고 사용자 확인을 기록합니다.
P0를 완벽한 범용 프레임워크로 키우지 않고 이 기준을 통과하면 P1로 넘어갑니다.

1. **P1 Unity 표시:** Scene 하나, 시험 원/문구, 직접 표시 모드, 수신 끊김/같은 pose 반복 시 숨김.
2. **P2 실제 정합:** 마커/나사 실측, 카메라 보정, 착용자 보정. 보정에 안 쓴 점에서 오차 확인.
3. **P3 자동 안내:** 시간 기반 머무름/유효한 이탈, 현재 대상 유지, pause/resume/최종 확인.
4. **P4 원격/관제:** 원격 YOLO 하나와 웹 한 페이지. bbox 계약, 저장 ACK/재전송, 읽기/쓰기 인증.
5. **P5 시연 평가:** 새 조립 세션, 가림/재착용/끊김 시험과 결과 기록.

Native 실행을 권장하는 이유는 세 작업이 같은 runtime을 순차 수정하며 범위가 작아
작업마다 새 에이전트를 띄우는 비용이 필요하지 않기 때문입니다.
사용자 승인으로 실행했습니다. 코드 구현과 실제 영상/장치 검증 완료는 구분합니다.
