# 중간 위치 복귀 시 HOLD 보존 수정

## 결론

기존 성공본과 A~D 보정은 그대로 두고, 추적 복구 직후 도구가 근접/이탈 사이의 중간 구간에 있으면 보존분을 바로 삭제하지 않는 시험 옵션을 추가했다. 기본값은 꺼짐이며 실행 설정에는 적용하지 않았다.

주요 저장 로그의 D에서 재확인 진입은 7회에서 5회, 완료 HOLD 소실은 3회에서 2회로 감소했다. C는 변화가 없었다. 재생 가능한 4개 세션, 총 7,883프레임에서 단계 전환 순서와 프레임은 기존과 동일했다. 이는 고정된 입력에 대한 결과이며 체감 개선이나 실기 안전성을 확정하는 결과는 아니다.

## 수정 범위

- [guidance_timing.py](C:/Users/fresh/OneDrive/Desktop/홍익대/4학년/2학기/vision/01_SUBMIT_KEEP/AR-assembly-psr_github_main_20260604/.worktrees/viture-beast-overlay-mvp/server/realtime/guidance_timing.py:19): `GuidanceTiming.retain_neutral_recovery = False`와 엄격한 boolean 검사.
- [복구 조건](C:/Users/fresh/OneDrive/Desktop/홍익대/4학년/2학기/vision/01_SUBMIT_KEEP/AR-assembly-psr_github_main_20260604/.worktrees/viture-beast-overlay-mvp/server/realtime/guidance_timing.py:182): 기존 보존분이 있을 때만 중간 구간에서 일시 보관. 제품 코드 변경은 9줄 추가.
- [회귀 테스트](C:/Users/fresh/OneDrive/Desktop/홍익대/4학년/2학기/vision/01_SUBMIT_KEEP/AR-assembly-psr_github_main_20260604/.worktrees/viture-beast-overlay-mvp/tests/realtime/test_neutral_hold_recovery.py:15): 실제 D 1364 입력을 포함한 25개 사례.
- [숫자 입력 fixture](C:/Users/fresh/OneDrive/Desktop/홍익대/4학년/2학기/vision/01_SUBMIT_KEEP/AR-assembly-psr_github_main_20260604/.worktrees/viture-beast-overlay-mvp/tests/realtime/fixtures/neutral_hold_recovery_d1364.json): 실제 세션의 1305~1366프레임 `filter_input` 62개. 사진/영상 없음.

변경하지 않은 것: A~D 좌표/양안 보정, Unity, YOLO, 마커 추적, 접근 800ms/이탈 400ms, 보존 상한, HMM, 성공본 실행 설정. 커밋/배포/실기 실행은 하지 않았다.

## 정확한 동작

다음 조건을 모두 만족할 때만 보존한다.

1. 시험 옵션이 켜져 있고 기존 `_suspended`가 있다.
2. 현재 나사의 점수가 `release_score_max < score < threshold`이다. 해당 세션에서는 0.15 < score < 0.30.
3. 다른 나사 점수는 모두 0.15 이하이다.
4. 최초 보존 시각부터 기존 보존 예산 안에 있다. 이번 세션은 미완료 600ms, 완료 HOLD 2,000ms이다.
5. 앞단의 프레임/관측 시각, 마커, 단일 도구, 도구 끝점 등 유효성 검사를 통과했다.

이 구간에서는 `PAUSED / tool_position_unknown / retained`를 반환한다. 중간 구간 시간을 유지 또는 이탈 증거에 더하지 않고, 최초 보존 마감도 연장하지 않는다. 유효한 근접 또는 이탈이 돌아오면 기존 복구 로직으로 이어간다. 이탈 시간은 복귀 후 새 관측부터 다시 400ms를 확보해야 한다.

다른 나사 근처로 이동, 다중 도구, 손상된 좌표, 명시적 리셋, 만료 처리 등은 기존 규칙을 유지한다. 이번 수정은 다음 나사로 옮겼을 때의 보존 정책까지 바꾸지 않는다.

## 실제 실패 재현

세션: `viture_aruco_rt_20261114_214414_1b5738df444c`

| 프레임 | 기존 | 시험 옵션 |
|---|---|---|
| 1363 | 완료 HOLD 4,399ms 보존 | 동일 |
| 1364 | D 점수 약 0.179로 복귀, 보존분 삭제 | 같은 보존분 유지, 남은 예산 1,200ms |
| 1365 | 재확인 필요 | 완료 HOLD 복구, 새 이탈 구간 시작 |
| 1366 | 재확인 필요 | 중복 관측으로 이탈 시간/단계 전환 증가 없음 |
| 1367 | 마커 손실, 보존분 없음 | 새 유효 관측까지 확보했던 HOLD를 기존 규칙으로 보관 |
| 1372 | 다시 HOLD 시작 | 기존 완료 HOLD로 복귀 |

