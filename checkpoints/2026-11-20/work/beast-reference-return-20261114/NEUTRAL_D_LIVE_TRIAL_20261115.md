# D 복구 후보 실기: 정상 흐름 확인, 옵션 효과 미확인

## 실행

- 세션: `viture_aruco_rt_20261115_001253_68e8ef4a18bc`
- D(S5)부터 최종 확인(S6)까지만 실행. 최대 90초, S6 도달 후 조기 종료.
- 실제 숫자 로그: 522프레임, 첫 입력부터 마지막 입력까지 52.317초.
- 기존 공통 A~D 후보와 `poll-candidate-build` 유지. 보정 및 보호 파일 9개 해시 일치.
- 미완료/완료 HOLD 보존 600/2000ms, 접근/이탈 800/400ms, 초록 표시 지연 2000ms 유지.
- `retain_neutral_recovery=true`는 별도 시험 실행기에만 적용.
- 사진/영상 저장 없음. 서버와 Unity의 소유 프로세스 종료 확인.

## 관측 결과

| 항목 | 실제 후보 ON | 같은 입력으로 후보 OFF 재생 |
|---|---:|---:|
| D 재확인 진입 | 0 | 0 |
| 확보한 HOLD 소실 | 0 | 0 |
| D → 최종 확인 프레임 | 490 | 490 |
| 새 중간 위치 복귀 조건 | 0 | 해당 없음 |

실제 기록 522프레임은 현재 코드로 완전히 재현됐다. 추적 유효 427프레임, 무효 95프레임이었다. 추적 끊김이 있었다고 해서 이번에 추가한 중간 구간 복귀 분기가 반드시 실행된 것은 아니다. 이번에는 그 조건이 기록되지 않았고, ON/OFF 결과도 같았다.

Unity 로그에는 `PAUSED - KEPT`와 `MOVE CLEAR`가 기록됐다. 이는 진행 보존 안내가 표시됐다는 근거지만 새 옵션의 추가 효과를 보여주는 증거는 아니다.

사용자 응답: “음... 잘 모르겠어.”

따라서 사용자 체감 개선, 실제 최종 문구 확인, 새 옵션의 실기 효과를 통과로 판정하지 않는다. 서버의 D→S6 진행은 확인됐으나 실제 체결 완료를 검증한 것이 아니다.

## 판단

이번 실기는 D 흐름에서 눈에 띄는 진행 회귀가 없음을 확인한 한 사례다. 새 옵션의 효과는 앞선 저장 로그 D 1364에서만 확인된 상태다. 같은 시험을 즉시 반복하거나 보존 시간을 늘리지 않는다. 기존 성공본은 그대로 두고, 후보 옵션의 기본값도 꺼진 상태를 유지한다.

다음 확인이 필요하면 기존 D 1364 재생을 회귀 기준으로 사용하고, 실기 중 해당 복귀 조건이 실제 발생했는지를 먼저 확인한다. 조건이 발생하지 않은 실기를 효과 비교 횟수로 세지 않는다.

## 파일

- [실기와 OFF 재생 비교](C:/Users/fresh/Documents/Codex/beast-reference-return-20261114/neutral-D-live-comparison.json)
- [숫자 로그](C:/Users/fresh/Documents/Codex/beast-reference-return-20261114/neutral-D-sessions/viture_aruco_rt_20261115_001253_68e8ef4a18bc/results.jsonl)
- [분석 스크립트](C:/Users/fresh/Documents/Codex/beast-reference-return-20261114/analyze_neutral_d_trial.py)
- [분리된 시험 런처](C:/Users/fresh/Documents/Codex/beast-reference-return-20261114/run-neutral-D-trial.ps1)
- [분리된 서버 진입점](C:/Users/fresh/Documents/Codex/beast-reference-return-20261114/run_neutral_d_server.py)

시험 진입점은 기존 설정 생성과 서버를 그대로 호출하고, 시작 단계 S5, 후보 옵션 ON, 독립 숫자 로그 경로만 바꾼다. 이 세 항목을 되돌리면 기존 격리 시험의 유효 설정과 일치하는 것을 실행 전에 확인했다. 기존 성공본의 런처나 YAML을 수정하지 않았다.
