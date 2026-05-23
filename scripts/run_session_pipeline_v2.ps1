param(
    [string]$SessionId = "session_17",
    [string]$SessionRoot = "data\raw_sessions",
    [string]$YoloWeights = "models\yolo\driver_standard_model\best.pt",
    [string]$RoiLayout = "configs\roi_layout_v2.yaml",
    [string]$RoiRefs = "refs\roi_templates_v2",
    [string]$Labels = "labels\labels_segments.csv",
    [double]$YoloNearThreshold = 100,
    [ValidateSet("polygon", "center", "tip")]
    [string]$YoloDistanceMode = "polygon",
    [double]$AssociationThreshold = 140,
    [double]$IndexNearThreshold = 120,
    [switch]$SwapHandedness,
    [switch]$UseHandednessFallback,
    [double]$ToolThreshold = 0.4,
    [double]$IndexWeight = 0.0,
    [double]$RoiWeight = 0.10,
    [double]$SelfProb = 0.92,
    [double]$NextProb = 0.08,
    [int]$MinDwell = 2,
    [int]$DebugLimit = 40
)

$ErrorActionPreference = "Stop"
$Py = ".\.venv_mp\Scripts\python.exe"
$SessionPath = Join-Path $SessionRoot $SessionId

Write-Host "=== Vision Assembly PSR v2 full pipeline ==="
Write-Host "Session: $SessionId"
Write-Host "Session path: $SessionPath"

if (!(Test-Path $Py)) { throw "Python venv not found. Run scripts\setup_env_v2.ps1 first." }
if (!(Test-Path $SessionPath)) { throw "Session folder not found: $SessionPath" }
if (!(Test-Path $YoloWeights)) { throw "YOLO weights not found: $YoloWeights" }
if (!(Test-Path $RoiLayout)) { throw "ROI layout not found: $RoiLayout. Create/edit configs\roi_layout_v2.yaml first." }
if (!(Test-Path $RoiRefs)) { throw "ROI refs not found: $RoiRefs. Create refs\roi_templates_v2 first." }
if (!(Test-Path $Labels)) { throw "Labels file not found: $Labels" }

New-Item -ItemType Directory -Force -Path outputs\calibration\$SessionId | Out-Null
New-Item -ItemType Directory -Force -Path outputs\warped_v2\$SessionId | Out-Null
New-Item -ItemType Directory -Force -Path outputs\debug_markers_v2\$SessionId | Out-Null
New-Item -ItemType Directory -Force -Path outputs\warp_v2 | Out-Null
New-Item -ItemType Directory -Force -Path outputs\roi_crops_v2\$SessionId | Out-Null
New-Item -ItemType Directory -Force -Path outputs\features_v2 | Out-Null
New-Item -ItemType Directory -Force -Path outputs\yolo | Out-Null
New-Item -ItemType Directory -Force -Path outputs\yolo_debug\$SessionId | Out-Null
New-Item -ItemType Directory -Force -Path outputs\yolo_feature_debug_v2\$SessionId | Out-Null
New-Item -ItemType Directory -Force -Path outputs\mediapipe | Out-Null
New-Item -ItemType Directory -Force -Path outputs\mediapipe_debug\${SessionId}_v2 | Out-Null
New-Item -ItemType Directory -Force -Path outputs\mediapipe_feature_debug_v2\${SessionId}_hybrid | Out-Null
New-Item -ItemType Directory -Force -Path outputs\hmm_v2 | Out-Null

$MarkerLayout = "configs\marker_layout_v2_${SessionId}_relaxed.yaml"
$Hcsv = "outputs\warp_v2\${SessionId}_homography_v2.csv"
$RoiFeatures = "outputs\features_v2\${SessionId}_roi_features_v2.csv"
$YoloRaw = "outputs\yolo\${SessionId}_yolo_raw.csv"
$YoloFeatures = "outputs\features_v2\${SessionId}_yolo_features_v2.csv"
$MpRaw = "outputs\mediapipe\${SessionId}_mediapipe_raw_v2.csv"
$MpFeatures = "outputs\features_v2\${SessionId}_mediapipe_features_v2_hybrid.csv"
$HmmInput = "outputs\hmm_v2\${SessionId}_hmm_input_v2.csv"
$PredCsv = "outputs\hmm_v2\${SessionId}_state_predictions_v2.csv"
$PredPlot = "outputs\hmm_v2\${SessionId}_state_timeline_v2.png"
$Metrics = "outputs\hmm_v2\${SessionId}_state_metrics_v2.csv"

