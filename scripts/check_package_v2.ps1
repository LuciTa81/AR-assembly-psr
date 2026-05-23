param(
    [string]$SessionId = "session_17"
)

$ErrorActionPreference = "Stop"
Write-Host "=== Vision Assembly PSR v2 package check ==="

$required = @(
    "server\vision\calibrate_marker_layout_v2.py",
    "server\vision\warp_session_v2.py",
    "server\vision\roi_cropper.py",
    "server\vision\roi_features.py",
    "server\vision\yolo_infer_session.py",
    "server\vision\build_yolo_features.py",
    "server\vision\mediapipe_extract_v2.py",
    "server\vision\build_mediapipe_features_hybrid.py",
    "server\state\build_hmm_input_v2.py",
    "server\state\run_state_baseline_v2.py",
    "configs\marker_layout_v2.yaml",
    "configs\roi_layout_v2.yaml",
    "labels\labels_segments.csv",
    "server\requirements.txt"
)

foreach ($p in $required) {
    if (Test-Path $p) { Write-Host "[OK] $p" }
    else { Write-Host "[MISS] $p" -ForegroundColor Red }
}

if (Test-Path "models\yolo\driver_standard_model\best.pt") {
    Write-Host "[OK] models\yolo\driver_standard_model\best.pt"
} else {
    Write-Host "[WARN] YOLO weights not found: models\yolo\driver_standard_model\best.pt" -ForegroundColor Yellow
}

$sessionPath = "data\raw_sessions\$SessionId"
if (Test-Path $sessionPath) {
    $n = (Get-ChildItem $sessionPath -Recurse -Filter *.jpg | Measure-Object).Count
    Write-Host "[OK] $sessionPath ($n jpg files)"
} else {
    Write-Host "[WARN] session folder not found: $sessionPath" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[DONE] Package check complete."
