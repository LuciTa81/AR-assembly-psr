# AR Assembly PSR 코드/명령어 레퍼런스

> 이 문서는 `AR_Assembly_PSR_Project_Handoff.md`의 부록입니다.  
> 프로젝트 설명이 아니라 **실행 명령어, 핵심 코드 패치, 확인 명령**만 따로 모았습니다.  
> AI 대회 관련 내용은 포함하지 않았습니다.

---

## 1. 기준 폴더 이동

```powershell
cd "C:\Users\user\Desktop\Vision-assembly-psr-v2-package"
```

---

## 2. 가상환경 재설치

MediaPipe에서 `mediapipe has no attribute solutions`가 뜨면 Python 3.11 환경으로 다시 만듭니다.

```powershell
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
.\.venv_mp\Scripts\python.exe -c "import sys, mediapipe as mp; print(sys.executable); print(mp.__file__); print(mp.__version__); print(hasattr(mp, 'solutions'))"
```

정상 출력:

```text
0.10.21
True
```

---

## 3. 전체 pipeline 공식 실행 명령

```powershell
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

## 4. safe pipeline에서 반드시 확인할 layout 분리

확인:

```powershell
Select-String -Path .\scripts\run_session_pipeline_v2_safe.ps1 -Pattern "roi_layout"
```

정상 구조:

```text
roi_cropper.py
→ --layout configs\roi_layout_v2.yaml

build_yolo_features.py
→ --layout configs\roi_layout_v2_assoc_active.yaml

build_mediapipe_features_hybrid.py
→ --layout configs\roi_layout_v2_assoc_active.yaml
```

만약 YOLO/MediaPipe feature 단계가 아직 `configs\roi_layout_v2.yaml`을 쓰면 아래처럼 바꿔야 합니다.

```powershell
notepad .\scripts\run_session_pipeline_v2_safe.ps1
```

수정해야 하는 부분:

```powershell
--layout configs\roi_layout_v2.yaml `
```

YOLO feature / MediaPipe feature 단계에서는 다음으로 변경:

```powershell
--layout configs\roi_layout_v2_assoc_active.yaml `
```

단, `roi_cropper.py` 단계는 변경하면 안 됩니다.

---

## 5. HMM만 다시 실행

`outputs\hmm_v2\session_17_hmm_input_v2.csv`가 이미 있으면 HMM만 다시 실행할 수 있습니다.

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

## 6. ROI weight만 바꿔 실험

### ROI 0.15

```powershell
.\.venv_mp\Scripts\python.exe server\state\run_state_baseline_v2.py `
  --input outputs\hmm_v2\session_17_hmm_input_v2.csv `
  --out-csv outputs\hmm_v2\session_17_state_predictions_v2_roi015.csv `
  --out-plot outputs\hmm_v2\session_17_state_timeline_v2_roi015.png `
  --out-metrics outputs\hmm_v2\session_17_state_metrics_v2_roi015.csv `
  --tool-threshold 0.4 `
  --index-weight 0.0 `
  --roi-weight 0.15 `
  --self-prob 0.92 `
  --next-prob 0.08 `
  --min-dwell 2
```

### ROI 0.20

```powershell
.\.venv_mp\Scripts\python.exe server\state\run_state_baseline_v2.py `
  --input outputs\hmm_v2\session_17_hmm_input_v2.csv `
  --out-csv outputs\hmm_v2\session_17_state_predictions_v2_roi020.csv `
  --out-plot outputs\hmm_v2\session_17_state_timeline_v2_roi020.png `
  --out-metrics outputs\hmm_v2\session_17_state_metrics_v2_roi020.csv `
  --tool-threshold 0.4 `
  --index-weight 0.0 `
  --roi-weight 0.20 `
  --self-prob 0.92 `
  --next-prob 0.08 `
  --min-dwell 2
```

결과 비교:

```powershell
Get-Content outputs\hmm_v2\session_17_state_metrics_v2.csv
Get-Content outputs\hmm_v2\session_17_state_metrics_v2_roi015.csv
Get-Content outputs\hmm_v2\session_17_state_metrics_v2_roi020.csv

start outputs\hmm_v2\session_17_state_timeline_v2.png
start outputs\hmm_v2\session_17_state_timeline_v2_roi015.png
start outputs\hmm_v2\session_17_state_timeline_v2_roi020.png
```

---

## 7. association up120 layout 생성

`roi_layout_v2_assoc_active.yaml`이 없으면 아래로 생성합니다.

```powershell
@'
import yaml
from pathlib import Path
import copy

