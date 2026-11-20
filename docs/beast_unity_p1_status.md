# Beast Unity P1 진행 기록

작성일: 2026-09-27

## 현재

P0 실카메라 검사 후 Unity 최소 클라이언트를 구현하고 실제 Windows Player로 검증했습니다.
Beast 디스플레이 선택과 1920x1080 출력은 로그/렌더 캡처로 확인했습니다.
120초 재시험 후 사용자가 착용 상태에서 원과 문구가 잘 보인다고 확인했습니다.
안경 native 표시 모드는 0DoF를 기준으로 권장했고, 2026-09-27 후속 정면 검사에서
사용자가 0DoF 설정을 확인했습니다. 앱/SDK가 설정값을 읽어 검증한 것은 아닙니다.
실제 나사 정합 성공을 뜻하지 않습니다.

| 항목 | 결과 |
| --- | --- |
| Python server age 계약 | 요청 시마다 frame_age_ms 계산, 새 테스트 3개 통과 |
| Python 전체 회귀 | 62개 통과 (기존 UTF-8 테스트 읽기 1곳 수정) |
| C# 상태/만료 계약 | production 코드를 .NET에서 실행, 25개 통과 |
| Unity UI/HTTP/빌드 코드 | 실제 Editor 컴파일 및 Windows Player 검사 통과 |
| Editor | 사용자 승인으로 6000.3.25f1 설치 완료 |
| Unity 라이선스 | 사용자 로그인 후 Unity Personal 활성 확인 |
| Windows 빌드/실행 | 빌드 스크립트 exit 0, Scene/실행 파일 생성 |
| Beast 디스플레이 출력 | VITURE Beast, 1920x1080, FullScreenWindow, Unity DPI 96 |
| 실제 렌더 화면 | 정상/유실/정지/복구/단절 캡처와 원 픽셀 검사 통과 |
| Beast 착용 시 보임/복시/잘림 | 사용자가 원과 글자가 잘 보인다고 확인, 복시/잘림은 보고하지 않음 |
| native 0DoF/3DoF 표시 모드 | 후속 검사에서 사용자 0DoF 선택 확인, 앱 직접 조회/자동 변경은 하지 않음 |
| 실제 나사 정합 | P2, 아직 미구현 |

## 변경 범위

- 기존 로컬 HTTP endpoint를 유지하고 frame_age_ms를 추가했습니다.
- Unity Scene 생성, Windows Mono 빌드, 명시적 Beast 디스플레이 선택을 작성했습니다.
- 시험 원은 opt-in이며 중앙 고정, NOT CALIBRATED 표시입니다.
- 같은 frame 반복 조회, 첫 응답부터 오래된 frame, 역행 frame/timestamp,
  연결 끊김, marker FALLBACK/LOST/DISABLED/UNSTABLE, 새 session을 검사했습니다.
- S6는 성공 확정이 아닌 사용자 확인 대기입니다.
- 상태 인식 임계값, YOLO 모델, 실시간 필터는 이번 단계에서 바꾸지 않았습니다.

## 실제 실행 증거

- 최종 빌드: outputs/unity_p1/build-20260927-143848-682.log
- 최종 Player: outputs/unity_p1/verified-player.log
- 렌더 캡처: outputs/unity_p1/verified-1790487576514/
- 실제 상태 순서:
  LIVE -> TRACKING_LOST -> LIVE -> STALE -> LIVE -> DISCONNECTED
- 1920x1080 LIVE 화면의 중앙 원 색상 픽셀은 3008개,
  TRACKING_LOST/STALE/DISCONNECTED에서는 각각 0개였습니다.
- 원뿐 아니라 작업 지시도 보류 문구로 교체되며 S2 기록은 유지됐습니다.
- 시험은 가짜 S2 snapshot을 제공하는 로컬 fixture입니다. 카메라/YOLO를
  실행하지 않았으며 이 결과를 실제 인식 정확도로 보고하지 않습니다.
- fixture는 24초 후 종료했고 포트 8765의 listener가 없는 것을 확인했습니다.
  Player의 이후 DISCONNECTED 및 Curl timeout 로그는 의도한 단절 시험 결과입니다.
- 실행 파일은 outputs/unity_p1/BeastAssemblyGuide.exe,
  Scene은 client_unity/Assets/Scenes/AssemblyGuide.unity입니다.

독립 코드 리뷰에서 UNSTABLE 계약 누락을 발견해 회귀 검사 2개와 함께 수정했습니다.
동결 직전 LIVE 상태를 두도록 fixture를 고쳐 보이던 원의 만료를 검사했습니다.
빌드 완료 뒤 PowerShell 대기가 끝나지 않는 문제와 비동기 해상도 변경 직후의
잘못된 초기 로그도 실제 실행에서 재현하고 수정/재검증했습니다.

## 남은 통과 조건

1. 안경의 native 표시 모드를 0DoF로 선택하고 화면 크기/거리와 Windows 배율을 기록합니다.
2. 이후 P2에서 마커/나사 실측, intrinsic/PnP, 착용 보정을 진행합니다.

## 착용 재시험과 표시 모드

2026-09-27, 짧은 자동 시험을 놓쳐 카메라 없는 정상 S2 fixture를 120초 유지했습니다.
Player 로그: outputs/unity_p1/player-20260927-144318-360.log.
VITURE Beast 1920x1080 FullScreenWindow 선택 및 LIVE 상태를 재확인했고,
사용자는 초록 원이 중앙에 있고 그 아래 문구가 잘 보인다고 답했습니다.
중앙 고정은 P1의 의도된 동작입니다. 120초 후 fixture는 정상 종료했습니다.

[공식 Beast 안내](https://www.viture.com/academy/xr-glasses/the-beast)의
Positioning Modes에 따르면 0DoF는 시야 중앙 고정, Smooth Follow는 부드러운
머리 추종, Anchor는 머리 회전에 반응하는 공간 고정 화면입니다.
우리 앱이 카메라/마커로 표시 좌표를 갱신할 예정이므로, 별도 native 화면 이동을
겹치지 않는 0DoF + Default 2D를 보정 기준으로 권장합니다.
이 선택은 우리 구조의 설계 판단이며 Anchor가 나사 위치를 알아서 추적한다는
뜻이 아닙니다. 화면 크기/거리/모드는 보정 후 임의로 바꾸지 않습니다.

P1 원은 화면 중앙의 진단 도형이며 위치 안내가 아닙니다. 실제 좌표가 없는 동안
target_visible을 가짜로 게시하거나 실제 나사에 맞았다고 판정하지 않습니다.

추가 클라우드 리소스, 외부 영상 전송, commit/push는 하지 않았습니다.
