# AR Assembly PSR 프로젝트 인수인계 문서

> 이 문서는 **AR 기반 조립 단계 추정 프로젝트(AR Assembly PSR)** 를 다른 채팅, 팀원, 또는 후속 작업자가 그대로 이어받을 수 있도록 정리한 인수인계 문서입니다.  
> 외부 행사, 공모, 심사, 제출 서류 등 프로젝트 외부 맥락은 제외하고, **AR Assembly 시스템 자체의 배경·구조·진행상황·실행법·로드맵**만 정리했습니다.

---

## 1. 프로젝트 배경

### 1.1 문제의식

본 프로젝트의 목표는 사용자가 실제 조립 작업을 수행하는 동안, 카메라 영상만으로 현재 조립 단계를 자동 추정하고, 추정된 상태를 AR 기기에서 안내하는 것입니다.

현실의 조립 작업에서는 다음과 같은 문제가 있습니다.

- 사용자가 매뉴얼을 보면서 손으로 조립해야 하므로 시선이 분산됩니다.
- 작업 중 손, 공구, 부품이 서로 가려져 단순 이미지 분류로는 현재 단계를 안정적으로 판단하기 어렵습니다.
- 나사 조립처럼 작은 변화는 픽셀 차이가 작아서 전후 상태를 직접 구분하기 어렵습니다.
- AR 환경에서는 실시간으로 현재 단계와 다음 작업을 알려줘야 하므로, 단일 이미지 판단보다 시간 흐름을 고려한 상태 추론이 필요합니다.

따라서 본 프로젝트는 다음 방향으로 설계되었습니다.

```text
카메라 영상 입력
→ 작업 공간 기준 좌표계 정렬
→ 부품/도구/손 위치 feature 추출
→ 시간 순서 기반 상태 추론
→ AR 기기에서 현재 단계 및 다음 행동 안내
```

---

### 1.2 최종 목표

최종 목표는 다음과 같습니다.

```text
사용자가 Quest 3, Viture, 또는 일반 카메라 기반 AR 환경에서 조립 작업을 수행하면,
시스템이 현재 조립 단계를 실시간으로 추정하고,
AR 화면에 현재 단계와 다음 작업을 안내한다.
```

최종 사용 시나리오 예시는 다음과 같습니다.

```text
1. 사용자가 조립 매트 위에 박스를 놓습니다.
2. 카메라가 조립 공간을 촬영합니다.
3. 시스템이 ArUco marker로 작업 공간을 정렬합니다.
4. YOLO가 드라이버 위치를 검출합니다.
5. ROI feature가 부품 상태를 보조적으로 확인합니다.
6. HMM이 현재 상태를 S0~S6 중 하나로 추정합니다.
7. AR 화면에 “현재 단계: B 나사 완료 / 다음 작업: C 나사 조립”처럼 안내합니다.
```

---

## 2. 상태 정의

현재 조립 단계는 총 7개 상태로 정의했습니다.

| 상태 | 의미 |
|---|---|
| S0 | 초기 상태 / 박스 배치 전 또는 조립 시작 전 |
| S1 | 박스가 작업 공간에 배치됨 |
| S2 | 뚜껑이 닫힘 |
| S3 | A 나사 작업 완료 |
| S4 | B 나사 작업 완료 |
| S5 | C 나사 작업 완료 |
| S6 | D 나사 작업 완료 / 최종 단계 |

HMM은 상태가 다음 순서로만 진행된다고 가정합니다.

```text
S0 → S1 → S2 → S3 → S4 → S5 → S6
```

허용되는 전이는 다음과 같습니다.

```text
S0 → S0 or S1
S1 → S1 or S2
S2 → S2 or S3
S3 → S3 or S4
S4 → S4 or S5
S5 → S5 or S6
S6 → S6
```

---

## 3. 현재 기준 프로젝트 폴더

현재 기준 프로젝트 폴더는 다음입니다.

```text
C:\Users\user\Desktop\Vision-assembly-psr-v2-package
```

예전 `AR-assembly-psr` 폴더는 더 이상 기준으로 사용하지 않습니다. 현재는 `Vision-assembly-psr-v2-package`만 안정화 대상으로 둡니다.

---

## 4. 현재 공식 기준 설정

현재까지 가장 안정적인 기준은 아래와 같습니다.

