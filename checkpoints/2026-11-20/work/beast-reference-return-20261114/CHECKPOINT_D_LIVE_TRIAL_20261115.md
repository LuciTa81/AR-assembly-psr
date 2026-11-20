# D 진행 보존 실기 결과 및 표시 보완

## 결과

- 세션: `viture_aruco_rt_20261115_133631_cc8c906ef029`
- 최대 90초 실행. 실제 저장 입력 835프레임, 83.358초.
- D HOLD는 frame 352에서 처음 완료됐다.
- 후보에서는 완료 후 OBSERVING으로 돌아가 HOLD를 다시 누적한 횟수가 0회였다.
- 동일한 숫자 입력에 후보 옵션만 끈 반사실 재생은 4회였다(frame 370, 373, 392, 772).
- 두 방식 모두 S5에 머물렀다. S6 최종 확인으로 넘어가지 못했으므로 전체 동작 성공으로 판단하지 않는다.
- 사용자 피드백: "너무 매끄럽지 않았어. 그파란불도 일관적이지 않고, 초록도 한번떴지만 다시 계속 돌아와서 넘어가질 않더라."
- 진행 보존의 수치 개선과 별개로, 이번 실기는 사용성 및 전체 완료 실패로 기록한다. 카메라와 Unity 플레이어는 종료 확인했다.
- 사진·영상은 저장하지 않았다. 기존 성공본 및 보정 보호 파일 9개의 해시도 유지됐다.

## 진행 보존과 진행 보류의 구분

완료 HOLD 이후 455프레임이 `checkpoint`로 유지됐다. 해당 보류의 이유는 다음과 같다.

| 이유 | 프레임 수 |
| --- | ---: |
| 드라이버 다중 후보 `multiple_tool_candidates` | 185 |
| 사용할 수 없는 관측 `invalid_observation` | 202 |
| 마커 추적 불안정 `marker_not_stable` | 54 |
| 도구 위치 불명확 `tool_position_unknown` | 14 |

이는 보류 로그 프레임의 수다. 서로 독립적인 물리 원인 횟수나 실제 검출 오탐률로 해석하면 안 된다. 특히 `invalid_observation`은 복구 경계의 이전 결과 거절 등이 포함될 수 있으므로, YOLO가 느린 탓이라고 단정하지 않는다.

이번에는 HOLD 초기화가 아니라, 이미 끝낸 HOLD는 보존한 채 새로운 유효 관측을 기다리는 시간이 길었다. 원본 사진을 저장하지 않았으므로 다중 후보가 실제 두 도구인지, 한 도구의 중복 검출인지 영상으로 확정할 수 없다.

## 사용자 피드백 후 추가 확인

저장 입력을 실제 후보로 다시 재생하여 `release_started_at`을 확인했다. 이탈 타이머가 시작된 프레임은 0개였다. 따라서 이 시험은 400ms 이탈 확인 도중 타이머가 반복 초기화된 사례가 아니라, 이탈 확인에 진입하기 전 차단된 사례다.

| 서버 OBSERVED 구간 | 바로 뒤 프레임 | 보류 원인 |
| --- | --- | --- |
| 352-362 | 363 | multiple_tool_candidates |
| 370 | 371 | multiple_tool_candidates |
| 373-381 | 382 | multiple_tool_candidates |
| 392-398 | 399 | multiple_tool_candidates |
| 772 | 773 | multiple_tool_candidates |

이는 서버 판정 구간이며, 사용자가 초록색을 본 횟수와 같지는 않다. Unity는 2초 표시 지연과 복구 안정화 과정을 추가로 적용한다.

frame 363은 마커 5개가 잡힌 상태였다. D 근처 드라이버 후보(confidence 0.63, bbox 약 725,432-748,590) 외에 화면 상단의 떨어진 후보(confidence 0.20, bbox 약 545,6-588,372)가 함께 검출됐다. 비슷한 상단 후보가 뒤에도 반복되며 일부 시점에는 confidence가 0.8 이상이므로, 신뢰도 임계값 하나를 올리는 것으로 해결된다고 단정하지 않는다. 실제 영상은 없으므로 상단 후보의 물체 정체는 미확정이다.

현재 `multiple_tool_candidates`는 완료 HOLD 기록은 보존하지만 즉시 이탈을 허용하는 `armed` 상태는 해제한다. 복귀 후 현재 나사 근접을 새로 확인해야 `armed`가 돌아온다. 따라서 초록 안내를 보고 도구를 떼더라도, 그 사이 다중 후보가 발생하면 멀어진 도구만으로는 복귀하지 못하는 경로가 있다. 이 기록에서도 OBSERVED 구간 전부가 다중 후보로 끝났다.

