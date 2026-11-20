# 완료된 HOLD 초기화 방지 후보 검증

후속 실기 및 최신 표시 보완 빌드: [D 실기 결과](C:/Users/fresh/Documents/Codex/beast-reference-return-20261114/CHECKPOINT_D_LIVE_TRIAL_20261115.md). 아래는 첫 오프라인 후보의 검증 기록이다.

## 결론

기존 성공본과 A-D 보정은 유지하고, `retain_completed_hold` 후보 옵션을 추가했다. 기본값은 `false`다. 코드 수정, 저장 입력 재생, 자동 테스트, 분리된 Unity 실행 파일 빌드까지 완료했다. 실제 착용 비교는 아직 하지 않았다.

이 변경은 **이미 관측한 0.8초 HOLD 완료 기록**과 **지금 다음 단계로 넘어가도 되는지에 대한 판단**을 분리한다. 완료 기록을 보존한다고 체결이나 이탈을 자동으로 인정하지 않는다.

## 확인한 원인

- 기존 복구는 부분 HOLD 600ms, 완료 HOLD 2,000ms의 시간 제한 안에서만 누적 정보를 보존했다.
- 이 시간이 지나면 `_pause()`가 `reset_step()`을 거쳐 완료 HOLD까지 버렸다. 같은 나사로 돌아와도 800ms 누적을 다시 시작했다.
- 다른 나사 근처로 판정되거나 드라이버가 여러 개로 검출되는 경로도 완료 기록을 버릴 수 있었다.
- 최근 D 시험의 frame 219가 완료 HOLD 복구 시간 만료의 재현 사례다. 해당 숫자 입력을 회귀 테스트로 고정했다.
- 같은 D 시험에서 실제 S5 -> S6 전환은 frame 834에 기록돼 있다. 이후 추적 단절 때문에 완료 안내를 보지 못한 문제와 HOLD 초기화는 구분해야 한다. 이번 변경은 후자를 대상으로 한다.

## 변경된 규칙

| 상황 | 후보 동작 |
| --- | --- |
| 정상 관측에서 800ms HOLD 충족 | 현재 나사의 완료 HOLD 기록을 저장 |
| 짧은 마커 가림, 도구 미검출, 처리 대기 | 기존 제한 시간 안의 복구 규칙 유지 |
| 복구 제한 시간이 지남 | 완료 기록은 보존, 이탈 판단 권한은 해제 |
| 다른 나사 근처, 여러 도구 후보, 화면 밖의 도구 끝 | 완료 기록은 보존, 기존 이탈 누적과 직접 복구 권한 모두 해제 |
| 이후 현재 나사에 드라이버 하나가 새로 확인됨 | 800ms를 반복하지 않고 OBSERVED로 복귀 |
| 완료 기록만 남은 상태의 재인가 관측이 오래됨 | 350ms보다 오래된 near 관측으로는 재인가하지 않음 |
| 복귀 후 드라이버 이탈 | 새 관측으로 원래 400ms 이탈 조건을 다시 확인 |
| 가려짐, 도구 부재, 중간 위치, 오래된 clear 관측만 반복 | 다음 단계로 넘어가지 않음 |
| 잘못된 데이터, 명시적 재시작, 단계 변경, 새 세션 | 완료 기록 폐기 |

부분 HOLD가 아직 800ms에 도달하지 않은 경우는 기존 규칙 그대로다. 정상적인 도구 끝 미검출의 `-1` 표시는 잘못된 숫자와 구분한다. NaN, 잘못된 설정값, 역전된 관측 식별자는 완료 기록을 무효화한다.

Unity에는 `HOLD KEPT`, 관제에는 `HOLD 기록 보존 · 위치 재확인`을 전달한다. 이 상태는 작업 진행이나 완료를 요청하지 않는 PAUSED 상태다. 연결이 끊기거나 오래된 응답만 남으면 현재 진행 보존 안내로 표시하지 않는다. 기존 파란 WORKING / 초록 MOVE CLEAR의 지연 설정은 바꾸지 않았고, 완료 HOLD 보존 때문에 그 지연을 처음부터 반복하지 않게 검사했다.

## 저장 로그 검증

실제 저장된 숫자 입력 6세션, 9,272프레임을 재생했다. 변경 옵션을 끈 결과가 원래 로그와 일치하는지 먼저 검사한 뒤 후보를 비교했다.

측정값은 **같은 나사에서 첫 HOLD 완료 이후 OBSERVING으로 재진입한 횟수**다. 단순 PAUSED 횟수나 실제 재작업 횟수가 아니다.

| 세션 | 프레임 | 기존 재누적 진입 | 후보 재누적 진입 |
| --- | ---: | ---: | ---: |
| 20261114_214414_1b5738df444c | 1,979 | 12 | 0 |
| 20261108_092152_bffcaa81289f | 1,595 | 3 | 0 |
| 20261108_015905_4c04f6b11ffe | 2,253 | 23 | 0 |
| 20261108_013536_ee474d86145b | 2,056 | 0 | 0 |
| 20261115_001253_68e8ef4a18bc | 522 | 0 | 0 |
| 20261115_012657_a830efa91f0b | 867 | 8 | 0 |
| 합계 | 9,272 | 46 | 0 |

