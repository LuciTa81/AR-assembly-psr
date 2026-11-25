$ErrorActionPreference = 'Stop'
$env:JAVA_HOME = 'C:/Users/fresh/Documents/Codex/2026-10-25/new-chat/work/toolchain/jdk/jdk-21.0.12.1+1'
$env:ANDROID_HOME = 'C:/Users/fresh/Documents/Codex/2026-10-25/new-chat/work/toolchain/android-sdk'
$env:ANDROID_USER_HOME = Join-Path $PSScriptRoot '.android'
$env:GRADLE_USER_HOME = 'C:/Users/fresh/Documents/Codex/2026-10-25/new-chat/work/gradle-cache'
Push-Location $PSScriptRoot
try {
    & "$env:GRADLE_USER_HOME/wrapper/dists/gradle-8.14.1-bin/baw1sv0jfoi8rxs14qo3h49cs/gradle-8.14.1/bin/gradle.bat" --no-daemon :app:assembleDebug :app:assembleDebugAndroidTest :app:lintDebug *> build-log.txt
    $result = $LASTEXITCODE
    Get-Content build-log.txt -Tail 40
    exit $result
} finally { Pop-Location }
