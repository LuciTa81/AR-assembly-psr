# Beast P0 하네스 진행 기록

작성일: 2026-09-26
최종 검증: 2026-09-27

## 현재 상태

P0 코드 보강과 실제 저장 영상 실행을 검증했습니다. **OpenCV 차단은 사용자가
Smart App Control을 끈 뒤 해소됐으며, 전체 테스트 59개가 통과했습니다.**
Beast 연결 후 실제 카메라 150프레임(약 15초) 실행과 입력 로그 재생도 검증했습니다.
P0 실행 기준선은 확보했으나, 추적 안정성과 실제 눈에 보이는 정합은 아직 미검증입니다.
Unity/정합/원격 서버는 이번 범위가 아닙니다.
커밋, 푸시, 에이전트의 보안 설정 변경, 외부 영상 업로드는 하지 않았습니다.
카메라 점검의 미리보기 2장은 로컬에 저장했으며, 실시간 검사 중 연속 영상은 저장하지 않았습니다.

## 적용 내용

- `scripts/run_beast_harness.ps1`: doctor / replay / live-local 실행기.
- `harness_check.py`: 필요한 의존성과 파일을 시작 전에 확인합니다.
  라이브러리 설치 여부뿐 아니라 실제 import 실패도 표시합니다.
- YOLO 결과에 원본 시각/세션/마커 유효성을 보존합니다. 만료 초깃값은 800 ms입니다.
- 캐시된 같은 결과를 확인 횟수나 dwell에 중복 반영하지 않습니다.
  마커 유실 또는 만료에는 미확정 후보만 초기화하고 확정 상태는 유지합니다.
- 한 실행은 한 세션이며 영상 재생은 EOF에서 끝납니다.
  원본 frame ID/시각을 별도 필드에 보존합니다.
- `results.jsonl.filter_input`에 실제 입력을 반올림 없이 기록합니다.
  전이는 결과/이벤트를 flush/fsync한 뒤 게시하고 저장 실패 시 중단합니다.
- 기존 세션을 덮어쓰지 않으며 설정, 모델 SHA-256, 코드 revision을 기록합니다.
  아직 커밋되지 않은 변경이 있으므로 revision만으로 현재 소스 전체가 보존되지는 않습니다.

인식 가중치와 점수 임계값은 변경하지 않았습니다. 다만 기존 프레임 단위 dwell은
YOLO가 필요한 단계에서 **새 유효 관측 수**로 집계되므로 실제 전이 시간은 재시험해야 합니다.
연속 시간 기반 dwell 및 도구 이탈 후 다음 안내는 P3에서 다룹니다.

## 실행

작업 위치는 `.worktrees/viture-beast-overlay-mvp`입니다.
실행기는 다른 작업 디렉터리에서도 동작하며 상대 설정/세션 경로는 저장소 기준입니다.

```powershell
# 카메라/GPU 없이 제공된 상태 입력 fixture 검증
.\scripts\run_beast_harness.ps1 -Mode replay -ValidateFilter -Session tests/realtime/fixtures/filter_session

# 같은 fixture의 준비 검사
.\scripts\run_beast_harness.ps1 -Mode doctor -ValidateFilter -Session tests/realtime/fixtures/filter_session

# 영상 실행 준비 검사. 가중치 경로는 실제 존재하는 파일을 명시합니다.
.\scripts\run_beast_harness.ps1 -Mode doctor -Weights "<best-3.pt 절대 경로>"

# 아래는 OpenCV import와 카메라 장치 확인 후에만 실행합니다.
.\scripts\run_beast_harness.ps1 -Mode live-local -Weights "<best-3.pt 절대 경로>"
```

Python 기본 경로는 `%LOCALAPPDATA%\ARAssembly\beast-mvp\.venv\Scripts\python.exe`입니다.
Codex 앱의 경로 리디렉션으로 실제 생성 위치가 다음 경로로 보고되었습니다.
일반 터미널에서 기본 경로가 없으면 `-PythonExe`로 이 경로를 명시합니다.

```text
C:\Users\fresh\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\ARAssembly\beast-mvp\.venv\Scripts\python.exe
```