src = Path("configs/roi_layout_v2.yaml")
base = yaml.safe_load(src.read_text(encoding="utf-8"))

data = copy.deepcopy(base)

for key in ["screw_a", "screw_b", "screw_c", "screw_d"]:
    data["rois"][key]["y"] = int(data["rois"][key]["y"]) - 120

out = Path("configs/roi_layout_v2_assoc_active.yaml")
out.write_text(
    yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
    encoding="utf-8"
)

print("saved:", out)
'@ | .\.venv_mp\Scripts\python.exe
```

확인:

```powershell
Test-Path configs\roi_layout_v2_assoc_active.yaml
type configs\roi_layout_v2_assoc_active.yaml
```

---

## 8. YOLO feature만 up120 기준으로 재생성

```powershell
.\.venv_mp\Scripts\python.exe server\vision\build_yolo_features.py `
  --yolo-raw outputs\yolo\session_17_yolo_raw.csv `
  --homography outputs\warp_v2\session_17_homography_v2.csv `
  --layout configs\roi_layout_v2_assoc_active.yaml `
  --out outputs\features_v2\session_17_yolo_features_v2.csv `
  --session-id session_17 `
  --near-threshold 100 `
  --distance-mode polygon `
  --warped-dir outputs\warped_v2\session_17 `
  --debug-dir outputs\yolo_feature_debug_v2\session_17_assoc_active_up120 `
  --debug-limit 100
```

통계 확인:

```powershell
$yf = Import-Csv outputs\features_v2\session_17_yolo_features_v2.csv

$yf | Group-Object chosen_screw | Format-Table Name, Count

"near_a=" + (($yf | Where-Object { $_.tool_near_a -eq "1" }).Count)
"near_b=" + (($yf | Where-Object { $_.tool_near_b -eq "1" }).Count)
"near_c=" + (($yf | Where-Object { $_.tool_near_c -eq "1" }).Count)
"near_d=" + (($yf | Where-Object { $_.tool_near_d -eq "1" }).Count)
```

---

## 9. MediaPipe feature 재생성

swapLR 파일 확인:

```powershell
Test-Path outputs\mediapipe\session_17_mediapipe_raw_v2_swapLR.csv
```

없으면 생성:

```powershell
@'
import pandas as pd

src = "outputs/mediapipe/session_17_mediapipe_raw_v2.csv"
dst = "outputs/mediapipe/session_17_mediapipe_raw_v2_swapLR.csv"

df = pd.read_csv(src)

def swap_lr(x):
    x = str(x)
    if x == "Left":
        return "Right"
    if x == "Right":
        return "Left"
    return x

if "handedness" in df.columns:
    df["handedness"] = df["handedness"].apply(swap_lr)

df.to_csv(dst, index=False, encoding="utf-8-sig")
print("saved:", dst)
print(df["handedness"].value_counts(dropna=False))
'@ | .\.venv_mp\Scripts\python.exe
```

MediaPipe hybrid feature 생성:

```powershell
.\.venv_mp\Scripts\python.exe server\vision\build_mediapipe_features_hybrid.py `
  --mediapipe-raw outputs\mediapipe\session_17_mediapipe_raw_v2_swapLR.csv `
  --yolo-raw outputs\yolo\session_17_yolo_raw.csv `
  --homography outputs\warp_v2\session_17_homography_v2.csv `
  --layout configs\roi_layout_v2_assoc_active.yaml `
  --out outputs\features_v2\session_17_mediapipe_features_v2_hybrid.csv `
  --session-id session_17 `
  --preferred-handedness Right `
  --association-threshold 140 `
  --near-threshold 120 `
  --warped-dir outputs\warped_v2\session_17 `
  --debug-dir outputs\mediapipe_feature_debug_v2\session_17_assoc_active_up120 `
  --debug-limit 60 `
  --disable-handedness-fallback
```

현재 HMM에서는 `index_weight=0.0`이므로 MediaPipe는 보조/시각화용입니다.

---

## 10. HMM input 재생성

```powershell
.\.venv_mp\Scripts\python.exe server\state\build_hmm_input_v2.py `
  --session data\raw_sessions\session_17 `
  --session-id session_17 `
  --homography outputs\warp_v2\session_17_homography_v2.csv `
  --roi outputs\features_v2\session_17_roi_features_v2.csv `
  --yolo outputs\features_v2\session_17_yolo_features_v2.csv `
  --mediapipe outputs\features_v2\session_17_mediapipe_features_v2_hybrid.csv `
  --labels labels\labels_segments.csv `
  --out outputs\hmm_v2\session_17_hmm_input_v2.csv `
  --smooth-window 5 `
  --seen-threshold 0.4
```

