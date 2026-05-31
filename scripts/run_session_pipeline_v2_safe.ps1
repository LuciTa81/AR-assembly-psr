param(
    [string]$SessionId = "session_17",
    [string]$SessionRoot = "data\raw_sessions",
    [string]$Weights = "models\yolo\driver_standard_model\best-3.pt",
    [string]$LabelFile = "labels\labels_segments.csv",

    [ValidateSet("polygon", "center", "tip")]
    [string]$YoloDistanceMode = "polygon",

    [int]$YoloNearThreshold = 100,
    [int]$MediaPipeAssocThreshold = 140,
    [int]$MediaPipeNearThreshold = 120,

    [switch]$SwapHandedness,
    [switch]$Clean,
    [switch]$RequireLabels
)

$ErrorActionPreference = "Stop"

$Py = ".\.venv_mp\Scripts\python.exe"

if (!(Test-Path $Py)) {
    throw "Python venv not found: $Py"
}

$SessionPath = Join-Path $SessionRoot $SessionId

if (!(Test-Path $SessionPath)) {
    throw "Session folder not found: $SessionPath"
}

if (!(Test-Path $Weights)) {
    throw "YOLO weights not found: $Weights"
}

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

$CalibLayoutRaw = "configs\marker_layout_v2_$SessionId.yaml"
$CalibLayout = "configs\marker_layout_v2_${SessionId}_relaxed.yaml"

$WarpDir = "outputs\warped_v2\$SessionId"
$WarpDebugDir = "outputs\debug_markers_v2\$SessionId"
$WarpCsv = "outputs\warp_v2\${SessionId}_homography_v2.csv"

$RoiCropsDir = "outputs\roi_crops_v2\$SessionId"
$RoiFeatures = "outputs\features_v2\${SessionId}_roi_features_v2.csv"
$RoiFeatureDebug = "outputs\features_v2\${SessionId}_roi_feature_debug_v2.csv"

$YoloRaw = "outputs\yolo\${SessionId}_yolo_raw.csv"
$YoloFeatures = "outputs\features_v2\${SessionId}_yolo_features_v2.csv"
$YoloDebugDir = "outputs\yolo_debug\$SessionId"
$YoloFeatureDebugDir = "outputs\yolo_feature_debug_v2\$SessionId"

$MpRaw = "outputs\mediapipe\${SessionId}_mediapipe_raw_v2.csv"
$MpRawUsed = $MpRaw
$MpDebugDir = "outputs\mediapipe_debug\${SessionId}_v2"

$MpFeatures = "outputs\features_v2\${SessionId}_mediapipe_features_v2_hybrid.csv"
$MpFeatureDebugDir = "outputs\mediapipe_feature_debug_v2\${SessionId}_hybrid"

$HmmInput = "outputs\hmm_v2\${SessionId}_hmm_input_v2.csv"
$HmmPred = "outputs\hmm_v2\${SessionId}_state_predictions_v2.csv"
$HmmPlot = "outputs\hmm_v2\${SessionId}_state_timeline_v2.png"
$HmmMetrics = "outputs\hmm_v2\${SessionId}_state_metrics_v2.csv"

if ($Clean) {
    Write-Host "[CLEAN] Removing old outputs for $SessionId" -ForegroundColor Yellow

    Remove-Item $WarpDir -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item $WarpDebugDir -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item $RoiCropsDir -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item $YoloDebugDir -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item $YoloFeatureDebugDir -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item $MpDebugDir -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item $MpFeatureDebugDir -Recurse -Force -ErrorAction SilentlyContinue

    Remove-Item "outputs\warp_v2\${SessionId}*" -Force -ErrorAction SilentlyContinue
    Remove-Item "outputs\features_v2\${SessionId}*" -Force -ErrorAction SilentlyContinue
    Remove-Item "outputs\hmm_v2\${SessionId}*" -Force -ErrorAction SilentlyContinue
    Remove-Item "outputs\yolo\${SessionId}*" -Force -ErrorAction SilentlyContinue
    Remove-Item "outputs\mediapipe\${SessionId}*" -Force -ErrorAction SilentlyContinue
}

mkdir outputs\calibration\$SessionId -Force | Out-Null
mkdir outputs\warp_v2 -Force | Out-Null
mkdir $WarpDir -Force | Out-Null
mkdir $WarpDebugDir -Force | Out-Null
mkdir $RoiCropsDir -Force | Out-Null
mkdir outputs\features_v2 -Force | Out-Null
mkdir outputs\yolo -Force | Out-Null
mkdir $YoloDebugDir -Force | Out-Null
mkdir $YoloFeatureDebugDir -Force | Out-Null
mkdir outputs\mediapipe -Force | Out-Null
mkdir $MpDebugDir -Force | Out-Null
mkdir $MpFeatureDebugDir -Force | Out-Null
mkdir outputs\hmm_v2 -Force | Out-Null

Invoke-Step "Calibrate 6-marker layout" {
    & $Py server\vision\calibrate_marker_layout_v2.py `
        --session $SessionPath `
        --out $CalibLayoutRaw `
        --preview-dir "outputs\calibration\$SessionId" `
        --width 800 `
        --height 600 `
        --margin-x 45 `
        --margin-y 45 `
        --detect-scale 1.5
}

Invoke-Step "Apply relaxed homography quality rules" {
    $code = @"
import yaml
from pathlib import Path

src = Path(r"$CalibLayoutRaw")
dst = Path(r"$CalibLayout")

data = yaml.safe_load(src.read_text(encoding="utf-8"))

data["quality_rules"] = {
    "min_markers": 3,
    "min_points": 12,
    "require_both_rows": True,
    "min_column_span": 2,
    "ransac_reproj_threshold": 8.0,
    "min_inlier_ratio": 0.55,
    "max_reprojection_error": 12.0,
}

data["fallback"] = {
    "use_previous_h": True,
    "max_fallback_gap": 2,
}

dst.write_text(
    yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
    encoding="utf-8"
)

print("saved:", dst)
"@
    $code | & $Py
}

