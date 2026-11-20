$ErrorActionPreference = 'Stop'
$output = 'C:\Users\fresh\OneDrive\Desktop\AI_Assembly_Video_Pack_20261115'
$assets = 'C:\Users\fresh\Documents\Codex\pamphlet-review-20261108'
$root = [IO.Path]::GetFullPath($output).TrimEnd('\')
$records = [Collections.Generic.List[object]]::new()
Add-Type -AssemblyName System.Drawing

function Copy-Asset([string]$Source, [string]$Relative, [string]$Kind, [string]$Use, [string]$Note) {
    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) { throw "Missing source: $Source" }
    $target = [IO.Path]::GetFullPath((Join-Path $root $Relative))
    if (-not $target.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Output outside pack' }
    New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
    $hash = (Get-FileHash -LiteralPath $Source -Algorithm SHA256).Hash
    if (Test-Path -LiteralPath $target) {
        if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $hash) { throw "Refusing to overwrite different file: $target" }
    } else { Copy-Item -LiteralPath $Source -Destination $target }
    $verified = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -eq $hash
    if (-not $verified) { throw "Copy verification failed: $target" }
    $dimensions = ''
    if ([IO.Path]::GetExtension($target) -match '^\.(png|jpg|jpeg)$') {
        $img = [Drawing.Image]::FromFile($target)
        try { $dimensions = '{0} x {1}' -f $img.Width, $img.Height } finally { $img.Dispose() }
    }
    $records.Add([pscustomobject]@{file=$Relative; source=$Source; kind=$Kind; use=$Use; note=$Note; dimensions=$dimensions; bytes=(Get-Item -LiteralPath $target).Length; sha256=$hash; verified=$verified})
}

New-Item -ItemType Directory -Path $root -Force | Out-Null
Copy-Asset "$PSScriptRoot\README_먼저읽기.md" 'README_먼저읽기.md' '안내' '폴더 사용법' ''
Copy-Asset "$PSScriptRoot\01_Claude_전달용_10분_구성안.md" '00_제작안\01_Claude_전달용_10분_구성안.md' '제작안' 'Claude에 먼저 전달' '10분 편집안, 실제 녹화 슬롯 포함'
Copy-Asset "$PSScriptRoot\02_녹화전_UX개선과_촬영목록.md" '00_제작안\02_녹화전_UX개선과_촬영목록.md' '개선 계획' '개발과 녹화 준비' '구현 완료 보고서가 아님'

Copy-Asset "$assets\ar-guidance-B-photo-unity-v14.png" '01_Unity_안내\AR_B_안내_디자인예시.png' '사진+Unity HUD 설명용 합성' '도입, 대표 안내 이미지' '실제 작업대 사진 기반. 링/화살표/테두리는 편집 좌표에 배치. 최신 실기나 렌즈 촬영 아님.'
Copy-Asset "$assets\unity-overlay-transparent-v14.png" '01_Unity_안내\AR_B_투명_HUD_디자인.png' 'Unity 렌더 디자인 레이어' '위 디자인 예시와 같은 사진에 맞춰 사용' '보정된 실제 좌표의 렌더가 아님. 다른 사진에 그대로 얹지 않기.'
Copy-Asset 'C:\Users\fresh\Documents\Codex\beast-reference-return-20261114\lid-prism-geometry-preview.png' '01_Unity_안내\몸체_뚜껑_단계별_기하미리보기.png' '기하 미리보기' '단계별 윤곽을 설명하는 보조 도식' '카메라/안경 캡처 아님. 원 강조와 최종 UI는 별도 녹화 필요.'

Copy-Asset 'C:\Users\fresh\AppData\Local\Temp\codex-clipboard-93c23741-68d5-4815-a29c-d92d2f5c399f.png' '02_작업대_사진\작업대_위에서_원본.png' '사용자 제공 실사' '도입, 부품/마커 배치 설명' '이전 배치 사진. 현재 마커 기하 설정의 증거로 사용하지 않기.'
Copy-Asset 'C:\Users\fresh\Downloads\Beast_202mm_AD_20261108\live-20261108T012754Z-f8cf2d50\frame-000017\raw.png' '02_작업대_사진\작업대_카메라_원본.png' '저장 카메라 사진' '실제 작업 환경 설명' '2026-11-08 저장 원본. 현재 단계와 동기화된 실시간 영상 아님.'
Copy-Asset "$assets\photo-only-v10-compact.png" '02_작업대_사진\작업대_편집용_크롭.png' '실사 크롭/확대' '사진 중심 PPT 구성' '카메라 원본 일부를 확대. 높은 픽셀 수가 원본 광학 해상도를 의미하지 않음.'