GT 확인:

```powershell
$hmm = Import-Csv outputs\hmm_v2\session_17_hmm_input_v2.csv
$hmm | Group-Object gt_state | Format-Table Name, Count
```

`UNKNOWN`만 나오면 label 문제입니다.

---

## 11. label fallback 금지 코드

`server/state/build_hmm_input_v2.py`의 `label_for_frame()`은 아래 정책이어야 합니다.

```python
def label_for_frame(frame_id: int, labels_df: pd.DataFrame, session_id: str) -> str:
    """
    세션별 GT 라벨을 반환합니다.

    중요:
    - labels_segments.csv에 현재 session_id가 있으면 해당 세션 라벨만 사용합니다.
    - 현재 session_id가 없으면 다른 세션 라벨을 fallback으로 사용하지 않습니다.
    - 라벨이 없으면 UNKNOWN을 반환합니다.
    """
    if labels_df.empty:
        return "UNKNOWN"

    df = labels_df.copy()

    if "session_id" in df.columns:
        matched = df[df["session_id"].astype(str) == str(session_id)]

        if matched.empty:
            return "UNKNOWN"

        df = matched

    required = {"start_frame", "end_frame", "state"}

    if not required.issubset(set(df.columns)):
        return "UNKNOWN"

    for _, row in df.iterrows():
        try:
            start = int(row["start_frame"])
            end = int(row["end_frame"])
        except Exception:
            continue

        if start <= frame_id <= end:
            return str(row["state"])

    return "UNKNOWN"
```

문법 체크:

```powershell
.\.venv_mp\Scripts\python.exe -m py_compile server\state\build_hmm_input_v2.py
```

---

## 12. safe PowerShell 실패 체크 함수

`run_session_pipeline_v2_safe.ps1` 안에는 아래와 같은 함수가 있어야 합니다.

```powershell
function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Command
    )

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor DarkGray
    Write-Host "[STEP] $Name" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor DarkGray

    & $Command

    if ($LASTEXITCODE -ne 0) {
        throw "[FAILED] $Name failed with exit code $LASTEXITCODE"
    }

    Write-Host "[OK] $Name" -ForegroundColor Green
}
```

---

## 13. ROI 편집

좋은 warped frame 하나를 골라 ROI를 다시 잡을 수 있습니다.

예시:

```powershell
.\.venv_mp\Scripts\python.exe server\vision\roi_cropper.py `
  --image outputs\warped_v2\session_17\000026_warped.jpg `
  --layout configs\roi_layout_v2.yaml `
  --edit `
  --roi-names enclosure lid base_front inner_area screw_a screw_b screw_c screw_d
```

ROI를 다시 잡으면 반드시 다음도 다시 해야 합니다.

```text
1. ROI crop 재생성
2. refs/roi_templates_v2 reference crop 재선택
3. roi_features 재생성
4. yolo_features 재생성
5. mediapipe_features 재생성
6. hmm_input 재생성
7. HMM 재실행
```

---

## 14. ROI crop 전체 재생성

```powershell
Remove-Item outputs\roi_crops_v2\session_17 -Recurse -Force -ErrorAction SilentlyContinue
mkdir outputs\roi_crops_v2\session_17 -Force

.\.venv_mp\Scripts\python.exe server\vision\roi_cropper.py `
  --input-dir outputs\warped_v2\session_17 `
  --layout configs\roi_layout_v2.yaml `
  --out outputs\roi_crops_v2\session_17
```

확인:

```powershell
explorer outputs\roi_crops_v2\session_17
```

---

## 15. ROI feature 재생성

```powershell
.\.venv_mp\Scripts\python.exe server\vision\roi_features.py `
  --crops-dir outputs\roi_crops_v2\session_17 `
  --refs refs\roi_templates_v2 `
  --out outputs\features_v2\session_17_roi_features_v2.csv `
  --debug-out outputs\features_v2\session_17_roi_feature_debug_v2.csv `
  --session-id session_17
```

---

## 16. ROI feature PNG 생성

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

결과 열기:

```powershell
explorer outputs\roi_feature_plots_v2\session_17
```

---

## 17. ROI delta debug plot

ROI raw score가 약할 때 delta cumulative signal을 확인하는 분석용 코드입니다.

