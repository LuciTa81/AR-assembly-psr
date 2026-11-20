# AR Assembly PSR 프로젝트 인수인계 문서

> 이 문서는 **AR 기반 산업용 인클로저 조립 단계 인식(Procedure Step Recognition, PSR) 및 작업 안내 시스템**을 다른 채팅이나 다른 작업자에게 그대로 인수인계하기 위한 문서입니다.  
---

## 1. 프로젝트 배경

본 프로젝트의 목적은 **산업용 인클로저 조립 작업에서 현재 작업자가 어느 조립 단계에 있는지를 카메라 영상으로 자동 추정하고, 향후 AR 기기에서 다음 작업을 안내하는 시스템**을 구현하는 것입니다.

초기 목표는 다음과 같았습니다.

```text
Quest 3 또는 AR 카메라에서 작업 영상을 입력받음
↓
작업대 기준 좌표계로 정렬
↓
상자, 뚜껑, 나사, 도구, 손 위치를 관측
↓
현재 조립 상태를 S0~S6으로 추론
↓
AR 화면에 현재 단계와 다음 작업 안내 표시
```

이 프로젝트는 일반적인 이미지 분류가 아니라, **조립 순서가 정해진 절차형 작업에서 시간에 따라 상태가 진행되는 문제**입니다. 따라서 단일 프레임만 보고 판단하는 것보다, 관측값의 흐름과 상태 전이 순서를 함께 고려하는 방식이 필요했습니다.

---

## 2. 문제 정의

### 2.1 작업 대상

현재 실험 대상은 다음으로 고정했습니다.

```text
대상 물체: 시판 산업용 인클로저 박스
작업 구성: 박스 배치 → 뚜껑 닫기 → A/B/C/D 나사 체결
도구: 드라이버
촬영 환경: 고정 작업 매트 + ArUco marker + Quest/카메라 프레임
```

### 2.2 상태 정의

현재 HMM에서 사용하는 상태는 총 7개입니다.

```text
S0 = initial / 초기 상태
S1 = box placed / 박스 배치
S2 = lid closed / 뚜껑 닫힘
S3 = screw A done / A 나사 완료
S4 = screw B done / B 나사 완료
S5 = screw C done / C 나사 완료
S6 = screw D done / D 나사 완료
```

상태 전이는 왼쪽에서 오른쪽으로만 진행됩니다.

```text
S0 → S1 → S2 → S3 → S4 → S5 → S6
```

역방향 전이는 허용하지 않습니다.

---

## 3. 현재 기준 프로젝트 폴더

현재 기준 폴더는 다음입니다.

```powershell
C:\Users\user\Desktop\Vision-assembly-psr-v2-package
```

예전 `AR-assembly-psr`는 삭제했고, 현재는 `Vision-assembly-psr-v2-package`를 기준 프로젝트로 사용합니다.

---

## 4. 현재 공식 기준 설정

현재 실험 기준은 다음으로 고정합니다.

```text
세션: session_17
프레임 수: 119장
마커: 6개 ArUco marker, DICT_4X4_50
YOLO 모델: models/yolo/driver_standard_model/best.pt
YOLO distance mode: polygon
YOLO near threshold: 100
ROI crop layout: configs/roi_layout_v2.yaml
YOLO/MediaPipe association layout: configs/roi_layout_v2_assoc_active.yaml
association 기준: screw 기준점을 y 방향 -120px, 즉 위쪽으로 120px 이동
MediaPipe: swapLR 적용 가능, 하지만 현재 HMM에서는 index_weight=0.0
HMM: Viterbi 기반 left-to-right sequence inference
```

중요한 점은 **ROI crop용 layout과 YOLO/MediaPipe near 판정용 layout을 분리**했다는 것입니다.

```text
configs/roi_layout_v2.yaml
→ ROI crop / ROI feature용

configs/roi_layout_v2_assoc_active.yaml
→ YOLO tool_near / MediaPipe index_near 계산용
→ 실제 screw 위치보다 위로 120px 이동한 기준
```

