param([string]$Source, [string]$Output)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $Output | Out-Null
$app = New-Object -ComObject PowerPoint.Application
$deck = $null
try {
    $deck = $app.Presentations.Open($Source, -1, 0, 0)
    $deck.Export($Output, 'PNG', 1600, 900)
    Write-Output ('Exported slides: ' + $deck.Slides.Count)
} finally {
    if ($null -ne $deck) { $deck.Close() }
    if ($null -ne $app) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($app) }
}
