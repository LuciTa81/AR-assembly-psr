[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Python,
    [Parameter(Mandatory)][string]$PresentationConfig,
    [string]$CandidateProjection,
    [switch]$TrialARight,
    [string]$StageDepthConfig,
    [switch]$ScrewAutoTrial,
    [switch]$AssemblyFlow,
    [switch]$NestedDriverDedup,
    [switch]$SourceRecoveryBoundary,
    [ValidateRange(0,5000)][int]$ObservedCueDelayMs = 0,
    [string]$UnityOutputDirectory,
    [ValidateRange(0,1000)][int]$ScrewResumeMs = 0,
    [ValidateRange(0,3000)][int]$CompletedHoldResumeMs = 0,
    [ValidateSet("S3", "S6")][string]$ScrewAutoEndState = "S3",
    [ValidateRange(0,600)][int]$DurationSeconds = 0,
    [int]$CameraIndex = 0,
    [ValidateRange(1024, 65535)][int]$Port = 8765,
    [switch]$CheckOnly
)
$ErrorActionPreference = "Stop"
if ($ObservedCueDelayMs -gt 0 -and !$UnityOutputDirectory) { throw 'Cue delay trial requires an explicit UnityOutputDirectory.' }
if ($NestedDriverDedup -and !$AssemblyFlow -and !$ScrewAutoTrial) {
    throw 'NestedDriverDedup requires AssemblyFlow or ScrewAutoTrial.'
}
if ($ScrewResumeMs -gt 0 -and !$AssemblyFlow -and !$ScrewAutoTrial) {
    throw 'ScrewResumeMs requires AssemblyFlow or ScrewAutoTrial.'
}
if ($CompletedHoldResumeMs -gt 0 -and !$AssemblyFlow -and !$ScrewAutoTrial) {
    throw 'CompletedHoldResumeMs requires AssemblyFlow or ScrewAutoTrial.'
}
if ($SourceRecoveryBoundary -and !$AssemblyFlow -and !$ScrewAutoTrial) {
    throw 'SourceRecoveryBoundary requires AssemblyFlow or ScrewAutoTrial.'
}
if ($AssemblyFlow -and ($ScrewAutoTrial -or !$CandidateProjection -or $DurationSeconds -le 0)) {
    throw "AssemblyFlow requires CandidateProjection and bounded DurationSeconds, without ScrewAutoTrial."
}
if ($PSBoundParameters.ContainsKey('ScrewAutoEndState') -and !$ScrewAutoTrial) {
    throw "ScrewAutoEndState requires ScrewAutoTrial."
}
if ($ScrewAutoTrial -and (!$CandidateProjection -or $DurationSeconds -le 0)) {
    throw "ScrewAutoTrial requires CandidateProjection and a bounded DurationSeconds."
}
if ($TrialARight -and !$CandidateProjection) { throw "TrialARight requires CandidateProjection." }
if ($StageDepthConfig) {
    if (!$CandidateProjection) { throw "StageDepthConfig requires CandidateProjection." }
    $StageDepthConfig = (Resolve-Path -LiteralPath $StageDepthConfig).Path
    $list = Get-Content -Raw -LiteralPath $StageDepthConfig | ConvertFrom-Json
    $base = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'ARAssembly/beast-mvp/display_correspondence'
    foreach ($target in 'c','d') {
        if ($list.$target.Count -ne 3) { throw "Expected three records for $target." }
        foreach ($name in $list.$target) {
            if ($name -notmatch '^[a-f0-9]{32}/diagnostic-frame-[0-9]+\.json$' -or
                !(Test-Path -LiteralPath (Join-Path $base $name) -PathType Leaf)) { throw "Missing or invalid $target record." }
        }
    }
}
$root = Split-Path -Parent $PSScriptRoot
$Python = (Resolve-Path -LiteralPath $Python).Path
$PresentationConfig = (Resolve-Path -LiteralPath $PresentationConfig).Path
$config = Join-Path $root "configs/realtime_viture_beast_aruco.yaml"
$runner = Join-Path $root "server/realtime/run_realtime_server.py"
$unityOutput = if ($UnityOutputDirectory) { (Resolve-Path -LiteralPath $UnityOutputDirectory).Path }
               else { Join-Path $root "outputs/unity_p1" }
$exe = Join-Path $unityOutput "BeastAssemblyGuide.exe"
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw "Build Unity first." }
if ($CandidateProjection) {
    $CandidateProjection = (Resolve-Path -LiteralPath $CandidateProjection).Path
    if ($CandidateProjection.StartsWith('\\') -or (Get-Item -LiteralPath $CandidateProjection).Length -gt 65536) {
        throw "Candidate must be a small local JSON file."
    }
    $candidate = Get-Content -LiteralPath $CandidateProjection -Raw | ConvertFrom-Json
    $profiles = Get-Content -LiteralPath $PresentationConfig -Raw | ConvertFrom-Json
    if ($candidate.schema_version -cne 'beast_candidate_projection_probe_v1' -or
        $candidate.candidate_only -isnot [bool] -or !$candidate.candidate_only -or
        $candidate.calibration_valid -isnot [bool] -or $candidate.calibration_valid -or
        $candidate.display_alignment_verified -isnot [bool] -or $candidate.display_alignment_verified -or
        $candidate.camera_profile_sha256 -ne (Get-FileHash -LiteralPath $profiles.camera_profile).Hash -or
        $candidate.workspace_profile_sha256 -ne (Get-FileHash -LiteralPath $profiles.workspace_profile).Hash) {
        throw "Unverified candidate bound to the same camera and workspace profiles required."
    }
}
$mode = if ($AssemblyFlow) { "hybrid" } elseif ($ScrewAutoTrial) { "auto" } else { "operator" }
$common = @("-X", "utf8", "-B", "-u", $runner, "--config", $config,
    "--guidance-mode", $mode, "--source", "camera", "--camera-index", "$CameraIndex",
    "--presentation-config", $PresentationConfig, "--host", "127.0.0.1")