`roi_layout_v2.yaml`을 up120으로 직접 덮어쓰면 안 됩니다.

---

## 5. 전체 파이프라인 개요

현재 전체 파이프라인은 다음 순서로 동작합니다.

```text
원본 frame
↓
6개 ArUco marker 검출
↓
workspace homography 계산
↓
warped top-view frame 생성
↓
ROI crop / ROI feature 생성
↓
YOLO driver detection 생성
↓
YOLO bbox를 homography로 warped 좌표에 투영
↓
tool_near_a/b/c/d 생성
↓
MediaPipe hand landmark 추출
↓
hand/index point를 warped 좌표에 투영
↓
index_near_a/b/c/d 생성
↓
hmm_input_v2.csv로 병합
↓
Framewise / FSM / HMM 실행
↓
state timeline 및 metrics 생성
```

---

## 6. 주요 코드 파일과 역할

### 6.1 scripts

```text
scripts/setup_env_v2.ps1
```

Python 가상환경 설치용입니다.

```text
scripts/check_package_v2.ps1
```

필수 파일과 세션 구조 확인용입니다.

```text
scripts/run_session_pipeline_v2_safe.ps1
```

현재 가장 중요한 실행 스크립트입니다. 전체 pipeline을 실행하고, 각 Python 단계가 실패하면 즉시 중단하도록 `$LASTEXITCODE`를 검사해야 합니다.

```text
scripts/run_hmm_v2_only.ps1
```

이미 `hmm_input_v2.csv`가 있을 때 HMM만 다시 돌리기 위한 스크립트입니다.

---

### 6.2 server/vision

```text
server/vision/calibrate_marker_layout_v2.py
```

6개 ArUco marker를 기준으로 session별 marker layout을 생성합니다.

```text
server/vision/warp_session_v2.py
```

ArUco marker와 marker layout을 사용해 원본 frame을 800x600 top-view workspace로 warp합니다. `homography_v2.csv`와 debug marker image를 저장합니다.

```text
server/vision/roi_cropper.py
```

warped image에서 ROI crop을 생성합니다. `--edit` 모드로 `enclosure`, `lid`, `base_front`, `inner_area`, `screw_a`~`screw_d` 영역을 직접 지정할 수 있습니다.

```text
server/vision/roi_features.py
```

ROI crop과 `refs/roi_templates_v2` reference crop을 비교해 `lid_closed_score`, `screw_a_done_score` 등의 ROI score를 생성합니다.

```text
server/vision/plot_roi_features.py
```

ROI feature timeline, heatmap, state별 분포, contact sheet 이미지를 생성하는 시각화 도구입니다.

```text
server/vision/yolo_infer_session.py
```

원본 frame에서 YOLO driver detection을 수행하고 `outputs/yolo/session_17_yolo_raw.csv`를 생성합니다.

```text
server/vision/build_yolo_features.py
```

YOLO bbox를 homography로 warped 좌표계에 투영하고, screw 기준점과의 거리를 계산해 `tool_near_a/b/c/d`를 생성합니다. 현재 공식 distance mode는 `polygon`입니다.

```text
server/vision/mediapipe_extract_v2.py
```

원본 frame에서 MediaPipe Hands를 실행하고 frame당 최대 2손의 landmark를 저장합니다.

```text
server/vision/build_mediapipe_features_hybrid.py
```

YOLO driver bbox와 가까운 손을 선택하고, 선택된 손의 index fingertip을 warped 좌표계로 투영해 `index_near_a/b/c/d`를 생성합니다.

```text
server/vision/make_detection_overlays.py
```

원본/warped 이미지에 ArUco, MediaPipe, YOLO overlay를 그려 발표 및 디버그용 이미지를 생성합니다. `--swap-handedness` 옵션으로 MediaPipe Left/Right 표시를 바꿀 수 있습니다.

---

### 6.3 server/state

```text
server/state/build_hmm_input_v2.py
```

homography, ROI, YOLO, MediaPipe, labels를 병합해 `hmm_input_v2.csv`를 생성합니다. 여기에서 smoothing feature도 만들어집니다.

