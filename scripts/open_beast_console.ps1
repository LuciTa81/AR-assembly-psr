[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Profile,
    [ValidateRange(1024,65535)][int]$Port = 8764,
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSHOME 'Modules/Microsoft.PowerShell.Utility/Microsoft.PowerShell.Utility.psd1') -Force
$Profile = (Resolve-Path -LiteralPath $Profile).Path
$p = Get-Content -LiteralPath $Profile -Raw -Encoding UTF8 | ConvertFrom-Json
if ($p.schema_version -cne 'beast_console_profile_v1') { throw 'Invalid console profile.' }
$root = Split-Path -Parent $PSScriptRoot
$url = "http://127.0.0.1:$Port"
$ready = $false
try {
    $status = Invoke-RestMethod "$url/console/status" -TimeoutSec 2
    if ($status.schema_version -cne 'beast_console_v1') { throw 'Different service at console port.' }
    $ready = $true
} catch { }
if (!$ready) {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
    $listener.ExclusiveAddressUse = $true
    try { $listener.Start() } catch { throw 'Console port is occupied. Use another Port; no process was stopped.' }
    finally { $listener.Stop() }
    $folder = Split-Path -Parent $Profile
    $argsList = @('-X','utf8','-B','-u',(Join-Path $root 'server/realtime/console_controller.py'),
                  '--profile',$Profile,'--port',"$Port") | ForEach-Object { '"' + $_ + '"' }
    $process = Start-Process -FilePath $p.python -ArgumentList $argsList -WorkingDirectory $root `
        -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $folder 'console.log') `
        -RedirectStandardError (Join-Path $folder 'console-error.log')
    for ($i=0; $i -lt 60; $i++) {
        if ($process.HasExited) { throw "Console could not start. See $folder/console-error.log" }
        try {
            $status = Invoke-RestMethod "$url/console/status" -TimeoutSec 1
            if ($status.schema_version -eq 'beast_console_v1') { $ready=$true; break }
        } catch { }
        Start-Sleep -Milliseconds 200
    }
    if (!$ready) {
        if (!$process.HasExited) { & taskkill.exe /PID $process.Id /T /F | Out-Null }
        throw 'Console startup timed out; no camera was opened.'
    }
}
if (!$NoBrowser) {
    $chrome = @("${env:ProgramFiles}/Google/Chrome/Application/chrome.exe", "${env:ProgramFiles(x86)}/Google/Chrome/Application/chrome.exe") |
        Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if ($chrome) { Start-Process -FilePath $chrome -ArgumentList @('--new-tab',"$url/") }
    else { Start-Process "$url/" }
}
Write-Output "$url/"
