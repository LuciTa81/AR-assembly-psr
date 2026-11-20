# Beast Software-First Roadmap Implementation Plan

2026-10-06 최신 진행: R6 최소 로컬 관제와 선택적 영상·판정 피드백을 구현했다.
H1 실제 눈별 정합 및 H2 안정적인 실제 조립 전이는 여전히 미완료다.
현재 실행·시연·후속 순서는 [최소 시연 로드맵](../../beast_demo_roadmap_20261006.md)을 우선 참조한다.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement each approved sub-plan task-by-task. Steps use checkbox syntax for tracking. This document is the roadmap; stages spanning independent subsystems receive a focused implementation plan before code changes.

**Goal:** 기존 측정값과 Python/Unity 코드를 유지하면서 실물 없는 개발을 먼저 진행하고, 착용 정합을 검증한 뒤 실제 조립 안내와 최소 관제를 완성한다.

**Architecture:** Windows 노트북이 카메라 입력, 위치 추적, 인식과 단계 판단을 소유한다. Unity는 눈별 원과 안내를 표시한다. 관제는 같은 상태를 읽는 보조 화면이며, 독립적으로 조립 상태를 판정하지 않는다.

**Tech Stack:** 기존 Python/OpenCV/YOLO, OnlineStateFilter, Unity 6000.3.25f1 Windows, 현재 로컬 HTTP와 재생 하네스.

**Spec:** ../specs/2026-09-26-beast-minimal-harness-design.md 및 ../specs/2026-09-27-beast-display-correspondence-design.md.
현재 증거: ../../beast_manual_alignment_probe.md.

작성: 2026-09-27. 2026-09-28 사용자 진행 승인으로 R1-R4 소프트웨어 구현/검사를 완료했다.
R4는 시간 기반 접근/이탈, 같은 목표 유지와 분리된 알림을 연결하고
독립 검토 및 실제 Unity JSON/렌더 회귀 검사까지 수행했다.
실제 눈별 정합과 조립 착용 검사 H1/H2는 남아 있다.
직접 구현 방식을 유지하며 커밋/푸시/배포하지 않았다.

## Global Constraints

- Windows 노트북 + VITURE Beast, 사용자1명, 인클로저1종, 작업대와 상자 상대 위치 고정.
- Neckband, 휴대폰 앱, JEV, 자유 이동 SLAM, 체결 토크 판정은 제외한다.
- 실기기 없이 개발한다는 것은 합성/재생/단위/통합 테스트를 생략한다는 뜻이 아니다.
- 카메라 실행과 착용 검사는 사용자의 준비 확인 후 유한 시간만 수행한다.
- 영상 저장/업로드는 기본 OFF. 기록된 metadata를 원본 영상으로 취급하지 않는다.
- 현재 원격 서비스/운영 SafeOps 자격증명/유료 리소스는 사용하지 않는다.
- 기존 카메라 보정, 작업대 실측, 나사 좌표를 보존한다. 배치/영상 모드가 바뀌면 재검증한다.
- 수동 원 위치 복원은 조작 시작값일 뿐 유효 pose나 광학 보정을 복원하지 않는다.
- pose 유효 나이는 서버 age + RTT + 수신 후 경과시간으로 판단한다. pose 기준150ms와 기존 P1 상태 표시500ms를 구분한다.
- marker 유실/만료/연결 오류를 정상 도구 이탈이나 조립 완료로 취급하지 않는다.
- S6는 관측된 순서의 마지막 단계이며 실제 토크/체결 품질을 보증하지 않는다.
- 기존 dirty worktree는 보존한다. 커밋은 승인 범위와 소유 변경을 확인한 뒤 별도 수행한다.

## 현재 기준선

| 항목 | 확인한 것 | 아직 미확인 |
| --- | --- | --- |
| 실행/재생 | Python 실행 하네스, 기록 재생, 유효성 검사 | 모든 현장 조건의 안정성 |
| Unity | Windows 빌드, 이전 Beast 출력, 일반 안내의 합성 눈별 SBS 렌더/유실 숨김 | 실제 보정 프로필로 자동 정합한 Beast 안내 |
| 기하 | 카메라 보정 후보, 실측 마커 좌표와 높이60mm의 나사 A-D 등록, PnP 구현 | 눈에서 보이는 실제 정합 오차 |
| 수동 SBS | 좌우 채널 분리, 한 자세에서 양안 단일 원 착용 확인 | 고개 이동/거리 변화/재착용 |
| 대응점 수집 | 카메라 관측과 눈별 화면 좌표 후보5개 기록 | 그 후보의 최종 광학 일치와 보정에 충분한 분포 |
| 실시간 인식 | ROI/YOLO/OnlineStateFilter, R4 시간 기반 접근·이탈/보류/문구 재생 검사 | 실제 체결 품질, 새 환경의 조기/지연 전이 성능 |
| 원격 관제 | 최소 구조 설계와 SafeOps 참고 저장소 | 이 AR 세션과의 구현/연동 |