Invoke-Step "Warp session v2" {
    & $Py server\vision\warp_session_v2.py `
        --session $SessionPath `
        --layout $CalibLayout `
        --out-dir $WarpDir `
        --debug-dir $WarpDebugDir `
        --homography-csv $WarpCsv `
        --session-id $SessionId `
        --width 800 `
        --height 600 `
        --detect-scale 1.5
}

Invoke-Step "ROI crop v2" {
    & $Py server\vision\roi_cropper.py `
        --input-dir $WarpDir `
        --layout configs\roi_layout_v2.yaml `
        --out $RoiCropsDir
}

Invoke-Step "ROI features v2" {
    & $Py server\vision\roi_features.py `
        --crops-dir $RoiCropsDir `
        --refs refs\roi_templates_v2 `
        --out $RoiFeatures `
        --debug-out $RoiFeatureDebug `
        --session-id $SessionId
}

Invoke-Step "YOLO raw inference" {
    & $Py server\vision\yolo_infer_session.py `
        --session $SessionPath `
        --weights $Weights `
        --out $YoloRaw `
        --debug-dir $YoloDebugDir `
        --debug-limit 30 `
        --conf 0.35 `
        --imgsz 640
}

Invoke-Step "YOLO features v2" {
    & $Py server\vision\build_yolo_features.py `
        --yolo-raw $YoloRaw `
        --homography $WarpCsv `
        --layout configs\roi_layout_v2_assoc_active.yaml `
        --out $YoloFeatures `
        --session-id $SessionId `
        --near-threshold $YoloNearThreshold `
        --distance-mode $YoloDistanceMode `
        --warped-dir $WarpDir `
        --debug-dir $YoloFeatureDebugDir `
        --debug-limit 40
}


Invoke-Step "MediaPipe raw v2, max 2 hands" {
    & $Py server\vision\mediapipe_extract_v2.py `
        --session $SessionPath `
        --out $MpRaw `
        --debug-dir $MpDebugDir `
        --debug-limit 50 `
        --session-id $SessionId `
        --max-num-hands 2 `
        --min-detection-confidence 0.5 `
        --min-tracking-confidence 0.5
}

if ($SwapHandedness) {
    $MpRawSwap = "outputs\mediapipe\${SessionId}_mediapipe_raw_v2_swapLR.csv"

    Invoke-Step "Swap MediaPipe handedness labels" {
        $code = @"
import pandas as pd

src = r"$MpRaw"
dst = r"$MpRawSwap"

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
"@
        $code | & $Py
    }

    $MpRawUsed = $MpRawSwap
}

Invoke-Step "MediaPipe hybrid features v2" {
    & $Py server\vision\build_mediapipe_features_hybrid.py `
        --mediapipe-raw $MpRawUsed `
        --yolo-raw $YoloRaw `
        --homography $WarpCsv `
        --layout configs\\roi_layout_v2_assoc_active.yaml `
        --out $MpFeatures `
        --session-id $SessionId `
        --preferred-handedness Right `
        --association-threshold $MediaPipeAssocThreshold `
        --near-threshold $MediaPipeNearThreshold `
        --warped-dir $WarpDir `
        --debug-dir $MpFeatureDebugDir `
        --debug-limit 60 `
        --disable-handedness-fallback
}

Invoke-Step "Build HMM input v2" {
    & $Py server\state\build_hmm_input_v2.py `
        --session $SessionPath `
        --session-id $SessionId `
        --homography $WarpCsv `
        --roi $RoiFeatures `
        --yolo $YoloFeatures `
        --mediapipe $MpFeatures `
        --labels $LabelFile `
        --out $HmmInput `
        --smooth-window 5 `
        --seen-threshold 0.4 `
        --tool-score-radius 100 `
        --tool-score-softness 25 `
        --index-score-radius 120 `
        --index-score-softness 30 `
        --roi-delta-window 1 `
        --roi-delta-scale 0.20 `
        --roi-delta-smooth-window 3
}

Invoke-Step "Check GT labels in HMM input" {
    $require = if ($RequireLabels) { "1" } else { "0" }

    $code = @"
import pandas as pd
import sys

path = r"$HmmInput"
df = pd.read_csv(path)

print("[GT counts]")
print(df["gt_state"].value_counts(dropna=False))

has_known = (df["gt_state"].astype(str) != "UNKNOWN").any()

if "$require" == "1" and not has_known:
    print("[ERROR] No labels for this session. gt_state is all UNKNOWN.")
    sys.exit(7)
"@
    $code | & $Py
}

Invoke-Step "Run HMM baseline v2" {
    & $Py server\state\run_state_baseline_v2.py `
        --input $HmmInput `
        --out-csv $HmmPred `
        --out-plot $HmmPlot `
        --out-metrics $HmmMetrics `
        --tool-threshold 0.4 `
        --index-weight 0.0 `
        --roi-weight 0.10 `
        --roi-delta-weight 0.0 `
        --screw-detect-weight 0.0 `
        --self-prob 0.92 `
        --next-prob 0.08 `
        --min-dwell 2
}

Write-Host ""
Write-Host "==================== DONE ====================" -ForegroundColor Green
Write-Host "HMM input   : $HmmInput"
Write-Host "Predictions : $HmmPred"
Write-Host "Plot        : $HmmPlot"
Write-Host "Metrics     : $HmmMetrics"
Write-Host "==============================================" -ForegroundColor Green