중요 정책:

```text
labels_segments.csv에 현재 session_id가 없으면 gt_state = UNKNOWN
다른 session의 label을 fallback으로 쓰면 안 됨
```

```text
server/state/run_state_baseline_v2.py
```

`hmm_input_v2.csv`를 읽어 Framewise_v2, FSM_v2, HMM_v2를 실행합니다. HMM은 left-to-right 전이 제약과 Viterbi algorithm으로 전체 상태 sequence를 추론합니다.

---

## 7. 데이터 구조

세션 폴더는 다음 구조를 사용합니다.

```text
data/raw_sessions/session_17/
├─ frames.csv
└─ frames/
   ├─ 000001.jpg
   ├─ 000002.jpg
   ├─ ...
   └─ 000119.jpg
```

`frames.csv`는 각 frame의 `frame_id`, `image_path` 등을 포함합니다.

새 세션을 만들 때도 같은 구조를 유지해야 합니다.

---

## 8. ArUco / Homography

초기에는 4개 marker 기반으로 진행했지만, 손과 도구가 marker를 가리는 경우가 많아 homography가 흔들렸습니다. 이후 6개 marker로 바꾸었습니다.

```text
ID 0, 1, 2 = 상단 marker
ID 3, 4, 5 = 하단 marker
```

6개 marker 도입 후 일부 marker가 가려져도 RANSAC homography가 더 안정적으로 계산됩니다.

현재 relaxed rule은 다음 기준입니다.

```yaml
quality_rules:
  min_markers: 3
  min_points: 12
  require_both_rows: true
  min_column_span: 2
  ransac_reproj_threshold: 8.0
  min_inlier_ratio: 0.55
  max_reprojection_error: 12.0

fallback:
  use_previous_h: true
  max_fallback_gap: 2
```

좋은 session_17에서는 대략 다음 수준이 나왔습니다.

```text
detected_ransac: 115
previous_h_fallback: 4
invalid: 0
average warp_quality: 약 0.70
```

---

## 9. ROI feature

ROI에서 보내는 주요 feature는 다음입니다.

```csv
box_present_score
lid_closed_score
screw_a_done_score
screw_b_done_score
screw_c_done_score
screw_d_done_score
```

ROI feature는 warped image에서 crop한 영역과 reference image를 비교해 생성합니다.

reference crop은 다음 폴더에 있습니다.

```text
refs/roi_templates_v2/
```

필요 파일:

```text
lid_open.jpg
lid_closed.jpg
screw_a_empty.jpg
screw_a_done.jpg
screw_b_empty.jpg
screw_b_done.jpg
screw_c_empty.jpg
screw_c_done.jpg
screw_d_empty.jpg
screw_d_done.jpg
```

현재 판단:

```text
ROI raw score는 나사 전후 변화가 약해 주 feature로 쓰기 어렵습니다.
상자/뚜껑 판단에는 도움이 됩니다.
나사 완료 판단에는 보조 feature로 사용합니다.
```

최근 ROI를 다시 잡은 뒤에는 raw score보다 `delta_cum` 방식으로 살릴 가능성이 보였습니다.

```text
smoothing
↓
초반 20프레임 median baseline
↓
delta = max(0, score - baseline)
↓
delta_cum = cumulative max
```

이 방식은 아직 공식 HMM에 완전히 반영되지는 않았고, 다음 개선 후보입니다.

---

## 10. YOLO feature

YOLO는 현재 핵심 feature입니다.

YOLO raw detection은 원본 frame에서 수행합니다.

```text
outputs/yolo/session_17_yolo_raw.csv
```

그 후 `build_yolo_features.py`가 bbox를 warped 좌표로 투영합니다.

공식 설정:

```text
layout = configs/roi_layout_v2_assoc_active.yaml
near-threshold = 100
distance-mode = polygon
```

HMM으로 들어가는 주요 feature:

