[CmdletBinding()]
param(
    [ValidateSet('doctor', 'replay', 'live-local')]
    [string]$Mode = 'doctor',
    [string]$PythonExe = (Join-Path $env:LOCALAPPDATA 'ARAssembly\beast-mvp\.venv\Scripts\python.exe'),
    [string]$Config = 'configs/realtime_viture_beast_aruco.yaml',
    [string]$Session = '',
    [string]$Weights = '',
    [switch]$ValidateFilter,
    [int]$MaxFrames = 0
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    Write-Error "Python not found: $PythonExe. Supply -PythonExe for the prepared environment."
    exit 1
}
$Arguments = @('-X', 'utf8', '-B', (Join-Path $Root 'server\realtime\run_realtime_server.py'),
               '--config', $Config)
if ($Weights) { $Arguments += @('--weights', $Weights) }
if ($Session) { $Arguments += @('--session', $Session) }
if ($Mode -eq 'doctor') { $Arguments += '--doctor' }
if ($Mode -eq 'live-local') { $Arguments += @('--source', 'camera') }
if ($Mode -eq 'replay') {
    if (-not $Session) { Write-Error 'replay requires -Session'; exit 2 }
    $Arguments += @('--source', 'session')
}
if ($ValidateFilter) { $Arguments += '--validate-filter' }
if ($MaxFrames -gt 0) { $Arguments += @('--max-frames', $MaxFrames) }
Push-Location -LiteralPath $Root
try {
    & $PythonExe @Arguments
    $Result = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $Result
