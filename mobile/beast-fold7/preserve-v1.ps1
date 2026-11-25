$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$destination=Join-Path $root 'baseline/v1-frozen-20261121'
if(Test-Path -LiteralPath $destination){throw 'v1 already exists; never overwrite the frozen checkpoint'}
New-Item -ItemType Directory -Path "$destination/source/app" -Force | Out-Null
Copy-Item -LiteralPath "$root/app/src" -Destination "$destination/source/app/src" -Recurse
Copy-Item -LiteralPath "$root/app/build.gradle" -Destination "$destination/source/app/build.gradle"
foreach($name in @('build.gradle','settings.gradle','gradle.properties','build.ps1')){
    Copy-Item -LiteralPath "$root/$name" -Destination "$destination/source/$name"
}
New-Item -ItemType Directory -Path "$destination/reports" | Out-Null
Get-ChildItem -LiteralPath $root -File | Where-Object {$_.Extension -eq '.md' -or $_.Name -like '*tests*.txt'} | Copy-Item -Destination "$destination/reports"
Copy-Item -LiteralPath "$root/screw-context-trial-20261121.txt" -Destination "$destination/reports"
Copy-Item -LiteralPath "$root/app/build/outputs/apk/debug/app-debug.apk" -Destination "$destination/v1.apk"
Copy-Item -LiteralPath "$root/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk" -Destination "$destination/v1-tests.apk"
if(Test-Path "$root/.android/debug.keystore"){
    New-Item -ItemType Directory -Path "$destination/source/.android" | Out-Null
    Copy-Item -LiteralPath "$root/.android/debug.keystore" -Destination "$destination/source/.android/debug.keystore"
}
$files=Get-ChildItem -LiteralPath $destination -File -Recurse | Sort-Object FullName
$manifest=@($files | ForEach-Object {
    [ordered]@{path=[IO.Path]::GetRelativePath($destination,$_.FullName);bytes=$_.Length;sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash}
})
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath "$destination/sha256-manifest.json" -Encoding utf8
foreach($entry in $manifest){if((Get-FileHash -LiteralPath (Join-Path $destination $entry.path) -Algorithm SHA256).Hash -ne $entry.sha256){throw "Mismatch: $($entry.path)"}}
Write-Output "Verified $($manifest.Count) files in $destination"
Get-FileHash -LiteralPath "$destination/v1.apk" -Algorithm SHA256 | Format-List