현재 가중치는 main checkout의
`models/yolo/driver_standard_model/best-3.pt`를 명시해 참조했습니다.
worktree에 자동 복사하거나 다른 모델을 내려받지 않았습니다.
이미지 없는 과거 로그는 영상 재생 대상이 아니며, `filter_input`이 없는 과거 로그는
기존 조회 기능만 지원합니다. Feature 재생은 저장된 필터 입력을 재현할 뿐,
비동기 GPU 실행 순서나 실제 조립 인식 정확도를 보장하지 않습니다.

## 차단 당시 확인 결과 (이력)

- 기존 requirements-dev.txt 설치 완료. 패키지 목록은 로컬 실행 증거에 보관합니다.
- 선택 검사: 49 passed, 3 skipped.
  명령: `python -X utf8 -B -m pytest tests/realtime --ignore=tests/realtime/test_probe_cameras.py -q`.
- 기존 장치 진단 unittest: discovery 방식으로 8개 통과. 위 49개에도 포함됩니다.
- fixture CLI: `matched=true, frames=6, scope=exact_filter_inputs_only`.
- `compileall` 및 `git diff --check` 통과.
- 전체 `pytest -q`: OpenCV 차단으로 아래 두 파일 수집 오류.
  `server/vision/test_warp_single_image.py`, `tests/realtime/test_probe_cameras.py`.
- 생략한 3개: 실제 OpenCV 카메라 미개방 검사, 이미지 유한 재생,
  손상 이미지 오류 검사. 통과로 계산하지 않았습니다.

Windows CodeIntegrity 로그의 3077/3118 이벤트에서 `cv2.pyd`가 서명/코드 무결성
정책에 의해 거부된 것을 확인했습니다. Ultralytics도 cv2를 가져오므로 함께 실패합니다.
이는 Python 패키지 미설치와 다른 문제입니다. 보안 설정을 끄거나 우회하지 않았습니다.

### OpenCV 차단 추가 진단 (2026-09-27)

- 사용자 확인: 학교/회사 관리 PC가 아닌 개인 개발용 PC입니다.
- 설치된 `cv2.pyd`는 PyPI의 공식
  `opencv_contrib_python-5.0.0.93-cp37-abi3-win_amd64.whl` 안의 파일과
  SHA-256이 일치합니다. 내려받은 wheel 자체도 PyPI에 게시된 SHA-256과 일치합니다.
  이는 배포 파일과의 동일성 확인이며 모든 취약점이 없다는 보장은 아닙니다.
- 해당 바이너리의 Authenticode 상태는 `NotSigned`입니다.
  공식 배포본과 일치하는 것과 Windows가 실행을 신뢰하는 것은 별개입니다.
- 기존 `.venv_rt`에는 `opencv-contrib-python==4.13.0.92`가 있었으나,
  새 requirements 설치에는 버전 제한이 없어 `5.0.0.93`이 선택됐습니다.
  새 환경에는 `opencv-python`과 `opencv-contrib-python`이 함께 설치돼 있습니다.
  OpenCV 공식 안내는 같은 `cv2` 네임스페이스를 사용하는 배포 패키지 중 하나만
  설치하도록 요구합니다. 이 구성 문제는 보안 차단과 구분해서 정리해야 합니다.
- 이번 추가 진단에서는 패키지 교체나 보안 설정 변경을 하지 않았습니다.
  Smart App Control은 개별 앱 예외를 지원하지 않으므로, PC 전체 보호를 줄이는
  설정 변경은 사용자에게 영향을 설명하고 별도 선택을 요청했습니다.
  재활성화 가능 여부는 설치된 Windows의 실제 설정 안내를 확인해야 합니다.

```text
Official wheel SHA-256:
461622db95c964652d4d8fda171034961c3de270f78a6095aaad31050771774a
Official and installed cv2.pyd SHA-256:
ae833b9b5771f5932200bd3b8ad0f483f4fbec92cbdbd26d21d38fe524c60e66
```

