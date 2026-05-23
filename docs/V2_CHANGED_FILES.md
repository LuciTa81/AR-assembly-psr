# v2 변경 파일 요약

## 추가된 파일

### server/tools/generate_aruco_markers_plain_6.py
글자 없이 ID 0~5 ArUco marker PNG를 생성합니다.

### configs/marker_layout_v2.yaml
6개 ArUco 배치 template입니다. 실제 실행 시에는 calibration으로 session별 layout을 생성합니다.

### server/vision/calibrate_marker_layout_v2.py
6개 마커가 모두 보이는 기준 프레임을 이용해 실제 배치 기반 calibrated marker layout을 생성합니다.

### server/vision/warp_session_v2.py
6개 마커 corner 전체와 RANSAC homography를 이용해 800x600 warped image를 생성합니다.
`homography_valid`, `homography_usable`, `marker_count`, `warp_quality`를 저장합니다.

### server/vision/build_yolo_features.py
YOLO driver bbox를 warped 좌표계로 변환하고 `tool_near_a/b/c/d`를 생성합니다.
이번 버전에서는 `chosen_screw` one-hot만 쓰지 않고, threshold 안에 들어온 모든 나사를 near=1로 만드는 multi-hot 방식을 지원합니다.
`--distance-mode polygon|center|tip` 옵션을 지원합니다.

### server/vision/mediapipe_extract_v2.py
MediaPipe Hands 결과를 frame당 최대 2개 손까지 저장합니다.

### server/vision/build_mediapipe_features_hybrid.py
YOLO driver bbox와 가까운 손을 작업손으로 선택하고, 선택된 index finger를 warped 좌표계로 변환합니다.
`--swap-handedness`, `--disable-handedness-fallback` 옵션을 지원합니다.

### server/state/build_hmm_input_v2.py
homography, ROI, YOLO, MediaPipe, GT label을 병합하여 HMM v2 입력 CSV를 생성합니다.
`smooth`, `cumulative seen`, `effective ROI score`를 함께 만듭니다.

### server/state/run_state_baseline_v2.py
Framewise, FSM, HMM v2를 실행하고 metrics 및 timeline plot을 생성합니다.
YOLO tool_near는 완료 상태가 아니라 state transition trigger로 사용합니다.

### scripts/setup_env_v2.ps1
v2용 Python 환경 설치 스크립트입니다.

### scripts/check_package_v2.ps1
v2 필수 파일과 session/model 존재 여부를 점검합니다.

### scripts/run_session_pipeline_v2.ps1
session 하나를 입력으로 받아 calibration부터 HMM v2 평가까지 한 번에 실행합니다.

### scripts/run_hmm_v2_only.ps1
이미 생성된 hmm_input_v2.csv에 대해 HMM 파라미터만 바꿔 재실행합니다.

## 기존 파일 중 그대로 유지

- server/vision/roi_cropper.py
- server/vision/roi_features.py
- server/vision/yolo_infer_session.py
- server/state/build_hmm_input_min.py
- server/state/run_state_baseline.py
- scripts/run_session_pipeline_min.ps1

## 주의

- `configs/roi_layout_v2.yaml`은 실제 session의 warped 이미지 기준으로 다시 맞춰야 합니다.
- `refs/roi_templates_v2`는 session_17처럼 안정화된 warped crop에서 새로 뽑는 것을 권장합니다.
- 물리적으로 마커 위치를 바꾸면 calibrated marker layout을 다시 생성해야 합니다.
