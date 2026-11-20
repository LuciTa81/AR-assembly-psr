# AR 조립 안내 시스템: 아키텍처 도식용 사실
확인일: 2026-11-08. 기준: 현재 저장소의 `scripts/start_beast_assembly.ps1 -Live` 통합 시연 경로.
이 문서의 "실시간"은 실시간 실행 경로에 구현되어 있다는 뜻이며, 현재 카메라가 켜져 있다는 뜻은 아니다. 이번 확인은 코드 열람만 수행했다.

## 1. 프로세스 / 경계

| 경계 | 실행 환경 | 역할 |
|---|---|---|
| 작업대 | 물리 환경 | 고정된 ArUco 마커, 상자, 뚜껑, A-D 나사, 드라이버 |
| VITURE Beast | 카메라 입력 + Windows 확장 디스플레이 | 작업 영상을 노트북에 입력하고 Unity의 Full SBS 화면 출력. 시연 설정은 0DoF / Extra Large / 4.5m |
| Python 실시간 서버 | Windows / Python / OpenCV / Ultralytics YOLO | 카메라 수집, 마커 기반 자세 추정, 도구 검출, 시간 판정, FSM, 로컬 HTTP, 숫자 로그 |
| Unity 앱 | Windows standalone / Unity / C# | 단계 상태와 카메라 좌표를 받아 눈별 화면 좌표 계산, 목표 원과 안내 문구 출력. 3840x1080, 눈별 1920x1080 |
| 관제 페이지 | Chrome / HTML·CSS·JavaScript | 작업대 영상, 단계, 보류 이유, 진행 상태 표시. 상자·뚜껑·최종 확인 입력 |
| 오프라인 분석 | 별도 실행 Python 스크립트 | 저장 프레임/특징 CSV로 MediaPipe·YOLO·ROI 특징 분석, HMM/Viterbi 비교 평가 |
| 실행 관리 | PowerShell | Python/Unity/Chrome 실행 및 세션 종료 관리. 인식 알고리즘은 아님 |

Python의 YOLO 워커와 HTTP 서버는 **동일 Python 프로세스의 스레드**다. 별도 AI 서버나 별도 통신 서비스가 아니다.
별도의 카메라 진단 도구에는 프로세스 분리가 있지만, 위 통합 실시간 경로와 구분한다.

## 2. Python 내부 처리

### 실시간 주 경로

| 순서 / 모듈 | 입력 → 출력 |
|---|---|
| 1. `frame_source.CameraFrameSource` | DirectShow 카메라 → BGR 프레임 + `frame_id` + 단조 증가 시계 기반 `timestamp_ms` |
| 2. `PresentationBridge.observe` / `workspace_live_preview.analyze_frame` | 동일 프레임 + 카메라/작업대 프로필 → ArUco ID·코너·마커 중심, 검출 상태 |
| 3. `workspace_projection.estimate_pose` | 알려진 마커 중심의 3D 좌표와 영상 좌표 + 카메라 내부 파라미터 → PnP 자세 `rvec,tvec_mm` + 재투영 오차 |
| 4. `project_targets` / `ObservationStore` | 등록된 A-D 3D 좌표 + 자세 → 카메라 좌표계 A-D XYZ 및 카메라 영상 픽셀 |
| 5. `MetricToolPlane` + `RealtimeYoloAnalyzer` | 영상 + 같은 입력 프레임의 자세/평면 변환 → driver/handle/screw 검출, 도구 끝 후보, 나사 평면 기준 거리·근접 점수 |
| 6. `make_filter_input` + `TimedEvidenceGate` | 도구 점수 + 현재 목표 + 관측 ID·시각·유효성 → 접근/유지/이탈 증거, `GUIDING/OBSERVING/OBSERVED/PAUSED` |
| 7. `OnlineStateFilter` + `AssemblySession` | 유효한 시간 증거 또는 관제 확인 → S0-S6, 현재 목표, 다음 행동, 보류 이유, 진행 보존 상태 |
| 8. `PresentationBridge.update` / `OverlayMessage` / `RealtimeLogger` | 단계 + 해당 프레임 관측 → 카메라 진단 영상, 상태 JSON, 로컬 CSV/JSONL |