$video = 'C:\Users\fresh\OneDrive\Desktop\홍익대\4학년\1학기\Ather수업들\졸업프로젝트1\최종발표\KakaoTalk_20260520_214158270.mp4'
Copy-Asset $video '03_AI_검출\AI_검출비교_원본_20260520.mp4' '원본 검출 영상' 'AI 설명에서 약 15초 재생' '1320x720, 119프레임, 약 14.8초, 오디오 트랙 없음. 5월 ArUco/MediaPipe/YOLO 비교; 최신 Unity 시연 아님.'
foreach ($name in @('aruco','mediapipe','yolo')) {
    Copy-Asset "$assets\detection-$name-v4.png" "03_AI_검출\검출_$name.png" '실제 검출 결과 크롭' '해당 알고리즘 설명' '5월 개발 영상의 검출 결과. MediaPipe는 현재 실시간 단계 판정과 구분.'
}
foreach ($frame in @('000','048','096')) {
    Copy-Asset "$assets\may-video-review\frame-$frame.png" "03_AI_검출\원본영상_프레임_$frame.png" '원본 영상 정지 프레임' '전체 6분할 비교 또는 도입 보조' '영상의 시작/6초/12초 프레임. 실제 검출 영상에서 추출한 기존 파일.'
}

Copy-Asset "$assets\supervisor-B-header-v7.png" '04_관제\관제_B_저장상태_발표용.png' '저장 상태 발표용 재생' '관제 기능 설명, PPT 임시 화면' '실제 저장 B 상태+별도 카메라 사진. 전송 시각은 재생용. 동기화된 라이브 녹화 아님.'
Copy-Asset 'C:\Users\fresh\Documents\Codex\AI-Assembly-Console\console-ready.png' '04_관제\노트북_실행준비_화면.png' '관제 준비 화면 캡처' '보조 참고용, 본편의 시작/종료 설명에서는 제외' '실행 전 화면. 이후 작은 UI 수정은 반영되지 않았을 수 있어 최종 영상에는 새 녹화 권장.'

Copy-Asset "$assets\beast-official-v5.jpg" '05_기기_로고\VITURE_Beast_사선_제품사진.jpg' '기존 제품 이미지' '기기 소개, 사진 도입' '기존 공식 제품 자료로 수집한 파일. 실제 착용 사진이 아님.'
foreach ($name in @('python','unity','csharp','opencv','yolo','mediapipe')) {
    Copy-Asset "$assets\logo-$name-v5.png" "05_기기_로고\logo_$name.png" '기술 로고' '구현 방식 설명에 소수만 사용' '기존 수집본. 로고가 있다고 현재 실시간 경로에 모두 사용되는 것은 아님.'
}

Copy-Asset 'C:\Users\fresh\OneDrive\Desktop\회사\Claude\AR 테크 교육 프로그램 제안서_학교용_v8.pptx' '06_참고\AR_교육프로그램_학교용_v8_참고.pptx' '사용자 제공 참고 제안서' 'PPT 시각 스타일과 전개 참고' '22장. 회사/시장/가격 내용은 졸업프로젝트 사실로 재사용하지 않기.'
Copy-Asset "$assets\C011207_최민준_팜플렛_최종.pdf" '06_참고\기존_팜플렛.pdf' '기존 팜플렛' '프로젝트 명칭과 기존 표현 참고' '11월 8~9일 자료. 이후 구현과 다르거나 과장된 기술 연결은 현재 코드 기준으로 바로잡기.'
New-Item -ItemType Directory -Path (Join-Path $root '07_새_녹화_추가') -Force | Out-Null

