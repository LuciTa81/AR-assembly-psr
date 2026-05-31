param(
    [string]$SessionId = "session_17",
    [string]$Weights = "models\yolo\driver_standard_model\best-3.pt",
    [switch]$Clean,
    [switch]$SwapHandedness
)

$ErrorActionPreference = "Stop"

$Py = ".\.venv_mp\Scripts\python.exe"

if (!(Test-Path $Py)) {
    throw "Python venv not found. Run scripts\setup_env_v2.ps1 first."
}

if (!(Test-Path $Weights)) {
    throw "YOLO weights not found: $Weights"
}

$pipelineArgs = @{
    SessionId = $SessionId
    Weights = $Weights
    RequireLabels = $true
}

if ($Clean) {
    $pipelineArgs.Clean = $true
}

if ($SwapHandedness) {
    $pipelineArgs.SwapHandedness = $true
}

Write-Host ""
Write-Host "=== Run full v2 feature pipeline ===" -ForegroundColor Cyan
& .\scripts\run_session_pipeline_v2_safe.ps1 @pipelineArgs

$HmmInput = "outputs\hmm_v2\${SessionId}_hmm_input_v2.csv"
$BaselineMetrics = "outputs\hmm_v2\${SessionId}_state_metrics_v2.csv"

Write-Host ""
Write-Host "[DONE] Current recommended metrics: baseline HMM v2" -ForegroundColor Green
Get-Content $BaselineMetrics

Write-Host ""
Write-Host "[NEXT] Run scripts\run_session17_best_role3_hmm.ps1 for the verified best-role3 HMM parameters." -ForegroundColor Yellow