```text
세션:
session_17

프레임 수:
119장

마커:
6개 ArUco marker
DICT_4X4_50
ID 0,1,2 = 위쪽 row
ID 3,4,5 = 아래쪽 row

YOLO 모델:
models/yolo/driver_standard_model/best.pt

YOLO distance mode:
polygon

YOLO near threshold:
100

ROI crop용 layout:
configs/roi_layout_v2.yaml

YOLO / MediaPipe near 판정용 layout:
configs/roi_layout_v2_assoc_active.yaml

association 보정:
기존 screw 기준점보다 y 방향으로 -120px
즉, 나사 중심보다 위쪽으로 120px 이동

MediaPipe:
frame당 최대 2손 추출
Left/Right handedness swap 적용
현재 HMM에서는 index_weight=0.0으로 보조/비활성

HMM 설정:
tool_threshold = 0.4
index_weight = 0.0
roi_weight = 0.10
self_prob = 0.92
next_prob = 0.08
min_dwell = 2
```

---

## 5. 현재 성능 요약

초기 구조에서는 HMM 정확도가 약 19% 수준까지 낮았습니다.

이후 다음 개선을 거쳐 성능이 크게 향상되었습니다.

```text
초기 ROI 중심 구조:
약 19%

6개 ArUco + YOLO tool_near + HMM v2:
약 71%

최근 label 구간 재정리 후 가능 결과:
약 82%
```

단, 82% 결과는 반드시 주의해서 다뤄야 합니다.

### 5.1 82% 결과 관련 주의사항

현재 업로드/공유된 일부 패키지에서는 다음 현상이 있었습니다.

```text
outputs/hmm_v2/session_17_state_metrics_v2.csv 안에는 약 71.4% 결과가 저장되어 있음

하지만 labels/labels_segments.csv가 이후 수정되었고,
같은 prediction을 새 labels 기준으로 다시 평가하면 약 82%가 나올 수 있음
```

따라서 82%를 공식 결과로 쓰려면 반드시 다음 과정을 다시 수행해야 합니다.

```text
1. labels_segments.csv가 실제 session_17 영상과 맞는지 확인
2. safe pipeline에서 association layout이 제대로 쓰이는지 확인
3. -Clean -RequireLabels로 fresh run
4. fresh run 결과도 82% 근처인지 확인
```

---

## 6. 19%에서 71~82%까지 개선된 이유

### 6.1 초기 19%였던 이유

초기에는 ROI crop 기반 픽셀 유사도만으로 상태를 판단하려 했습니다.

```text
warped image
→ ROI crop
→ lid_closed_score / screw_done_score
→ HMM
```

하지만 나사 조립은 전후 픽셀 차이가 매우 작습니다.

예를 들어 다음 score가 대부분 0.45~0.55 근처에서 움직였습니다.

```text
screw_a_done_score
screw_b_done_score
screw_c_done_score
screw_d_done_score
```

이 때문에 HMM은 A/B/C/D 나사 완료 여부를 ROI만으로 구분하기 어려웠습니다.

또한 초기에는 marker 가림과 homography 불안정으로 ROI 위치가 frame마다 흔들렸습니다. 이로 인해 HMM이 조기 전이하거나, 특정 상태에 오래 머무르거나, S6로 튀는 문제가 발생했습니다.

---

### 6.2 개선 1: 6개 ArUco marker 적용

기존 4개 marker 또는 불안정한 marker 기준에서 6개 ArUco marker로 전환했습니다.

```text
위쪽 row: ID 0, ID 1, ID 2
아래쪽 row: ID 3, ID 4, ID 5
```

효과:

```text
- 손/도구가 일부 marker를 가려도 homography 유지 가능
- workspace warp 안정화
- ROI crop 위치 안정화
- YOLO bbox와 MediaPipe landmark를 warped 좌표계로 변환할 기반 확보
```

session_17 기준으로 warp가 크게 안정화되었습니다.

```text
detected_ransac 약 115장
previous_h_fallback 약 4장
invalid 0장
average warp_quality 약 0.70 수준
```

---

### 6.3 개선 2: YOLO driver detection 추가

ROI만으로 나사 완료 여부를 직접 판단하기 어렵기 때문에 관점을 바꿨습니다.

```text
나사가 조여졌는지 직접 보기
↓
드라이버가 어느 나사 근처에서 작업 중인지 보기
```

YOLO는 원본 frame에서 드라이버를 검출합니다.

그 후 다음 처리를 합니다.

```text
YOLO bbox 원본 좌표
↓
homography 적용
↓
warped workspace 좌표로 변환
↓
screw_a/b/c/d 기준점과 거리 계산
↓
tool_near_a/b/c/d 생성
```

