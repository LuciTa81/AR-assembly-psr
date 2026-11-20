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
    [switch]$ReleaseAbsenceTrial,
    [switch]$CompletedHoldCheckpointTrial,
    [switch]$HandleLinkedDriverTrial,
    [switch]$ReleaseRecoveryTrial,
    [switch]$StageContextTrial,
    [switch]$BoxOutlineTrial,
    [switch]$RoundedBoxTrial,
    [ValidateSet('dim', 'uniform', 'focused', 'lid-prism')][string]$RoundedBoxStyle = 'dim',
    [ValidateSet('original', 'brighter')][string]$StageContextStyle = 'original',
    [ValidateRange(0,5000)][int]$ObservedCueDelayMs = 0,
    [string]$UnityOutputDirectory,
    [ValidateRange(0,1000)][int]$ScrewResumeMs = 0,
    [ValidateRange(0,3000)][int]$CompletedHoldResumeMs = 0,
    [ValidateSet("S3", "S6")][string]$ScrewAutoEndState = "S3",
    [ValidateRange(0,600)][int]$DurationSeconds = 0,
    [int]$CameraIndex = 0,
    [ValidateRange(1024, 65535)][int]$Port = 8765,
    [switch]$CheckOnly,
    [switch]$Managed,
    [string]$ExternalStopFile,
    [string]$ManagedRunFolder,
    [switch]$NoBrowser
)
$ErrorActionPreference = "Stop"
$trialRoot = 'C:/Users/fresh/Documents/Codex/beast-reference-return-20261114'
if ($DurationSeconds -ne 180 -or !$ReleaseRecoveryTrial -or
    !$StageContextTrial -or !$RoundedBoxTrial -or $RoundedBoxStyle -ne 'lid-prism') {
    throw 'Korean guidance requires the verified full-flow configuration.'
}
if ($Managed -and (!$AssemblyFlow -or !$ExternalStopFile -or !$ManagedRunFolder -or !$NoBrowser)) {
    throw 'Managed sessions require full flow, owned run folder, stop signal and NoBrowser.'
}
if (!$Managed -and ($ExternalStopFile -or $ManagedRunFolder)) { throw 'Managed arguments require Managed.' }
if ($ReleaseRecoveryTrial -and (!$AssemblyFlow -or !$HandleLinkedDriverTrial -or $CompletedHoldResumeMs -lt 2000)) {
    throw 'Release recovery requires the verified full flow with a 2000 ms completed HOLD recovery budget.'
}
if ($BoxOutlineTrial -and !$StageContextTrial) { throw 'BoxOutlineTrial requires StageContextTrial.' }
if ($RoundedBoxTrial -and !$BoxOutlineTrial) { throw 'RoundedBoxTrial requires BoxOutlineTrial.' }
if ($PSBoundParameters.ContainsKey('RoundedBoxStyle') -and !$RoundedBoxTrial) {
    throw 'RoundedBoxStyle requires RoundedBoxTrial.'
}
if ($PSBoundParameters.ContainsKey('StageContextStyle') -and !$StageContextTrial) {
    throw 'StageContextStyle requires StageContextTrial.'
}
if ($StageContextTrial -and (!$AssemblyFlow -or !$HandleLinkedDriverTrial -or
    !$CandidateProjection -or $TrialARight -or $StageDepthConfig)) {
    throw 'Stage context requires the verified full-flow candidate without legacy offsets.'
}
if ($HandleLinkedDriverTrial -and (!$CompletedHoldCheckpointTrial -or !$NestedDriverDedup)) {
    throw 'Single-tool trial requires the checkpoint candidate and nested-driver deduplication.'
}
if ($CompletedHoldCheckpointTrial -and (!$ReleaseAbsenceTrial -or !$UnityOutputDirectory -or $CompletedHoldResumeMs -le 0)) {
    throw 'Checkpoint trial requires ReleaseAbsenceTrial, the reviewed candidate Unity build, and a bounded completed HOLD resume budget.'
}
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
    $list = Get-Content -Raw -Encoding UTF8 -LiteralPath $StageDepthConfig | ConvertFrom-Json
    $base = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'ARAssembly/beast-mvp/display_correspondence'
    foreach ($target in 'c','d') {
        if ($list.$target.Count -ne 3) { throw "Expected three records for $target." }
        foreach ($name in $list.$target) {
            if ($name -notmatch '^[a-f0-9]{32}/diagnostic-frame-[0-9]+\.json$' -or
                !(Test-Path -LiteralPath (Join-Path $base $name) -PathType Leaf)) { throw "Missing or invalid $target record." }
        }
    }
}
$root = 'C:/Users/fresh/OneDrive/Desktop/홍익대/4학년/2학기/vision/01_SUBMIT_KEEP/AR-assembly-psr_github_main_20260604/.worktrees/viture-beast-overlay-mvp'
if ($AssemblyFlow) {
    if (!$HandleLinkedDriverTrial -or $DurationSeconds -le 0 -or $DurationSeconds -gt 300) {
        throw 'Full flow requires the single-tool candidate and a duration of 1..300 seconds.'
    }
} elseif (!$ScrewAutoTrial -or $ScrewAutoEndState -ne 'S6' -or
    $DurationSeconds -le 0 -or $DurationSeconds -gt 90) {
    throw 'This isolated D trial requires ScrewAutoTrial, end S6, and a duration of 1..90 seconds.'
}
$protected = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $trialRoot 'poll-protected-hashes-after.json') | ConvertFrom-Json
foreach ($item in $protected) {
    if ((Get-FileHash -LiteralPath $item.Path -Algorithm SHA256).Hash -ne $item.Hash) {
        throw "Protected baseline or calibration changed: $($item.Path)"
    }
}
$Python = (Resolve-Path -LiteralPath $Python).Path
$PresentationConfig = (Resolve-Path -LiteralPath $PresentationConfig).Path
$config = Join-Path $root "configs/realtime_viture_beast_aruco.yaml"
$trialName = if ($ReleaseAbsenceTrial) { 'release-absence-D' } else { 'neutral-D' }
$runnerName = if ($ReleaseAbsenceTrial) { 'run_release_absence_d_server.py' } else { 'run_neutral_d_server.py' }
if ($CompletedHoldCheckpointTrial) {
    $trialName = 'checkpoint-D'
    $runnerName = 'run_completed_hold_d_server.py'
}
if ($HandleLinkedDriverTrial) {
    $trialName = 'handle-linked-D'
    $runnerName = 'run_handle_linked_d_server.py'
}
if ($AssemblyFlow) {
    $trialName = 'handle-linked-flow'
    $runnerName = 'run_handle_linked_flow_server.py'
}
if ($StageContextTrial) {
    $trialName = if ($StageContextStyle -eq 'brighter') { 'context-overlay-brighter-flow' } else { 'context-overlay-flow' }
}
if ($BoxOutlineTrial) { $trialName = 'box-outline-flow' }
if ($RoundedBoxTrial) { $trialName = 'rounded-box-flow' }
if ($RoundedBoxTrial -and $RoundedBoxStyle -eq 'uniform') { $trialName = 'uniform-box-flow' }
if ($RoundedBoxTrial -and $RoundedBoxStyle -eq 'focused') { $trialName = 'focused-box-flow' }
if ($RoundedBoxTrial -and $RoundedBoxStyle -eq 'lid-prism') { $trialName = 'lid-prism-flow' }
if ($ReleaseRecoveryTrial) {
    $runnerName = 'run_release_recovery_flow_server.py'
    $trialName += '-release-recovery'
}
$trialName = if ($Managed) { 'korean-action-flow' } else { 'korean-action-A-B' }
$runner = Join-Path $trialRoot $runnerName
$filmingOption = Join-Path $PSScriptRoot 'filming-auto-advance.json'
$filming = (Test-Path -LiteralPath $filmingOption) -and
    ((Get-Content -Raw -LiteralPath $filmingOption | ConvertFrom-Json).enabled -eq $true)
