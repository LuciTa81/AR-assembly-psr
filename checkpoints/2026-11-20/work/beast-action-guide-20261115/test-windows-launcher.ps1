param()
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -ne 5) {
    throw 'Run this regression check with Windows PowerShell 5.1.'
}
$protected = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $PSScriptRoot 'protected-before.json') | ConvertFrom-Json
$expectedRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $protected[0].Path))
$results = @()
foreach ($name in 'run-korean-player.ps1', 'run-korean-trial.ps1', 'start-korean-trial.ps1') {
    $tokens = $null
    $errors = $null
    $ast = [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot $name), [ref]$tokens, [ref]$errors)
    $assignment = $ast.Find({
        param($node)
        $node -is [System.Management.Automation.Language.AssignmentStatementAst] -and $node.Left.Extent.Text -eq '$root'
    }, $true)
    $literal = $assignment.Right.Find({
        param($node)
        $node -is [System.Management.Automation.Language.StringConstantExpressionAst]
    }, $true)
    $valid = $errors.Count -eq 0 -and $null -ne $literal -and
        $literal.Value.Replace('/', '\') -eq $expectedRoot -and
        (Test-Path -LiteralPath $literal.Value -PathType Container)
    $results += [pscustomobject]@{ check = $name; passed = [bool]$valid }
}

# Intercept the process boundary: exercise the real launcher without opening Unity or a camera.
function Start-Process {
    param($FilePath, $ArgumentList, $WorkingDirectory, [switch]$PassThru)
    if (!(Test-Path -LiteralPath $FilePath -PathType Leaf)) { throw 'Player executable missing.' }
    if (!(Test-Path -LiteralPath $WorkingDirectory -PathType Container)) { throw 'Player working directory is unreadable.' }
    if ($WorkingDirectory.Replace('/', '\') -ne $expectedRoot) { throw 'Player working directory changed.' }
    if ('--action-korean' -notin $ArgumentList -or '--sbs-guidance' -notin $ArgumentList) { throw 'Korean SBS flags missing.' }
    if ('--observed-cue-delay-ms' -notin $ArgumentList -or '2000' -notin $ArgumentList) { throw 'Cue delay changed.' }
    [pscustomobject]@{ Id = 0; Intercepted = $true }
}
try {
    $player = & (Join-Path $PSScriptRoot 'run-korean-player.ps1') -Beast -SbsGuidance -ObservedCueDelayMs 2000 -UnityOutputDirectory (Join-Path $PSScriptRoot 'player-v2') -PassThru
    $results += [pscustomobject]@{ check = 'actual-player-launch-intercepted'; passed = $player.Intercepted -eq $true }
} catch {
    $results += [pscustomobject]@{ check = 'actual-player-launch-intercepted'; passed = $false; error = $_.Exception.Message }
}
$results | ConvertTo-Json
if (@($results | Where-Object { !$_.passed }).Count) { exit 1 }