HMM에서는 YOLO feature가 핵심 전이 trigger가 되었습니다.

---

### 6.4 개선 3: polygon distance 사용

YOLO bbox 중심만 쓰면 드라이버가 길게 잡힐 때 오판이 발생했습니다.

따라서 공식 기준은 다음입니다.

```text
YoloDistanceMode = polygon
```

즉, warped bbox polygon과 screw 기준점 사이 거리를 계산합니다.

`tip` 모드도 실험했지만 현재 세션에서는 안정적이지 않아 사용하지 않기로 했습니다.

---

### 6.5 개선 4: association 기준점 up120 적용

가장 중요한 개선입니다.

실제 나사 중심점과 YOLO가 잡은 driver bbox의 위치가 잘 맞지 않았습니다. 드라이버 bbox는 나사 머리보다 위쪽, 즉 드라이버 shaft/tip 쪽에 더 가깝게 잡히는 경향이 있었습니다.

따라서 나사 기준점을 위쪽으로 올리는 실험을 했습니다.

```text
up120
up150
up180
```

그중 `up120`이 가장 자연스럽게 맞았습니다.

최종 구조는 다음입니다.

```text
ROI crop / ROI feature용:
configs/roi_layout_v2.yaml

YOLO / MediaPipe near 판정용:
configs/roi_layout_v2_assoc_active.yaml
= roi_layout_v2_assoc_up120.yaml
```

즉, 실제 ROI crop은 나사 위치 그대로 잡고, 도구가 어느 나사 근처인지 판단할 때만 기준점을 위로 120px 올립니다.

효과:

```text
- C/D 단계 evidence가 살아남
- HMM이 S4→S5→S6로 자연스럽게 전이
- 전체 timeline이 계단형으로 안정화
```

---

### 6.6 개선 5: HMM v2 ordered evidence

YOLO가 특정 frame에서 C/D로 튀는 경우가 있기 때문에, 단순히 `tool_near_c=1`이면 바로 S5로 가게 하면 안 됩니다.

따라서 HMM v2에서는 순서 제약을 넣었습니다.

```text
A evidence가 충분히 나온 뒤에야 B를 봄
B evidence가 충분히 나온 뒤에야 C를 봄
C evidence가 충분히 나온 뒤에야 D를 봄
```

즉, `tool_near`는 상태 자체가 아니라 **전이 trigger**로 사용됩니다.

```text
S2 → S3: A evidence
S3 → S4: B evidence
S4 → S5: C evidence
S5 → S6: D evidence
```

---

## 7. 전체 파이프라인 구조

```text
원본 frame
↓
ArUco marker detection
↓
Homography 계산
↓
Workspace warp
↓
ROI crop / ROI feature
↓
YOLO driver detection
↓
YOLO bbox warped 좌표 투영
↓
MediaPipe hand landmark 추출
↓
MediaPipe index point warped 좌표 투영
↓
hmm_input_v2.csv 생성
↓
Framewise / FSM / HMM 추론
↓
state timeline / metrics 출력
```

---

## 8. Feature 상세

### 8.1 Homography / Warp feature

출력 파일:

```text
outputs/warp_v2/session_17_homography_v2.csv
```

주요 feature:

```csv
homography_valid
homography_usable
homography_source
marker_count
warp_quality
```

역할:

```text
warp_quality가 높으면 ROI score를 더 신뢰
warp_quality가 낮으면 ROI score를 0.5에 가깝게 약화
```

---

### 8.2 ROI feature

ROI crop layout:

```text
configs/roi_layout_v2.yaml
```

ROI 이름:

```text
enclosure
lid
base_front
inner_area
screw_a
screw_b
screw_c
screw_d
```

reference crop 폴더:

```text
refs/roi_templates_v2/
```

필요한 reference:

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

HMM으로 보내는 ROI feature:

```csv
box_present_score
lid_closed_score
screw_a_done_score
screw_b_done_score
screw_c_done_score
screw_d_done_score
```

`build_hmm_input_v2.py`에서 effective score를 생성합니다.

```csv
box_present_score_effective
lid_closed_score_effective
screw_a_done_score_effective
screw_b_done_score_effective
screw_c_done_score_effective
screw_d_done_score_effective
```

현재 ROI의 역할:

```text
S0/S1/S2: box/lid 판단에 도움
S3~S6: 나사 완료 상태의 약한 보조 feature
```

---

### 8.3 ROI delta 개선 후보

최근 ROI를 다시 잡은 뒤 raw score보다는 baseline 대비 변화량이 의미 있어 보였습니다.