```csv
tool_visible
tool_confidence
tool_detection_count
tool_inside_workspace
tool_dist_a
tool_dist_b
tool_dist_c
tool_dist_d
tool_near_a
tool_near_b
tool_near_c
tool_near_d
chosen_screw
```

`build_hmm_input_v2.py`에서 rolling smoothing도 생성합니다.

```csv
tool_near_a_smooth
tool_near_b_smooth
tool_near_c_smooth
tool_near_d_smooth
```

HMM에서 YOLO는 전이 trigger 역할을 합니다.

```text
S2 → S3: tool_near_a_smooth
S3 → S4: tool_near_b_smooth
S4 → S5: tool_near_c_smooth
S5 → S6: tool_near_d_smooth
```

---

## 11. MediaPipe feature

MediaPipe는 손 landmark를 추출합니다. 현재 frame당 최대 2손을 저장하는 v2 흐름을 사용합니다.

raw 파일:

```text
outputs/mediapipe/session_17_mediapipe_raw_v2.csv
outputs/mediapipe/session_17_mediapipe_raw_v2_swapLR.csv
```

MediaPipe handedness가 실제와 반대로 잡히는 경향이 있어 swapLR을 적용했습니다.

MediaPipe에서 HMM으로 들어갈 수 있는 feature:

```csv
hand_visible
selected_hand_visible
selected_hand_source
selected_handedness
selected_hand_score
selected_hand_to_tool_dist
index_inside_workspace
index_x_warped
index_y_warped
index_dist_a
index_dist_b
index_dist_c
index_dist_d
index_near_a
index_near_b
index_near_c
index_near_d
```

하지만 현재 공식 HMM에서는:

```text
index_weight = 0.0
```

즉, MediaPipe는 현재 상태 추론의 핵심이 아니라 **시각화, 디버그, ablation용 보조 feature**입니다.

---

## 12. HMM 구조

HMM은 `run_state_baseline_v2.py`에서 실행합니다.

공식 실행 인자:

```text
--tool-threshold 0.4
--index-weight 0.0
--roi-weight 0.10
--self-prob 0.92
--next-prob 0.08
--min-dwell 2
```

HMM은 전체 frame sequence를 보고 Viterbi algorithm으로 가장 그럴듯한 상태 sequence를 찾습니다.

Framewise와 FSM도 같이 출력됩니다.

```text
Framewise_v2: 프레임별 observation score만 보고 판단
FSM_v2: 규칙 기반 baseline
HMM_v2: 전이확률 + observation score + Viterbi
```

FSM은 ROI threshold에 막히면 특정 상태에 갇힐 수 있어 낮은 성능이 나올 수 있습니다. HMM은 sequence 전체를 보고 판단하므로 더 안정적입니다.

---

## 13. 성능 변화 요약

초기에는 ROI 중심 feature와 불안정한 marker/warp 때문에 HMM accuracy가 약 19% 수준까지 낮았습니다.

개선 흐름:

```text
1. 4-marker / ROI 중심
   → 낮은 정확도, warp 흔들림, ROI score 약함

2. 6-marker ArUco 도입
   → homography 안정화

3. YOLO driver detection 도입
   → tool 위치 관측 가능

4. YOLO bbox를 warped 좌표로 투영
   → screw 기준 거리 계산 가능

5. polygon distance 적용
   → 길쭉한 driver bbox에 더 적합

6. association 기준점 up120 적용
   → tool_near_a/b/c/d가 실제 작업 위치와 잘 맞음

7. HMM ordered evidence 적용
   → A→B→C→D 순서 제약으로 조기 전이 방지
```

현재 성능:

```text
기존 안정화 결과: HMM accuracy 약 71%
최근 label 기준 재평가 결과: HMM accuracy 약 82% 가능성
```

단, 82%는 반드시 fresh run으로 재현 확인이 필요합니다.

---

## 14. 82% 결과에 대한 주의사항

최근 버전에서 82%가 나온 이유는 다음 두 가지가 겹쳤을 가능성이 큽니다.

