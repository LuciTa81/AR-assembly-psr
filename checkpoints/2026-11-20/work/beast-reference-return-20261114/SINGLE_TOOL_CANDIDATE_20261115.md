# 단일 드라이버 후보 선택 검증

## 결론

아래 첫 설명은 오프라인 개발 당시 기록이다. 이후 D 단독과 전체 흐름 실기를 실행했으며, 최신 결과는 마지막 `전체 흐름 실기` 항목에 구분해 기록한다. 기존 성공본과 보정은 교체하지 않았다.

실제 드라이버는 항상 하나라는 사용자 조건에 맞춰, 여러 YOLO 검출 중 손잡이에 연결된 축이 하나로 구분될 때만 선택하는 후보를 추가했다. 기본값은 꺼짐이다. 기존 성공 실행 파일, 기본 설정, A-D 보정은 유지했다. 카메라와 Unity 실기는 실행하지 않았다.

최신 D 실패 로그를 같은 입력으로 재생하면 기존은 S5에 머물고 후보는 frame 562에서 S6으로 넘어간다. 이는 저장 동작에 대한 오프라인 비교이며 실기 성공률이나 체결 완료 검증이 아니다.

## 변경 범위

- `server/realtime/yolo_realtime.py`: `handle_linked_driver=False`. 기존 작업영역 필터, NMS, nested dedup 뒤에 적용한다.
- 검출된 축의 한 끝만 손잡이 내부 또는 작은 연결 여유 범위에 있고, 반대 끝은 밖에 있어야 한다. 연결 조합이 정확히 하나일 때만 선택한다.
- 여러 연결, 손잡이 없음, 잘못된 좌표에서는 복수 후보를 임의로 하나로 줄이지 않는다. 단일 검출의 기존 동작은 유지한다.
- 선택된 손잡이가 작업영역 밖이어도 확인한 축 방향을 버리지 않는다.
- 원본 검출은 모두 로그에 보존한다. 선택 전 개수와 제외 개수도 남긴다.
- `harness_check.py`, `run_realtime_server.py`: boolean 검증과 metric 시험 모드 제한, 분석기 전달만 추가한다.
- 이번 변경에서 FSM, 유지 800ms, 이탈 400ms, 진행 보존 정책, 파란 안내 이후 초록 안내 지연 2초는 수정하지 않았다.
- 드라이버 미검출만으로 완료시키지 않는다. 마커 가림 자체를 복구하는 변경도 아니다.

## 검증

1. 최신 D 로그의 검출 좌표를 회귀 사례로 사용했다. 배경 후보의 신뢰도가 더 높아도 연결된 축을 선택한다.
2. 손잡이 내부 조각을 축으로 오인하는 경우와 작업영역 밖 손잡이에서 끝점 방향이 뒤집히는 경우를 실제 실패 테스트로 재현한 뒤 수정했다.
3. 합성 A-D 전체 흐름에서 배경 오검출을 추가해도 접근, 유지, 이탈 후에만 단계가 전환된다. 최종 확인은 계속 사용자 입력이다.
4. `tests/realtime`: **1008 passed**. 결과: `handle-linked-all-retry.xml`.
5. 최초 전체 검사는 작업 디렉터리 복귀의 Windows 접근 오류로 종료됐다. 쓰기 가능한 분석 폴더에서 같은 전체 검사를 재실행하여 통과했다. 테스트를 제외하거나 기준을 완화하지 않았다.
6. 별도 읽기 전용 코드 검토에서 위 두 반례 수정 후 잔여 blocker는 발견되지 않았다.
7. 시험 실행기 `-CheckOnly` 통과. 모델 추론, 카메라 캡처, 눈 정합 실기는 이 검사 범위가 아니다.
8. 보호 목록 9개 파일의 SHA-256 일치 확인. Git diff는 작업 트리/접근 오류로 확인하지 못했으며 Git 설정은 바꾸지 않았다.

## 저장 로그 재생

각 로그에서 원래 상태 판정의 정확 재생을 확인했다. 유효 관측의 원본 프레임 마커 좌표와 같은 카메라/작업대 프로필로 도구 좌표를 다시 계산했다. 원래 도구 특징과의 일치도 확인한 뒤 선택 규칙만 바꿨다. 이미지 재촬영이나 YOLO 재추론은 하지 않았다.

