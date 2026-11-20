# Beast Assembly Guide: P1

2026-11-04 통합 실행은 [사용자 확인형 V1](../docs/beast_integrated_v1_20261104.md)을 참고한다.
일반 SBS 단계 문구는 눈 보정 없이 표시하며, 실물 위치 원의 정합 게이트는 유지한다.
S6는 기본적으로 확인 대기이고, 사용자 확인 모드의 명시적 최종 확인 뒤에만 COMPLETED가 된다.
서버 주소는 --state-url로 지정할 수 있다(loopback 전용).

Unity 6.3 LTS (6000.3.25f1), Windows x64 / Mono.
Neckband, XR Plugin, Android, 클라우드 연결은 필요하지 않습니다.

## 하는 일

기존 Python 서버의 http://127.0.0.1:8765/state.json 을 순차 조회하여
마지막 단계, 안내 문구와 연결 상태를 검은 화면에 표시합니다.
카메라 영상이나 YOLO 추론을 Unity에서 실행하지 않습니다.

시험 원은 기본 OFF이며 켜면 화면 중앙에 고정됩니다.
실제 나사 좌표가 아니며, 화면에도 NOT CALIBRATED가 표시됩니다.
유효한 새 프레임과 marker OK가 있어야 원이 보입니다.
S6는 체결 완료가 아니라 최종 사용자 확인 대기입니다.

## 빌드

1. Unity Hub에서 계정 로그인과 적합한 라이선스를 활성화합니다.
2. 저장소 루트에서 다음을 실행합니다.

```powershell
.\scripts\build_beast_unity.ps1
```

Editor 위치가 다르면 -UnityExe로 지정합니다. 스크립트가
Assets/Scenes/AssemblyGuide.unity를 생성하고 Windows 실행 파일을 빌드합니다.
출력은 ../outputs/unity_p1/BeastAssemblyGuide.exe입니다.
빌드는 생성용 Scene을 다시 만들므로, 직접 수정할 Scene은 다른 이름으로 저장합니다.
Unity Editor 안에서는 AR Assembly > Create P1 Scene 메뉴로 생성할 수 있습니다.

## 실행

기존 run_beast_harness.ps1로 Python 서버를 먼저 실행한 다음:

```powershell
# 우선 노트북 창에서 검사합니다.
.\scripts\run_beast_unity.ps1 -TestRing

# 연결된 디스플레이 이름에 VITURE가 단 하나 있을 때만 이동합니다.
.\scripts\run_beast_unity.ps1 -Beast -TestRing
```

Esc로 종료합니다. 유효 디스플레이가 없거나 두 개 이상 일치하면 종료하며
임의의 화면을 Beast로 간주하지 않습니다. Windows가 복제 모드이면 별도
디스플레이를 찾지 못할 수 있으므로 사용자 설정에서 확장 모드를 확인합니다.

실행 로그에는 display 이름/렌더 해상도/Unity DPI/윈도 모드를 기록합니다.
Unity DPI가 Windows 배율을 보장하지는 않습니다. 실제 안경의 native 3DoF/
0DoF, 화면 고정 여부와 착용 출력은 별도로 확인해야 합니다.

## 만료와 보류

- frame_age_ms는 Python monotonic clock에서 HTTP 요청 시마다 계산됩니다.
- Unity는 서버 age + 요청 왕복 시간 + 수신 후 경과시간으로 만료시킵니다.
- 같은 session/frame 재수신은 원의 수명을 연장하지 않습니다.
- P1 시험 표시 제한은 500 ms입니다. P2 실제 pose의 목표인 150 ms와 다릅니다.
- 연결 끊김/잘못된 응답/프레임 정지/마커 유실 시 원을 숨기고 안내를 보류합니다.
- 마지막 단계는 참고용으로 남지만 과거 작업 지시를 계속 표시하지 않습니다.
- 같은 frame으로 통신이 복구되어도 새 유효 frame 전까지 원을 다시 켜지 않습니다.

## 테스트

순수 상태 로직은 Editor 없이 .NET SDK 10으로 실행할 수 있습니다.

```powershell
dotnet run --project tests/unity/GuidanceTests.csproj -- --noresult
python -m pytest -q
```

.NET 검사는 UnityWebRequest, JsonUtility, GPU 렌더링이나 Beast 출력을
검증하지 않습니다. 최종 검증 상태는 ../docs/beast_unity_p1_status.md를 봅니다.

카메라 없는 실제 Player 시험은 tests/unity/serve_snapshot_fixture.py를
사용합니다. 24초 동안 LIVE/유실/복구/동결/복구를 보내고 종료합니다.
Player에 --capture-ui <새 출력 폴더>를 전달하면 상태 변경 시 자체 렌더 화면만
캡처합니다. 데스크톱이나 실제 카메라를 캡처하지 않으며 기본 실행에는 꺼져 있습니다.

## R3 일반 SBS 안내

눈별 좌표 계약을 사용하는 일반 안내 화면은 선택적 `-SbsGuidance` 모드다.
실제 보정 프로필이 없으면 위치 원은 숨겨진다. 합성 입력은 별도
`-SpatialPreviewConfig` 설정으로 노트북 창에서만 시험한다.
실행 방법, 검사 결과, 실제 정합과의 구분은
[R3 SBS 안내](../docs/beast_sbs_guidance.md)를 참조한다.