- PnP: 현재 주 경로는 **등록 마커 중심 4개 이상**을 사용한다. `SOLVEPNP_IPPE` 후보 계산 → 물리적 자세/모호성 검사 → `solvePnPRefineLM` → RMS 3px·최대 5px 이하 검사. 코너 전체를 쓰는 별도 후보 함수는 오프라인용이다.
- A-D는 마커 기준으로 미리 등록된 3D 위치다. 매 프레임 YOLO가 나사 중심의 3D 위치를 새로 찾는 구조가 아니다.
- YOLO는 `best-3.pt`를 쓰며, 설정상 매 2번째 입력 프레임을 제출한다. 백그라운드 추론 결과에는 원본 프레임 ID와 시각이 붙는다. 실제 처리 주기는 카메라·추론 속도에 따라 달라진다.
- 도구 끝은 검출 상자/손잡이 관계 등에서 구하는 후보다. 이를 나사머리 높이의 평면으로 변환해 목표별 거리와 점수를 계산한다.
- 시간 검증: 중복·역순 관측, 오래된 결과, 관측 간격, 마커 상태, 도구 후보의 유일성, 다른 나사와의 점수 경쟁을 확인한다.
- 기본 나사 판정은 접근 후 유효한 유지 **800ms**, 이후 도구가 보이는 상태의 이탈 **400ms**다. 관측 간격 기준은 350ms, 도구 관측 최대 나이는 800ms다.
- 단계: **S0 상자 배치(수동 확인) → S1 뚜껑 닫힘(수동 확인) → S2 A → S3 B → S4 C → S5 D(자동 접근·유지·이탈) → S6 최종 확인(수동)**. 최종 확인 후 S6에서 `completed=true`.
- 이 자동 전이는 도구의 접근·유지·이탈 관측이다. 나사 체결 토크나 실제 조임 완료를 직접 측정하는 기능은 미구현이다.
- 기존 상자/뚜껑 ROI 분석 코드는 있지만, 현재 hybrid 통합 경로에서는 기존 ROI/평면 ArUco 분기를 끈다. 위의 **metric ArUco/PnP 분기는 계속 사용**한다.

### MediaPipe / HMM / Viterbi 경로

저장 세션 프레임 → ArUco 정규화/ROI 특징 + YOLO 도구 특징 + MediaPipe 손 랜드마크 특징 → `build_hmm_input_v2.py`의 프레임별 특징 CSV → `run_state_baseline_v2.py`의 관측 점수·상태 전이 확률 → Viterbi 최적 상태열 → 예측 CSV·타임라인·평가 지표.

**구현 및 실험은 존재하지만 오프라인 경로다. 실시간 FSM에 HMM/Viterbi가 연결되어 있지는 않다.**
`run_session17_best_role3_hmm.ps1`은 MediaPipe 특징 CSV를 입력으로 받지만 `--index-weight 0.0`이므로 그 설정에서 손끝 특징이 상태 점수에 기여한다고 표현하면 안 된다.

## 3. 프로세스 간 통신

| 데이터 방향 | 전달 방식 | 필드 / 내용 | 주기 |
|---|---|---|---|
| Beast 카메라 → Python | 카메라 드라이버 / OpenCV DirectShow | BGR 영상 | 카메라 읽기·처리 속도 기준. 고정 실측 FPS로 단정 불가 |
| Python → Unity, 관제 | 로컬 HTTP `GET /state.json`에 대한 JSON 응답 | `session_id, frame_id, timestamp_ms, current_state, target, next_action, marker_status, held_reason, guidance, extra.operator` | 서버는 처리 프레임마다 최신 상태 갱신. Unity SBS는 응답 후 다음 렌더 프레임에 재요청. 관제는 응답 완료 후 50ms 대기 |
| Python → Unity | 별도 loopback HTTP `GET /observation`, Bearer 인증 | `session_id, frame_id, age_ms, status, reason_code, marker_ids, rms_px, rvec, tvec_mm, camera_targets[{target_id,camera_xyz_mm}], ...` | 처리 프레임마다 최신 관측 갱신. Unity 나사 단계 요청 시작 최소 간격 1/64초, 그 외 1/30초. 단일 in-flight 요청으로 실제 빈도는 렌더/응답 속도에 제한 |
| Python → 관제 | HTTP `GET /frame.jpg` | 최신 JPEG + `X-AR-Session, X-AR-Frame-Id, X-AR-Timestamp-Ms, X-AR-Frame-Age-Ms` 등 헤더 | 영상 표시를 켠 동안 응답 완료 후 200ms 대기. MJPEG/WebRTC 스트림 아님 |
| 관제 → Python | same-origin HTTP `POST /operator/confirm` | JSON `{session_id, revision}`, 헤더 `X-AR-Operator: confirm` | 사용자가 확인 버튼을 누를 때. 서버가 검증 후 다음 유효 프레임에서 반영 |
| Python/실행기 → Unity | 로컬 `client-config.json` 경로를 실행 인자로 전달 | 관측 URL, 세션, 토큰, 프로필 ID/해시 | 세션 시작 시 |
| 로컬 보정 자료 → Unity | JSON 파일 읽기 | 좌·우 3x4 투영 행렬, C/D 거리별 보정 기록 등 | 시작 시 읽고 매 렌더에서 적용 |
| Unity → Beast | Windows 확장 디스플레이 렌더 출력 | 좌우 SBS 원·안내 문구 | Unity 렌더 주기 |
| Python → 디스크 / 오프라인 스크립트 간 | 로컬 CSV·JSONL·JSON | 상태·전이·타이밍·관측 숫자 / 오프라인 특징·예측 | 실시간 로그는 프레임·이벤트별, 오프라인은 배치 실행 |

주 HTTP 서버는 `127.0.0.1:8765`가 기본이며 실행기가 빈 포트를 선택할 수 있다. `/observation`은 같은 Python 프로세스가 만든 **별도 동적 포트**다.
`guidance` 예: `phase, reason, hold_progress, hold_remaining_ms, acknowledgement`.
`extra.operator` 예: `mode, revision, pending, completed, can_confirm`.

