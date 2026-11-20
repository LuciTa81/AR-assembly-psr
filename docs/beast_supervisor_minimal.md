# 최소 로컬 관제 화면

2026-10-06. 승인한 읽기 전용 표시 범위만 추가했다.

후속: 같은 날 선택적 영상·판정 피드백을 보강했다.
최신 범위, 합성 시연, 테스트 및 후속 순서는
[최소 시연 로드맵](beast_demo_roadmap_20261006.md)을 참조한다.
아래 내용은 최초 상태 전용 관제와 실입력 진단 기록이다.

## 구현 범위

```text
기존 Python 인식 / 상태 서버
              /state.json
              ├─ 기존 Unity 안내 클라이언트
              └─ /supervisor.html 읽기 전용 관제
```

- 현재 상태, 서버 target, 서버 next_action, guidance phase, 별도 acknowledgement.
- S0~S6 단계 표시, 마커/품질/FPS/처리 시간, 수신 데이터 나이.
- 실제 카메라 / 저장 세션 / 합성 재생 구분. S6는 최종 확인 대기.
- 최초 입력 전에는 상태 미확정. 서버 나이와 HTTP 왕복 시간을 포함한 500 ms
  예산을 넘기거나 연결/추적이 끊기면 안내 보류. 마지막 수신 상태는 참고로 유지.
- 반복 프레임은 유효 시간을 연장하지 않는다. 새 프레임만 연결 회복 가능.
- 실물 정합은 미검증으로 표시. 브라우저는 좌표나 조립 상태를 추론하지 않는다.
- R4 `assembly_guidance_v1` 계약을 사용한다. guidance가 빠진 이전 메시지는
  임의 추론하지 않고 오류로 처리한다.

수정하지 않은 것: Python 인식/상태 알고리즘, Unity, 기존 카메라 진단 페이지,
HTTP 서버, 모델/임계값. 이번 페이지는 영상을 자동 요청하지 않는다.
클라우드, AWS, Laravel, 원격 접근, 영상 관제, 이벤트 이력, 정합 보정은 추가하지 않았다.

## 실행

프로젝트 루트에서 기존 서버를 실행한 뒤 아래 주소로 접속한다.

- 관제: http://127.0.0.1:8765/supervisor.html
- 기존 카메라 진단: http://127.0.0.1:8765/
- Unity: 기존 `scripts/run_beast_unity.ps1` 사용. 같은 서버의 상태를 수신한다.

합성 재생은 아래 명령으로 24초간 실행되고 자동 종료한다.
실제 카메라와 합성 서버를 같은 포트에서 동시에 실행하지 않는다.

```powershell
& "$env:USERPROFILE\AppData\Local\ARAssembly\beast-mvp\.venv\Scripts\python.exe" -X utf8 -B tests/unity/serve_snapshot_fixture.py --guidance
```

실입력은 `scripts/run_beast_harness.ps1 -Mode live-local`을 사용하되,
`-PythonExe`에 위 Python 경로, `-Weights`에 기존 주 체크아웃의
`models/yolo/driver_standard_model/best-3.pt` 절대 경로를 지정한다.
현재 worktree에는 weight 파일이 없으므로 기본 경로만 사용하면 doctor가 실패한다.
복사/다운로드나 설정 변경 대신 기존 weight 경로를 명시했다.

## 검증 결과

- Python 전체: 288 passed.
- Unity C# NUnit: 165 passed. 이번에 Unity 코드는 변경하거나 재빌드하지 않았다.
- 웹 상태 표시: 13 passed. 실제 필터가 생성한 합성 R4 snapshot 481개를 대조했다.
- 실제 Chromium: S0~S6, GUIDING/OBSERVING/OBSERVED/PAUSED/TRACKING_LOST/
  AWAITING_CONFIRMATION/DISCONNECTED 표시 확인. 데스크톱 1440x900,
  모바일 390x844에서 가로 넘침 없음, page error 없음.
- 웹 요청은 loopback 내부만 사용. 관제 페이지의 frame.jpg 요청 없음.
- 기록: `outputs/supervisor_r6/browser-report.json`, 같은 폴더의 화면 PNG.
- 합성 프레임 검증은 실제 작업 정확도나 광학 정합 성공을 의미하지 않는다.
- 오래된 프레임의 안내 차단은 상태 모델 테스트로 검증했다.