참고: [Microsoft Smart App Control FAQ](https://support.microsoft.com/en-us/windows/security/threat-malware-protection/smart-app-control-frequently-asked-questions),
[OpenCV 패키지 설치 안내](https://pypi.org/project/opencv-python/).

### 해결 및 실제 영상 검증 (2026-09-27)

- 사용자가 Smart App Control을 직접 껐다고 확인한 뒤,
  `VerifiedAndReputablePolicyState=0`과 기존 OpenCV 5.0의 정상 import를 확인했습니다.
  패키지 교체 이전에 차단이 해소됐으므로 보안 정책이 직접 원인이었음을 분리해 확인했습니다.
- 실시간 전용 환경의 두 OpenCV 패키지를 제거하고
  `opencv-python==4.14.0.94` 하나로 requirements를 고정했습니다.
  ArUco는 이 버전의 main 패키지에 포함되며 Ultralytics의 의존성도 충족합니다.
  기존 1학기 `.venv_rt`와 `server/requirements.txt`는 변경하지 않았습니다.
  두 환경의 requirements를 같은 가상환경에 혼합 설치하지 않습니다.
- `pip check`: `No broken requirements found`.
  OpenCV/ArUco/Ultralytics import 성공, 정상 doctor는 `ready=true`.
  없는 weights 경로는 `ready=false`, 종료 코드 1로 거부됐습니다.
- 실제 템플릿의 한글 절대 경로에서 `cv2.imread` 실패를 재현하고,
  세션 프레임 로더와 동일하게 bytes + `cv2.imdecode` 방식으로 수정했습니다.
  한글 경로/빈 파일/손상 파일 회귀 검사 3개를 추가했습니다.
- 구형 Quest CSV의 `timestamp_unix_ms`도 원본 촬영 시각으로 보존합니다.
  기존 `timestamp_ms` 형식과 함께 회귀 검사했습니다.
- 최종 전체 검사: `python -X utf8 -B -m pytest -q --tb=short -rs`.
  **59 passed, 실패/생략/수집 오류 없음**.
- `raw_sessions_keep_for_future/Yolo_session/session_37`의 실제 JPG 119개를
  ArUco/ROI/YOLO/상태 필터 경로로 처리하고 EOF에서 정상 종료했습니다.
  최종 로그: `outputs/realtime_sessions/viture_aruco_rt_20260927_002954_579e4cd15288`.
  원본 frame ID와 촬영 시각을 입력 CSV와 119개 모두 대조해 일치를 확인했습니다.
- 해당 실행에서 marker_ok 93/119, ROI 처리 119/119, 유효 YOLO 결과 66/119를
  확인했습니다. 상태는 S0 -> S1 -> S2였습니다. 이 수치는 실행 진단이며
  정답 대비 인식 정확도나 S3-S6 체결 성능을 의미하지 않습니다.
- 직전 전체 실행에서 `/state.json`과 `/frame.jpg`의 실제 HTTP 응답을 확인했습니다.
  영상 응답은 HTTP 200, image/jpeg, 62,168 bytes였습니다.
  재생 종료 후 서버가 닫혔으며 상시 서버를 남기지 않았습니다.
- 최종 실행 로그의 필터 재생: `matched=true, frames=119,
  scope=exact_filter_inputs_only`. 비동기 YOLO 추론 순서까지 동일함을 뜻하지 않습니다.
- 장치 점검에서는 Beast 카메라/제어 장치/모니터가 발견되지 않았습니다.
  노트북 카메라를 Beast로 대신 간주하거나 실카메라 캡처를 실행하지 않았습니다.
- 방화벽 Domain/Private/Public은 모두 켜져 있습니다. Defender는 `Not running`,
  McAfee가 백신 공급자로 등록돼 있고 McAfee Framework Host는 실행 중입니다.
  이것만으로 McAfee의 실시간 보호 상태까지 확정할 수는 없습니다.
  백신 활성 상태는 사용자가 Windows 보안의 바이러스 및 위협 방지에서 확인해야 합니다.
  에이전트는 백신/방화벽 설정을 변경하지 않았습니다.

로컬 검사 로그는 `outputs/harness_p0/opencv-repair-*.log`, 장치 목록은
`outputs/harness_p0/beast-device-after-opencv.json`에 보관합니다.

### Beast 연결 및 실카메라 검사 (2026-09-27 14:06 KST)

- 연결 후 `USB VID_0C45&PID_6368` 카메라와 `Generic Monitor (VITURE Beast)`가
  Windows에서 Status OK로 감지됐습니다. 디스플레이 열거 성공은 착용 표시/정합 성공과 다릅니다.
- DirectShow index 0/1의 미리보기를 대조했습니다. 0은 노트북 카메라 시점,
  1은 책과 노트가 있는 책상 시점이었습니다. 사용자가 Beast를 착용하고 작업대를
  보고 있다고 확인한 뒤 기존 설정의 index 1로 마커/작업대 인식을 확인했습니다.
  연결 순서가 바뀌면 이 번호는 다시 확인해야 합니다.
- 캡처 해상도는 요청/실제 모두 1280x720입니다. 첫 2초 단독 probe의 index 1은
  13프레임, 6.489 FPS, 읽기 실패 0회였습니다. 아래 전체 실행 속도와 구분합니다.
- 기존 `live-local` 경로를 `-MaxFrames 150`으로 실행해 정상 종료했습니다.
  세션: `viture_aruco_rt_20260927_140643_ac8c8ecc6380`.
  첫/마지막 프레임 로컬 시각 차이는 14.911초, 첫 FPS 표본을 제외한
  루프 FPS 중앙값은 10.379입니다. 센서 노출부터 안경 표시까지의 지연은 측정하지 않았습니다.
- 유효 마커 54/150프레임, 최대 검출 5개, 이전 homography fallback 12프레임,
  homography 없음 84프레임이었습니다. ROI 처리 66프레임, 유효 YOLO 결과 43프레임.
  상태는 S0 -> S1로 전이했고 마커 유실 구간에서는 S1을 유지했습니다.
  조립 수행/정답 대조 시험이 아니므로 단계 인식 정확도를 주장하지 않습니다.
- 이 실카메라 실행의 입력 로그 재생은 `matched=true, frames=150,
  scope=exact_filter_inputs_only`입니다. `save_frames=false`였으므로 이 세션 자체의
  원본 영상 재추론은 불가능하며, 상태 필터 입력 재생만 가능합니다.
- 작업대 확인 프레임을 HTTP로 가져오는 시도는 자동 종료 후 연결 거부로 실패했습니다.
  실제 저장된 이미지는 최초 카메라 probe의 미리보기 2장뿐입니다.
  실행 프로세스와 로컬 서버는 종료됐습니다.
- 제어용 `USB VID_35CA&PID_1102&MI_02` 인터페이스에는 Code 10이 있습니다.
  카메라/모니터의 상태는 OK였고 캡처는 가능했습니다. 장치 제어에 미치는 영향은
  미확인으로 남기며 P1의 표시 모드 점검 전에 다시 확인합니다. 드라이버를 변경하지 않았습니다.

증거: `outputs/harness_p0/beast-device-connected-20260927.json`,
`outputs/harness_p0/beast_capture_20260927/camera_probe_dshow.csv`,
`outputs/harness_p0/beast-live-20260927.log`, 위 실시간 세션 디렉터리.

## 다음 순서

독립 리뷰의 중요 지적 1건(영상 없는 폴더도 ready로 판정)을 회귀 검사 4개와 함께
수정했습니다. 경미한 보류 항목은 이벤트 CSV의 confidence가 표시용 반올림 값이라는
점입니다. 원정밀도 filter_input/results 및 재생 결과에는 영향이 없어 이번 범위에서는
변경하지 않았습니다. 실제 템플릿 로드와 이미지 경로 호환성은 이번 영상 실행에서
수정 및 검증했습니다.

1. P1: Unity Windows Scene 하나로 시험 원/문구 출력, 표시 모드와 수신 중단 처리.
   제어 인터페이스 Code 10의 영향도 이 단계에서 확인합니다.
2. P2: 실제 치수/카메라/착용자 보정 및 별도 검증점의 정합 오차 측정.
3. P3: 자동 상태 인식과 안내 연결, 도구 이탈 확인.
4. P4: 최소 원격 YOLO 및 관제 페이지. P5: 실제 조립 시연 평가.

서버 임대나 AWS 설정은 지금 필요하지 않습니다.
