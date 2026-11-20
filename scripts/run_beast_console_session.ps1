[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Profile,
    [Parameter(Mandatory)][string]$GateFile,
    [Parameter(Mandatory)][string]$RunFolder,
    [switch]$CheckOnly,
    [switch]$Managed,
    [string]$ExternalStopFile
)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSHOME 'Modules/Microsoft.PowerShell.Utility/Microsoft.PowerShell.Utility.psd1') -Force
Import-Module (Join-Path $PSHOME 'Modules/CimCmdlets/CimCmdlets.psd1') -Force
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
if ($CheckOnly.IsPresent -eq $Managed.IsPresent) { throw 'Choose check or managed session.' }
$deadline = [DateTime]::UtcNow.AddSeconds(10)
while (!(Test-Path -LiteralPath $GateFile)) {
    if ([DateTime]::UtcNow -gt $deadline) { throw 'Process ownership gate timed out.' }
    Start-Sleep -Milliseconds 50
}
$root = Split-Path -Parent $PSScriptRoot
$p = Get-Content -LiteralPath $Profile -Raw -Encoding UTF8 | ConvertFrom-Json
if ($p.schema_version -cne 'beast_console_profile_v1') { throw 'Invalid local profile.' }
$trial = (Resolve-Path -LiteralPath $p.trial_directory).Path
$runner = Join-Path $trial 'run-neutral-D-trial.ps1'
$options = @{
    Python = $p.python
    PresentationConfig = (Join-Path $root 'outputs/demo/presentation.json')
    CandidateProjection = (Join-Path $trial 'candidate-ABCD-joint-unverified.json')
    NestedDriverDedup = $true
    SourceRecoveryBoundary = $true
    ReleaseAbsenceTrial = $true
    CompletedHoldCheckpointTrial = $true
    HandleLinkedDriverTrial = $true
    ReleaseRecoveryTrial = $true
    ObservedCueDelayMs = 2000
    UnityOutputDirectory = (Join-Path $trial 'lid-prism-build')
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
if ($p.presentation_config) {
    $presentation = (Resolve-Path -LiteralPath $p.presentation_config).Path
    if ($presentation.StartsWith('\\\\')) { throw 'Presentation config must use a local file.' }
    $options.PresentationConfig = $presentation
}
if ($p.action_guidance_directory) {
    $display = (Resolve-Path -LiteralPath $p.action_guidance_directory).Path
    if ($display.StartsWith('\\\\')) { throw 'Action guidance must use a local directory.' }
    $runner = (Resolve-Path -LiteralPath (Join-Path $display 'run-korean-trial.ps1')).Path
    $options.UnityOutputDirectory = (Resolve-Path -LiteralPath (Join-Path $display 'player-v2')).Path
}
Push-Location $root
try {
    if ($CheckOnly) {
        $report = @{ files=$false; camera=$false; screens=@(); busy=$false }
        try {
            & $runner @options -CheckOnly
            $report.files = $true
            $report.camera = [bool]@(Get-CimInstance Win32_PnPEntity | Where-Object {
                $_.DeviceID -match 'VID_0C45&PID_6368(?:&|\\|$)' -and
                $_.Status -eq 'OK' -and $_.ConfigManagerErrorCode -eq 0
            }).Count
            Add-Type -AssemblyName System.Windows.Forms
            $report.screens = @([System.Windows.Forms.Screen]::AllScreens | ForEach-Object {
                @{ width=$_.Bounds.Width; height=$_.Bounds.Height; primary=$_.Primary }
            })
            $report.busy = [bool]@(Get-CimInstance Win32_Process | Where-Object {
                $_.Name -eq 'BeastAssemblyGuide.exe' -or
                ($_.Name -match '^python(w)?\.exe$' -and $_.CommandLine -match 'run_(realtime|handle_linked_d|handle_linked_flow|release_recovery_flow)_server\.py')
            }).Count
        } finally {
            $report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $RunFolder 'check.json') -Encoding UTF8
        }
        return
    }
    if (!$ExternalStopFile) { throw 'Managed launch requires a stop signal.' }
    if (Test-Path -LiteralPath $ExternalStopFile) { return }
    & $runner @options -Managed `
        -ExternalStopFile $ExternalStopFile -ManagedRunFolder $RunFolder -NoBrowser
} finally {
    Pop-Location
}
