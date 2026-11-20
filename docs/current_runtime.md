# 현재 실행 버전과 보관 후보

2026-11-20 기준. 기본 관제, 촬영 후보, 과거 실험을 구분하는 안내입니다.
이 문서를 추가하면서 기존 Player, A~D 보정, 로컬 관제 프로필은 변경하지 않았습니다.

## 대표 실행 경로

```text
바탕화면 AI Assembly Guide / scripts/open_beast_console.ps1
  -> server/realtime/console_controller.py (127.0.0.1:8764)
  -> server/realtime/console_process.py
  -> scripts/run_beast_console_session.ps1
  -> 로컬 profile.json이 가리키는 run-korean-trial.ps1
  -> Python 실시간 판단 + 별도 Unity Player
```

기본 화면은 `web_overlay/supervisor_demo.html`입니다. 파일명의 `demo`는 기존 이름이며, 실행 관리 컨트롤러가 이 페이지에 `supervisor_console.js`와 CSS를 붙여 제공합니다. `/supervisor.html`은 이전 관제 화면입니다.

로컬 관제 프로필의 보관본은 [여기](../checkpoints/2026-11-20/work/AI-Assembly-Console/profile.json)에 있습니다. 그 파일은 당시 PC의 경로 기록이지, 다른 PC에서 바로 실행하는 기본값이 아닙니다.

## 경로별 구분

| 경로 | 의미 | 자동 기본 선택 여부 |
| --- | --- | --- |
| 저장소의 `server/realtime`, `web_overlay`, `scripts` | 현재 통합하는 인식·관제·실행 관리 코드 | 현재 체크아웃한 소스의 진입점 |
| `beast-action-guide-20261115/player-v2` | 로컬 프로필이 선택한 한글 행동 안내 Player | 해당 프로필에서 선택 |
| `beast-reference-return-20261114` | 이탈 복구·진행 보존·윤곽과 joint 보정 실행 지원 | 로컬 프로필이 참조 |
| `beast-pose-continuation-20261116/presentation-rms32.json` | 3.2 px 표시 프로필 후보 | 로컬 프로필이 명시적으로 선택 |
| `beast-preparation-text-20261116` | S0/S1 안내 문구 보존 후보 | 기본 경로로 자동 승격하지 않음 |
| `beast-line-clip-20261116` | 촬영 프레이밍·선 클리핑 및 촬영용 실행 | 별도 촬영 경로 |
| `checkpoints/2026-11-20` | 공개 가능한 보관 소스 | 실행 탐색·자동 선택 없음 |

같은 날짜라도 기능별 후보가 다릅니다. 최신 폴더명이나 최신 빌드 시각만 보고 실행 파일을 교체하지 않습니다.

## 서로 다른 2초 설정

1. **표시 지연:** 기본 관제 런처는 `ObservedCueDelayMs = 2000`을 전달합니다. 기존 판단 뒤 사용자가 보는 초록 이탈 안내의 타이밍에 관한 설정입니다.
2. **촬영 자동 전환:** 보관된 `filming-auto-advance.json`에는 `enabled: true`, `mode: filming_only`, `delay_ms: 2000`이 있습니다. 촬영용 서버·런처에서 사용하는 별도 옵션입니다. 파일이 있다는 이유로 기본 관제에 적용되지는 않습니다.

사용자가 요청한 **자동 전환 2초 -> 3초**는 두 번째 정책을 대상으로 한 다음 작업입니다. 이번 문서 통합에서 어느 시간값도 변경하지 않았습니다.

## 단계 판단의 범위

- 기본 관리 실행은 hybrid: 상자·뚜껑·마지막 검사는 직접 확인하고, 나사 A~D는 시간 증거와 상태 필터로 진행합니다.
- HMM/Viterbi 성능 수치는 별도의 오프라인 session_17 평가입니다. 현재 관제의 실시간 완료 판단을 그 수치로 설명하지 않습니다.
- 도구 접근·유지·이탈 확인과 체결 토크·조립 품질 측정은 다른 기능입니다.
- 저장된 시험 보고서는 각 날짜와 후보에 대한 결과입니다. 이번 merge가 모든 후보의 재촬영·착용 검사를 의미하지 않습니다.

## 새 환경에 복원할 때

1. 소스와 실행 프로필이 가리키는 로컬 폴더를 확인합니다.
2. 검증된 Player와 외부 런처·모델·보정을 별도 백업에서 준비합니다.
3. 외부 런처에 남은 절대 경로와 보호 파일 해시 조건을 점검합니다. 프로필 한 파일만 수정하면 모든 경로가 바뀌는 구조는 아닙니다.
4. 보정 JSON은 바이트를 보존합니다. 해시를 맞추기 위해 검사를 제거하거나 임의의 후보로 대체하지 않습니다.
5. 카메라를 켜기 전 연결 확인을 통과시키고, 작업 시작 후 실제 카메라 시점과 눈별 정합을 다시 확인합니다.

완전한 이식형 설치 패키지, Android APK, 자동 상자·뚜껑 확인과 원격 관제는 이번 통합 범위에 없습니다.