2026-09-28 R3 구현 후 소프트웨어 검증은 pytest242, NUnit146,
실제 Unity spatial JSON smoke26 및 기존 수집 HTTP/JSON smoke37 통과다.
Windows Unity 최종 빌드와 실제 Player 렌더34장 픽셀 검사도 통과했다.
R4 이후 최신 검증은 pytest288, NUnit165, 실제 Unity 안내 JSON629,
공간26/수집37, 최종 R4 렌더57장 및 기존 R3 회귀 렌더40장 통과다.
상세와 실행 방법: ../../beast_state_guidance.md.
실기기/착용 정합 검사를 대체하는 결과가 아니다.
마지막180초 수집은 tracking93/1764, 새 후보0으로 종료했다.
수집 실패 응답의 marker_ids 누락은 실제0개 검출과 다르며, 카메라 미시작으로 해석하지 않는다.

## Review Focus

1. 실패 응답의 누락 필드를0으로 표시하지 않는다: R1에서 missing과 empty를 각각 검사한다.
2. 이전 좌표 복원이 이전 저장/보정 성공까지 복원하지 않는다: R1에서 복원 후 Enter 전 미저장 상태를 검사한다.
3. 같은 관측 재수신이 원의 유효 시간을 연장하지 않는다: R2/R3에서 중복/지연/역순을 검사한다.
4. 도구 검출 실패가 정상 이탈로 오인되지 않는다: R4에서 lost/stale/missing과 유효한 멀어짐을 분리한다.
5. 관제 영상과 상태가 서로 다른 시점일 수 있다: R6에서 각각의 시각/신선도를 표시하며 일치한다고 꾸미지 않는다.

## 실행 순서

R1 수집 진단 -> R2 좌표 계약/계산 -> R3 Unity SBS 안내 -> R4 상태 통합
-> H1 착용 정합 게이트 -> H2 조립 통합 게이트 -> R6 최소 관제 -> H3 최종 평가.

R1-R4의 소프트웨어 구현과 검사는 박스/Beast 없이 진행할 수 있다.
H1에서 필요한 실제 눈별 보정 데이터 수집/계수 확정은 소프트웨어 검사로 대체하지 않는다.
R6의 정적 화면/로컬 모의 계약은 미리 만들 수 있으나, 큰 원격 인프라 확장은 H1 이후로 제한한다.

## R1. 수집 진단과 조작 개선

**결과물:** 다음 착용 시험에서 입력 장면과 실패 이유가 보이는 작은 수집 도구.

**Files:**
- Modify: server/realtime/workspace_live_preview.py, server/realtime/display_observation_server.py.
- Modify: client_unity/Assets/Scripts/DisplayObservation.cs, DisplayObservationRecorder.cs, StereoAlignmentProbe.cs, StereoAlignmentState.cs.
- Modify: scripts/run_beast_unity.ps1.
- Test: tests/realtime/test_workspace_live_preview.py, test_display_observation_server.py; tests/unity/DisplayObservationTests.cs, StereoAlignmentStateTests.cs.