$previousFilmingLog = $env:AR_FILMING_PLAYER_LOG
if ($filming) {
    $runner = Join-Path $trialRoot 'run_filming_green_server.py'
    $env:AR_FILMING_PLAYER_LOG = if ($Managed) { Join-Path $ManagedRunFolder 'filming-player.log' }
        else { Join-Path $PSScriptRoot ('filming-player-' + [guid]::NewGuid().ToString('N') + '.log') }
    if (Test-Path -LiteralPath $env:AR_FILMING_PLAYER_LOG) { throw 'Filming requires a new player log.' }
}
$unityOutput = if ($UnityOutputDirectory) { (Resolve-Path -LiteralPath $UnityOutputDirectory).Path }
               else { Join-Path $root "outputs/unity_p1" }
$exe = Join-Path $unityOutput "BeastAssemblyGuide.exe"
$dll = Join-Path $unityOutput 'BeastAssemblyGuide_Data/Managed/Assembly-CSharp.dll'
$expectedDllHash = if ($CompletedHoldCheckpointTrial) { 'BA3A43B347836F9FFD850F7BDACBAB2CB3B56D2D7CC34336E78646A1E84DD097' }
                   else { '61EB05BA62D69FEB344743371A5BCCEF03881C2E8188522DFE6CD28014D5938A' }