관찰된 패턴:

```text
screw_a_delta_cum: frame 48~55 부근 상승
screw_b_delta_cum: frame 60대 상승
screw_c_delta_cum: frame 80대 상승
screw_d_delta_cum: frame 108 이후 상승
```

개선 후보:

```text
ROI raw score
↓
rolling smoothing
↓
초반 20프레임 median baseline
↓
delta = max(0, smooth - baseline)
↓
delta_cum = cumulative max
↓
HMM 보조 evidence로 사용
```

주의:

```text
GT state를 보고 baseline을 잡으면 안 됨.
실제 적용에서는 초반 N프레임 median으로 baseline을 잡아야 함.
```

아직 공식 반영 전이며, 다음 개선 후보입니다.

---

### 8.4 YOLO feature

YOLO raw 출력:

```text
outputs/yolo/session_17_yolo_raw.csv
```

YOLO feature 출력:

```text
outputs/features_v2/session_17_yolo_features_v2.csv
```

공식 설정:

```text
layout = configs/roi_layout_v2_assoc_active.yaml
distance-mode = polygon
near-threshold = 100
```

HMM으로 보내는 YOLO feature:

```csv
tool_visible
tool_confidence
tool_detection_count
tool_inside_workspace
tool_x
tool_y
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

`build_hmm_input_v2.py`에서 smoothing 생성:

```csv
tool_near_a_smooth
tool_near_b_smooth
tool_near_c_smooth
tool_near_d_smooth
```

현재 rolling window는 5입니다.

---

### 8.5 MediaPipe feature

MediaPipe v2는 frame당 최대 2손을 저장합니다.

raw 출력:

```text
outputs/mediapipe/session_17_mediapipe_raw_v2.csv
outputs/mediapipe/session_17_mediapipe_raw_v2_swapLR.csv
```

MediaPipe handedness가 실제 왼손/오른손과 반대로 잡히는 경향이 있어 `swapLR`을 적용했습니다.

MediaPipe raw feature:

```csv
frame_id
hand_id
hand_visible
num_hands
handedness
hand_score
index_x
index_y
index_z
wrist_x
wrist_y
wrist_z
```

hybrid feature 처리:

```text
YOLO driver bbox와 가까운 손 선택
↓
선택된 손의 index point를 homography로 warped 좌표에 투영
↓
index point와 screw 기준점 거리 계산
↓
index_near_a/b/c/d 생성
```

HMM으로 보내는 feature:

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

현재 공식 HMM에서는 다음 설정으로 사용합니다.

```text
index_weight = 0.0
```

즉, MediaPipe는 현재 HMM 성능의 핵심이 아니라 시각화/보조/ablation용입니다.

---

## 9. 핵심 파일 구조

```text
Vision-assembly-psr-v2-package/
│
├─ configs/
│  ├─ marker_layout_v2.yaml
│  ├─ marker_layout_v2_session_17.yaml
│  ├─ marker_layout_v2_session_17_relaxed.yaml
│  ├─ roi_layout_v2.yaml
│  ├─ roi_layout_v2_assoc_up120.yaml
│  └─ roi_layout_v2_assoc_active.yaml
│
├─ data/
│  └─ raw_sessions/
│     └─ session_17/
│        ├─ frames.csv
│        └─ frames/
│           ├─ 000001.jpg
│           └─ ...
│
├─ labels/
│  └─ labels_segments.csv
│
├─ models/
│  └─ yolo/
│     └─ driver_standard_model/
│        └─ best.pt
│
├─ refs/
│  └─ roi_templates_v2/
│
├─ scripts/
│  ├─ setup_env_v2.ps1
│  ├─ check_package_v2.ps1
│  ├─ run_session_pipeline_v2_safe.ps1
│  └─ run_hmm_v2_only.ps1
│
├─ server/
│  ├─ vision/
│  └─ state/
│
└─ outputs/
   ├─ warp_v2/
   ├─ warped_v2/
   ├─ features_v2/
   ├─ hmm_v2/
   ├─ roi_feature_plots_v2/
   └─ visual_debug/
```

---

## 10. 주요 코드 파일과 역할

### 10.1 scripts

#### `scripts/setup_env_v2.ps1`

Python 가상환경 설치용입니다.

#### `scripts/check_package_v2.ps1`

필수 파일 존재 여부를 확인합니다.

#### `scripts/run_session_pipeline_v2_safe.ps1`

전체 pipeline 실행 스크립트입니다.

주요 특징:

```text
- 각 Python 단계 후 $LASTEXITCODE 검사
- 실패 시 즉시 중단
- -Clean 옵션으로 기존 output 삭제 후 fresh run
- -RequireLabels 옵션으로 GT 없는 평가 방지
```

반드시 확인할 layout 분리:

```text
roi_cropper.py:
--layout configs\roi_layout_v2.yaml

