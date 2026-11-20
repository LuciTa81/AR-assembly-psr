[CmdletBinding()]
param(
    [string]$PythonExe = "",
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $PythonExe = Join-Path $repoRoot ".venv_rt\Scripts\python.exe"
}
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    throw "Provide -PythonExe with a working Python 3 path. This check uses only the standard library."
}
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $repoRoot "outputs\realtime_camera_probe\beast_device_inventory.json"
}

$scriptPath = Join-Path $repoRoot "server\realtime\beast_device_check.py"
& $PythonExe $scriptPath --output $OutputPath
$checkExitCode = $LASTEXITCODE
if ($checkExitCode -eq 1) {
    Write-Host "[NOT READY] No healthy Beast camera candidate was found."
} elseif ($checkExitCode -ne 0) {
    throw "Device check failed (exit $checkExitCode). Check Python and Windows device access."
}
exit $checkExitCode
