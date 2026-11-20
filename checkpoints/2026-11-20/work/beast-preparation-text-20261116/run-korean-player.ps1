[CmdletBinding()]
param(
    [switch]$Beast,
    [switch]$TestRing,
    [switch]$AlignmentProbe,
    [switch]$StereoAlignmentProbe,
    [switch]$SbsGuidance,
    [ValidateRange(0,5000)][int]$ObservedCueDelayMs = 0,
    [string]$UnityOutputDirectory,
    [switch]$CandidatePresentation,
    [switch]$StageTargets,
    [switch]$StageContext,
    [string]$BoxOutlineConfig,
    [switch]$TrialARight,
    [string]$StageDepthConfig,
    [switch]$CandidateCorners,
    [switch]$TrackedAlignment,
    [switch]$TrialDLeftUp,
    [string[]]$DDepthRecords,
    [string[]]$CDepthRecords,
    [string]$SpatialPreviewConfig,
    [string]$DisplayObservationConfig,
    [string]$StereoStartPoint,
    [string]$CandidateProjection,
    [string]$StateUrl = "http://127.0.0.1:8765/state.json",
    [switch]$PassThru,
    [ValidateRange(1, 600)][int]$ProbeSeconds = 180
)
$ErrorActionPreference = "Stop"
if ($ProbeSeconds -gt 300 -and !$TrackedAlignment) { throw "Only tracked eye alignment permits up to 600 seconds." }
if ($PSBoundParameters.ContainsKey('DDepthRecords') -and $PSBoundParameters.ContainsKey('CDepthRecords')) { throw "Choose one depth trial target." }
if ($PSBoundParameters.ContainsKey('DDepthRecords') -or $PSBoundParameters.ContainsKey('CDepthRecords')) {
    $depthRecords = if ($PSBoundParameters.ContainsKey('CDepthRecords')) { $CDepthRecords } else { $DDepthRecords }
    if ($depthRecords.Count -ne 3 -or !$Beast -or !$StereoAlignmentProbe -or !$CandidateProjection -or !$DisplayObservationConfig -or
        $TrackedAlignment -or $TrialDLeftUp -or $CandidateCorners -or $StereoStartPoint -or $CandidatePresentation) {
        throw "Depth trial requires three near-to-far records and a read-only single-target candidate stereo probe."
    }
    $depthRecords = @($depthRecords | ForEach-Object { (Resolve-Path -LiteralPath $_).Path })
}
if ($TrialDLeftUp -and !$TrackedAlignment) { throw "TrialDLeftUp requires a D tracked alignment probe." }
if ($TrialARight -and !$StageTargets) { throw "TrialARight requires StageTargets." }
if ($StageDepthConfig) {
    if (!$StageTargets) { throw "StageDepthConfig requires StageTargets." }
    $StageDepthConfig = (Resolve-Path -LiteralPath $StageDepthConfig).Path
}
if ($StageTargets -and -not $CandidatePresentation) { throw "StageTargets requires CandidatePresentation." }
if ($StageContext -and (!$StageTargets -or !$UnityOutputDirectory -or $TrialARight -or $StageDepthConfig)) {
    throw 'StageContext requires StageTargets, an explicit trial build and no legacy offsets.'
}
if ($BoxOutlineConfig) {
    if (!$StageContext) { throw 'BoxOutlineConfig requires StageContext and an explicit trial build.' }
    $BoxOutlineConfig = (Resolve-Path -LiteralPath $BoxOutlineConfig).Path
}
if ($TrackedAlignment -and (-not $Beast -or -not $StereoAlignmentProbe -or -not $CandidateProjection -or
    -not $DisplayObservationConfig -or $CandidateCorners -or $StereoStartPoint -or $CandidatePresentation)) {
    throw "TrackedAlignment requires a single candidate stereo probe and observation config, without corners/start point/presentation."
}
if ($CandidateCorners -and (-not $Beast -or -not $StereoAlignmentProbe -or -not $CandidateProjection)) {
    throw "CandidateCorners requires -Beast -StereoAlignmentProbe -CandidateProjection."
}
if ($StateUrl -notmatch '^http://127\.0\.0\.1:([0-9]+)/state\.json$' -or
    [int]$Matches[1] -lt 1 -or [int]$Matches[1] -gt 65535) { throw "StateUrl must be local." }
