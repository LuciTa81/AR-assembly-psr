$ErrorActionPreference='Stop'
$root='C:/Users/fresh/OneDrive/Desktop/홍익대/4학년/2학기/vision/01_SUBMIT_KEEP/AR-assembly-psr_github_main_20260604/.worktrees/viture-beast-overlay-mvp'
$protected=Get-Content -Raw -LiteralPath "$PSScriptRoot/poll-protected-hashes-after.json" | ConvertFrom-Json
foreach($item in $protected) {
    if((Get-FileHash -LiteralPath $item.Path).Hash -ne $item.Hash) { throw "Protected file changed: $($item.Path)" }
}
$players=@{
    'checkpoint-text-build'='BA3A43B347836F9FFD850F7BDACBAB2CB3B56D2D7CC34336E78646A1E84DD097'
    'context-overlay-build'='5BAED4843ABBB14AC46912B5E3422DBE84FD15119F617763FA18C085414AFE9F'
    'context-overlay-brighter-build'='9ACC4E3A0DB390F3BAD875E82DB05E68AF0BE569D6482A3DFFFBAB31EF091BAA'
    'box-outline-build'='6DA1477D2ED194B4E866BCCEE2CE905D7D91FB7C2B6616B1D2A32D35FCC5AFC5'
}
foreach($name in $players.Keys) {
    $path=Join-Path $PSScriptRoot "$name/BeastAssemblyGuide_Data/Managed/Assembly-CSharp.dll"
    if((Get-FileHash -LiteralPath $path).Hash -ne $players[$name]) { throw "Previous player changed: $name" }
}
if((Get-FileHash -LiteralPath "$PSScriptRoot/box-outline-124mm/box-outline-124mm.json").Hash -ne
    '14308E57C782951755CB5FCB373519A4A9F29AEDA80C23B97765D0BDB4F22F06') { throw 'Previous geometry changed.' }
[xml]$unity=Get-Content -Raw -LiteralPath "$PSScriptRoot/rounded-box-all-tests.xml"
[xml]$server=Get-Content -Raw -LiteralPath "$PSScriptRoot/rounded-box-server-regression.xml"
if([int]$unity.'test-run'.failed -ne 0 -or [int]$unity.'test-run'.passed -lt 456) { throw 'Unity tests failed.' }
if([int]$server.testsuites.testsuite.errors -ne 0 -or [int]$server.testsuites.testsuite.failures -ne 0 -or
    [int]$server.testsuites.testsuite.tests -ne 4) { throw 'Flow regression tests failed.' }
$buildLog=Get-ChildItem -LiteralPath "$PSScriptRoot/rounded-box-build" -Filter 'build-*.log' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if(!(Select-String -LiteralPath $buildLog.FullName -Pattern 'Build completed with a result of.*Succeeded|Build Successful' -Quiet)) { throw 'Unity build success not found.' }
$manifest=[ordered]@{
    dll_sha256=(Get-FileHash -LiteralPath "$PSScriptRoot/rounded-box-build/BeastAssemblyGuide_Data/Managed/Assembly-CSharp.dll").Hash
    box_profile_sha256=(Get-FileHash -LiteralPath "$PSScriptRoot/rounded-box-124mm.json").Hash
    option='-StageContextTrial -BoxOutlineTrial -RoundedBoxTrial'
    approximate_dimensions_mm=@(124,124,60)
    lid_height_mm=10
    derived_body_height_mm=50
    display_corner_rounding_mm=3
    stages=@{S0='body 2, no lid or screw rings';S1='body 2, lid 3, no screw rings';S2_S5='body/lid 2, active screw unchanged';hidden='1; box surface geometry only';S6='no box'}
    unity_tests_passed=[int]$unity.'test-run'.passed
    unity_tests_skipped=[int]$unity.'test-run'.skipped
    server_tests_passed=4
    protected_files_unchanged=$protected.Count
    previous_visual_players_unchanged=$players.Count
    previous_geometry_unchanged=$true
    unity_build='passed'
    optical_test='pending'
    activation_status='not_activated'
    source_sha256=@(Get-FileHash -LiteralPath "$root/client_unity/Assets/Scripts/BoxOutlineProfile.cs","$root/client_unity/Assets/Scripts/SbsGuidancePresenter.cs","$root/tests/unity/BoxOutlineTests.cs" | Select-Object Path,Hash)
}
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath "$PSScriptRoot/rounded-box-build-verified.json" -Encoding utf8
$manifest | ConvertTo-Json -Depth 4
