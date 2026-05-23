param(
    [string]$SessionId = "session_17",
    [string]$Input = "outputs\hmm_v2\session_17_hmm_input_v2.csv",
    [double]$ToolThreshold = 0.4,
    [double]$IndexWeight = 0.0,
    [double]$RoiWeight = 0.10,
    [double]$SelfProb = 0.92,
    [double]$NextProb = 0.08,
    [int]$MinDwell = 2
)
$ErrorActionPreference = "Stop"
$Py = ".\.venv_mp\Scripts\python.exe"
if (!(Test-Path $Input)) { throw "HMM input not found: $Input" }
New-Item -ItemType Directory -Force -Path outputs\hmm_v2 | Out-Null
& $Py server\state\run_state_baseline_v2.py `
  --input $Input `
  --out-csv "outputs\hmm_v2\${SessionId}_state_predictions_v2.csv" `
  --out-plot "outputs\hmm_v2\${SessionId}_state_timeline_v2.png" `
  --out-metrics "outputs\hmm_v2\${SessionId}_state_metrics_v2.csv" `
  --tool-threshold $ToolThreshold `
  --index-weight $IndexWeight `
  --roi-weight $RoiWeight `
  --self-prob $SelfProb `
  --next-prob $NextProb `
  --min-dwell $MinDwell
Get-Content "outputs\hmm_v2\${SessionId}_state_metrics_v2.csv"