```text
1. YOLO association up120으로 C/D evidence가 살아남
2. labels_segments.csv의 session_17 구간이 HMM transition 타이밍과 더 잘 맞게 수정됨
```

하지만 이전 zip 안에서는 다음 불일치가 있었습니다.

```text
outputs/hmm_v2/session_17_state_metrics_v2.csv
→ 71.4% 결과가 저장되어 있음

labels/labels_segments.csv
→ 새 구간으로 바뀌어 있음

즉, output과 label이 stale 상태로 섞여 있었을 가능성 있음
```

따라서 공식 성능으로 쓰려면 반드시 다음을 해야 합니다.

```text
1. labels_segments.csv가 실제 session_17 영상과 맞는지 눈으로 확인
2. run_session_pipeline_v2_safe.ps1에서 association layout이 사용되는지 확인
3. -Clean -RequireLabels로 fresh run
4. 그 결과로 나온 metrics만 공식값으로 사용
```

---

## 15. Label 정책

`labels_segments.csv`는 모델 입력이 아니라 평가용 정답표입니다.

추론만 할 때는 라벨이 없어도 됩니다.

```text
라벨 없음
→ gt_state = UNKNOWN
→ timeline만 확인
```

평가할 때는 해당 session_id의 라벨이 반드시 필요합니다.

```text
session_18을 평가하려면 session_18 라벨 필요
session_17 라벨을 session_18에 재사용하면 안 됨
```

중요 정책:

```text
다른 session label fallback 금지
```

---

## 16. 실행 방법

### 16.1 환경 확인

```powershell
cd "C:\Users\user\Desktop\Vision-assembly-psr-v2-package"

.\.venv_mp\Scripts\python.exe -c "import mediapipe as mp; print(mp.__version__); print(hasattr(mp, 'solutions'))"
```

정상:

```text
0.10.21
True
```

MediaPipe에서 `mediapipe has no attribute solutions`가 뜨면 Python 3.11 환경으로 다시 만들어야 합니다.

---

### 16.2 전체 pipeline 실행

```powershell
cd "C:\Users\user\Desktop\Vision-assembly-psr-v2-package"

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

.\scripts\run_session_pipeline_v2_safe.ps1 `
  -SessionId session_17 `
  -SwapHandedness `
  -YoloDistanceMode polygon `
  -YoloNearThreshold 100 `
  -Clean `
  -RequireLabels
```

---

### 16.3 결과 확인

```powershell
Get-Content outputs\hmm_v2\session_17_state_metrics_v2.csv
start outputs\hmm_v2\session_17_state_timeline_v2.png
```

---

### 16.4 HMM만 다시 실행

```powershell
.\.venv_mp\Scripts\python.exe server\state\run_state_baseline_v2.py `
  --input outputs\hmm_v2\session_17_hmm_input_v2.csv `
  --out-csv outputs\hmm_v2\session_17_state_predictions_v2.csv `
  --out-plot outputs\hmm_v2\session_17_state_timeline_v2.png `
  --out-metrics outputs\hmm_v2\session_17_state_metrics_v2.csv `
  --tool-threshold 0.4 `
  --index-weight 0.0 `
  --roi-weight 0.10 `
  --self-prob 0.92 `
  --next-prob 0.08 `
  --min-dwell 2
```

---

## 17. 새 세션 검증 방법

예를 들어 `session_18`을 새로 찍으면 폴더 구조는 다음과 같아야 합니다.

```text
data/raw_sessions/session_18/
├─ frames.csv
└─ frames/
   ├─ 000001.jpg
   ├─ 000002.jpg
   └─ ...
```

라벨 없이 추론만 먼저 실행합니다.

```powershell
.\scripts\run_session_pipeline_v2_safe.ps1 `
  -SessionId session_18 `
  -SwapHandedness `
  -YoloDistanceMode polygon `
  -YoloNearThreshold 100 `
  -Clean
