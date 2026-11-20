[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$ProjectRoot,
    [string]$Python = 'C:/Users/fresh/AppData/Local/ARAssembly/beast-mvp/.venv/Scripts/python.exe',
    [switch]$Live,
    [ValidateRange(1,300)][int]$DurationSeconds = 300
)
$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$candidate = Join-Path $PSScriptRoot 'candidate-ABCD-joint-unverified.json'
$unityOutput = Join-Path $PSScriptRoot 'poll-candidate-build'
$protected = Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'poll-protected-hashes-after.json') | ConvertFrom-Json
foreach ($item in $protected) {
    if ((Get-FileHash -LiteralPath $item.Path -Algorithm SHA256).Hash -ne $item.Hash) {
        throw "Protected baseline or calibration changed: $($item.Path)"
    }
}
$dll = Join-Path $unityOutput 'BeastAssemblyGuide_Data/Managed/Assembly-CSharp.dll'
if ((Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash -ne '61EB05BA62D69FEB344743371A5BCCEF03881C2E8188522DFE6CD28014D5938A') {
    throw 'Trial Unity build changed; verify it before running.'
}
$options = @{
    Python = $Python
    PresentationConfig = Join-Path $ProjectRoot 'outputs/demo/presentation.json'
    CandidateProjection = $candidate
    UnityOutputDirectory = $unityOutput
    AssemblyFlow = $true
    NestedDriverDedup = $true
    SourceRecoveryBoundary = $true
    ObservedCueDelayMs = 2000
    ScrewResumeMs = 600
    CompletedHoldResumeMs = 2000
    DurationSeconds = $DurationSeconds
    CameraIndex = 0
    CheckOnly = !$Live
}
# The common projection replaces, rather than stacks with, the old per-target offsets.
Push-Location $ProjectRoot
try {
    & (Join-Path $ProjectRoot 'scripts/run_beast_demo.ps1') @options
} finally {
    Pop-Location
}