1367에서의 보존 기준 갱신은 1365의 새 유효 이탈 관측에 따른 기존 동작이다. 중간 점수 자체가 만료를 갱신한 것은 아니다.

## 전체 로그 비교

| 지표 | 기존 | 시험 옵션 |
|---|---:|---:|
| A 재확인 진입 | 0 | 0 |
| B 재확인 진입 | 0 | 0 |
| C 재확인 진입 | 5 | 5 |
| D 재확인 진입 | 7 | 5 |
| C 완료 HOLD 소실 | 2 | 2 |
| D 완료 HOLD 소실 | 3 | 2 |
| D 최초 armed 이후 재확인 프레임 | 52 | 41 |
| D 마지막 armed 확보 프레임 | 1552 | 1552 |

`armed`는 근접 유지 조건을 확보했다는 뜻이지 실제 나사 체결 완료 판정이 아니다. 소실 횟수는 활성 상태 또는 보존된 완료 HOLD가 같은 단계 안에서 사라진 경우를 센다. 정상적인 다음 단계 전환은 소실로 세지 않는다.

주요 세션의 자동 전환 프레임은 A→B 542, B→C 682, C→D 1087, D→최종 확인 1617로 동일했다. 최종 수동 확인도 1712로 같다. 고정 로그는 사용자가 안내 변화에 반응해 동작을 바꾸는 효과를 측정할 수 없다.

| 세션 | 프레임 | 기본 동작 재현 | 옵션 적용 후 전환 프레임 |
|---|---:|---|---|
| 20261114_214414_1b5738df444c | 1,979 | 일치 | 동일 |
| 20261108_092152_bffcaa81289f | 1,595 | 일치 | 동일 |
| 20261108_015905_4c04f6b11ffe | 2,253 | 일치 | 동일 |
| 20261108_013536_ee474d86145b | 2,056 | 일치 | 동일 |

나머지 3개 세션에서는 진단 추적값도 변경되지 않았다. 비교 대상으로 시도한 과거 세션 2개(`135122_53d3a8b0ae45`, `103747_327f67195a7c`)는 기본 재생부터 첫 행이 불일치하여 효과 집계에서 제외했다. 수정 전 소스를 별도 메모리에 불러와도 같은 불일치를 확인했다. 해당 세션을 이번 변경의 성공/실패 근거로 사용하지 않았다.

## 테스트와 보존 확인

실제 D 1364 테스트가 먼저 실패하는 것을 확인한 뒤 조건을 수정했다. 관련 검사 106개가 통과했다. 검사는 A~D, 미완료/완료 HOLD, 만료, 중복 입력, 재손실, 다른 나사, 다중 도구, 잘못된 좌표, 명시적 리셋, 이탈 시간 확보와 단계 건너뛰기 방지를 포함한다.

최종 정식 `tests` 폴더 전체 검사: **872개 통과, 0개 실패(60.83초)**. 결과는 `neutral-recovery-tests.xml`에 저장했다. 기존 백업 폴더까지 수집하는 기본 pytest 호출에는 관련 없는 과거 테스트의 import 오류가 있어 정식 폴더를 지정했다. 실행 경로와 자식 프로세스 import 경로도 맞췄다. 중간 실행에서 로컬 HTTP 검사 한 건이 Windows 연결 중단으로 실패했지만, 해당 파일의 8개 검사와 최종 전체 재실행은 모두 통과했다. 이 재시도 이력은 숨기지 않고 기록한다.

보호 대상 실행 파일/보정 등 9개 파일은 SHA-256이 기존 기록과 모두 일치했다. 카메라 모드 프로브나 실제 카메라/Unity는 실행하지 않았다.

## 다음 단계

1. 이 옵션만 켠 별도 시험 설정으로 D의 짧은 복구를 확인한다. 기존 성공본을 덮어쓰지 않는다.
2. 실제로 중간 위치 복귀가 발생했는지 로그와 함께 보고, 재접근 부담과 오전환 여부를 확인한다.
3. C의 긴 입력 공백은 별도 원인으로 다룬다. 보존 상한 증가나 마커/PnP 변경을 이번 수정에 묶지 않는다.

## 재현 자료

- [숫자 비교 결과](C:/Users/fresh/Documents/Codex/beast-reference-return-20261114/neutral-recovery-replay.json)
- [오프라인 비교 스크립트](C:/Users/fresh/Documents/Codex/beast-reference-return-20261114/compare_neutral_recovery.py)
- [전체 테스트 결과](C:/Users/fresh/Documents/Codex/beast-reference-return-20261114/neutral-recovery-tests.xml)
- [수정 전 소스 보관본](C:/Users/fresh/Documents/Codex/beast-reference-return-20261114/guidance_timing.before-neutral-recovery.py)

시험 설정 키는 `state_filter.timing.retain_neutral_recovery: true`이다. 이번 비교에서는 복사한 설정의 메모리 값에만 적용했다.
