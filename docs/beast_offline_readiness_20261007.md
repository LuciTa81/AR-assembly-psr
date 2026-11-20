# Beast 최소 구현: 오프라인 정리와 다음 검증

2026-10-07. 추가 착용 시험 없이 진행한 소프트웨어 작업의 정리다.
현재 위치는 **기존 안내 경로의 회귀 검증과 위치 추적 실패의 수치 재현 준비 완료**다.
깜빡임 해결, 자동 눈별 정합 완료, A~D 실물 오버레이 완료를 의미하지 않는다.

## 현재 구조와 범위

```text
Beast 카메라 -> Python: ArUco/ROI + 비동기 YOLO
                         |-> timed_v1 상태/접근/이탈 판정 -> 안내 snapshot
                         |                              |-> Unity 단계 안내
                         |                              |-> 노트북 관제
                         |-> metric pose -> 후보 눈별 투영 -> SBS A 참조 원
                         |-> 결과/관측/지연 숫자 로그 -> 오프라인 재현/요약
```

- 상태의 단일 판단 주체는 Python이다. Unity와 브라우저는 같은 결과를 표시한다.
- 현재 실시간 상태 경로는 전체 시퀀스 Viterbi가 아니다.
- 나사 접근과 이탈을 관측하는 것이며 토크나 실제 체결 완료를 검증하지 않는다.
- SBS 원은 아직 **A 고정 참조, 미검증 후보**다. 다음 나사 지시와 혼동하지 않는다.
- 관제의 카메라 투영 영상은 안경을 통해 실제 눈에 보이는 모습의 녹화가 아니다.
- 로컬 실행을 유지한다. SafeOps 운영망, AWS, Laravel, 외부 AI, Neckband는 추가하지 않는다.

## 이번에 마친 것

1. 기존 위치 분석 결과에 등록 마커의 네 모서리 픽셀 좌표를 보존했다.
   중복 ID는 사용하지 않으며 비정상 좌표를 기록하지 않는다. 검출을 한 번 더 수행하지 않는다.
2. `presentation_diagnostics`에 `detected_corners_px`, `image_size`, 카메라와 작업대
   프로필 SHA-256을 추가했다. 기존 frame ID, 마커 ID, 거부 원인, 지연 정보와 같이 남는다.
3. `server/realtime/tracking_report.py`를 추가했다. 구간별 상태, 위치 거부 원인,
   마커 조합, 시간 통계와 누락 자료 수를 계산한다. 선택적으로 검출 숫자부터 pose를 재계산한다.
   사진에서 마커를 다시 찾거나 보정값을 생성하는 도구는 아니다.
4. 숫자 재계산은 당시 두 프로필의 해시가 일치해야 한다. 다른 보정으로 원인을 비교했다고
   잘못 결론 내리지 않도록 불일치 시 실패한다. 중복/역순 프레임과 진단 frame ID 혼합도 거부한다.
5. 실제 저장 사진에서 얻은 숫자 fixture와 합성 데이터로 기록 -> 읽기 -> pose 재계산을 검사했다.
   카메라 접근을 금지한 테스트이며 사진/영상 저장 없이 정상/퇴화 조합을 구분한다.
6. 기본 실행 경로에서 없던 YOLO 모델을 원 저장소의 같은 파일로 복구했다.
   지난 시연 메타데이터와 SHA-256이 일치함을 확인했다. 학습이나 모델 교체는 하지 않았다.

수정 경계: `workspace_live_preview.py`, `presentation_bridge.py`, 새 `tracking_report.py`와
관련 테스트/문서다. 상태 임계값, 표시 유효 시간 150ms, pose 품질 조건, solver,
눈별 보정 프로필은 이번 작업에서 바꾸지 않았다.

모델은 기존에 Git에서 제외된 로컬 산출물이다. 복제한 다른 PC에는 별도 준비가 필요하다.
`models/yolo/driver_standard_model/best-3.pt`, 19,179,866 bytes,
SHA-256 `a69070553f50eb124896f237107db9ff5653b19d0f1869fd5e01573ccbb34efe`.

## 남는 로그

실행별 `outputs/realtime_sessions/<session>/`의 기존 결과/상태 로그에 숫자 진단이 추가된다.
숫자 진단은 presentation 경로를 실행할 때만 생긴다. 일반 상태 서버만 실행하면 없다.
카메라 사진 저장을 켜지 않아도 남으며 이번에는 사진 저장을 켜지 않았다.
현재 작업 폴더는 OneDrive 안이므로 숫자 로그도 사용자 동기화 설정의 영향을 받을 수 있다.

- 과거 로그에 없던 마커 ID나 모서리를 새 도구로 복구할 수는 없다.
- 숫자 재생 가능 수에는 비어 있거나 누락된 검출 자료를 포함하지 않는다.
- 위치 추적 비율은 서버의 pose 계산 결과다. Unity 표시율이나 눈별 정합 정확도가 아니다.
- 상태 재생은 당시 feature 입력으로 필터 결과를 재현한다. 인식의 정답 정확도 평가는 아니다.
- 현재 CLI 출력 파일은 새 파일만 만들며 기존 결과를 덮어쓰지 않는다.

프로젝트 루트에서 사용하는 예:

```powershell
$Python = "$env:USERPROFILE/AppData/Local/ARAssembly/beast-mvp/.venv/Scripts/python.exe"
& ./scripts/run_beast_harness.ps1 -Mode doctor
& $Python -X utf8 -B -m server.realtime.realtime_replay --session outputs/realtime_sessions/<session> --validate-filter
& $Python -X utf8 -B -m server.realtime.tracking_report --session outputs/realtime_sessions/<session> --output outputs/<new-report-name>.json
```