- [x] rejected 응답에도 알려진 marker_ids와 검출 수를 전달하되, 영상이 없는 경우 unknown과0을 구분하는 회귀 검사를 먼저 만든다.
- [x] 현재 run_collection에 명시적 no-save preview 옵션을 추가한다. 기존 camera_worker 하나만 소유하고 같은 패킷으로 관측과 Tk 미리보기를 만든다. 카메라를 두 번 열지 않는다.
- [x] 미리보기 image는 로컬 표시에서만 소비한다. ObservationStore와 HTTP 응답에는 영상 배열을 전달하거나 복사하지 않는다.
- [x] 미리보기 저장 단축키/자동 저장/영상 endpoint는 제공하지 않는다. 창 종료 및 카메라 오류 시 소유 자원을 정리한다.
- [x] Unity에 수집 가능/불가와 거절 이유를 표시한다. 관측 상태 조회는 단일 요청 경로를 사용하고 Enter용 저장 관측을 캐시 성공값으로 대체하지 않는다.
- [x] 명시적으로 선택한 이전 수동 좌표를 시작 위치로 불러온다. 화면 크기/눈별 좌표 범위를 검사하고 saved/confirmed/calibrated 상태는 복원하지 않는다.
- [x] 조절/눈 전환 후 오래된 SAVED를 현재 위치의 저장 성공으로 보여주지 않는다. 최종 저장 좌표와 현재 좌표의 일치 여부를 검사한다.
- [x] 모의 camera_worker로 preview ON/OFF, 저장0, 캡처 소유자1개, 유한 종료를 검증한다.

**완료 조건:** 가짜 입력에서도 검출0/정보 없음/pose 거절/시간 만료가 구분되고, 영상 파일 없이 좌표 기록 동작이 재현된다.

## R2. 좌표 계산과 표시 계약

**결과물:** synthetic 또는 기록된 위치 입력을 받아 눈별 표시 좌표를 산출/검사하는 모듈.

**Files:**
- Reuse: server/realtime/workspace_projection.py.
- Create: server/realtime/display_calibration.py, tests/realtime/test_display_calibration.py.
- Modify: server/realtime/schemas.py, overlay_http_server.py; client_unity/Assets/Scripts/GuidanceSnapshot.cs.

- [x] 입력을 target_id, camera_xyz_mm, camera/workspace/display profile 식별자, pose 원본 frame_id와 age로 정의한다.
- [x] 출력은 각 눈의 eye-local pixel 좌표, eye 이미지 크기, target_visible, 불가 사유와 시험/검증 상태로 정의한다. 왼눈 좌표와 오른눈 좌표를 복제하지 않는다.
- [x] 현 realtime_v1 상태 필드를 유지하며 추가 위치 payload 계약을 Python/C# 공동 fixture로 고정한다. 계약 하위 계획에서 필드명과 버전을 하나로 확정한다.
- [x] 합성 표시 프로필로 좌표계 방향/단위/투영/화면 밖/음수 깊이/NaN/불일치 프로필을 검사한다. 합성 프로필은 일반 실제 안내에서 활성화하지 않는다.
- [x] 눈별 실제 보정 모델 선택과 계수 추정은 수집 범위/분포를 평가하는 H1 하위 계획에서 다룬다. 현재 후보5개로 일반 보정 행렬을 확정하지 않는다.

**완료 조건:** 알려진 합성 입력에 대한 기대 좌표와 거절 조건이 일치한다. 실제 눈 정합 통과와 구분해서 보고한다.

계약 상세: ../../beast_display_contract.md.
구현/검증 기록: 2026-09-28-beast-display-contract-r2.md.

## R3. 일반 안내 화면의 SBS 연결

**결과물:** 수동 시험이 아닌 일반 안내 화면에서 서로 다른 눈별 좌표로 원을 표시하는 Unity 클라이언트.

**Files:**
- Modify: client_unity/Assets/Scripts/GuidanceSnapshot.cs, GuidanceState.cs, GuidanceReceiver.cs, GuidancePresenter.cs, DisplayBootstrap.cs.
- Reuse: StereoAlignmentProbe.cs의 눈별 반쪽 좌표 원칙. 수동 키 조작 자체는 일반 안내로 옮기지 않는다.
- Create: client_unity/Assets/Scripts/SpatialGuidanceState.cs, SbsGuidanceOptions.cs, SbsGuidancePresenter.cs.
- Test: tests/unity/SpatialGuidanceStateTests.cs, serve_spatial_fixture.py, check_sbs_capture.py 및 기존 Unity Editor/Player 검사 도구.

- [x] 3840x1080 Full SBS의 각1920x1080 eye-local 표시 경계를 검사한다. 창 모드 모의 SBS와 실제 Beast 활성화를 구분한다.
- [x] 합성 목표 이동과 A-D 전환을 fixture로 재생해 눈별 원이 해당 영역을 벗어나지 않는지 확인한다.
- [x] 위치 유효150ms를 상태 문구의500ms 시험 예산과 분리한다. 중복 관측 수신으로 위치 수명을 연장하지 않는다.
- [x] 추적 유실/카메라 정지/출력 변경/프로필 불일치 시 원은 숨기고 마지막 상태는 참고 정보로만 남긴다.
- [x] 실제 보정 프로필이 없으면 미보정 상태로 유지한다. synthetic 원을 실제 나사에 맞춘 안내라고 표시하지 않는다.
- [x] Unity 자체 렌더 결과와 실제 HTTP/JSON 검사를 수행한다. 이는 착용 광학 검사가 아니다.