```

이후 timeline이 자연스럽게 S0→S6로 가는지 확인합니다.

```powershell
start outputs\hmm_v2\session_18_state_timeline_v2.png
```

평가하려면 `labels/labels_segments.csv`에 session_18 라벨을 추가한 뒤 다시 실행합니다.

```powershell
.\scripts\run_session_pipeline_v2_safe.ps1 `
  -SessionId session_18 `
  -SwapHandedness `
  -YoloDistanceMode polygon `
  -YoloNearThreshold 100 `
  -Clean `
  -RequireLabels
```

---

## 18. 디버그 및 시각화

### 18.1 ROI feature plot

```powershell
mkdir outputs\roi_feature_plots_v2\session_17 -Force

.\.venv_mp\Scripts\python.exe server\vision\plot_roi_features.py `
  --features outputs\features_v2\session_17_roi_features_v2.csv `
  --crops-dir outputs\roi_crops_v2\session_17 `
  --hmm-input outputs\hmm_v2\session_17_hmm_input_v2.csv `
  --out-dir outputs\roi_feature_plots_v2\session_17 `
  --session-id session_17 `
  --sample-step 8 `
  --max-samples 18
```

생성 결과:

```text
session_17_roi_scores_timeline.png
session_17_roi_scores_heatmap.png
session_17_roi_scores_by_state.png
session_17_roi_crop_contact_sheet.png
```

---

### 18.2 원본/warped overlay 생성

```powershell
.\.venv_mp\Scripts\python.exe server\vision\make_detection_overlays.py `
  --session data\raw_sessions\session_17 `
  --warped-dir outputs\warped_v2\session_17 `
  --weights models\yolo\driver_standard_model\best.pt `
  --out-dir outputs\visual_debug\session_17_swapLR `
  --session-id session_17 `
  --conf 0.35 `
  --imgsz 640 `
  --limit 0 `
  --swap-handedness