재검증 명령:

```powershell
$py = "$env:USERPROFILE\AppData\Local\ARAssembly\beast-mvp\.venv\Scripts\python.exe"
& $py -X utf8 -B tests/unity/guidance_fixture.py --output outputs/supervisor_r6/r4_fixture.json
$env:GUIDANCE_FIXTURE = 'outputs/supervisor_r6/r4_fixture.json'
node --test tests/web/supervisor_state.test.cjs
$env:BEAST_PYTHON = $py
$env:PLAYWRIGHT_MODULE = "$env:USERPROFILE\.codex\skills\gstack\browse\dist\node_modules\playwright"
node tests/web/supervisor_browser.cjs
```

## 이번 실입력 검사의 한계

- Beast 카메라 후보와 모니터는 Windows에 연결되어 있었다.
- 기존 DirectShow index 1에서 160프레임, 첫/마지막 timestamp 차이 5.301초를
  수집하고 정상 종료했다. 예상보다 빠르게 프레임 한도에 도달했다.
- 모든 프레임에서 marker_count=0, marker_status=LOST, state=S0,
  guidance=PAUSED였다. YOLO도 전체 표본에서 warming_up이었다.
- 세션: `viture_aruco_rt_20261006_141114_2c9205685860`.
- 영상은 저장/외부 전송하지 않았다. 로컬 상태/feature 로그만 남겼다.
- 이 결과로 Beast 시점 일치, 조립 인식 성공, 실입력과 Unity/웹 동시 표시를
  검증했다고 주장할 수 없다. HTTP 조회는 자동 종료 시점과 겹쳐 실패했다.
- USB 연결 순서에 따라 camera index가 바뀔 수 있다. 다음 착용 검사에서는
  실제 시점과 마커 입력부터 확인한다. 이번에는 임계값을 완화하지 않았다.

## 마커 0개 원인 확인 및 수정 (2026-10-06 후속)

카메라 선택 번호가 이전 측정 때와 달라져 있었다. 현재 DirectShow index 0은
Beast이고 index 1은 노트북 카메라였다. 두 입력을 각각 10초간 저장 없는
로컬 미리보기로 비교했으며, 사용자가 0번의 작업대 시점과 안경 움직임을 확인했다.

| 비교 입력 | 프레임 | 검출 ID | 정상 추적 |
| --- | --- | --- | --- |
| index 0 (Beast) | 94 | 0, 1, 2, 3, 4, 5 | 65 (LOST 13, FALLBACK 16) |
| index 1 (노트북) | 300 | 없음 | 0 (LOST 300) |

두 입력에 동일한 DICT_4X4_50, marker layout, min_markers=4,
min_quality=0.25를 적용했다. 임계값이나 마커 알고리즘을 바꾸지 않고
`configs/realtime_viture_beast_aruco.yaml`의 camera_index만 1에서 0으로 수정했다.

기존 전체 파이프라인 재검사:

- 세션: `viture_aruco_rt_20261006_141857_fe281dec6f91`.
- 200프레임, 첫/마지막 timestamp 차이 19.900초, 최대 마커 6개.
- marker_status=OK 197프레임, FALLBACK 3프레임, LOST 0프레임.
- S0→S1 전이, 유효 YOLO 결과(`reason=ok`) 발생 확인.
- 이 비율은 추적 가용성이지 조립 단계 인식 정확도가 아니다.
- 원본 영상 저장/외부 전송 없음. 모든 진단 캡처는 종료했다.
- 후속 HTTP 조회는 서버 종료 뒤 연결 거부됐으므로, 이번에도 Unity/웹
  동시 표시나 물리 정합까지 검증한 것으로 보고하지 않는다.

재발 방지: **Beast 재연결 후에는 카메라 번호를 기기 ID처럼 신뢰하지 않는다.**
짧은 미리보기로 실제 작업대 시점과 안경 움직임이 일치하는지 확인한다.
`run_realtime_server.py --camera-index 0`으로 일회성 지정할 수 있다.
대응점 수집 등 별도 도구를 실행할 때도 현재 확인한 번호를 명시해야 한다.
다른 예전 설정/도구의 기본 camera_index=1은 이번에 일괄 변경하지 않았다.