`<session>`과 출력 파일명은 실제 값으로 바꾼다. 일부 구간만 볼 때는
`--first-frame 12269 --last-frame 12467`처럼 지정한다. 숫자 pose 재생은 위 report 명령에
`--camera-profile <당시-camera.json> --workspace-profile <당시-workspace.json>`을 함께 추가한다.
당시 파일은 덮어쓰지 않고 유지해야 한다. 이 명령들은 카메라나 Beast 화면을 켜지 않는다.

## 확인한 결과

- Python realtime 전체: **408 passed**.
- C# NUnitLite: **208 passed**. 웹 Node: **21 passed**.
- Unity Editor의 실제 loopback HTTP/JSON/cancel 검사: **46 checks 통과**.
  `outputs/unity_p1/offline-readiness-smoke-20261007.log`.
- Windows Player 빌드 성공: `outputs/unity_p1/build-20261007-132232-915.log`.
  Unity 로그에는 라이선스/그래픽 초기화 경고가 있으나 위 smoke와 빌드는 성공 종료했다.
- 관제 Playwright: S0~S6/안내 상태, 영상 기본 OFF/유실/정지/늦은 응답,
  데스크톱과 모바일 위치 보류 이유 16개 조합 통과. 페이지 오류 없음.
  `outputs/supervisor_r6/`, `outputs/supervisor_visual_feedback/`, `outputs/supervisor_pose/`.
- 합성 이미지 1장으로 로컬 YOLO 모델 추론 성공, 검출 0개.
  실제 드라이버 검출 성능이나 실시간 추론 지연을 평가한 것은 아니다.
- 실제 서버 진입점을 dummy 입력으로 30프레임 실행 후 정상 종료했다.
  카메라 API를 금지한 상태이며 `source=dummy`, S0 유지, 마커 LOST는 예상 결과다.
  세션: `viture_aruco_rt_20261007_132047_e03696d8362e`.
- 지난 실입력 세션 `viture_aruco_rt_20261006_215103_9c13d797a2da`의
  **13,068프레임** 상태 필터 재생이 기록 결과와 일치했다.

마지막 착용 구간 12269~12467의 199프레임도 다시 요약했다:
tracking 163, pose 품질 거부 21, 마커 부족 15. 서버 추적 비율은 약 81.91%다.
이 수치는 새 착용 결과가 아니라 이전 자료의 재집계다. 당시 숫자 검출 자료는 없으므로
그 21개 원인을 전부 마커 배치 문제라고 확정하지 않는다.
`outputs/tracking_offline_20261007/last-worn-baseline-v2.json`에 결과가 있다.

## 이후 순서와 완료 조건

| 순서 | 최소 작업 | 완료를 판단할 증거 |
| --- | --- | --- |
| 1. 현재 소프트웨어 기준선 | 기본 실행, 상태 재생, UI 회귀, 빌드 | 위 검사 완료. 실기기 성능 완료로 해석하지 않음 |
| 2. 편한 자세의 추적 연속성 | 다음 착용 때 정면/작은 좌우 이동의 짧은 숫자 로그 수집, Unity 가시성 로그와 구분해 분석 | 마커 부족/기하 퇴화/품질 거부/지연을 실제 실패 프레임으로 재현하고 수정 전후 비교 |
| 3. A 원 정합 | 기존 설정을 고정하고 보정에 쓰지 않은 자세·거리에서 A 확인 | 단안 위치 오차, 양안 깊이·편안함, 고개 이동 시 오차를 실측. 다른 착용자는 별도 검증 |
| 4. 실제 단계 전이 | A~D 접근, 충분한 관측, 유효한 이탈을 순서대로 검사 | 손 스침에는 유지, 돌리는 중에는 유지, 미검출/마커 유실만으로 전이하지 않음 |
| 5. 단계별 공간 안내 | 2·3 통과 후 기존 target에 따른 원/화살표부터 연결 | 표시 대상이 현재 지시와 일치하고 추적 불가 시 숨김. A 고정 참조 시험과 구분 |
| 6. 반복 시연 | Unity와 관제를 켜고 독립 조립 3회 이상 및 가림/재연결 사례 기록 | 조기 전이·지연·표시율·정합 오차를 따로 보고, 실패와 한계까지 재현 가능하게 정리 |

정합이 불편한 상태에서 표시 유효 시간을 늘리거나 거부 조건을 풀어 원을 계속 보이게 만들지는 않는다.
목표 화살표 다음에 나사 윗면 연결선을 검토한다. 알려준 11cm 크기와 6cm 높이만으로
상자 외곽 전체 치수를 확정하지 않으며, 직육면체 외곽선은 필요한 치수와 정합 범위를 확인한 뒤 확장한다.
먼저 물체 하나, 고정된 작업대, 검증한 자세·거리 범위에서 반복 가능한 시연을 완성한다.

## 이번에 하지 않은 것

카메라 재촬영, Beast Player 실행, 새 눈별 보정, 자동 A~D 광학 오버레이,
원격 관제 배포, 유료 인프라, Git 커밋/푸시는 하지 않았다.
테스트용 로컬 서버와 Unity batch 검사도 종료했다.
다음 단계의 핵심 제약은 UI 코드 양이 아니라 실제 착용 상태에서의 추적과 정합 증거다.

## 양안 보정 후속 보강

2026-10-07 후속 작업에서 같은 카메라 관측에 좌우 화면 좌표를 저장하는 양안 수집과
거리별 독립 검증 보고서를 추가했다. 현재 정합이 검증됐다는 의미는 아니다.
최신 변경·검사 결과·다음 착용 순서는
[양안 보정 수집 보강](beast_paired_calibration_20261007.md)을 따른다.
