param(
    [string]$UnityExe = "C:\Program Files\Unity\Hub\Editor\6000.3.25f1\Editor\Unity.exe",
    [string]$OutputDirectory
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$project = Join-Path $root "client_unity"
$output = if ($OutputDirectory) { $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputDirectory) }
          else { Join-Path $root "outputs\unity_p1" }
if (-not (Test-Path -LiteralPath $UnityExe -PathType Leaf)) {
    throw "Unity Editor not found. Install 6000.3.25f1 or pass -UnityExe."
}
New-Item -ItemType Directory -Path $output -Force | Out-Null
$log = Join-Path $output ("build-" + (Get-Date -Format "yyyyMMdd-HHmmss-fff") + ".log")
$exe = Join-Path $output "BeastAssemblyGuide.exe"
$arguments = @("-batchmode", "-quit", "-projectPath", ('"' + $project + '"'),
    "-executeMethod", "ARAssembly.Editor.AssemblyGuideBuilder.BuildWindows",
    "-guideBuildPath", ('"' + $exe + '"'), "-logFile", ('"' + $log + '"'))
$process = Start-Process -FilePath $UnityExe -ArgumentList $arguments -WindowStyle Hidden -PassThru
# Wait for the Editor, not unrelated long-lived descendants in its Windows job.
$process.WaitForExit()
if ($process.ExitCode -ne 0) { throw "Unity build failed ($($process.ExitCode)). See $log" }
if (-not (Test-Path -LiteralPath $exe)) { throw "Build output missing. See $log" }
Write-Output "Built: $exe"
Write-Output "Log: $log"