$sbs = $SbsGuidance -or [bool]$SpatialPreviewConfig -or $CandidatePresentation
if ($ObservedCueDelayMs -gt 0 -and (!$sbs -or !$UnityOutputDirectory)) {
    throw 'Cue delay trial requires SBS guidance and an explicit UnityOutputDirectory.'
}
if ($CandidatePresentation -and (-not $Beast -or -not $CandidateProjection -or -not $DisplayObservationConfig -or
    $SpatialPreviewConfig -or $StereoStartPoint)) {
    throw "CandidatePresentation requires -Beast, candidate and live observation config, without preview/start point."
}
if (([int]$TestRing.IsPresent + [int]$AlignmentProbe.IsPresent + [int]$StereoAlignmentProbe.IsPresent + [int]$sbs) -gt 1) {
    throw "Choose only one probe mode."
}
if ($SpatialPreviewConfig) {
    if ($Beast) { throw "Synthetic preview is laptop-only." }
    if (-not (Test-Path -LiteralPath $SpatialPreviewConfig -PathType Leaf)) { throw "Preview config not found." }
    $SpatialPreviewConfig = (Resolve-Path -LiteralPath $SpatialPreviewConfig).Path
    if ($SpatialPreviewConfig.StartsWith('\\') -or (Get-Item -LiteralPath $SpatialPreviewConfig).Length -gt 65536) {
        throw "Preview config must be a small local JSON file."
    }
}
if ($StereoAlignmentProbe -and -not $Beast) { throw "StereoAlignmentProbe requires -Beast." }
if ($StereoStartPoint) {
    if (-not ($Beast -and $StereoAlignmentProbe)) { throw "StereoStartPoint requires -Beast -StereoAlignmentProbe." }
    if (-not (Test-Path -LiteralPath $StereoStartPoint -PathType Leaf)) { throw "Start point not found." }
    $StereoStartPoint = (Resolve-Path -LiteralPath $StereoStartPoint).Path
    if ($StereoStartPoint.StartsWith('\\') -or (Get-Item -LiteralPath $StereoStartPoint).Length -gt 65536) {
        throw "Start point must be a small local JSON file."
    }
}
if ($DisplayObservationConfig) {
    if (-not ($Beast -and ($StereoAlignmentProbe -or $CandidatePresentation))) {
        throw "DisplayObservationConfig requires -Beast and a stereo probe or candidate presentation."
    }
    if (-not (Test-Path -LiteralPath $DisplayObservationConfig -PathType Leaf)) { throw "Observation config not found." }
    $DisplayObservationConfig = (Resolve-Path -LiteralPath $DisplayObservationConfig).Path
}
$root = 'C:/Users/fresh/OneDrive/Desktop/홍익대/4학년/2학기/vision/01_SUBMIT_KEEP/AR-assembly-psr_github_main_20260604/.worktrees/viture-beast-overlay-mvp'
if ($CandidateProjection) {
    if (-not $CandidatePresentation) {
        if (-not $PSBoundParameters.ContainsKey('ProbeSeconds') -and -not $TrackedAlignment) { $ProbeSeconds = 30 }
        if ($ProbeSeconds -gt 30 -and -not $TrackedAlignment) { throw "CandidateProjection is limited to 30 seconds." }
    }
    if (-not ($Beast -and ($StereoAlignmentProbe -or $CandidatePresentation) -and $DisplayObservationConfig)) {
        throw "CandidateProjection requires -Beast, live observation config and a candidate mode."
    }
    if (-not (Test-Path -LiteralPath $CandidateProjection -PathType Leaf)) { throw "Candidate profile not found." }
    $CandidateProjection = (Resolve-Path -LiteralPath $CandidateProjection).Path
    if ($CandidateProjection.StartsWith('\\') -or (Get-Item -LiteralPath $CandidateProjection).Length -gt 65536) {
        throw "Candidate must be a small local JSON file."
    }
}
$output = if ($UnityOutputDirectory) { (Resolve-Path -LiteralPath $UnityOutputDirectory).Path }
          else { Join-Path $root "outputs\unity_p1" }
$exe = Join-Path $output "BeastAssemblyGuide.exe"
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw "Build first with scripts\build_beast_unity.ps1."
}
$log = Join-Path $output ("player-" + (Get-Date -Format "yyyyMMdd-HHmmss-fff") + ".log")
$arguments = @("-screen-fullscreen", "0", "-screen-width", "1280", "-screen-height", "720",
    "-logFile", ('"' + $log + '"'), "--state-url", $StateUrl)
if ($Beast) { $arguments += @("--display-name", "VITURE") }
if (!$sbs -or !$Beast) { throw 'Korean comparison requires Beast SBS guidance.' }
if ($sbs) { $arguments += @('--sbs-guidance', '--action-korean') }
if ($ObservedCueDelayMs -gt 0) { $arguments += @("--observed-cue-delay-ms", "$ObservedCueDelayMs") }
if ($CandidatePresentation) { $arguments += "--candidate-presentation" }
if ($StageTargets) { $arguments += "--stage-targets" }
if ($StageContext) { $arguments += "--stage-context" }
if ($BoxOutlineConfig) { $arguments += @('--box-outline-config', ('"' + $BoxOutlineConfig + '"')) }
if ($TrialARight) { $arguments += "--trial-a-right" }
if ($StageDepthConfig) { $arguments += @("--stage-depth-config", ('"' + $StageDepthConfig + '"')) }
if ($SpatialPreviewConfig) { $arguments += @("--spatial-preview-config", ('"' + $SpatialPreviewConfig + '"')) }
if ($TestRing) { $arguments += "--test-ring" }
if ($AlignmentProbe) { $arguments += @("--alignment-probe", "--probe-seconds", "$ProbeSeconds") }
if ($StereoAlignmentProbe) { $arguments += @("--stereo-alignment-probe", "--probe-seconds", "$ProbeSeconds") }
if ($CandidateCorners) { $arguments += "--candidate-corners" }
if ($TrackedAlignment) { $arguments += "--tracked-alignment" }
if ($TrialDLeftUp) { $arguments += "--trial-d-left-up" }
if ($depthRecords) {
    $arguments += if ($CDepthRecords) { "--c-depth-records" } else { "--d-depth-records" }
    $arguments += @($depthRecords | ForEach-Object { '"' + $_ + '"' })
}
if ($DisplayObservationConfig) { $arguments += @("--display-observation-config", ('"' + $DisplayObservationConfig + '"')) }
if ($StereoStartPoint) { $arguments += @("--stereo-start-point", ('"' + $StereoStartPoint + '"')) }
if ($CandidateProjection) { $arguments += @("--candidate-projection", ('"' + $CandidateProjection + '"')) }
# This is the visible client the user is testing, not a background helper.
$process = Start-Process -FilePath $exe -ArgumentList $arguments -WorkingDirectory $root -PassThru
Write-Host "Player PID: $($process.Id)"
Write-Host "Log: $log"
if ($PassThru) { $process }
