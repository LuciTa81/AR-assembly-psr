# Beast 눈별 카메라-표시 대응점 수집 설계

작성: 2026-09-27. 상태: 사용자 설계 승인 완료. 아직 구현/카메라 실행 전.
승인: 사용자가 "이 범위로 진행해"라고 확인했습니다. 구현계획은 별도 검토합니다.
상위 설계: 2026-09-26-beast-minimal-harness-design.md의 P2를 작은 수집 단계로 구체화합니다.
기존 수동 SBS 결과: ../../beast_manual_alignment_probe.md.
커밋/푸시/외부 배포는 하지 않습니다.

사용자는 지난 SBS 수동 정합을 같은 자세에서 수행했다고 확인했습니다.
지난 양안 단일점 성공은 유효한 관찰로 유지합니다. 당시 카메라가 꺼져 있어
화면 좌표와 연결할 카메라 관측이 없다는 점을 이번 수집으로 보완합니다.

## 목적과 완료 범위

같은 사용자가 Beast 0DoF + Full SBS로 나사 A에 눈별 원을 수동 정합하고,
각 눈에서 Enter를 누른 시점 부근의 유효 카메라 관측을 화면 좌표와 묶습니다.
왼눈과 오른눈은 별도 관측입니다. 두 눈을 조절하는 동안 머리가 계속 같은 자세였다고
가정하여 나중의 카메라 pose 하나를 두 눈에 공통 적용하지 않습니다.
이는 앞으로 여러 대응점을 모을 때의 기록 방식이며, 지난 시험에서 자세가 달라졌다는
판정이 아닙니다.

이번 완료 조건은 독립적인 왼눈/오른눈 후보 기록을 실제 기기에서 각각 한 개 이상
얻고, 실패 조건이 후보 저장으로 표시되지 않음을 확인하는 것입니다.
좌표 보정 계산, 자동으로 움직이는 원, 인식 모델 변경은 이번 범위가 아닙니다.
한 점의 수집 성공을 보정 또는 mm 단위 정합 정확도 통과로 보고하지 않습니다.

## 선택한 방식

1. 권장: 기존 수동 SBS 앱에 선택적 로컬 관측 연결을 추가하고 눈별 Enter마다 기록합니다.
2. 미채택: 마지막에 양쪽 원 좌표와 pose 하나를 저장하면 눈별 자세 차이를 놓칩니다.
3. 미채택: 영상 스트리밍/클라우드/하드웨어 동기화 장치를 먼저 추가하면 초기 수집 범위가 커집니다.

기존 2D/SBS 수동 시험은 카메라/HTTP 없이 계속 동작합니다.
별도 수집 옵션을 지정했을 때만 로컬 카메라 프로세스와 통신합니다.
일반 인식 서버, OnlineStateFilter, YOLO 및 기존 /state.json 계약을 바꾸지 않습니다.

## 흐름

```text
Beast UVC -> 기존 ArUco/PnP 계산 -> 최신 관측 1개 (Python)
                                         |
                    127.0.0.1 임시 포트 /observation
                                         |
Unity: 한쪽 눈 원 정합 -> Enter -> 화면 좌표 고정 -> 관측 요청
  -> 세션/프로필/시각/표시 조건 검사
  -> 성공: 눈별 후보 JSON 저장 + SAVED
  -> 실패: 사유 표시, SAVED 및 기록 수 증가 없음
```

카메라의 영상은 메모리에서 마커 검출 후 버립니다. 프로세스 간에는 원본 영상 대신
frame_id, 수신시각, pose와 품질 지표만 보냅니다. 최신 불량 관측을 이전의 정상 pose로
대체하지 않습니다. 카메라 오류는 프레임 큐와 별도로 전달하고 즉시 관측을 무효화합니다.

## 관측과 좌표 계약

Python 응답에는 다음 값을 넣습니다.

- schema_version, session_id, frame_id, status/reason.
- 카메라/작업대 profile ID와 원본 JSON SHA-256, 카메라 해상도.
- age_ms: OpenCV read 반환 직후부터 응답 생성까지의 Python monotonic 경과시간.
- pose rvec, tvec_mm, 검출 마커 ID, reprojection RMS/최대값.
- target_id=A, world_xyz_mm, camera_xyz_mm, 원본 왜곡 카메라 영상의 target_pixel.
- 카메라 XYZ는 OpenCV 좌표계(+X 오른쪽, +Y 아래, +Z 전방), world는 기존 작업대 mm 좌표계.
  camera_xyz_mm = Rodrigues(rvec) * world_xyz_mm + tvec_mm.

Unity는 Enter 시점의 eye=left/right와 눈별 x/y(1920px 너비 기준), 화면/출력 해상도를
고정하여 요청합니다. 요청 중에는 이동/눈 전환/중복 Enter를 막고 Q/Esc 종료는 허용합니다.
Both 화면은 광학 비교용이며, 수집 모드의 Enter로 두 눈의 대응점을 한 번에 만들지 않습니다.