6세션 모두 단계 전환의 순서와 프레임 번호가 기존과 같았다. 추가 전환이나 앞당겨진 전환은 없었다. 이 결과는 저장된 행동에 대한 회귀 검증이며, 실제 착용 성공률이나 작업 시간 단축을 입증하는 수치는 아니다.

상세 결과: [checkpoint-replay-final.json](C:/Users/fresh/Documents/Codex/beast-reference-return-20261114/checkpoint-replay-final.json)

## 자동 검사 및 빌드

- Python 전체: 987개 통과. [결과](C:/Users/fresh/Documents/Codex/beast-reference-return-20261114/checkpoint-python-tests-final.xml)
- C# 로직: 398개 통과, 실패 0, 선택적 투영/깊이 재생 3개 생략. [결과](C:/Users/fresh/Documents/Codex/beast-reference-return-20261114/checkpoint-csharp-tests-final.xml)
- 웹 상태 로직: 53개 통과, 실패 0, 별도 저장 세션 환경변수가 필요한 검사 1개 생략.
- 추가 읽기 전용 검토에서 A-D, 모호한 도구 관측 4종, 관측 나이 경계의 합성 사례를 확인했다.
- 후보 Unity 빌드 성공. 첫 시도는 로컬 라이선스 IPC 접근에 실패해 종료했고, 접근을 허용한 재시도는 정상 종료했다. [빌드 로그](C:/Users/fresh/Documents/Codex/beast-reference-return-20261114/checkpoint-candidate-build/build-retry.log)
- 후보 실행 설정 사전 검사 통과. 카메라 열기와 모델 추론은 하지 않았다.
- 성공본 실행 파일, 기존 설정과 보정 등 보호 대상 9개 파일의 SHA256이 모두 유지됐다.

## 관련 코드

- [guidance_timing.py](C:/Users/fresh/OneDrive/Desktop/홍익대/4학년/2학기/vision/01_SUBMIT_KEEP/AR-assembly-psr_github_main_20260604/.worktrees/viture-beast-overlay-mvp/server/realtime/guidance_timing.py): 완료 HOLD 기록과 재인가 분리.
- [online_state_filter.py](C:/Users/fresh/OneDrive/Desktop/홍익대/4학년/2학기/vision/01_SUBMIT_KEEP/AR-assembly-psr_github_main_20260604/.worktrees/viture-beast-overlay-mvp/server/realtime/online_state_filter.py): 보존 메타데이터와 보류 원인을 함께 전달.
- [GuidanceState.cs](C:/Users/fresh/OneDrive/Desktop/홍익대/4학년/2학기/vision/01_SUBMIT_KEEP/AR-assembly-psr_github_main_20260604/.worktrees/viture-beast-overlay-mvp/client_unity/Assets/Scripts/GuidanceState.cs): checkpoint 검증 및 비활성 보존 안내.
- [supervisor_state.js](C:/Users/fresh/OneDrive/Desktop/홍익대/4학년/2학기/vision/01_SUBMIT_KEEP/AR-assembly-psr_github_main_20260604/.worktrees/viture-beast-overlay-mvp/web_overlay/supervisor_state.js): 관제 보존 및 위치 재확인 안내.
- [회귀 테스트](C:/Users/fresh/OneDrive/Desktop/홍익대/4학년/2학기/vision/01_SUBMIT_KEEP/AR-assembly-psr_github_main_20260604/.worktrees/viture-beast-overlay-mvp/tests/realtime/test_completed_hold_checkpoint.py): 실제 D219와 가림, 다중 도구, 다른 나사, 지연, 재시작, 이탈 조건.

## 다음 실기 준비

후보 빌드: `C:/Users/fresh/Documents/Codex/beast-reference-return-20261114/checkpoint-candidate-build`

후보 서버 진입점: [run_completed_hold_d_server.py](C:/Users/fresh/Documents/Codex/beast-reference-return-20261114/run_completed_hold_d_server.py)

기존 분리 시험 스크립트 [run-neutral-D-trial.ps1](C:/Users/fresh/Documents/Codex/beast-reference-return-20261114/run-neutral-D-trial.ps1)에 `-CompletedHoldCheckpointTrial`을 추가했다. 기존 옵션이 없으면 기존 동작과 실행 파일 해시 검사를 유지한다. 새 옵션은 `-ReleaseAbsenceTrial`, 명시적 후보 빌드 경로, 완료 HOLD 복구 시간 설정을 요구한다. 후보의 숫자 로그는 별도 `checkpoint-D-sessions`에 저장하며, 기존 보정과 성공본은 덮어쓰지 않는다.

다음에는 같은 설정에서 D 한 번만 비교한다. HOLD 완료 뒤 잠깐 가렸다가 돌아와도 반복 HOLD가 필요 없는지, 오래 가렸다면 현재 D 위치를 잠깐 보여준 뒤 새 이탈로 넘어가는지 확인한다. 실제 나사를 더 조일 필요는 없다. 시작 전 착용 준비 확인이 필요하다.

원 자체의 추적 끊김, 실제 체결 강도 확인, 화면 밖으로 곧바로 뺀 도구의 무조건 완료 처리는 이번 변경에 포함하지 않는다. 사진과 영상은 촬영하지 않았다.
