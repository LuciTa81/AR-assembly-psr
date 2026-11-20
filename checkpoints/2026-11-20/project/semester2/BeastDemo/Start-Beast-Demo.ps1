[CmdletBinding()]
param(
    [ValidateSet('Live','Sbs')][string]$Mode = 'Live',
    [int]$CameraIndex = 0
)
$ErrorActionPreference = 'Stop'
$root = 'C:\Users\fresh\OneDrive\Desktop\홍익대\4학년\2학기\vision\01_SUBMIT_KEEP\AR-assembly-psr_github_main_20260604\.worktrees\viture-beast-overlay-mvp'
$python = 'C:/Users/fresh/AppData/Local/ARAssembly/beast-mvp/.venv/Scripts/python.exe'
$camera = 'C:\Users\fresh\AppData\Local\ARAssembly\beast-mvp\camera_calibration\combined-review-20260927T065914Z-89414bbe\candidate.json'
$workspace = 'C:/Users/fresh/AppData/Local/ARAssembly/beast-mvp/workspace_registration/comfort-layout-20261006-v1/workspace-candidate.json'
$candidate = 'C:/Users/fresh/AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/ARAssembly/beast-mvp/display_fits/fit-20261006T092953Z-a3b26250/candidate-probe.json'
$startPoint = 'C:/Users/fresh/AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/ARAssembly/beast-mvp/display_correspondence/74510324a63c4ad68d87f2cb48da63fd/point-009.json'
$logRoot = Join-Path $PSScriptRoot 'logs'
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
if (Get-Process -Name BeastAssemblyGuide -ErrorAction SilentlyContinue) {
    throw 'Close the current Beast Unity app (Esc or Q) before starting this demo.'
}
if (Get-NetTCPConnection -State Listen -LocalPort 8765 -ErrorAction SilentlyContinue) {
    throw 'Stop the current live server before switching modes. Do not open one camera twice.'
}
$player = $null
$observer = $null
Push-Location $root
try {
    if ($Mode -eq 'Live') {
        $launch = & ./scripts/run_beast_unity.ps1 -Beast
        $launch | Write-Output
        $playerLine = $launch | Where-Object { $_ -match '^Player PID: (\d+)$' }
        if ($playerLine -match '^Player PID: (\d+)$') { $player = Get-Process -Id ([int]$Matches[1]) }
        $main = Split-Path -Parent (Split-Path -Parent $root)
        $weights = Join-Path $main 'models/yolo/driver_standard_model/best-3.pt'
        Write-Host 'Normal 2D + 0DoF. Browser: http://127.0.0.1:8765/supervisor.html'
        Write-Host 'Enable video in the browser. Ctrl+C stops the live session.'
        & $python -u -X utf8 -B server/realtime/run_realtime_server.py --config configs/realtime_viture_beast_aruco.yaml --source camera --camera-index $CameraIndex --weights $weights
    } else {
        foreach ($file in @($camera,$workspace,$candidate,$startPoint)) {
            if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Missing profile: $file" }
        }
        $stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
        $out = Join-Path $logRoot "sbs-$stamp.out.log"
        $err = Join-Path $logRoot "sbs-$stamp.err.log"
        $arguments = @('-u','-X','utf8','-B','-m','server.realtime.display_observation_server',
            '--camera-profile',('"' + $camera + '"'),'--workspace-profile',('"' + $workspace + '"'),
            '--camera-index',"$CameraIndex",'--seconds','45','--preview')
        $observer = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
        $config = $null
        for ($i = 0; $i -lt 40; $i++) {
            if ($observer.HasExited) { throw "Camera server exited. Read $err" }
            if (Test-Path -LiteralPath $out) {
                $line = Get-Content -LiteralPath $out | Where-Object { $_ -like 'Client config: *' } | Select-Object -First 1
                if ($line) { $config = $line.Substring('Client config: '.Length).Trim(); break }
            }
            Start-Sleep -Milliseconds 250
        }
        if (-not $config) { throw "Observation server startup timed out. Read $err" }
        Write-Host 'EXPERIMENTAL A RING: Full SBS + 0DoF, unchanged fit and workspace.'
        Write-Host 'Focus Beast Assembly Guide, then Space to start. Q stops. Maximum 30 seconds.'
        $launch = & ./scripts/run_beast_unity.ps1 -Beast -StereoAlignmentProbe -ProbeSeconds 30 -DisplayObservationConfig $config -StereoStartPoint $startPoint -CandidateProjection $candidate
        $launch | Write-Output
        $playerLine = $launch | Where-Object { $_ -match '^Player PID: (\d+)$' }
        if ($playerLine -match '^Player PID: (\d+)$') {
            $player = Get-Process -Id ([int]$Matches[1])
            $null = $player.WaitForExit(40000)
        }
    }
} finally {
    if ($player -and -not $player.HasExited) { $player.Kill(); $player.WaitForExit() }
    if ($observer -and -not $observer.HasExited) {
        Write-Host 'Waiting for the bounded camera session to close...'
        if (-not $observer.WaitForExit(60000)) { Write-Warning 'Camera helper has not exited. Close its preview with Q before restarting.' }
    }
    Pop-Location
}