## 실입력 Unity / 관제 동시 연결 검사 (2026-10-06)

- 세션: `viture_aruco_rt_20261006_144320_5024f97a0eb4`.
- 사용자 확인: 일반 2D, 0DoF, 확장 모드. Unity 로그에서 VITURE Beast
  1920x1080 FullScreenWindow 선택 확인. 사용자는 화면과 안내 문구가 보인다고
  확인했지만 단계는 넘어가지 않았다고 보고했다.
- 900프레임, 89.916초, 평균 처리 약 10.05 FPS. 상태 S0 3프레임,
  S1 897프레임. 마커 OK 440, FALLBACK 97, LOST 363프레임.
- 웹 브라우저 20초 관측의 95개 표본에서 원본 HTTP 메시지와 표시 상태/활성
  안내 문구가 일치했다. page error와 대조 실패는 없었다.
  표본의 단계는 S1이며 GUIDING/TRACKING_LOST를 포함한다.
- Unity에서도 OBSERVING/ GUIDING/ TRACKING_LOST를 확인했다.
  서버 종료 뒤 STALE → DISCONNECTED로 안내를 보류했다. 새 원은 표시하지 않았다.
- Unity 증거: `outputs/unity_p1/player-20261006-144317-694.log`.
- 웹 증거: `outputs/supervisor_r6/live-joint-20261006/report.json`,
  `samples.json`, `supervisor.png`. 저장된 PNG는 관제 UI이며 카메라 영상이 아니다.
- 상태 필터 입력 재생은 900프레임 모두 일치했다.
- HTTP 응답 중 클라이언트 연결 취소에 따른 WinError 10053이 한 번 기록됐다.
  서버는 나머지 프레임을 처리하고 exit 0으로 종료했다. 원인 확정/수정은 하지 않았다.
- 촬영과 Unity 시험 앱은 종료했다. 이번에는 코드/인식 임계값을 변경하지 않았다.

### 뚜껑 단계 정체

사용자는 뚜껑을 완전히 닫고 손을 뗀 상태에서도 `Close the lid`가 계속 보였다고
확인했다. 현재 전이 조건은 `max(lid_threshold=0.52, lid_min_confidence=0.54)`
이상의 raw ROI 점수를 정상 추적 상태에서 300 ms 유지하는 것이다.

S1 구간에서 조건을 만족한 표본은 27개였고 가장 긴 연속 구간은 209 ms였다.
410프레임은 점수 미달, 460프레임은 추적 불안정으로 유지 조건이 끊겼다.
정상 추적 프레임의 lid 점수는 평균 0.5194, 최솟값 0.4474, 최댓값 0.5580이다.
이는 전이가 보류된 직접 조건을 설명하지만, 낮은 점수의 시각적 원인을 확정하지는 않는다.

다음 진단은 현재 열린/닫힌 뚜껑의 점수 분포와 실제 ROI 위치 비교다.
오검출 여부를 확인하지 않은 채 threshold나 유지 시간을 낮추지는 않는다.
현재 동시 연결 확인은 S1과 추적 유실/복구 범위이며, S2~S6 실제 조립 안내와
실물 위치 정합까지 완료한 것으로 보고하지 않는다.

닫힌 상태를 별도로 10초 측정한 결과(사용자 준비 확인 후, 영상 미저장):

- 마커 OK 64, LOST 24, FALLBACK 6프레임.
- OK 표본의 lid 점수 평균 0.52099, 범위 0.50975~0.53686.
- 0.54 이상인 표본은 0개. 10/50/90 백분위는 0.51237/0.52161/0.52749.
- 스칼라 기록: `outputs/supervisor_r6/lid-diagnostic-20261006/closed-metrics.json`.
- 초록 사각형은 노트북 진단 창의 lid ROI다. 실제 안경 오버레이와 구분한다.
- 열린 상태 측정과 ROI의 시각적 일치 확인 전에는 원인이나 조정값을 확정하지 않는다.

### 열린 상태 비교와 임시 기준 조정