build_yolo_features.py:
--layout configs\roi_layout_v2_assoc_active.yaml

build_mediapipe_features_hybrid.py:
--layout configs\roi_layout_v2_assoc_active.yaml
```

#### `scripts/run_hmm_v2_only.ps1`

이미 생성된 `hmm_input_v2.csv`만 가지고 HMM을 다시 돌릴 때 사용합니다.

---

### 10.2 server/vision

#### `server/vision/calibrate_marker_layout_v2.py`

6개 ArUco marker를 detect해서 session별 marker layout을 생성합니다.

#### `server/vision/warp_session_v2.py`

ArUco marker와 layout으로 homography를 계산하고 원본 frame을 800x600 workspace로 warp합니다.

#### `server/vision/roi_cropper.py`

warped image에서 ROI crop을 생성합니다. `--edit` 모드로 ROI를 직접 조정할 수 있습니다.

#### `server/vision/roi_features.py`

ROI crop과 `refs/roi_templates_v2` reference crop을 비교해 box/lid/screw score를 생성합니다.

#### `server/vision/plot_roi_features.py`

ROI score timeline, heatmap, by-state boxplot, crop contact sheet PNG를 생성합니다.

#### `server/vision/yolo_infer_session.py`

원본 frame에서 YOLO driver detection을 실행합니다.

#### `server/vision/build_yolo_features.py`

YOLO bbox를 homography로 warped 좌표에 투영하고, screw 기준점과의 거리를 계산해 `tool_near_a/b/c/d`를 생성합니다.

공식 mode:

```text
polygon
```

#### `server/vision/mediapipe_extract_v2.py`

원본 frame에서 MediaPipe Hands를 실행하고 frame당 최대 2손을 저장합니다. debug image 저장도 가능합니다.

#### `server/vision/build_mediapipe_features_hybrid.py`

YOLO driver bbox와 가까운 손을 선택하고, index point를 warped 좌표로 투영해 `index_near_a/b/c/d`를 생성합니다.

#### `server/vision/make_detection_overlays.py`

원본/warped 이미지에 ArUco, MediaPipe, YOLO overlay를 생성합니다.

지원 옵션:

```text
--swap-handedness
```

---

### 10.3 server/state

#### `server/state/build_hmm_input_v2.py`

homography, ROI, YOLO, MediaPipe, labels를 병합해 HMM 입력 CSV를 생성합니다.

출력:

```text
outputs/hmm_v2/session_17_hmm_input_v2.csv
```

중요 정책:

```text
labels에 현재 session_id가 없으면 gt_state=UNKNOWN
다른 session 라벨을 fallback으로 쓰지 않음
```

#### `server/state/run_state_baseline_v2.py`

Framewise, FSM, HMM을 실행합니다.

출력:

```text
outputs/hmm_v2/session_17_state_predictions_v2.csv
outputs/hmm_v2/session_17_state_metrics_v2.csv
outputs/hmm_v2/session_17_state_timeline_v2.png
```

---

## 11. 실행 환경

권장 환경:

```text
Python 3.11
mediapipe==0.10.21
numpy<2
opencv-contrib-python
pandas
matplotlib
pyyaml
ultralytics
```

MediaPipe 에러가 난 적이 있습니다.

```text
AttributeError: module 'mediapipe' has no attribute 'solutions'
```

복구 방법:

```powershell
cd "C:\Users\user\Desktop\Vision-assembly-psr-v2-package"

Remove-Item .venv_mp -Recurse -Force -ErrorAction SilentlyContinue

py -3.11 -m venv .venv_mp

.\.venv_mp\Scripts\python.exe -m pip install --upgrade pip

.\.venv_mp\Scripts\python.exe -m pip install `
  "numpy<2" `
  opencv-contrib-python `
  pandas `
  matplotlib `
  pyyaml `
  ultralytics `
  "mediapipe==0.10.21"
```

확인:

```powershell
.\.venv_mp\Scripts\python.exe -c "import mediapipe as mp; print(mp.__version__); print(hasattr(mp, 'solutions'))"
```

정상 결과:

```text
0.10.21
True
```

---

## 12. 공식 실행법

### 12.1 전체 pipeline 실행

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

