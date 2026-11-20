[CmdletBinding()]
param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
$options = @{
    Python = 'C:/Users/fresh/AppData/Local/ARAssembly/beast-mvp/.venv/Scripts/python.exe'
    PresentationConfig = 'C:/Users/fresh/Documents/Codex/beast-pose-continuation-20261116/presentation-rms32.json'
    CandidateProjection = 'C:/Users/fresh/Documents/Codex/beast-reference-return-20261114/candidate-ABCD-joint-unverified.json'
    UnityOutputDirectory = (Join-Path $PSScriptRoot 'player')
    NestedDriverDedup = $true
    SourceRecoveryBoundary = $true
    ReleaseAbsenceTrial = $true
    CompletedHoldCheckpointTrial = $true
    HandleLinkedDriverTrial = $true
    ReleaseRecoveryTrial = $true
    AssemblyFlow = $true
    StageContextTrial = $true
    BoxOutlineTrial = $true
    RoundedBoxTrial = $true
    RoundedBoxStyle = 'lid-prism'
    ObservedCueDelayMs = 2000
    ScrewResumeMs = 600
    CompletedHoldResumeMs = 2000
    DurationSeconds = 300
    CameraIndex = 0
}
& (Join-Path $PSScriptRoot 'run-korean-trial.ps1') @options -CheckOnly:$CheckOnly
