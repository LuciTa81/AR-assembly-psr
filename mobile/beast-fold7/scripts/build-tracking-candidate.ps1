$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$env:JAVA_HOME='C:/Users/fresh/Documents/Codex/2026-10-25/new-chat/work/toolchain/jdk/jdk-21.0.12.1+1'
$env:ANDROID_HOME='C:/Users/fresh/Documents/Codex/2026-10-25/new-chat/work/toolchain/android-sdk'
$env:ANDROID_USER_HOME=Join-Path $root '.android'
$env:GRADLE_USER_HOME='C:/Users/fresh/Documents/Codex/2026-10-25/new-chat/work/gradle-cache'
Push-Location $root
try {
    & "$env:GRADLE_USER_HOME/wrapper/dists/gradle-8.14.1-bin/baw1sv0jfoi8rxs14qo3h49cs/gradle-8.14.1/bin/gradle.bat" --no-daemon -PtrackingTestBuildType=trackingCandidate :app:assembleTrackingCandidate :app:assembleTrackingCandidateAndroidTest :app:lintTrackingCandidate :app:testDebugUnitTest *> .local/tracking-candidate-build.txt
    $result=$LASTEXITCODE
    Get-Content .local/tracking-candidate-build.txt -Tail 45
    exit $result
} finally { Pop-Location }