결과 확인:

```powershell
Get-Content outputs\hmm_v2\session_17_state_metrics_v2.csv
start outputs\hmm_v2\session_17_state_timeline_v2.png
```

---

### 12.2 HMM만 다시 실행

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

## 13. Labels 관리

`labels/labels_segments.csv`는 평가용 정답표입니다.

중요:

```text
labels_segments.csv는 모델 입력이 아니라 평가용 GT이다.
새 세션을 평가하려면 새 세션 전용 라벨을 만들어야 한다.
```

session_17 라벨 후보는 두 버전이 있었습니다.

### 13.1 기존 Vision 기준

```csv
session_17,1,4,S0,initial
session_17,5,11,S1,box placed
session_17,12,19,S2,lid closed
session_17,20,49,S3,screw A done
session_17,50,69,S4,screw B done
session_17,70,89,S5,screw C done
session_17,90,119,S6,screw D done
```

이 기준에서 HMM 약 71%가 나왔습니다.

### 13.2 최근 82% 기준으로 보이는 라벨

```csv
session_17,1,7,S0,initial
session_17,8,14,S1,box placed
session_17,15,28,S2,lid closed
session_17,29,50,S3,screw A done
session_17,51,71,S4,screw B done
session_17,72,90,S5,screw C done
session_17,91,119,S6,screw D done
```

이 기준이 실제 영상과 맞다면 82% 결과가 의미 있습니다. 단, fresh run이 필요합니다.

---

## 14. 새 세션 검증 방법

예시: `session_18`

폴더 구조:

```text
data/raw_sessions/session_18/
├─ frames.csv
└─ frames/
   ├─ 000001.jpg
   ├─ 000002.jpg
   └─ ...
```

라벨 없이 추론만 실행:

```powershell
.\scripts\run_session_pipeline_v2_safe.ps1 `
  -SessionId session_18 `
  -SwapHandedness `
  -YoloDistanceMode polygon `
  -YoloNearThreshold 100 `
  -Clean
```

이때 `gt_state=UNKNOWN`이어도 정상입니다.

평가하려면 `labels/labels_segments.csv`에 `session_18` 라벨을 추가한 뒤 실행합니다.

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

## 15. 시각화 / 디버그 output

### 15.1 ROI feature plot

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

생성 파일:

```text
session_17_roi_scores_timeline.png
session_17_roi_scores_heatmap.png
session_17_roi_scores_by_state.png
session_17_roi_crop_contact_sheet.png
```

---

### 15.2 원본/warped ArUco + MediaPipe + YOLO overlay

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

주의:

```text
warped_yolo는 발표/디버그용 비교이다.
실제 HMM에서는 YOLO를 원본 frame에서 돌리고 bbox를 homography로 warped 좌표에 투영한다.
```

---

## 16. macro_f1 설명

`accuracy`는 전체 프레임 중 맞춘 프레임 비율입니다.

```text
accuracy = 맞춘 프레임 수 / 전체 프레임 수
```

`macro_f1`은 각 상태 S0~S6의 F1을 따로 계산한 뒤 평균낸 값입니다.

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

따라서 accuracy는 전체 timeline 유사도, macro_f1은 각 상태를 골고루 잘 맞췄는지를 보는 지표입니다.

---

## 17. FSM이 낮게 나오는 이유

FSM_v2는 deterministic rule baseline입니다. 현재 FSM은 특정 조건, 특히 S1→S2에서 lid 조건이 약하면 뒤 상태로 넘어가지 못하고 S1에 오래 갇힐 수 있습니다.

즉 FSM이 낮은 이유는 다음입니다.

```text
단순 threshold 기반 FSM은 noisy ROI feature에 취약하다.
HMM은 전체 sequence와 transition probability를 함께 보므로 더 안정적이다.
```

발표/문서화 시 FSM은 단순 규칙 baseline으로 설명하면 됩니다.

---

## 18. 팀원 역할분담

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
screw_delta_cum 분석
MediaPipe index_near 활용 가능성 검토
```

실험:

```text
ROI only
YOLO only
YOLO + ROI
YOLO + ROI + MediaPipe
association up0 / up120 비교
```

산출물:

```text
feature ablation 결과표
feature별 성능 기여도 정리
```

---

### 담당 C: 평가 / 시각화 / 기술 문서

업무:

```text
accuracy / macro_f1 정리
confusion matrix 작성
state timeline 정리
ROI score plot 정리
4-marker vs 6-marker 비교자료 정리
시스템 구조도 작성
```