열린 뚜껑을 옆에 놓고 손을 뗀 상태를 별도로 10초 측정했다.

- 마커 OK 67, LOST 23, FALLBACK 3프레임.
- OK 표본의 lid 점수 평균 0.44162, 범위 0.41500~0.47943.
- 스칼라 기록: `outputs/supervisor_r6/lid-diagnostic-20261006/open-metrics.json`.
- 이 짧은 두 측정에서는 열린 상태 최댓값과 닫힌 상태 최솟값이 겹치지 않았다.
  이를 근거로 `roi.lid_threshold`와 `state_filter.lid_min_confidence`를 각각
  0.50으로 조정했다. 유효 임계값은 기존 0.54에서 0.50이 됐다.
- placement_ms=300, 최소 마커 수와 추적 품질 기준은 유지했다.
- `tests/realtime/test_beast_lid_calibration.py`는 실제 설정을 읽어 측정한
  열린 점수 유지, 닫힌 점수의 짧은 노출 보류, 마커 유실 시 누적 시간 초기화,
  복구 뒤 300 ms 유지 후 S2 전이를 검사한다. 수정 전 실패, 수정 후 통과했다.
- 후속 전체 realtime 테스트: 289개 통과(22.09초).

0.50은 현재 환경의 임시 조정값이며 범용 보정값이 아니다. 상대적인 템플릿
유사도 점수를 확률로 해석하지 않는다. ROI의 실제 뚜껑 위치 일치 여부와
자세/조명 변화에 따른 열린 상태 오인식은 별도로 확인해야 한다.

### 수정 후 실입력 확인

- 세션: `viture_aruco_rt_20261006_145621_23f49fc0b7aa`.
- 900프레임, 첫/마지막 timestamp 차이 89.915초.
- 사용자는 열린 상태로 시작했으며 시험 중간에 뚜껑을 닫았다고 확인했다.
  닫기 지시 전에 전이가 관측됐지만, 이 사실만으로 열린 상태 오인식이라고
  판단하지 않는다. 실제 닫은 시각을 기록하지 못해 전이 지연이나 선후 관계를
  정량 검증한 시험으로도 보지 않는다.
- frame 27에서 S0→S1, frame 98에서 S1→S2가 발생했다. S2 전이는 시작 후
  약 9.69초이며, frame 94~98에서 점수 0.50422~0.52992가 392 ms 동안
  기준을 넘었다. 상태별 표본은 S0 26, S1 71, S2 803프레임이다.
- 마커 OK 306, FALLBACK 103, LOST 491프레임. 추적 안정성 개선은 남아 있다.
- HTTP에서 S2와 target=screw_a, Unity 로그에서 S2 표시 상태를 확인했다.
  Unity 로그: `outputs/unity_p1/player-20261006-145619-781.log`.
  이 검사는 정확한 문구 전환 시점의 사용자 확인이나 실물 나사 정합 검증을
  대신하지 않는다. 새 원은 표시하지 않았다.
- 저장된 필터 입력의 900프레임 재생 결과가 일치했다. 이는 필터 재현성이지
  영상 인식 정확도 검증이 아니다.
- 서버 정상 종료(exit 0), Unity STALE→DISCONNECTED 확인 후 시험 앱 종료.
  카메라 프레임 저장은 0개이며 외부 전송하지 않았다.

## 다음 순서

1. 완료: 카메라 시점 확인 → 마커 검출 회복 → 유효 YOLO 결과 확인.
2. 부분 확인: 같은 실입력으로 Unity와 관제의 S1 및 추적 유실/복구 표시.
3. 부분 확인: 임시 기준으로 S1→S2 및 Unity S2 표시. 다음 착용 검사에서는
   열린 상태 유지와 닫는 시각을 구분해 기록하고, ROI 위치 및 자세 변화 영향을
   확인한다. 이후 A~D 실제 작업 안내를 검사한다.
4. 별도 착용 세션에서 눈별 정합 수집과 나사 위치 오차 검증.

최소 로컬 관제 화면 구현과 전체 시스템 실기기 완료는 구분한다.
서버 임대/추가 비용, commit/push는 이번 작업에 없다.