```

생성 폴더:

```text
outputs/visual_debug/session_17_swapLR/original_aruco
outputs/visual_debug/session_17_swapLR/original_mediapipe
outputs/visual_debug/session_17_swapLR/original_yolo
outputs/visual_debug/session_17_swapLR/original_all
outputs/visual_debug/session_17_swapLR/warped_aruco
outputs/visual_debug/session_17_swapLR/warped_mediapipe
outputs/visual_debug/session_17_swapLR/warped_yolo
outputs/visual_debug/session_17_swapLR/warped_all
outputs/visual_debug/session_17_swapLR/compare_original_warped
outputs/visual_debug/session_17_swapLR/summary.csv
```

---

## 19. 평가 지표

### 19.1 accuracy

전체 frame 중 맞춘 frame 비율입니다.

```text
accuracy = 맞춘 frame 수 / 전체 frame 수
```

### 19.2 macro_f1

각 상태 S0~S6의 F1을 따로 계산한 뒤 평균낸 값입니다.

```text
S0 F1
S1 F1
S2 F1
S3 F1
S4 F1
S5 F1
S6 F1
↓
평균 = macro_f1
```

accuracy는 전체 frame 기준 성능이고, macro_f1은 각 상태를 골고루 잘 맞추는지 보는 지표입니다.

---

## 20. 현재 문제점 및 주의사항

1. `tip` mode는 현재 세션에서 좋지 않았으므로 사용하지 않습니다.

2. `roi_layout_v2.yaml`과 `roi_layout_v2_assoc_active.yaml`을 혼동하면 안 됩니다.

3. safe pipeline에서 YOLO/MediaPipe feature 생성 시 `roi_layout_v2_assoc_active.yaml`을 써야 합니다.

4. labels fallback은 금지해야 합니다.

5. MediaPipe swapLR은 시각화와 보조 feature에는 의미가 있지만, 현재 HMM 성능의 핵심 원인은 아닙니다.

6. 82% 결과는 반드시 fresh-run으로 재현 확인해야 합니다.

7. 새 session은 labels 없이 먼저 추론하고, 평가 시에만 해당 session 전용 labels를 작성합니다.

8. stale output이 섞이면 성능 비교가 무의미해지므로 `-Clean`을 사용합니다.

---

## 21. 현재까지의 역할분담 제안

### 담당 A: HMM / 상태추론 정교화

업무:

```text
run_state_baseline_v2.py 개선
Viterbi HMM 전이확률 튜닝
tool_threshold, self_prob, next_prob 실험
ROI delta_cum feature 추가
상태별 observation score 조정
```

산출물:

```text
state_metrics 비교표
state_timeline 비교 이미지
최종 HMM 설정값
```

---

### 담당 B: Feature 조합 / 가중치 분석

업무:

```text
hmm_input_v2.csv feature 분석
tool_near_a/b/c/d_smooth 확인
ROI raw / ROI delta / YOLO / MediaPipe ablation
association up0 / up120 비교
```

산출물:

```text
feature ablation 결과표
어떤 feature가 성능 향상에 기여했는지 정리
```

---

### 담당 C: 평가 / 시각화 / 발표 근거

업무:

```text
accuracy / macro_f1 정리
confusion matrix 작성
state timeline 정리
ROI score plot 정리
4-marker vs 6-marker 비교자료 정리
실패 사례 / 개선 사례 이미지 정리
```

산출물:

```text
성능표
timeline 이미지
ROI feature plot
발표용 시스템 구조도
```

---

### 담당 D: 파이프라인 / 새 세션 / 실시간화 준비

업무:

```text
run_session_pipeline_v2_safe.ps1 관리
새 session_18/session_19 촬영 및 실행
labels_segments.csv 세션별 작성
stale output 방지
팀원 공유용 zip / README 정리
```

---

## 22. 이번주 / 다음주 계획

### 이번주 목표

```text
1. Vision-assembly-psr-v2-package 기준으로 통일
2. session_17 labels_segments.csv 확정
3. polygon + up120 association 기준 공식화
4. HMM 71~82% 결과 fresh-run으로 확인
5. ROI delta feature 추가 여부 실험
6. roi-weight / roi-delta-weight / tool-threshold 비교
7. Framewise / FSM / HMM 결과표 정리
8. 팀원 공유용 zip 정리
```

### 다음주 목표

```text
1. session_18 또는 session_19 새로 촬영
2. 같은 v2 pipeline 실행
3. 라벨 없이 timeline 먼저 확인
4. 새 session labels_segments 작성
5. accuracy / macro_f1 재평가
6. session_17과 새 session 결과 비교
7. ablation 정리
   - ROI only
   - YOLO only
   - ROI + YOLO
   - ROI + YOLO + MediaPipe