```powershell
@'
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

roi_path = "outputs/features_v2/session_17_roi_features_v2.csv"
hmm_path = "outputs/hmm_v2/session_17_hmm_input_v2.csv"

df = pd.read_csv(roi_path)
df["frame_id"] = df["frame_id"].astype(int)
df = df.sort_values("frame_id").reset_index(drop=True)

cols = [
    "screw_a_done_score",
    "screw_b_done_score",
    "screw_c_done_score",
    "screw_d_done_score",
]

for c in cols:
    sm = (
        df[c]
        .astype(float)
        .rolling(window=5, min_periods=1, center=True)
        .median()
        .rolling(window=5, min_periods=1, center=True)
        .mean()
    )
    df[c + "_smooth"] = sm

# 실제 적용에서는 GT를 baseline 계산에 쓰면 안 됩니다.
# 이 debug 코드는 초반 20프레임 median을 baseline으로 사용합니다.
for c in cols:
    sm_col = c + "_smooth"
    delta_col = c + "_delta"
    cum_col = c + "_delta_cum"

    baseline = float(df.loc[df["frame_id"] <= 20, sm_col].median())
    df[delta_col] = (df[sm_col] - baseline).clip(lower=0.0)
    df[cum_col] = df[delta_col].cummax()

    print(c, "baseline=", round(baseline, 4), "max_delta=", round(float(df[delta_col].max()), 4))

out_csv = "outputs/features_v2/session_17_roi_delta_debug.csv"
df.to_csv(out_csv, index=False, encoding="utf-8-sig")
print("saved:", out_csv)

plt.figure(figsize=(14, 5))
for c in cols:
    plt.plot(df["frame_id"], df[c + "_delta_cum"], label=c.replace("_done_score", "_delta_cum"))

plt.xlabel("frame_id")
plt.ylabel("ROI cumulative delta")
plt.ylim(0, 0.30)
plt.grid(True)
plt.legend()
plt.tight_layout()
out_png = "outputs/features_v2/session_17_roi_delta_cum_debug.png"
plt.savefig(out_png, dpi=150)
print("saved:", out_png)
'@ | .\.venv_mp\Scripts\python.exe

start outputs\features_v2\session_17_roi_delta_cum_debug.png
```

---

## 18. 원본/warped ArUco + MediaPipe + YOLO overlay 생성

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

결과 확인:

```powershell
explorer outputs\visual_debug\session_17_swapLR

Get-ChildItem outputs\visual_debug\session_17_swapLR\original_all -Filter *.jpg | Measure-Object
Get-ChildItem outputs\visual_debug\session_17_swapLR\warped_all -Filter *.jpg | Measure-Object
Get-ChildItem outputs\visual_debug\session_17_swapLR\compare_original_warped -Filter *.jpg | Measure-Object
```

---

## 19. 새 세션 실행

라벨 없이 추론만:

```powershell
.\scripts\run_session_pipeline_v2_safe.ps1 `
  -SessionId session_18 `
  -SwapHandedness `
  -YoloDistanceMode polygon `
  -YoloNearThreshold 100 `
  -Clean
```

라벨 추가 후 평가:

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

## 20. warp 상태 확인

```powershell
$h = Import-Csv outputs\warp_v2\session_17_homography_v2.csv

$h | Group-Object homography_source | Format-Table Name, Count
$h | Group-Object failure_reason | Sort-Object Count -Descending | Format-Table Name, Count
$h | Group-Object marker_count | Sort-Object Name | Format-Table Name, Count

$h | Where-Object { $_.homography_source -eq "detected_ransac" } |
  Measure-Object warp_quality -Minimum -Maximum -Average
```

---

## 21. chosen_screw / state별 YOLO 확인

```powershell
@'
import pandas as pd

df = pd.read_csv("outputs/hmm_v2/session_17_state_predictions_v2.csv")

print("\n[chosen_screw by GT state]")
print(pd.crosstab(df["gt_state"], df["chosen_screw"]))

print("\n[near counts by GT state]")
print(df.groupby("gt_state")[[
    "tool_near_a",
    "tool_near_b",
    "tool_near_c",
    "tool_near_d"
]].sum())
'@ | .\.venv_mp\Scripts\python.exe
```

---

## 22. 현재 공식 기준 요약

```text
폴더: Vision-assembly-psr-v2-package
세션: session_17
마커: 6개 ArUco
YOLO: driver_standard_model/best.pt
YOLO mode: polygon
YOLO threshold: 100
ROI crop layout: configs/roi_layout_v2.yaml
Association layout: configs/roi_layout_v2_assoc_active.yaml
Association offset: up120
MediaPipe: swapLR 가능, HMM에서는 index_weight=0.0
HMM: tool_threshold 0.4, roi_weight 0.10, self_prob 0.92, next_prob 0.08
```
