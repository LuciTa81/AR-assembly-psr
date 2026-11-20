[CmdletBinding()]
param(
    [string]$Python = $env:BEAST_PYTHON,
    [switch]$Live,
    [switch]$Preview,
    [switch]$SourceRecoveryBoundary,
    [ValidateRange(0,5000)][int]$ObservedCueDelayMs = 0,
    [string]$UnityOutputDirectory,
    [ValidateRange(1,600)][int]$DurationSeconds = 300,
    [ValidateRange(1,3600)][int]$PreviewSeconds = 3600,
    [ValidateRange(0,16)][int]$CameraIndex = 0
)
$ErrorActionPreference = 'Stop'
if ($Live -and $Preview) { throw 'Choose either -Live or -Preview, not both.' }
if ($Preview -and $SourceRecoveryBoundary) { throw 'SourceRecoveryBoundary is not part of the synthetic UI preview.' }
if ($Preview -and ($ObservedCueDelayMs -gt 0 -or $UnityOutputDirectory)) { throw 'Unity options are not part of the web preview.' }
if (!$Python) {
    $candidates = @(
        (Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'ARAssembly/beast-mvp/.venv/Scripts/python.exe'),
        (Join-Path $env:USERPROFILE 'AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/ARAssembly/beast-mvp/.venv/Scripts/python.exe')
    )
    $Python = $candidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
}
if (!$Python -or !(Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw 'Existing Python environment not found. Pass -Python or set BEAST_PYTHON; nothing was installed or started.'
}
$Python = (Resolve-Path -LiteralPath $Python).Path
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    if ($Preview) {
        Write-Output 'SYNTHETIC rehearsal only. No camera or Unity. Ctrl+C stops; closing the browser does not stop the server.'
        & $Python -X utf8 -B -u tests/web/serve_assembly_fixture.py --preview --seconds $PreviewSeconds --open
        if ($LASTEXITCODE -ne 0) { throw 'Rehearsal stopped with an error.' }
        return
    }
    # Keep the last tested hybrid configuration in the existing bounded launcher.
    $options = @{
        Python = $Python
        PresentationConfig = 'outputs/demo/presentation.json'
        CandidateProjection = 'outputs/display_retarget/fit-20261104T133307Z-3f75411a/candidate-probe.json'
        StageDepthConfig = 'configs/beast_stage_depth_records.json'
        TrialARight = $true
        AssemblyFlow = $true
        NestedDriverDedup = $true
        ScrewResumeMs = 600
        CompletedHoldResumeMs = 2000
        CameraIndex = $CameraIndex
        DurationSeconds = $DurationSeconds
        CheckOnly = !$Live
    }
    if ($SourceRecoveryBoundary) { $options.SourceRecoveryBoundary = $true }
    $options.ObservedCueDelayMs = $ObservedCueDelayMs
    if ($UnityOutputDirectory) { $options.UnityOutputDirectory = $UnityOutputDirectory }
    Write-Output $(if ($Live) { 'LIVE: bounded camera + Unity session. Closing Unity ends this session.' }
                  else { 'CHECK ONLY: camera and Unity will not start. Use -Preview for rehearsal; -Live only when ready.' })
    & ./scripts/run_beast_demo.ps1 @options
} finally {
    Pop-Location
}