**완료 조건:** 노트북 모의 실행에서 이동/유실/복구/지연 시나리오가 재현되고 잘못된 원이 남지 않는다.

구현/검사 상세: ../../beast_sbs_guidance.md 및 2026-09-28-beast-sbs-guidance-r3.md.
캡처 실행 중 간헐적인150ms 만료 숨김이 관측됐으므로 무깜빡임/실기기 성능은 보장하지 않는다.

## R4. 상태와 사용자 안내 통합

**결과물:** 기존 인식 결과에 맞춰 현재 작업을 유지하고 다음 목표를 안내하는 로컬 흐름.

**Files:**
- Create: server/realtime/guidance_timing.py.
- Modify: server/realtime/online_state_filter.py, run_realtime_server.py, schemas.py, realtime_replay.py.
- Reuse: yolo_realtime.py, roi_realtime.py, realtime_replay.py, realtime_logger.py.
- Modify: client_unity/Assets/Scripts/GuidanceState.cs, GuidanceReceiver.cs, GuidancePresenter.cs, SbsGuidancePresenter.cs.
- Test: tests/realtime/test_online_state_filter.py, test_replay.py, test_runtime_lifecycle.py; tests/unity/GuidanceStateTests.cs.

- [x] 조립 상태 S0-S6와 표시 상태를 분리한다. 표시 상태는 미보정/추적 대기/안내/작업 관찰/확인 대기/중단/최종 확인을 다룬다.
- [x] 유효한 새 증거의 연속 머무름과 관측 가능한 도구 이탈을 구분한다. 프레임 수 기준의 FPS 의존성을 관측 시간 기준으로 줄이는 변경을 별도 회귀 검증한다.
- [x] 나사 A 작업 중에는 A 안내를 유지한다. 검출 실패나 마커 유실만으로 B로 넘어가지 않는다.
- [x] 손 스침, 다른 나사 접근, 같은 관측 반복, 타임아웃, 유실 후 복구의 부정 사례를 합성 fixture로 검사한다.
- [x] state authority는 OnlineStateFilter 한 곳에 둔다. Unity/관제가 별도의 다음 상태를 추측하지 않는다.
- [x] 기존 영상 재생 경로는 유지하고, 이번 metadata 입력은 상태/표시 재생으로 검사한다. 실제 영상 인식 성능 검증과 구분한다.
- [x] S6 문구는 최종 사용자 확인을 요구하며 체결 토크 보증을 하지 않는다.

**완료 조건:** 정해진 재생 시나리오에서 상태/목표/문구/이벤트가 일치한다. 현장 정확도 향상은 H2에서 별도로 측정한다.

구현/검사 상세: ../../beast_state_guidance.md 및 2026-09-28-beast-state-guidance-r4.md.
실제 정책은 명시적 timed_v1이며, 구형 기록은 legacy_frames로 유지한다.
최종 확인 버튼/완료 저장 명령은 추가하지 않았다.

## H1. 다음 착용 정합 게이트

**진입 조건:** R1의 같은 입력 미리보기와 R2/R3의 합성 검사가 준비됐다. 이번 문서로 촬영을 시작하지 않는다.

- [ ] 나사 A를 보는 편한 자세에서 실제 camera image/검출 수와 눈별 원을 함께 확인한다.
- [ ] 최종 정렬한 눈별 위치와 유효 카메라 관측을 저장하고 양안 일치를 착용자가 확인한다.
- [ ] 그 결과와 수집 분포를 기준으로 실제 보정 모델, 여러 위치/거리의 수집 계획 및 검증점 오차 기준을 먼저 확정한다.
- [ ] 필요한 대응점을 수집하고 보정에 쓰지 않은 위치에서 오차를 확인한다. 단일점 성공을 모든 자세/거리의 성공으로 확대하지 않는다.
- [ ] 고개 이동, 마커 가림/복구, 재착용을 확인하고 허용 작업 범위를 문서화한다.

