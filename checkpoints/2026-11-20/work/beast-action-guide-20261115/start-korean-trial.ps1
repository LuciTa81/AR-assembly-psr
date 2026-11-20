[CmdletBinding()]
param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
$root = 'C:/Users/fresh/OneDrive/Desktop/홍익대/4학년/2학기/vision/01_SUBMIT_KEEP/AR-assembly-psr_github_main_20260604/.worktrees/viture-beast-overlay-mvp'
$trial = 'C:/Users/fresh/Documents/Codex/beast-reference-return-20261114'
$options = @{
    Python = 'C:/Users/fresh/AppData/Local/ARAssembly/beast-mvp/.venv/Scripts/python.exe'
    PresentationConfig = (Join-Path $root 'outputs/demo/presentation.json')
    CandidateProjection = (Join-Path $trial 'candidate-ABCD-joint-unverified.json')
    NestedDriverDedup = $true
    SourceRecoveryBoundary = $true
    ReleaseAbsenceTrial = $true
    CompletedHoldCheckpointTrial = $true
    HandleLinkedDriverTrial = $true
    ReleaseRecoveryTrial = $true
    ObservedCueDelayMs = 2000
    UnityOutputDirectory = (Join-Path $PSScriptRoot 'player-v2')
    ScrewResumeMs = 600
    CompletedHoldResumeMs = 2000
    AssemblyFlow = $true
    StageContextTrial = $true
    BoxOutlineTrial = $true
    RoundedBoxTrial = $true
    RoundedBoxStyle = 'lid-prism'
    DurationSeconds = 180
    CameraIndex = 0
}
Add-Type -AssemblyName System.Windows.Forms
$screens = @([System.Windows.Forms.Screen]::AllScreens)
if ($screens.Count -lt 2 -or !($screens | Where-Object { $_.Bounds.Width -eq 3840 -and $_.Bounds.Height -eq 1080 })) {
    throw 'Full SBS 3840x1080 extended display is required. Camera not started.'
}
$busy = @(Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq 'BeastAssemblyGuide.exe' -or
    ($_.Name -match '^python(w)?\.exe$' -and $_.CommandLine -match 'run_(realtime|handle_linked_d|handle_linked_flow|release_recovery_flow)_server\.py')
})
if ($busy.Count) { throw 'Another assembly session is active. Camera not started.' }
Push-Location $root
try { & (Join-Path $PSScriptRoot 'run-korean-trial.ps1') @options -CheckOnly:$CheckOnly }
finally { Pop-Location }