산출물:

```text
성능표
timeline 이미지
ROI feature plot
시스템 구조도
실패 사례 / 개선 사례 이미지
```

---

### 담당 D: 파이프라인 / 새 세션 / 실시간화 준비

업무:

```text
run_session_pipeline_v2_safe.ps1 관리
새 session_18/session_19 촬영 및 실행
labels_segments.csv 세션별 작성
stale output 방지
공유용 zip / README 정리
```

---

## 19. 실시간화 로드맵

현재 구조는 batch/offline입니다.

```text
119장 전체 처리
→ HMM Viterbi
→ 전체 sequence 출력
```

실시간에서는 미래 frame을 알 수 없으므로 전체 Viterbi를 그대로 쓰기 어렵습니다. 따라서 online HMM으로 바꿔야 합니다.

---

### 19.1 실시간 MVP 구조

```text
현재 frame 입력
↓
ArUco homography 계산
↓
YOLO driver detection
↓
tool_near 계산
↓
최근 N프레임 smoothing
↓
online HMM forward update
↓
현재 state 출력
```

실시간 MVP에서 우선순위:

```text
필수:
ArUco + YOLO + online HMM

선택:
ROI delta

후순위:
MediaPipe
```

---

### 19.2 실시간 구현 단계

#### 1단계: offline replay realtime

```text
session_17 frame을 한 장씩 읽으면서 실시간처럼 처리
```

파일 후보:

```text
server/realtime/replay_realtime_state.py
```

#### 2단계: online state estimator

파일 후보:

```text
server/state/online_state_estimator.py
```

내부 구조:

```text
current_alpha
transition_matrix
rolling buffer for tool_near
rolling buffer for ROI score
update(frame_features)
return current_state, confidence
```

#### 3단계: WebSocket 서버

파일 후보:

```text
server/realtime/state_ws_server.py
```

출력 예시:

```json
{
  "frame_id": 52,
  "state": "S4",
  "confidence": 0.82,
  "message": "B 나사 완료, C 나사를 조립하세요."
}
```

#### 4단계: AR HUD 연동

초기에는 복잡한 3D overlay보다 텍스트 HUD만 표시합니다.

```text
현재 단계: S4
다음 작업: C 나사 조립
진행률: 4 / 6
```

---

## 20. 앞으로의 구체적 로드맵

### 20.1 이번 단계: 기준 재현성 고정

목표:

```text
session_17에서 현재 성능을 fresh run으로 재현
```

해야 할 일:

```text
1. labels_segments.csv가 실제 session_17 영상과 맞는지 확인
2. run_session_pipeline_v2_safe.ps1에서 association layout 분리 확인
3. -Clean -RequireLabels로 fresh run
4. HMM accuracy / macro_f1 저장
5. 71% 또는 82% 중 fresh run으로 재현되는 값을 공식 baseline으로 확정
```

산출물:

```text
outputs/hmm_v2/session_17_state_metrics_v2_final.csv
outputs/hmm_v2/session_17_state_timeline_v2_final.png
outputs/hmm_v2/session_17_hmm_input_v2_final.csv
```

---

### 20.2 다음 단계: 새 세션 검증

목표:

```text
session_17에서만 맞는 것이 아니라 새 촬영 세션에서도 동작하는지 확인
```

해야 할 일:

```text
1. session_18 촬영
2. data/raw_sessions/session_18에 저장
3. labels 없이 pipeline 실행
4. 예측 timeline이 S0→S6로 자연스럽게 올라가는지 확인
5. session_18 labels_segments 작성
6. -RequireLabels로 평가 실행
7. session_17과 session_18 성능 비교
```

확인 지표:

```text
accuracy
macro_f1
state별 precision / recall / F1
transition timing error
```

---

### 20.3 다음 개선: ROI delta_cum 공식 feature화

목표:

```text
ROI raw score를 직접 쓰는 대신 baseline 대비 변화량을 보조 feature로 사용
```

해야 할 일:

```text
1. build_hmm_input_v2.py에 ROI smoothing/delta/cum 컬럼 추가
2. run_state_baseline_v2.py에서 delta_cum을 S3~S6 보조 evidence로 사용
3. roi_delta_weight 0.05 / 0.10 / 0.15 / 0.20 실험
4. YOLO only vs YOLO+ROI raw vs YOLO+ROI delta 비교
```

주의:

```text
GT state로 baseline 잡지 말 것.
초반 N프레임 median으로 baseline 계산.
```

---

### 20.4 다음 개선: 평가 지표 확장

