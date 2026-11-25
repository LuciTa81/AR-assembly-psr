$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$destination=Join-Path $root 'baseline/exhibition-v1-20261125'
if(Test-Path -LiteralPath $destination){throw 'Checkpoint exists; never overwrite'}
New-Item -ItemType Directory -Path $destination | Out-Null
Copy-Item -LiteralPath "$root/app/build/outputs/apk/debug/app-debug.apk" -Destination "$destination/AR-Assembly-v1-1.4.2.apk"
Copy-Item -LiteralPath 'C:/Users/fresh/Downloads/AR-Assembly-bb01b2a2-5954-46ca-901b-b0c930ab0013.mp4' -Destination "$destination/success-20261125-1756.mp4"
& tar -czf "$destination/source.tar.gz" --exclude=node_modules --exclude=.next --exclude=.env --exclude='.env.*' -C $root app/src app/build.gradle build.gradle settings.gradle gradle.properties build.ps1 scripts internet-supervisor/server internet-supervisor/shared internet-supervisor/tests internet-supervisor/scripts internet-supervisor/deploy internet-supervisor/docs internet-supervisor/web internet-supervisor/package.json internet-supervisor/pnpm-lock.yaml internet-supervisor/tsconfig.json
if($LASTEXITCODE -ne 0){throw 'Source archive failed'}
Copy-Item -LiteralPath "$root/internet-supervisor/docs/V1_ACCEPTANCE_20261125.md" -Destination "$destination/ACCEPTANCE.md"
Copy-Item -LiteralPath "$root/internet-supervisor/docs/TEN_MINUTE_RECORDING_20261125.md" -Destination "$destination/DEPLOYMENT.md"
$manifest=@(Get-ChildItem -LiteralPath $destination -File | Sort-Object Name | ForEach-Object {
    [ordered]@{path=$_.Name;bytes=$_.Length;sha256=(Get-FileHash -LiteralPath $_.FullName).Hash}
})
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath "$destination/sha256-manifest.json" -Encoding utf8
foreach($entry in $manifest){if((Get-FileHash -LiteralPath (Join-Path $destination $entry.path)).Hash -ne $entry.sha256){throw "Hash mismatch: $($entry.path)"}}
Write-Output "Verified $($manifest.Count) checkpoint files: $destination"