| 로그 | 프레임 | 고유 관측 재계산 | 결과 |
| --- | ---: | ---: | --- |
| 20261115_133631_cc8c906ef029 | 835 | 295 | 기존 전이 없음, 후보 S5->S6 frame 562 |
| 20261114_214414_1b5738df444c | 1979 | 486 | 전체 흐름의 전환 프레임 모두 동일 |
| 20261115_001253_68e8ef4a18bc | 522 | 177 | S5->S6 frame 490 유지 |
| 20261115_012657_a830efa91f0b | 867 | 268 | S5->S6 frame 834 유지 |

최신 D의 새 전환은 source frame 556, 558, 560에서 각각 D 거리 38.25, 101.88, 227.45mm를 관측한 결과다. 세 관측 모두 마커 유효, 증거 유효, 선택 도구 1개이며 source timestamp 290193440부터 290193840까지 400ms의 보이는 이탈이다. 바로 앞 source 552, 554에서는 3.84, 2.56mm였다. 단순 미검출 완료가 아니다.

전체 835프레임 집계에서 `multiple_tool_candidates` 보류는 247에서 26으로 줄었다. 단, 후보가 중간에 S6에 도달하므로 이후 단계 조건이 달라진다. 이 수치는 같은 단계의 개선율 또는 실제 작업시간 절감률로 사용하지 않는다.

최종 자료:
- `handle-linked-D-replay-final.json`
- `handle-linked-full-flow-replay-final.json`
- `handle-linked-D-earlier-replay-final.json`
- `handle-linked-D-second-replay-final.json`
- `audit_handle_linked_driver.py`

## 다음 시험

### 2026-11-15 D 실기 결과

- 세션: `viture_aruco_rt_20261115_141146_52bb3e0131c5`. 약 35.6초, 356프레임 후 자동 종료했다.
- frame 190에서 HOLD 완료, frame 324에서 S5->S6. 완료 HOLD 이후 OBSERVING으로 다시 시작한 횟수는 0회였다.
- 이탈 전환 근거: source 318, 320, 322의 D 거리 42.99, 45.24, 48.83mm, 유효/고유/마커 정상 관측 401ms. 바로 앞 source 316은 4.10mm였다.
- 사용자 확인: "초록 안내 뒤에 뗐고 최종 확인도 봤어", "확실히 매끄러워졌어".
- 잠깐 보류는 남아 있었다. HOLD 완료 이후 마커/관측/도구 보류 50프레임이 있었으나 완료 HOLD를 처음부터 다시 하지 않았다.
- 이번 실기에서 연결되지 않은 후보를 실제 제외한 프레임은 1개뿐이다. 체감 개선을 이번 선택 규칙 하나의 효과로 단정하지 않는다. 기존 진행 보존 및 표시 수정과 함께 실행된 후보의 D 단독 확인 결과다.
- 실제 입력 정확 재생 통과, 보호 파일 9개 불변, 사진/영상 저장 없음, 카메라와 Unity 종료 확인.
- 첫 실행은 로컬 연결 파일 접근 오류로 Unity 시작 전에 중단됐다. 권한을 확인한 두 번째 실행이 위 실기다.
- 결과: `handle-linked-D-live-result.json`. 후보 D 단독 확인은 통과로 기록하되 기본 성공본은 교체하지 않는다. 다음에는 동일 후보의 전체 A-D 흐름을 확인한다.
- Unity의 cue 로그 집계는 문구/힌트가 바뀐 로그 항목 수이며, 육안 깜빡임 횟수로 해석하지 않는다.

새 후보는 `run_handle_linked_d_server.py`와 기존 별도 실행기의 `-HandleLinkedDriverTrial`로만 켠다. 기본 실행에 자동 적용하지 않는다. 이전 진행 보존 후보와 검토된 안내 표시 빌드를 그대로 사용한다.

현재 경로 기준 사전 점검 명령이다. 실제 실행은 사용자 착용/준비 확인 후에만 `-CheckOnly`를 빼고 시행한다.

```powershell
$root = 'C:/Users/fresh/OneDrive/Desktop/홍익대/4학년/2학기/vision/01_SUBMIT_KEEP/AR-assembly-psr_github_main_20260604/.worktrees/viture-beast-overlay-mvp'
$trial = 'C:/Users/fresh/Documents/Codex/beast-reference-return-20261114'
& "$trial/run-neutral-D-trial.ps1" `
  -Python 'C:/Users/fresh/AppData/Local/ARAssembly/beast-mvp/.venv/Scripts/python.exe' `
  -PresentationConfig "$root/outputs/demo/presentation.json" `
  -CandidateProjection "$trial/candidate-ABCD-joint-unverified.json" `
  -ScrewAutoTrial -ScrewAutoEndState S6 -NestedDriverDedup -SourceRecoveryBoundary `
  -ReleaseAbsenceTrial -CompletedHoldCheckpointTrial -HandleLinkedDriverTrial `
  -ObservedCueDelayMs 2000 -UnityOutputDirectory "$trial/checkpoint-text-build" `
  -ScrewResumeMs 600 -CompletedHoldResumeMs 2000 -DurationSeconds 90 -CheckOnly
