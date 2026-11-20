param(
    [string]$DataPath = "$PSScriptRoot/rounded-box-preview.json",
    [string]$OutputPath = "$PSScriptRoot/rounded-box-geometry-preview.png",
    [ValidateSet(3,4)][int]$StageCount = 3
)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Drawing
$data = Get-Content -Raw -LiteralPath $DataPath | ConvertFrom-Json
$points = @($data[0..($StageCount-1)] | ForEach-Object { $_.strokes | ForEach-Object { $_.left | ForEach-Object { ,$_ } } })
$xs = $points | ForEach-Object { $_[0] }
$ys = $points | ForEach-Object { $_[1] }
$minX = ($xs | Measure-Object -Minimum).Minimum
$minY = ($ys | Measure-Object -Minimum).Minimum
$rangeX = ($xs | Measure-Object -Maximum).Maximum - $minX
$rangeY = ($ys | Measure-Object -Maximum).Maximum - $minY
$scale = [Math]::Min(390/$rangeX,300/$rangeY)
$bitmap = [Drawing.Bitmap]::new(480*$StageCount,410)
$g = [Drawing.Graphics]::FromImage($bitmap)
$g.Clear([Drawing.Color]::FromArgb(10,14,15))
$g.SmoothingMode = [Drawing.Drawing2D.SmoothingMode]::AntiAlias
$font = [Drawing.Font]::new('Segoe UI',17)
try {
    for($column=0;$column -lt $StageCount;$column++) {
        $label = @('S0  Body placement','S1  Close lid','S2-S5  Screw work','S6  Final inspection')[$column]
        $g.DrawString($label,$font,[Drawing.Brushes]::White,[single]($column*480+30),[single]22)
        foreach($stroke in $data[$column].strokes) {
            $light = switch($stroke.level) { 1 { .22 } 2 { .55 } 3 { .8 } }
            $width = switch($stroke.level) { 1 { 1.5 } 2 { 3 } 3 { 4 } }
            $color = [Drawing.Color]::FromArgb(255,[int](255*.55*$light),[int](255*.95*$light),[int](255*.85*$light))
            $pen = [Drawing.Pen]::new($color,[single]$width)
            try {
                $line = [Drawing.PointF[]]@($stroke.left | ForEach-Object {
                    [Drawing.PointF]::new([single]($column*480+45+($_[0]-$minX)*$scale),[single](80+($_[1]-$minY)*$scale))
                })
                $g.DrawLines($pen,$line)
            } finally { $pen.Dispose() }
        }
    }
    $output = $OutputPath
    $bitmap.Save($output,[Drawing.Imaging.ImageFormat]::Png)
    Write-Output $output
} finally { $font.Dispose(); $g.Dispose(); $bitmap.Dispose() }