**Unity에서 하는 계산:** 카메라 XYZ → 로컬 눈별 투영/거리별 보정 → 좌·우 화면 픽셀 → SBS 렌더.
현재 경로에서 Python이 눈별 최종 픽셀을 매번 만들어 Unity로 보내는 것으로 그리면 부정확하다.

HTTP는 클라이언트가 요청하는 폴링이다. WebSocket, 클라우드 AI 추론, 브라우저↔Unity 직접 통신, 프로세스 간 OS 공유메모리는 현재 주 경로에서 사용하지 않는다.
관제 영상은 카메라 시점이며 실제 안경 속 양안 시야 캡처가 아니다.

## 4. 피드백 / 예외 경로

- 마커 부족·잘못된 자세·관측 만료 → 해당 자세를 무효화. 상태/관측 HTTP에 보류 사유를 노출하고, Unity는 유효한 공간 좌표가 없으면 원을 숨긴다. 최신 정상 관측에서 다시 계산한다.
- 도구 검출 누락·잘못된 끝 위치·오래된 YOLO 결과 → `TimedEvidenceGate`가 `PAUSED` 판정. 도구가 안 보이는 것을 이탈 완료로 취급하지 않는다.
- 현재 성공본 실행기의 보존 설정: 유지 중 증거 **최대 600ms**, 유지 완료 후 대기 증거 **최대 2000ms**. 새 유효 관측과 목표 일치 조건을 만족하면 이어가며, 보류 시간을 정상 유지 시간으로 더하지 않는다.
- 예산 초과 또는 상충하는 관측 → 현재 나사 동작을 재확인. 이미 완료한 이전 나사 단계까지 자동으로 S0으로 되돌리지 않는다.
- `SourceRecoveryBoundary`는 선택 옵션이다. 도구 관측 문제의 복구 경계를 해당 YOLO 원본 프레임 기준으로 두는 구현이며, 기본 실행에는 켜져 있지 않다.
- 관제/Unity 연결 지연 → 각 클라이언트가 오래된 상태를 표시하거나 안내를 보류한다. 클라이언트의 끊김이 서버에 단계 초기화 명령을 보내지는 않는다.
- 관제 수동 확인 → 세션/리비전/입력 신선도 검증 → Python `AssemblySession`에 대기 → 다음 유효 프레임에서 단계 반영 → 상태 HTTP를 통해 Unity와 관제에 재전달.
- 위 복구는 Python 내부 상태·다음 관측 사이의 경로다. 인식 실패가 YOLO 재학습, HMM 자동 실행 또는 물리 장치 제어로 되돌아가는 경로는 없다.
- 진행 상태는 세션 메모리에 있다. 프로세스 종료 후 자동으로 이전 진행을 복원하는 기능은 미구현이다.

## 5. 현재 상태 구분

| 기능 | 분류 |
|---|---|
| 카메라 입력, metric ArUco/PnP, A-D 좌표 변환 | 실시간 경로 구현 |
| YOLO 도구 검출, 목표별 근접·유지·이탈, FSM | 실시간 경로 구현·실기 흐름 확인 |
| 상자·뚜껑·최종 관제 확인, Unity SBS, 웹 관제 | 실시간 경로 구현·통합 실기 확인 |
| 짧은 끊김 진행 보존·재확인 | 실시간 경로 구현·실기 비교 수행 |
| SourceRecoveryBoundary | 실시간 선택 옵션 구현, 기본은 비활성 |
| MediaPipe 손 특징 + HMM/Viterbi | 오프라인 구현·분석 |
| 상자/뚜껑 ROI 자동 판정 | 기존 구현 존재, 현재 hybrid 통합 경로는 비활성 |
| 카메라/작업대/눈별 보정 및 C/D 보정 자료 생성 | 별도 진단·보정 절차. 결과 파일은 실시간 렌더에 사용 |
| MediaPipe/HMM의 현재 실시간 FSM 통합, 토크 판정, 재시작 후 진행 자동 복원 | 미구현 |
| 현재 카메라 실측 FPS, 현재 실행 중인 프로세스 상태 | 이번 코드 조사만으로 미확정 |

### 코드 근거
저장소 기준 상대 경로:
- `scripts/start_beast_assembly.ps1`, `scripts/run_beast_demo.ps1`, `configs/realtime_viture_beast_aruco.yaml`
- `server/realtime/run_realtime_server.py`, `frame_source.py`, `presentation_bridge.py`, `workspace_projection.py`
- `server/realtime/yolo_realtime.py`, `guidance_timing.py`, `online_state_filter.py`, `assembly_session.py`
- `server/realtime/overlay_http_server.py`, `display_observation_server.py`, `schemas.py`
- `client_unity/Assets/Scripts/GuidanceReceiver.cs`, `ObservationHttpTransport.cs`, `CandidateProjection.cs`, `SbsGuidancePresenter.cs`
- `web_overlay/supervisor.js`, `supervisor_video.js`
- `scripts/run_session17_best_role3_hmm.ps1`, `server/state/build_hmm_input_v2.py`, `run_state_baseline_v2.py`