```

실기는 D만 최대 90초, 사진/영상 저장 없이 숫자 로그로 확인한다. 기존 착용/화면 설정과 작업대를 유지한다. 추가로 나사를 조일 필요 없이 접근, 유지, 초록 안내 뒤 이탈로 검사한다. 확인 항목은 진행 초기화 느낌, 파란/초록 안내의 일관성, 이탈 후 최종 확인 전환이다. 실제 체결 강도나 토크는 판단하지 않는다.

## 2026-11-15 전체 흐름 실기

- 세션: `viture_aruco_rt_20261115_142256_ea194634ad7d`. 1336프레임, 약 133.5초. 최종 사용자 확인 후 자동 종료.
- 같은 D 후보의 timing, YOLO 설정을 전체 hybrid 흐름에 그대로 연결했다. `run_handle_linked_flow_server.py`로 격리했고 생산 기본 설정, Unity 바이너리, A-D 보정은 수정하지 않았다.
- 실행기는 `-AssemblyFlow`일 때만 S0에서 시작한다. 이 후보 옵션과 1~300초 제한을 요구하며, S6 진입만으로 끝내지 않고 `operator.completed=true`까지 기다린다. 기존 D 단독 경로의 90초 제한은 유지한다.
- 상자/뚜껑 직접 확인: frame 399, 411. A->B 539, B->C 759, C->D 962, D->최종 확인 1184. 마지막 직접 확인 1304, 최종 `COMPLETED`.
- HOLD 최초 완료: A 498, B 708, C 900, D 1122. 각 대상에서 완료 이후 `OBSERVING` 재진입은 모두 0회. 이는 완료 HOLD 초기화가 없었다는 로그 결과이며, 잠깐 보류나 눈에 보이는 깜빡임이 없었다는 뜻은 아니다.
- HOLD 완료 이후 PAUSED 프레임: A 0, B 4, C 12, D 8. 사유는 마커/관측 유효성 및 도구 미검출. 보류가 없어진 것은 아니지만 사용자는 전체적으로 매끄러워졌다고 확인했다.
- 연결되지 않은 도구 후보를 제외한 프레임은 28개. 고유 검출 사건 수나 개선율로 해석하지 않는다.
- 실제 판정 입력 1336프레임 정확 재생 일치. 보호 파일 9개 SHA-256 불변. 사진/영상 저장 없음. 실행한 카메라 서버/자식 프로세스와 Unity 잔여 수 0 확인.
- 자동 검사: 새 후보 연결 검사와 실제 로그 회귀 검사 총 4개 통과. 기존 realtime 전체는 1007 통과, HTTP 검사 1개가 Windows 연결 중단으로 실패했다. 해당 파일 8개를 수정 없이 즉시 다시 검사해 모두 통과했다. 두 결과를 보존했다.
- 자료: `handle-linked-flow-live-result.json`, `audit_handle_linked_flow.py`, `test_handle_linked_flow_trial.py`, `handle-linked-flow-realtime-tests.xml`, `handle-linked-flow-http-retry.xml`.
- 사용자 확인: "안내에 맞춰 진행했고 마지막 완료도 봤어", "전체적으로 매끄러워졌어". 동작보다 먼저 넘어간 단계는 보고하지 않았다.
- 판정: 같은 착용/화면 설정과 고정 작업대에서 전체 흐름 실기 1회 통과. 다음 시연의 비교 기준 후보로 기록한다. 기존 성공본과 기본 실행 설정은 교체하지 않았으며, 다른 착용/배치에서의 재현성이나 체결 강도 검증을 뜻하지 않는다.

전체 흐름 사전 점검은 위 명령에서 `-ScrewAutoTrial -ScrewAutoEndState S6`을 `-AssemblyFlow`로, `-DurationSeconds 90`을 `-DurationSeconds 300`으로 바꾼다. 나머지 후보 옵션과 보정 경로는 동일하다. 착용 준비 확인 없이 `-CheckOnly`를 제거하지 않는다.