if ($ScrewAutoTrial) { $common += @("--screw-auto-trial", "--screw-auto-end-state", $ScrewAutoEndState) }
if ($ScrewResumeMs -gt 0) { $common += @('--screw-resume-ms', "$ScrewResumeMs") }
if ($CompletedHoldResumeMs -gt 0) { $common += @('--completed-hold-resume-ms', "$CompletedHoldResumeMs") }
if ($NestedDriverDedup) { $common += '--nested-driver-dedup' }
if ($SourceRecoveryBoundary) { $common += '--source-recovery-boundary' }
& $Python @common --doctor
if ($LASTEXITCODE -ne 0) { throw "Preflight failed; no camera or Unity started." }
if ($CheckOnly) { Write-Output "Preflight passed. Hardware and optical alignment NOT tested."; return }

# Reserve-check a local port without replacing another running service.
try {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
    $listener.Start()
} catch {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $listener.Start()
}
$Port = $listener.LocalEndpoint.Port
$listener.Stop()
$url = "http://127.0.0.1:$Port"
$folder = Join-Path $root ("outputs/demo/" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $folder | Out-Null
$stopFile = Join-Path $folder "stop"
$arguments = @($common + @("--port", "$Port", "--stop-file", $stopFile)) | ForEach-Object { '"' + $_ + '"' }
$server = $player = $null
try {
    $timer = [Diagnostics.Stopwatch]::StartNew()
    $server = Start-Process -FilePath $Python -ArgumentList $arguments -WorkingDirectory $root -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $folder "server.log") -RedirectStandardError (Join-Path $folder "server-error.log")
    $ready = $false
    for ($i = 0; $i -lt 100; $i++) {
        if ($server.HasExited) { throw "Server exited. See $folder" }
        try {
            $state = Invoke-RestMethod "$url/state.json" -TimeoutSec 1
            $startup = Get-Content -LiteralPath (Join-Path $folder "server.log") -Raw
            $ownedSession = [regex]::Match($startup, '\[INFO\] session_id=(\S+)').Groups[1].Value
            if ($ownedSession -and $state.session_id -eq $ownedSession -and
                (($ScrewAutoTrial -and $state.extra.screw_auto_trial -eq $true -and
                    $state.extra.screw_auto_end_state -eq $ScrewAutoEndState) -or
                 (!$ScrewAutoTrial -and $state.extra.operator.mode -eq $mode)) -and
                $state.frame_age_ms -ge 0 -and $state.frame_age_ms -lt 500) {
                $ready = $true
                break
            }
        } catch { }
        Start-Sleep -Milliseconds 200
    }
    if (-not $ready) { throw "No fresh camera input. See $folder" }
    $launch = @{ Beast=$true; SbsGuidance=$true; StateUrl="$url/state.json"; PassThru=$true }
    $launch.ObservedCueDelayMs = $ObservedCueDelayMs
    $launch.UnityOutputDirectory = $unityOutput
    if ($CandidateProjection) {
        # Use this server's own observation channel. Never open a second camera.
        $observation = [regex]::Match($startup, '(?m)^Presentation client config: ([^\r\n]+)').Groups[1].Value
        if (!$observation) { throw "Presentation observation channel missing. See $folder" }
        $binding = Get-Content -LiteralPath $observation -Raw | ConvertFrom-Json
        if ($binding.session_id -ne $ownedSession -or $binding.camera_profile_sha256 -ne $candidate.camera_profile_sha256 -or
            $binding.workspace_profile_sha256 -ne $candidate.workspace_profile_sha256) { throw "Observation session/profile mismatch." }
        $launch.CandidatePresentation=$true
        $launch.StageTargets=$true
        $launch.TrialARight=$TrialARight.IsPresent
        if ($StageDepthConfig) { $launch.StageDepthConfig=$StageDepthConfig }
        $launch.CandidateProjection=$CandidateProjection
        $launch.DisplayObservationConfig=$observation
    }
    $player = & (Join-Path $PSScriptRoot "run_beast_unity.ps1") @launch
    Start-Process "$url/supervisor.html"
    Write-Host "$mode guidance$(if ($ScrewAutoTrial) {" screw trial S2 -> $ScrewAutoEndState"}): $url/supervisor.html"
    Write-Host "No image saving. Close the Unity window or press Ctrl+C here to stop."
    while (-not $player.HasExited -and -not $server.HasExited -and
           (!$DurationSeconds -or $timer.Elapsed.TotalSeconds -lt $DurationSeconds)) { Start-Sleep -Milliseconds 300 }
} finally {
    if ($player -and -not $player.HasExited) { Stop-Process -Id $player.Id }
    if ($server -and -not $server.HasExited) {
        New-Item -ItemType File -Path $stopFile | Out-Null
        $null = $server.WaitForExit(5000)
    }
    if ($server -and -not $server.HasExited) {
        # The venv Python launcher can own a child interpreter; stop only this owned tree.
        & taskkill.exe /PID $server.Id /T /F | Out-Null
    }
}