저장 파일에는 위 응답과 눈별 화면 좌표, 요청 시작/종료 Unity monotonic 시각,
request_rtt_ms, conservative_age_ms=age_ms+request_rtt_ms를 함께 기록합니다.
Python과 Unity의 원시 monotonic 시각을 직접 빼지 않습니다.
Enter부터 응답 완료까지 자세를 잠시 유지하도록 안내합니다.

최신 관측이어야 하고 conservative_age_ms가 0~150ms일 때만 후보 기록을 허용합니다.
이는 기존 수신 신선도 기준을 적용한 것으로, 센서 노출 시각이나 실제 광학 지연을
150ms 이내라고 보증하지 않습니다. 정확한 동기 캡처가 아니라 시간 범위를 기록한
수동 대응점 후보이며, 이후 여러 위치/거리의 별도 검증이 필요합니다.

## 최소 거절 조건

- 채널 확인 전, 잘못된 눈 선택, 표시 이름/렌더/실제 출력 크기 변경.
- 연결 단절, HTTP 오류/리다이렉트, 요청 지연, 비정상/누락/비유한 값.
- 세션/프로필 불일치, 잘못된 카메라 해상도, 카메라 종료.
- 현재 마커 pose 무효, 나사 A 화면 밖/카메라 뒤, 오래된 관측.
- 같은 눈에서 같은 frame_id를 재사용한 중복 후보.
- 로컬 파일 쓰기 실패. SAVED는 쓰기가 성공한 경우에만 표시합니다.

실패 시 이전 정상 pose를 붙여 성공 처리하거나 신선도 기준을 자동 완화하지 않습니다.
수동으로 조절하는 원은 측정용이라는 표시를 유지하며 자동 추적 원으로 취급하지 않습니다.

## 저장·보안·수명

- Python은 127.0.0.1의 빈 임시 포트에만 바인드합니다. 영상 제공 endpoint는 없습니다.
- 실행별 랜덤 토큰을 Authorization 헤더로 확인하고 CORS/리다이렉트를 허용하지 않습니다.
- Unity는 로컬 실행 설정의 http://127.0.0.1 주소만 받습니다. 토큰을 로그에 출력하지 않습니다.
- 설정/후보/요약은 %LOCALAPPDATA%/ARAssembly/beast-mvp/display_correspondence 아래에
  고유 폴더로 저장합니다. OneDrive/저장소에 영상 또는 실행 토큰을 저장하지 않습니다.
- 파일에는 candidate_only=true, calibration_valid=false, display_alignment_verified=false를
  유지합니다. 기존 보정 profile/조립 상태를 변경하지 않습니다.
- 서버와 Unity는 최대 300초의 유한 시험으로 실행하고, 대기/단절/종료를 테스트합니다.
  카메라는 전용 자식 프로세스가 소유하며 종료 지연 시 그 자식만 정리합니다.
- 시작 전 사용자가 착용/작업대/카메라 실행 준비를 확인합니다. 새 서버 비용은 없습니다.

## 파일 범위

- server/realtime/workspace_live_preview.py: 기존 camera_worker에 영상 미전송 옵션.
  기존 미리보기의 기본 동작은 유지합니다.
- server/realtime/display_observation_server.py: 최신 관측, 로컬 API, 유한 실행/설정 기록.
- client_unity/Assets/Scripts/DisplayObservation.cs: 관측 DTO와 순수 검증/기록 규칙.
- client_unity/Assets/Scripts/DisplayObservationRecorder.cs: 선택적 요청/저장.
- StereoAlignmentProbe.cs / StereoAlignmentState.cs: 수동 시험의 눈별 수집 연결.
- scripts/run_beast_unity.ps1: 선택적 수집 설정 경로 인수.
- tests/realtime 및 tests/unity: 기하/계약/거절/종료 테스트와 실제 파일 기록 검증.

## 검사와 다음 단계

실카메라를 켜기 전에 합성 pose -> HTTP -> Unity 관측 검증을 검사합니다.
프로필 불일치, 마지막 정상 프레임 뒤 marker 유실/카메라 정지, stale/미래 시각,
출력 크기 변경, 늦은 응답, 중복 Enter, 저장 실패, 유한 종료를 포함합니다.
전체 Python/C# 테스트와 Unity 빌드를 재실행합니다.

실기기에서는 상자/마커와 화면 크기/거리 설정을 고정하고, 나사 A의 왼눈/오른눈 후보를
짧게 수집합니다. 기록 수/거절 사유/관측 나이/pose 품질을 먼저 보고합니다.
이 확인 뒤 별도 단계에서 여러 관측의 공간적 분포와 반복성, 보정 모델, 검증점 오차를
검토합니다. 아직 고개 이동을 따라가는 자동 오버레이를 활성화하지 않습니다.
