param(
    [string]$SessionId = "session_13",
    [string]$Weights = "models\yolo\driver_yolo11s_colab\best.pt"
)

$PY = ".\.venv_mp\Scripts\python.exe"

$SessionDir = "data\raw_sessions\$SessionId"

$WarpedDir = "outputs\warped\$SessionId"
$MarkerDebugDir = "outputs\debug_markers\$SessionId"
$HomographyCsv = "outputs\warp\${SessionId}_homography.csv"

$RoiCropsDir = "outputs\roi_crops\$SessionId"
$RoiFeatures = "outputs\features\${SessionId}_roi_features.csv"
$RoiDebug = "outputs\features\${SessionId}_roi_feature_debug.csv"

$YoloRaw = "outputs\yolo\${SessionId}_yolo_raw.csv"
$YoloDebug = "outputs\yolo_debug\$SessionId"

$MpRaw = "outputs\mediapipe\${SessionId}_mediapipe_raw.csv"
$MpDebug = "outputs\mediapipe_debug\$SessionId"

$HmmInput = "outputs\hmm\${SessionId}_hmm_input_min.csv"
$PredCsv = "outputs\hmm\${SessionId}_state_predictions.csv"
$PredPlot = "outputs\hmm\${SessionId}_state_timeline.png"
$MetricsCsv = "outputs\hmm\${SessionId}_state_metrics.csv"

Write-Host "=== Session pipeline: $SessionId ==="

New-Item -ItemType Directory -Force -Path outputs\warp | Out-Null
New-Item -ItemType Directory -Force -Path $WarpedDir | Out-Null
New-Item -ItemType Directory -Force -Path $MarkerDebugDir | Out-Null
New-Item -ItemType Directory -Force -Path $RoiCropsDir | Out-Null
New-Item -ItemType Directory -Force -Path outputs\features | Out-Null
New-Item -ItemType Directory -Force -Path outputs\yolo | Out-Null
New-Item -ItemType Directory -Force -Path $YoloDebug | Out-Null
New-Item -ItemType Directory -Force -Path outputs\mediapipe | Out-Null
New-Item -ItemType Directory -Force -Path $MpDebug | Out-Null
New-Item -ItemType Directory -Force -Path outputs\hmm | Out-Null

Write-Host "[1/7] Warp session"
& $PY server\vision\warp_session.py `
  --session $SessionDir `
  --out-dir $WarpedDir `
  --debug-dir $MarkerDebugDir `
  --homography-csv $HomographyCsv `
  --session-id $SessionId `
  --width 800 `
  --height 600

Write-Host "[2/7] ROI crop"
& $PY server\vision\roi_cropper.py `
  --input-dir $WarpedDir `
  --layout configs\roi_layout_v1.yaml `
  --out $RoiCropsDir

Write-Host "[3/7] ROI features"
& $PY server\vision\roi_features.py `
  --crops-dir $RoiCropsDir `
  --refs refs\roi_templates `
  --out $RoiFeatures `
  --debug-out $RoiDebug `
  --session-id $SessionId

Write-Host "[4/7] YOLO raw"
& $PY server\vision\yolo_infer_session.py `
  --session $SessionDir `
  --weights $Weights `
  --out $YoloRaw `
  --debug-dir $YoloDebug `
  --debug-limit 30 `
  --conf 0.35 `
  --imgsz 640

Write-Host "[5/7] MediaPipe raw"
& $PY server\vision\mediapipe_extract.py `
  --session $SessionDir `
  --out $MpRaw `
  --debug-dir $MpDebug `
  --debug-limit 30

Write-Host "[6/7] Build HMM input"
& $PY server\state\build_hmm_input_min.py `
  --session-id $SessionId `
  --roi $RoiFeatures `
  --yolo $YoloRaw `
  --mediapipe $MpRaw `
  --labels labels\labels_segments.csv `
  --out $HmmInput

Write-Host "[7/7] Run HMM baseline"
& $PY server\state\run_state_baseline.py `
  --input $HmmInput `
  --out-csv $PredCsv `
  --out-plot $PredPlot `
  --out-metrics $MetricsCsv

Write-Host "=== DONE ==="
Write-Host "HMM input: $HmmInput"
Write-Host "Predictions: $PredCsv"
Write-Host "Plot: $PredPlot"
Write-Host "Metrics: $MetricsCsv"
