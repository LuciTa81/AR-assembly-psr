[CmdletBinding()]
param(
    [int]$MaxIndex = 8,
    [string]$Modes = "640x480@30,1280x720@30,1920x1080@30",
    [double]$SampleSeconds = 3.0
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv_rt\Scripts\python.exe"
$outDir = Join-Path $repoRoot "outputs\realtime_camera_probe"
$checklist = Join-Path $repoRoot "docs\beast_hardware_gate.md"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Missing realtime virtual environment: $python"
}

New-Item -ItemType Directory -Force -Path $outDir | Out-Null

foreach ($backend in @("dshow", "msmf")) {
    & $python "server\realtime\probe_cameras.py" `
        --backend $backend `
        --max-index $MaxIndex `
        --modes $Modes `
        --sample-seconds $SampleSeconds `
        --out-dir $outDir `
        --save-preview
    if ($LASTEXITCODE -ne 0) {
        throw "Camera probe failed for backend=$backend with exit code $LASTEXITCODE"
    }
}

$probeCsvs = @(
    Join-Path $outDir "camera_probe_dshow.csv"
    Join-Path $outDir "camera_probe_msmf.csv"
)
Import-Csv -LiteralPath $probeCsvs | Export-Csv -NoTypeInformation -Encoding utf8 (Join-Path $outDir "beast_camera_modes.csv")

Write-Host "[DONE] Combined camera mode report: $(Join-Path $outDir 'beast_camera_modes.csv')"
Write-Host "[MANUAL] Complete the checklist: $checklist"