추가할 지표:

```text
confusion matrix
state별 precision
state별 recall
state별 F1
transition timing error
±3 frame tolerance accuracy
```

목표:

```text
프레임 단위 정확도뿐 아니라 실제 조립 단계 전환 타이밍이 얼마나 맞는지 평가
```

---

### 20.5 실시간 MVP 구현

목표:

```text
offline batch pipeline을 online 단계 추정기로 전환
```

순서:

```text
1. replay_realtime_state.py 작성
2. online_state_estimator.py 작성
3. session_17 replay로 online HMM 검증
4. 카메라 입력 적용
5. WebSocket 상태 출력
6. AR HUD 연결
```

---

### 20.6 장기 개선

```text
1. YOLO 데이터 추가 학습
   - C/D 나사 근처 드라이버 장면 보강
   - 손/도구 가림 장면 보강
   - motion blur 장면 보강

2. MediaPipe 활용 재검토
   - 작업손 선택 안정화
   - 손이 workspace 밖일 때 무시
   - index_weight를 0.05~0.10으로 낮게 실험

3. 마커 배치 개선
   - 실제 AR 환경에서 marker 가림 최소화
   - 카메라 시점 변화에 대한 robustness 검증

4. AR UI 고도화
   - 텍스트 HUD
   - 단계 progress bar
   - 다음 나사 위치 highlight
```

---

## 21. 공유용 zip에 포함할 것

포함 권장:

```text
configs/
data/raw_sessions/session_17/
docs/
labels/
models/yolo/driver_standard_model/best.pt
refs/roi_templates_v2/
scripts/
server/
outputs/features_v2/
outputs/hmm_v2/
outputs/roi_feature_plots_v2/
README_V2_UPDATE.md
```

제외 권장:

```text
.venv_mp/
__pycache__/
*.pyc
outputs/debug*/
outputs/warped_v2/
outputs/roi_crops_v2/
outputs/yolo_debug/
outputs/mediapipe_debug/
```

발표/시각화 자료가 필요하면 선택적으로 포함:

```text
outputs/visual_debug/session_17_swapLR/
```

---

## 22. 팀원에게 전달할 핵심 실행 명령

```powershell
cd "압축푼경로\Vision-assembly-psr-v2-package"

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

.\scripts\setup_env_v2.ps1

.\scripts\check_package_v2.ps1 -SessionId session_17

.\scripts\run_session_pipeline_v2_safe.ps1 `
  -SessionId session_17 `
  -SwapHandedness `
  -YoloDistanceMode polygon `
  -YoloNearThreshold 100 `
  -Clean `
  -RequireLabels
```

---

## 23. 가장 중요한 주의사항

```text
1. tip mode 사용하지 말 것.
   공식 기준은 polygon.

2. roi_layout_v2.yaml을 up120으로 덮어쓰지 말 것.
   ROI crop용과 association용은 분리.

3. labels_segments.csv는 반드시 현재 session_id에 맞아야 함.
   다른 session 라벨 fallback 금지.

4. MediaPipe left/right swap은 현재 HMM 성능의 핵심 원인이 아님.
   현재 index_weight=0.0.

5. 82%는 fresh run으로 재현되기 전까지는 가능성 있는 최신 결과로만 볼 것.

6. 새 session은 labels 없이 먼저 추론하고,
   평가하려면 해당 session 전용 labels_segments를 작성해야 함.

7. safe pipeline에서 build_yolo_features.py와 build_mediapipe_features_hybrid.py가
   configs\roi_layout_v2_assoc_active.yaml을 쓰는지 반드시 확인.
```

---

## 24. 아주 짧은 요약

```text
현재 프로젝트는 AR 조립 작업에서 S0~S6 단계를 자동 추정하는 시스템이다.
6개 ArUco로 workspace를 안정적으로 warp하고,
YOLO driver bbox를 warped 좌표로 투영해 tool_near_a/b/c/d를 만든다.
나사 중심과 드라이버 bbox 위치 차이를 보정하기 위해 association 기준점을 위로 120px 올렸다.
HMM은 tool_near_smooth를 A→B→C→D 순서 제약이 있는 전이 evidence로 사용한다.
ROI는 현재 보조 feature이며, MediaPipe는 index_weight=0.0으로 거의 비활성이다.
현재 성능은 label 기준에 따라 71~82%이며, 82%는 fresh run 재현 확인이 필요하다.
다음 핵심 작업은 session_18 검증, ROI delta_cum 추가, online HMM 기반 실시간화이다.
```