Write-Host "[1/11] 6-marker layout calibration"
& $Py server\vision\calibrate_marker_layout_v2.py `
    --session $SessionPath `
    --out $MarkerLayout `
    --preview-dir "outputs\calibration\$SessionId" `
    --width 800 `
    --height 600 `
    --margin-x 45 `
    --margin-y 45 `
    --detect-scale 1.5

Write-Host "[2/11] Warp session v2"
& $Py server\vision\warp_session_v2.py `
    --session $SessionPath `
    --layout $MarkerLayout `
    --out-dir "outputs\warped_v2\$SessionId" `
    --debug-dir "outputs\debug_markers_v2\$SessionId" `
    --homography-csv $Hcsv `
    --session-id $SessionId `
    --width 800 `
    --height 600 `
    --detect-scale 1.5

Write-Host "[3/11] ROI crop v2"
& $Py server\vision\roi_cropper.py `
    --input-dir "outputs\warped_v2\$SessionId" `
    --layout $RoiLayout `
    --out "outputs\roi_crops_v2\$SessionId"

Write-Host "[4/11] ROI features v2"
& $Py server\vision\roi_features.py `
    --crops-dir "outputs\roi_crops_v2\$SessionId" `
    --refs $RoiRefs `
    --out $RoiFeatures `
    --debug-out "outputs\features_v2\${SessionId}_roi_feature_debug_v2.csv" `
    --session-id $SessionId

Write-Host "[5/11] YOLO raw"
& $Py server\vision\yolo_infer_session.py `
    --session $SessionPath `
    --weights $YoloWeights `
    --out $YoloRaw `
    --debug-dir "outputs\yolo_debug\$SessionId" `
    --debug-limit $DebugLimit `
    --conf 0.35 `
    --imgsz 640

Write-Host "[6/11] YOLO features v2"
& $Py server\vision\build_yolo_features.py `
    --yolo-raw $YoloRaw `
    --homography $Hcsv `
    --layout $RoiLayout `
    --out $YoloFeatures `
    --session-id $SessionId `
    --near-threshold $YoloNearThreshold `
    --distance-mode $YoloDistanceMode `
    --warped-dir "outputs\warped_v2\$SessionId" `
    --debug-dir "outputs\yolo_feature_debug_v2\$SessionId" `
    --debug-limit $DebugLimit

Write-Host "[7/11] MediaPipe raw v2"
& $Py server\vision\mediapipe_extract_v2.py `
    --session $SessionPath `
    --out $MpRaw `
    --debug-dir "outputs\mediapipe_debug\${SessionId}_v2" `
    --debug-limit $DebugLimit `
    --session-id $SessionId `
    --max-num-hands 2

Write-Host "[8/11] MediaPipe hybrid features"
$mpArgs = @(
    "server\vision\build_mediapipe_features_hybrid.py",
    "--mediapipe-raw", $MpRaw,
    "--yolo-raw", $YoloRaw,
    "--homography", $Hcsv,
    "--layout", $RoiLayout,
    "--out", $MpFeatures,
    "--session-id", $SessionId,
    "--preferred-handedness", "Right",
    "--association-threshold", $AssociationThreshold,
    "--near-threshold", $IndexNearThreshold,
    "--warped-dir", "outputs\warped_v2\$SessionId",
    "--debug-dir", "outputs\mediapipe_feature_debug_v2\${SessionId}_hybrid",
    "--debug-limit", $DebugLimit
)
if ($SwapHandedness) { $mpArgs += "--swap-handedness" }
if (-not $UseHandednessFallback) { $mpArgs += "--disable-handedness-fallback" }
& $Py @mpArgs

Write-Host "[9/11] HMM input v2"
& $Py server\state\build_hmm_input_v2.py `
    --session $SessionPath `
    --session-id $SessionId `
    --homography $Hcsv `
    --roi $RoiFeatures `
    --yolo $YoloFeatures `
    --mediapipe $MpFeatures `
    --labels $Labels `
    --out $HmmInput `
    --smooth-window 5 `
    --seen-threshold 0.4

Write-Host "[10/11] HMM baseline v2"
& $Py server\state\run_state_baseline_v2.py `
    --input $HmmInput `
    --out-csv $PredCsv `
    --out-plot $PredPlot `
    --out-metrics $Metrics `
    --tool-threshold $ToolThreshold `
    --index-weight $IndexWeight `
    --roi-weight $RoiWeight `
    --self-prob $SelfProb `
    --next-prob $NextProb `
    --min-dwell $MinDwell

Write-Host "[11/11] Summary"
Get-Content $Metrics
Write-Host ""
Write-Host "[DONE] HMM input: $HmmInput"
Write-Host "[DONE] Predictions: $PredCsv"
Write-Host "[DONE] Plot: $PredPlot"
Write-Host "[DONE] Metrics: $Metrics"