색상은 `SbsGuidancePresenter`에서 화면 상태에 직접 연결돼 있다. 정상 WORKING은 파랑, OBSERVED는 초록, PAUSED 등은 주황이다. `ObservedCueDelay`는 일반적인 PAUSED 동안 2초 시계 자체는 유지하지만, 보류 화면을 가리지 않는다. 따라서 이번 불일치는 단순히 2초 타이머가 매번 초기화된 것으로 설명하면 안 된다. 진행 기록, 관측 신뢰도, 다음 행동이 같은 표시 상태에 함께 반영되는 것이 사용자 혼란의 구조적 원인이다.

## 실기에서 찾은 화면 표시 누락

Unity의 `GuidanceState`는 `HOLD KEPT`를 만들고 있었지만, 뒤에 적용되는 `GuidanceTextStability`는 `retained`, `recheck`만 보존 안내로 취급했다. 새 `checkpoint`는 이유 문구가 안정화되기 전 일반 `PAUSED`로 덮였다.

플레이어 로그에도 `HOLD KEPT`는 6번 기록됐지만, 여러 보류 이유가 바뀌는 구간에서는 일반 `PAUSED`가 반복됐다. 이 수치는 화면 변경 로그 횟수이며 프레임 비율이 아니다.

보완은 `GuidanceTextStability`의 보존 안내 조건에 `checkpoint`를 포함하는 한 곳으로 제한했다. 시간 역전·NaN, 연결 끊김, 현재 보존 상태가 사라진 경우에는 이전 안내를 재사용하지 않는다. 서버 판단, 800ms HOLD, 400ms 이탈, A-D 보정은 바꾸지 않았다.

- 실패 재현: 새 checkpoint 표시 테스트 2개가 기존 코드에서 실패.
- 수정 후 C# 전체: 401개 통과, 실패 0, 선택적 투영/깊이 검사 3개 생략.
- Unity 재빌드: 성공. 이 표시 보완 빌드는 아직 착용 시험하지 않았다.
- 최신 후보 폴더: `C:/Users/fresh/Documents/Codex/beast-reference-return-20261114/checkpoint-text-build`
- 최신 DLL SHA256: `BA3A43B347836F9FFD850F7BDACBAB2CB3B56D2D7CC34336E78646A1E84DD097`
- 방금 실기에 쓴 이전 후보는 `checkpoint-candidate-build`에 그대로 보존했다. 실행 스크립트의 checkpoint 옵션만 최신 빌드 해시를 요구하도록 갱신했다.

## 다음 우선순위

1. 저장된 검출 좌표로 상단 후보와 실제 작업 도구의 손잡이-축 연결, 위치 연속성을 비교한다. 임계값 일괄 완화나 가장 높은 confidence 선택만으로 통과시키지 않는다.
2. 완료된 진행, 현재 관측의 신뢰도, 이탈 확인 대기를 구분해서 안내하도록 검토한다. 불확실할 때 초록 행동 지시를 무조건 유지하지 않는다.
3. HOLD 완료 뒤 다중 후보 발생, 실제 도구 이탈, 단일 후보 복귀 순서의 회귀 사례를 만든 뒤 제한적인 후보 개선을 검증한다. 가림이나 단순 미검출만으로 완료시키지 않는다.

이번 턴에는 이탈 판정이나 검출 임계값을 추가 변경하지 않았다. 표시 누락 수정 빌드의 CheckOnly도 통과했지만, 이는 하드웨어 시험이 아니다. 기존 성공본과 A-D 보정은 유지한다.

## 근거

- [실기 및 동일 입력 비교](C:/Users/fresh/Documents/Codex/beast-reference-return-20261114/checkpoint-D-live-comparison.json)
- [분석 스크립트](C:/Users/fresh/Documents/Codex/beast-reference-return-20261114/analyze_checkpoint_d_trial.py)
- [표시 실패 재현](C:/Users/fresh/Documents/Codex/beast-reference-return-20261114/checkpoint-text-red.xml)
- [수정 후 C# 검사](C:/Users/fresh/Documents/Codex/beast-reference-return-20261114/checkpoint-text-tests.xml)
- [최신 빌드 로그](C:/Users/fresh/Documents/Codex/beast-reference-return-20261114/checkpoint-text-build/build.log)
- [표시 수정 코드](C:/Users/fresh/OneDrive/Desktop/홍익대/4학년/2학기/vision/01_SUBMIT_KEEP/AR-assembly-psr_github_main_20260604/.worktrees/viture-beast-overlay-mvp/client_unity/Assets/Scripts/GuidanceTextStability.cs:15)
- [이전 오프라인 검증](C:/Users/fresh/Documents/Codex/beast-reference-return-20261114/COMPLETED_HOLD_CHECKPOINT_20261115.md)