8. 발표자료 제작
```

---

## 23. 장기 로드맵

### Phase 1. Offline PSR 안정화

목표:

```text
session_17 fresh-run 기준 성능 확정
session_18에서 재현성 확인
```

할 일:

```text
- label 정합성 확인
- association layout 고정
- HMM parameter sweep
- ROI delta feature 실험
- confusion matrix 추가
- state별 precision/recall/F1 추가
```

---

### Phase 2. 새 세션 일반화

목표:

```text
특정 session에만 맞춘 것이 아니라 새 촬영에서도 동작하는지 확인
```

할 일:

```text
- session_18/session_19 촬영
- 새 labels 작성
- 같은 pipeline으로 평가
- marker 가림/손 가림 실패 사례 정리
- YOLO 데이터 추가 필요성 판단
```

---

### Phase 3. Online HMM / 실시간 replay

현재 HMM은 offline Viterbi입니다. 실시간에서는 전체 sequence를 미리 볼 수 없기 때문에 online update가 필요합니다.

목표:

```text
session 이미지를 한 장씩 읽으며 실시간처럼 상태를 업데이트
```

구현 파일 후보:

```text
server/state/online_state_estimator.py
server/realtime/replay_realtime_state.py
```

동작:

```text
현재 frame feature
+ 이전 state probability
+ transition matrix
↓
현재 state probability 업데이트
↓
현재 state와 confidence 출력
```

---

### Phase 4. Real-time camera input

목표:

```text
카메라 frame을 실시간으로 받아 현재 상태 추론
```

추천 MVP:

```text
ArUco + YOLO + Online HMM
```

MediaPipe는 현재 우선순위 낮음.

---

### Phase 5. AR HUD 연결

목표:

```text
Quest 3 또는 AR 기기에서 현재 단계와 다음 작업 안내 표시
```

처음에는 3D overlay보다 텍스트 HUD가 적합합니다.

예상 메시지:

```json
{
  "state": "S4",
  "confidence": 0.82,
  "message": "B 나사 완료, C 나사를 조립하세요."
}
```

전송 구조:

```text
Python state server
↓ WebSocket JSON
Unity / AR HUD
```

---

## 24. 실시간화 관련 기존 판단

Quest 3에서 passthrough camera frame을 저장하는 것이 첫 번째 관문입니다.

초기 성공 기준은 다음입니다.

```text
Unity 앱이 실기기에서 카메라 frame 1장을 저장한다.
저장 구조가 meta.json + frames.csv + frames/*.jpg로 맞춰진다.
Python offline pipeline이 해당 session을 읽어 처리한다.
```

CPU 기반 `GetColors()`는 비용이 클 수 있으므로, 장기적으로는 낮은 FPS 샘플링 또는 `GetTexture() + AsyncGPUReadback` 구조가 더 적합합니다.

---

## 25. 발표용 핵심 문장

```text
본 프로젝트는 AR 조립 안내를 위해 산업용 인클로저 조립 작업의 현재 단계를 자동 추론하는 시스템입니다. 6개 ArUco marker를 이용해 작업대를 안정적으로 top-view 좌표계로 정렬하고, YOLO로 검출한 드라이버 위치를 homography로 투영하여 어느 나사에서 작업 중인지 판단합니다. ROI feature는 부품 상태의 보조 신호로 사용하고, HMM은 조립 순서가 S0→S6으로 진행된다는 제약을 반영하여 전체 상태 sequence를 안정적으로 추론합니다.
```

---

## 26. 다음 채팅에서 바로 해야 할 일

다음 채팅에서 이어서 할 경우, 먼저 아래 순서로 확인하면 됩니다.

```powershell
cd "C:\Users\user\Desktop\Vision-assembly-psr-v2-package"

# 1. association layout 존재 확인
Test-Path configs\roi_layout_v2_assoc_active.yaml

# 2. safe pipeline layout 사용 확인
Select-String -Path .\scripts\run_session_pipeline_v2_safe.ps1 -Pattern "roi_layout"

# 3. labels 확인
Get-Content labels\labels_segments.csv

# 4. 환경 확인
.\.venv_mp\Scripts\python.exe -c "import mediapipe as mp; print(mp.__version__); print(hasattr(mp, 'solutions'))"

# 5. fresh run
.\scripts\run_session_pipeline_v2_safe.ps1 `
  -SessionId session_17 `
  -SwapHandedness `
  -YoloDistanceMode polygon `
  -YoloNearThreshold 100 `
  -Clean `
  -RequireLabels
```

---

## 27. 핵심 요약

```text
이 프로젝트는 AR 기반 산업용 인클로저 조립 단계 추론 시스템입니다.
현재 기준 폴더는 Vision-assembly-psr-v2-package입니다.
6개 ArUco marker로 workspace를 안정화했습니다.
ROI는 보조 feature입니다.
YOLO driver 위치가 핵심 feature입니다.
YOLO bbox는 원본에서 검출한 뒤 warped 좌표계로 투영합니다.
실제 나사 중심보다 위쪽 120px 기준인 roi_layout_v2_assoc_active.yaml을 사용합니다.
HMM은 tool_near_smooth와 A→B→C→D 순서 제약으로 상태를 추론합니다.
MediaPipe는 현재 index_weight=0.0으로 보조/시각화용입니다.
현재 성능은 label 기준에 따라 71~82%이며, 82%는 fresh-run으로 재현 확인이 필요합니다.
다음 핵심 작업은 session_17 fresh-run 확정, session_18 검증, ROI delta_cum 추가, online HMM 실시간화입니다.
```
