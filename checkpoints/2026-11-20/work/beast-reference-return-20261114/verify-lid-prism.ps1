$ErrorActionPreference='Stop'
$root='C:/Users/fresh/OneDrive/Desktop/홍익대/4학년/2학기/vision/01_SUBMIT_KEEP/AR-assembly-psr_github_main_20260604/.worktrees/viture-beast-overlay-mvp'
$protected=@(Get-Content -Raw -LiteralPath "$PSScriptRoot/poll-protected-hashes-after.json" | ConvertFrom-Json)
foreach($item in $protected) {
    if((Get-FileHash -LiteralPath $item.Path).Hash -ne $item.Hash) { throw "Protected file changed: $($item.Path)" }
}
$previous=@('context-overlay-build','context-overlay-brighter-build','box-outline-build','rounded-box-build','uniform-box-build','focused-box-build')
foreach($name in $previous) {
    $verified=Get-Content -Raw -LiteralPath "$PSScriptRoot/$name-verified.json" | ConvertFrom-Json
    $dll="$PSScriptRoot/$name/BeastAssemblyGuide_Data/Managed/Assembly-CSharp.dll"
    if((Get-FileHash -LiteralPath $dll).Hash -ne $verified.dll_sha256) { throw "Previous player changed: $name" }
}
if((Get-FileHash -LiteralPath "$PSScriptRoot/checkpoint-text-build/BeastAssemblyGuide_Data/Managed/Assembly-CSharp.dll").Hash -ne
    'BA3A43B347836F9FFD850F7BDACBAB2CB3B56D2D7CC34336E78646A1E84DD097') { throw 'Successful player changed.' }
$geometryHash=(Get-FileHash -LiteralPath "$PSScriptRoot/rounded-box-124mm.json").Hash
if($geometryHash -ne 'A0DA620706430F4CD59C09CE46336A99F1912D272C2C56CE227580933F996B65') { throw 'Geometry changed.' }

function StrokeKeys($row) {
    foreach($stroke in $row.strokes) {
        [ordered]@{left=$stroke.left;right=$stroke.right} | ConvertTo-Json -Depth 8 -Compress
    }
}
$old=@(Get-Content -Raw -LiteralPath "$PSScriptRoot/uniform-box-preview-data.json" | ConvertFrom-Json)
$new=@(Get-Content -Raw -LiteralPath "$PSScriptRoot/lid-prism-preview-data.json" | ConvertFrom-Json)
if($old.Count -ne 9 -or $new.Count -ne 12) { throw 'Expected three saved poses.' }
for($pose=0;$pose -lt 3;$pose++) {
    $full=@(StrokeKeys $old[$pose*3+1])
    for($step=0;$step -lt 4;$step++) {
        $row=$new[$pose*4+$step]
        if($row.step -ne @('S0','S1','S2','S6')[$step]) { throw 'Preview stage order changed.' }
        $keys=@(StrokeKeys $row)
        if($keys.Count -ne @(20,20,20,32)[$step] -or @($keys | Select-Object -Unique).Count -ne $keys.Count) {
            throw 'Unexpected or duplicate geometry strokes.'
        }
        foreach($key in $keys) { if($key -cnotin $full) { throw 'Retained stereo coordinates changed.' } }
        $level=if($step -eq 1) {3} else {2}
        if(@($row.strokes | Where-Object {$_.level -ne $level}).Count) { throw 'Unexpected emphasis level.' }
        if($step -eq 0 -and @(Compare-Object @(StrokeKeys $old[$pose*3]) $keys -CaseSensitive).Count) {
            throw 'Body placement geometry changed.'
        }
    }
}
[xml]$tests=Get-Content -Raw -LiteralPath "$PSScriptRoot/lid-prism-all-tests.xml"
[xml]$server=Get-Content -Raw -LiteralPath "$PSScriptRoot/lid-prism-server-regression.xml"
if([int]$tests.'test-run'.failed -ne 0 -or [int]$tests.'test-run'.passed -ne 464) { throw 'Unity tests failed.' }
if([int]$server.testsuites.testsuite.errors -ne 0 -or [int]$server.testsuites.testsuite.failures -ne 0 -or
    [int]$server.testsuites.testsuite.tests -ne 4) { throw 'Flow regression failed.' }
$log=Get-ChildItem -LiteralPath "$PSScriptRoot/lid-prism-build" -Filter 'build-*.log' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if(!(Select-String -LiteralPath $log.FullName -Pattern 'Build completed with a result of.*Succeeded|Build Successful' -Quiet)) { throw 'Build failed.' }
$manifest=[ordered]@{
    dll_sha256=(Get-FileHash -LiteralPath "$PSScriptRoot/lid-prism-build/BeastAssemblyGuide_Data/Managed/Assembly-CSharp.dll").Hash
    box_profile_sha256=$geometryHash
    option='-StageContextTrial -BoxOutlineTrial -RoundedBoxTrial -RoundedBoxStyle lid-prism'
    stages=@{S0='body only 20 strokes';S1='lid prism only 20 strokes, level 3';S2_S5='lid prism 20 strokes level 2, four rings, active screw emphasis, no links';S6_inspection='full body/lid 32 strokes level 2 and four rings, fresh pose only';S6_confirmed='text only; no spatial cue'}
    retained_geometry_both_eyes_unchanged=$true
    saved_pose_stage_cases=12
    calibration_changed=$false
    unity_tests_passed=464
    unity_tests_skipped=[int]$tests.'test-run'.skipped
    server_tests_passed=4
    protected_files_unchanged=$protected.Count
    previous_players_unchanged=$previous.Count+1
    build='passed'
    optical_test='pending'
    activation_status='not_activated'
    source_sha256=@(Get-FileHash -LiteralPath "$root/client_unity/Assets/Scripts/BoxOutlineProfile.cs","$root/client_unity/Assets/Scripts/SbsGuidancePresenter.cs","$root/tests/unity/BoxOutlineTests.cs" | Select-Object Path,Hash)
}
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath "$PSScriptRoot/lid-prism-build-verified.json" -Encoding utf8
$manifest | ConvertTo-Json -Depth 4