**통과:** 사전에 정한 작업 범위/오차 기준에서 실제 눈별 자동 표시가 맞고, 유실 시 숨김이 동작한다.
**미통과:** R1-R4 성과는 유지하되 정합/시야 문제를 먼저 해결한다. 원격 관제로 핵심 결함을 덮지 않는다.
카메라에 겹친 진단 화면은 개발 보조물이며 실제 물체 정합의 대체 성공으로 보고하지 않는다.

## H2. 실제 조립 안내 게이트

- [ ] 실제 박스에서 S0-S6를 실행하고 조기 전이/전이 지연/오안내를 구분해서 기록한다.
- [ ] 나사를 돌리는 동안 목표가 바뀌지 않는지, 손 스침/다른 나사/마커 가림에 잘못 진행하지 않는지 확인한다.
- [ ] 정합 오차, 추적 유효율, 서버 수신 이후 표시 경과시간, 단계 전이 오차를 별개 지표로 보고한다.

**통과:** 실제 작업을 반복해 다음 단계 안내와 중단 동작이 설명 가능한 결과를 보인다.
한 번 성공한 시연만으로 일반화 성능을 주장하지 않는다.

## R6. 최소 관제 확장

**결과물:** 같은 작업 세션의 상태, 목표, 추적 상태, 최근 이벤트와 선택적 미리보기를 보여주는 웹1페이지.

**Files:** 기존 server/realtime/realtime_logger.py와 상태 계약을 재사용한다.
필요한 추가 경계는 server/remote/app.py, event_store.py 및 web_supervisor/이며,
독립 하위 계획 승인 후 생성한다. 처음에는 같은 노트북의 별도 프로세스만 사용한다.

- [ ] session_id/event_id/state_version으로 이벤트를 저장하며 재전송 중복과 역순 최신 상태 덮어쓰기를 막는다.
- [ ] 모의 세션으로 대시보드를 만들고 오래된 상태/연결 끊김을 표시한다.
- [ ] 영상 미리보기는 별도 opt-in으로 추가하고 영상과 상태의 각 시각을 표시한다.
- [ ] 초기 원격 추론/외부 서버는 필수로 만들지 않는다. 우선 로컬 YOLO를 유지한다.
- [ ] 실제 원격 YOLO 또는 외부 접속은 필요성이 생길 때 별도 승인한다. 모델 adapter/인증/TLS/프레임 결합 및 비용을 그때 검토한다.

**완료 조건:** 로컬 모의 세션이 Unity와 관제에서 같은 확정 상태를 보이며, 관제 단절이 로컬 안내를 멈추지 않는다.
KVS/IVS/SQS/Laravel/노드 풀은 초기 요구사항이 아니다. 새 서버 임대는 별도 승인 전 하지 않는다.

## H3. 최종 평가와 결과물

- [ ] 서로 다른 조립 실행3회 이상과 실패 사례를 기록한다. 같은 기록 재생3회와 구분한다.
- [ ] 입력/모델/보정/코드 버전과 한계를 결과에 함께 남긴다.
- [ ] 실행 스크립트, Unity Windows 앱, 로컬 Python 서버, 관제1페이지, 시연 기록과 보고서를 정리한다.
- [ ] 이전1학기 session17 오프라인 HMM 성능을 새 실시간 시스템의 성능으로 재사용하지 않는다.

## 당장 할 일과 하지 않을 일

**R1 완료:** ../plans/2026-09-28-beast-collection-r1.md 및 ../../beast_manual_alignment_probe.md 참조.
**R4 완료:** 상태/안내 재생 통합과 Unity 실제 렌더 검사를 마쳤다.
**다음 핵심 게이트:** H1 실제 눈별 정합. 사용자 준비 전 카메라/착용 검사는 켜지 않는다.
계속 실물 없이 진행하려면 R6의 최소 로컬 관제 모의 화면을 다음 독립 단위로 잡는다.
이 경우에도 실제 정합/현장 성능은 H1/H2에서 검증한다.
실물 없는 개발 구간에 새로운 AWS 비용은 필요 없다.

**오늘 하지 않음:** 추가 촬영, 긴 착용 시험, 새 모델 도입, 서버 임대, 운영 SafeOps 연결.
달력상 완료일이나 최종 정합 성공은 아직 약속하지 않는다. H1의 결과가 그 범위를 결정한다.