if ($StageContextTrial) {
    $buildName = if ($StageContextStyle -eq 'brighter') { 'context-overlay-brighter-build' } else { 'context-overlay-build' }
    if ($BoxOutlineTrial) { $buildName = 'box-outline-build' }
    if ($RoundedBoxTrial) { $buildName = 'rounded-box-build' }
    if ($RoundedBoxTrial -and $RoundedBoxStyle -eq 'uniform') { $buildName = 'uniform-box-build' }
    if ($RoundedBoxTrial -and $RoundedBoxStyle -eq 'focused') { $buildName = 'focused-box-build' }
    if ($RoundedBoxTrial -and $RoundedBoxStyle -eq 'lid-prism') { $buildName = 'lid-prism-build' }
    $verified = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $trialRoot ($buildName + '-verified.json')) | ConvertFrom-Json
    $expectedOutput = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot 'player-v2')).Path
    if ($unityOutput -ne $expectedOutput -or $verified.dll_sha256 -notmatch '^[A-F0-9]{64}$') {
        throw 'Stage context must use the separately verified visual trial build.'
    }
    $baselineDll = Join-Path $trialRoot 'checkpoint-text-build/BeastAssemblyGuide_Data/Managed/Assembly-CSharp.dll'
    if ((Get-FileHash -LiteralPath $baselineDll).Hash -ne $expectedDllHash) { throw 'Successful player changed.' }
    $previousDll = Join-Path $trialRoot 'lid-prism-build/BeastAssemblyGuide_Data/Managed/Assembly-CSharp.dll'
    if ((Get-FileHash -LiteralPath $previousDll).Hash -ne $verified.dll_sha256) { throw 'Successful visual player changed.' }
    $expectedDllHash = 'C41B49184B63CBB4DD73C5267822A045C052124D23651B7785EB7E2631ECE963'
    if ($BoxOutlineTrial) {
        $boxOutlineConfig = Join-Path $trialRoot 'box-outline-124mm/box-outline-124mm.json'
        if ($RoundedBoxTrial) { $boxOutlineConfig = Join-Path $trialRoot 'rounded-box-124mm.json' }
        if ($verified.box_profile_sha256 -notmatch '^[A-F0-9]{64}$' -or
            (Get-FileHash -LiteralPath $boxOutlineConfig).Hash -ne $verified.box_profile_sha256) {
            throw 'Box outline geometry changed; verify before running.'
        }
    }
}
if ((Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash -ne $expectedDllHash) {
    throw 'Trial Unity build changed; verify before running.'
}
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw "Build Unity first." }
if ($CandidateProjection) {
    $CandidateProjection = (Resolve-Path -LiteralPath $CandidateProjection).Path
    if ($CandidateProjection.StartsWith('\\') -or (Get-Item -LiteralPath $CandidateProjection).Length -gt 65536) {
        throw "Candidate must be a small local JSON file."
    }
    $candidate = Get-Content -Encoding UTF8 -LiteralPath $CandidateProjection -Raw | ConvertFrom-Json
    $profiles = Get-Content -Encoding UTF8 -LiteralPath $PresentationConfig -Raw | ConvertFrom-Json
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
if ($LASTEXITCODE -ne 0) {
    $env:AR_FILMING_PLAYER_LOG = $previousFilmingLog
    throw "Preflight failed; no camera or Unity started."
}
if ($CheckOnly) {
    $env:AR_FILMING_PLAYER_LOG = $previousFilmingLog
    Write-Output "Preflight passed. Hardware and optical alignment NOT tested."
    return
}

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
$folder = if ($Managed) { (Resolve-Path -LiteralPath $ManagedRunFolder).Path }
          else { Join-Path $PSScriptRoot ($trialName + "-runs/" + [guid]::NewGuid().ToString("N")) }
New-Item -ItemType Directory -Path $folder -Force | Out-Null
$stopFile = Join-Path $folder "stop"
$arguments = @($common + @("--port", "$Port", "--stop-file", $stopFile)) | ForEach-Object { '"' + $_ + '"' }
$server = $player = $null
try {
    if ($Managed -and (Test-Path -LiteralPath $ExternalStopFile)) { return }
    $timer = [Diagnostics.Stopwatch]::StartNew()
    $server = Start-Process -FilePath $Python -ArgumentList $arguments -WorkingDirectory $root -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $folder "server.log") -RedirectStandardError (Join-Path $folder "server-error.log")
    $ready = $false
    for ($i = 0; $i -lt 100; $i++) {
        if ($Managed -and (Test-Path -LiteralPath $ExternalStopFile)) { return }
        if ($server.HasExited) { throw "Server exited. See $folder" }
        try {
            $state = Invoke-RestMethod "$url/state.json" -TimeoutSec 1
            $startup = Get-Content -Encoding UTF8 -LiteralPath (Join-Path $folder "server.log") -Raw
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
        $binding = Get-Content -Encoding UTF8 -LiteralPath $observation -Raw | ConvertFrom-Json
        if ($binding.session_id -ne $ownedSession -or $binding.camera_profile_sha256 -ne $candidate.camera_profile_sha256 -or
            $binding.workspace_profile_sha256 -ne $candidate.workspace_profile_sha256) { throw "Observation session/profile mismatch." }
        $launch.CandidatePresentation=$true
        $launch.StageTargets=$true
        $launch.StageContext=$StageContextTrial.IsPresent
        if ($BoxOutlineTrial) { $launch.BoxOutlineConfig=$boxOutlineConfig }
        $launch.TrialARight=$TrialARight.IsPresent
        if ($StageDepthConfig) { $launch.StageDepthConfig=$StageDepthConfig }
        $launch.CandidateProjection=$CandidateProjection
        $launch.DisplayObservationConfig=$observation
    }
    $expectedState = if ($AssemblyFlow) { 'S0' } else { 'S5' }
    if ($state.current_state -ne $expectedState) { throw "Expected $expectedState before launching the player." }
    if ($Managed -and (Test-Path -LiteralPath $ExternalStopFile)) { return }
    $player = & (Join-Path $PSScriptRoot 'run-korean-player.ps1') @launch
    @{ folder=$folder; url=$url; server_pid=$server.Id; player_pid=$player.Id; session=$ownedSession } |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot ($trialName + '-current-run.json')) -Encoding UTF8
    if ($Managed) {
        @{ url=$url; session=$ownedSession } | ConvertTo-Json |
            Set-Content -LiteralPath (Join-Path $folder 'session.tmp') -Encoding UTF8
        Move-Item -LiteralPath (Join-Path $folder 'session.tmp') -Destination (Join-Path $folder 'session.json')
    }
    if (!$NoBrowser) { Start-Process -FilePath 'C:/Program Files/Google/Chrome/Application/chrome.exe' -ArgumentList "$url/supervisor.html" }
    $endLabel = if ($Managed) { 'S6 (operator stop)' } else { 'S3' }
    Write-Host "$trialName $expectedState -> ${endLabel}: $url/supervisor.html"
    Write-Host "No image saving. Close the Unity window or press Ctrl+C here to stop."
    while (-not $player.HasExited -and -not $server.HasExited -and
           ($Managed -or !$DurationSeconds -or $timer.Elapsed.TotalSeconds -lt $DurationSeconds)) {
        if ($Managed -and (Test-Path -LiteralPath $ExternalStopFile)) { break }
        Start-Sleep -Milliseconds 300
        try {
            $current = Invoke-RestMethod "$url/state.json" -TimeoutSec 1
            $finished = $current.current_state -in @('S3', 'S4', 'S5', 'S6')
            if (!$Managed -and $current.session_id -eq $ownedSession -and $finished) {
                Write-Host 'Trial reached its completion condition; ending trial.'
                Start-Sleep -Seconds 3
                break
            }
        } catch { }
    }
} finally {
    $env:AR_FILMING_PLAYER_LOG = $previousFilmingLog
    if ($player -and -not $player.HasExited) { Stop-Process -Id $player.Id }
    if ($server -and -not $server.HasExited) {
        New-Item -ItemType File -Path $stopFile -Force | Out-Null
        $null = $server.WaitForExit(5000)
    }
    if ($server -and -not $server.HasExited) {
        # The venv Python launcher can own a child interpreter; stop only this owned tree.
        & taskkill.exe /PID $server.Id /T /F | Out-Null
    }
}
