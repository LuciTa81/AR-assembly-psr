param(
    [string]$SessionId = "session_17",
    [string]$SessionRoot = "data\raw_sessions",
    [string]$LabelFile = "labels\labels_segments.csv"
)

$ErrorActionPreference = "Stop"

$Py = ".\.venv_mp\Scripts\python.exe"

if (!(Test-Path $Py)) {
    throw "Python venv not found: $Py"
}

$SessionPath = Join-Path $SessionRoot $SessionId

$WarpCsv = "outputs\warp_v2\${SessionId}_homography_v2.csv"
$RoiFeatures = "outputs\features_v2\${SessionId}_roi_features_v2.csv"
$YoloFeatures = "outputs\features_v2\${SessionId}_yolo_features_v2.csv"
$MpFeatures = "outputs\features_v2\${SessionId}_mediapipe_features_v2_hybrid.csv"

$OutDir = "outputs\hmm_v2\best_role3"
$HmmInput = "$OutDir\${SessionId}_hmm_input_best_role3.csv"
$HmmPred = "$OutDir\${SessionId}_state_predictions_best_role3.csv"
$HmmPlot = "$OutDir\${SessionId}_state_timeline_best_role3.png"
$HmmMetrics = "$OutDir\${SessionId}_state_metrics_best_role3.csv"

mkdir $OutDir -Force | Out-Null

Write-Host ""
Write-Host "=== Build HMM input: best-role3 params ===" -ForegroundColor Cyan

& $Py server\state\build_hmm_input_v2.py `
    --session $SessionPath `
    --session-id $SessionId `
    --homography $WarpCsv `
    --roi $RoiFeatures `
    --yolo $YoloFeatures `
    --mediapipe $MpFeatures `
    --labels $LabelFile `
    --out $HmmInput `
    --smooth-window 2 `
    --seen-threshold 0.4 `
    --tool-score-radius 90 `
    --tool-score-softness 45 `
    --index-score-radius 100 `
    --index-score-softness 30 `
    --roi-delta-window 3 `
    --roi-delta-scale 0.20 `
    --roi-delta-smooth-window 3

Write-Host ""
Write-Host "=== Run HMM: best-role3 params ===" -ForegroundColor Cyan

& $Py server\state\run_state_baseline_v2.py `
    --input $HmmInput `
    --out-csv $HmmPred `
    --out-plot $HmmPlot `
    --out-metrics $HmmMetrics `
    --tool-threshold 0.4 `
    --index-weight 0.0 `
    --roi-weight 0.10 `
    --roi-delta-weight 0.12 `
    --screw-detect-weight 0.55 `
    --self-prob 0.76 `
    --next-prob 0.24 `
    --min-dwell 2

Write-Host ""
Write-Host "==================== DONE ====================" -ForegroundColor Green
Write-Host "HMM input   : $HmmInput"
Write-Host "Predictions : $HmmPred"
Write-Host "Plot        : $HmmPlot"
Write-Host "Metrics     : $HmmMetrics"
Write-Host "Expected HMM_v2 on session17: accuracy about 0.9412, macro-F1 about 0.9485"
Write-Host "==============================================" -ForegroundColor Green