$records | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $root 'asset-manifest.json') -Encoding utf8
$lines = [Collections.Generic.List[string]]::new()
$lines.Add('# 자료 목록 및 사용 구분')
$lines.Add('')
$lines.Add('복사 파일은 모두 원본과 SHA-256 일치 확인. 실시간 실행 영상, 재생 화면, 설명용 합성을 구분한다.')
$lines.Add('')
foreach ($r in $records) {
    $lines.Add('## ' + $r.file)
    $lines.Add('- 종류: ' + $r.kind)
    $lines.Add('- 용도: ' + $r.use)
    if ($r.dimensions) { $lines.Add('- 해상도: ' + $r.dimensions) }
    if ($r.note) { $lines.Add('- 확인 사항: ' + $r.note) }
    $lines.Add('- 원본: `' + $r.source + '`')
    $lines.Add('')
}
$lines.Add('## 기존 외부 이미지 출처 기록')
$lines.Add('- Beast: https://www.viture.com/product/viture-beast-xr-glasses (기존 수집 기록 기준, 이번 작업에서 새로 내려받지 않음)')
$lines.Add('- 개발 로고: https://github.com/devicons/devicon')
$lines.Add('- YOLO 로고: https://github.com/ultralytics/assets')
$lines.Add('- MediaPipe 로고: https://cdn.simpleicons.org/mediapipe/0097A7')
$lines | Set-Content -LiteralPath (Join-Path $root '00_제작안\03_자료목록.md') -Encoding utf8

$cards = foreach ($r in $records) {
    $ext = [IO.Path]::GetExtension($r.file).ToLowerInvariant()
    if ($ext -notin @('.png','.jpg','.jpeg','.mp4')) { continue }
    $url = (($r.file -replace '\\','/').Split('/') | ForEach-Object { [Uri]::EscapeDataString($_) }) -join '/'
    $label = [Net.WebUtility]::HtmlEncode($r.file)
    $note = [Net.WebUtility]::HtmlEncode($r.note)
    $kind = [Net.WebUtility]::HtmlEncode($r.kind)
    $background = if ($r.file.StartsWith('01_Unity_안내')) { 'background:#0b0f0e' } else { '' }
    $title = [Net.WebUtility]::HtmlEncode([IO.Path]::GetFileNameWithoutExtension($r.file).Replace('_',' '))
    $media = if ($ext -eq '.mp4') { "<video controls preload='metadata' src='$url'></video>" } else { "<a href='$url'><img loading='lazy' style='$background' src='$url' alt='$label'></a>" }
    "<article>$media<h2>$title</h2><p>$kind / $($r.dimensions)</p><p>$note</p></article>"
}
$html = @"
<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AI Assembly Guide 자료</title>
<style>*{box-sizing:border-box}body{margin:0;background:#171a19;color:#f3f5f4;font:16px/1.6 'Malgun Gothic',sans-serif}header{padding:28px 24px;border-bottom:1px solid #404542}h1{font-size:26px;margin:0 0 8px}header p{margin:0;color:#bec9c4}main{padding:24px;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,360px),1fr));gap:24px}article{min-width:0;border-bottom:1px solid #404542;padding-bottom:20px}img,video{display:block;width:100%;height:240px;object-fit:contain;background:#fff}h2{font-size:16px;overflow-wrap:anywhere;margin:14px 0 4px}p{font-size:14px;color:#bec9c4;margin:4px 0}a{color:#81d9c4}</style>
<header><h1>AI Assembly Guide</h1><p>10분 영상용 자료 · 실제 사진 / Unity 안내 디자인 / 검출 영상 / 관제</p><p>최신 Unity 연속 시연 영상은 별도 녹화 예정입니다. 제작안과 자료 구분을 함께 확인해 주세요.</p></header>
<main>$($cards -join "`n")</main></html>
"@
$html | Set-Content -LiteralPath (Join-Path $root '자료_미리보기.html') -Encoding utf8
[pscustomobject]@{output=$root; copied=$records.Count; verified=($records | Where-Object verified).Count; totalBytes=($records | Measure-Object bytes -Sum).Sum; preview=(Join-Path $root '자료_미리보기.html')} | ConvertTo-Json
