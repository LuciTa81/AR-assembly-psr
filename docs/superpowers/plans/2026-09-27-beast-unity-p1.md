# Beast Unity P1 Implementation Plan

Spec: ../specs/2026-09-26-beast-minimal-harness-design.md

## Scope

사용자가 승인한 P1을 현재 worktree에서 순서대로 구현합니다.
Windows Unity Scene 1개, 기존 로컬 HTTP snapshot, 시험 원/안내만 추가합니다.
PnP, 착용 보정, 실제 나사 좌표, 원격 서버, XR SDK, 상태 임계값 변경은 제외합니다.
commit/push와 라이선스 동의는 자동으로 하지 않습니다.

## Decisions

- Unity Hub만 설치되어 있습니다. Editor 설치는 사용자에게 확인하며 로그인/
  라이선스 활성화는 사용자가 직접 합니다. Editor 없이는 렌더링 성공을 주장하지 않습니다.
- 서버의 monotonic clock으로 계산한 frame_age_ms를 응답에 추가합니다.
  Unity는 서로 다른 clock의 timestamp를 빼지 않고 서버 age + HTTP 왕복 시간 +
  수신 후 경과시간으로 만료시킵니다. 같은 frame_id 재수신은 수명을 늘리지 않습니다.
- P1 시험 표시의 freshness budget은 500 ms입니다. 실제 위치 pose의 150 ms
  설계 목표와 다르며, P2 정합 성능으로 해석하지 않습니다.
- 시험 원은 명시적으로 켜야 합니다. 화면 중앙의 고정된 진단 원이며
  NOT CALIBRATED 표시를 함께 둡니다. marker OK가 아니면 숨깁니다.
- Unity는 현재 Python 상태/문구를 표시만 합니다. 단절 시 마지막 단계는
  기록으로 유지하되 작업 지시 대신 단절 상태를 보여줍니다.
- 기존 인식/모델/P0 변경은 보존합니다. 빌드 산출물은 outputs에 저장합니다.

## Tasks

1. 서버 age 계약: SharedOverlayState의 최신 요청 시점 age, 누락 timestamp,
   정지한 프레임의 age 증가 테스트를 먼저 실패시키고 구현합니다.
2. 순수 C# 수신 상태: schema/session/frame 검증, 새 프레임 수용, 중복/
   역행/만료/HTTP 실패/마커 유실/새 세션을 NUnit 테스트로 먼저 검사합니다.
   Unity 없이도 같은 production C#를 .NET SDK로 테스트할 수 있게 합니다.
3. Unity adapter: 순차 UnityWebRequest, 검은 Scene, 시험 원/문구,
   명시적 Beast 디스플레이 선택, Scene 생성/Windows Mono 빌드 스크립트.
4. 검증: Python 전체 테스트, C# 테스트, Editor import/build와 실제 실행.
   카메라 없는 로컬 fixture로 정상/유실/동결/복구를 확인합니다.
   착용 결과는 사용자 확인과 구분하여 기록합니다.

## Files

- server/realtime/overlay_http_server.py
- tests/realtime/test_overlay_http_server.py
- client_unity/Assets/Scripts/GuidanceSnapshot.cs, GuidanceState.cs
- client_unity/Assets/Scripts/GuidanceReceiver.cs, GuidancePresenter.cs, DisplayBootstrap.cs
- client_unity/Assets/Editor/AssemblyGuideBuilder.cs
- client_unity/Packages/manifest.json, ProjectSettings/ProjectVersion.txt
- tests/unity/GuidanceTests.csproj, GuidanceStateTests.cs, Program.cs
- scripts/build_beast_unity.ps1, scripts/run_beast_unity.ps1
- docs/beast_unity_p1_status.md

## Review Focus

최초 연결부터 오래된 snapshot, 같은 frame 재전송, 통신 복구 후 오래된 frame,
session 전환, marker fallback, HTTP redirect, Unity 비활성화/종료 시 request 해제,
잘못된 디스플레이 출력, Scene/build 미검증을 완료로 보고하는 문제를 검사합니다.

## Progress

- [x] Spec/P0/API/환경 확인. 사용자도 Editor 미설치를 확인했으며 설치를 승인했습니다.
- [x] Task 1: server age (새 테스트 3개 RED -> GREEN, 전체 Python 62개 통과)
- [x] Task 2: C# state (최초 23개, 리뷰 보완 2개 RED -> GREEN, 합계 25개)
- [x] Task 3: Unity scene/adapter/build (Editor 설치/활성화, Scene 생성, Windows 빌드 성공)
- [x] Task 4: runtime verification and independent review (Beast 1920x1080, 상태별 화면/픽셀 검사)
- [x] 착용 사용자 확인: 120초 재시험 후 원과 문구가 잘 보인다고 답변
- [ ] native 표시 모드 0DoF 선택/화면 크기와 거리 고정 (P1 하드웨어 완료 조건)

Ruling: P1은 기존 realtime_v1의 추가 필드만 사용하고 pose schema는 P2에서
구현합니다. 비용: P2에서 계약을 갱신해야 하지만 가짜 위치 좌표를 만들지 않습니다.

Ruling: 전체 pytest 실행에서 기존 config_used.yaml 읽기의 cp949 오류를 재현했습니다.
실제 writer의 UTF-8 계약에 맞춰 테스트 read_text 한 곳에 encoding을 지정했습니다.
runtime 저장 형식은 바꾸지 않았습니다.

Final review: 독립 리뷰어가 UNSTABLE 누락과 LOST 직후 동결 fixture의 한계를 지적했습니다.
UNSTABLE 수용/새 세션 교체 테스트 2개를 실패 후 수정했고 25개 모두 통과했습니다.
fixture는 LIVE 복구 후 동결되도록 변경했으며 실제 Player에서
LIVE -> TRACKING_LOST -> LIVE -> STALE -> LIVE -> DISCONNECTED를 확인했습니다.

실행 중 발견: Start-Process -Wait가 Editor 종료 뒤에도 반환되지 않았습니다.
종료 로그/프로세스 부재를 확인하고 WaitForExit로 Editor 자체만 기다리게 수정했습니다.
이후 빌드 스크립트는 exit 0으로 반환됐습니다.

실행 중 발견: Screen.SetResolution은 다음 프레임 이후 적용되므로 첫 로그에
이전 Windowed 해상도가 기록됐습니다. 실제 설정 적용을 최대 5초 기다린 뒤
최종 화면/모드를 확인하도록 수정했습니다.
