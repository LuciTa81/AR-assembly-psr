$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Push-Location (Join-Path $root 'internet-supervisor/web')
try {
    $icons = 'const React=require("react"),{renderToStaticMarkup}=require("react-dom/server"),icons=require("lucide-react"); console.log(JSON.stringify(Object.fromEntries(["Box","Play","Square","Settings2","Glasses","Camera","RefreshCw","ChevronRight","Wifi","Radio"].map(n=>[n,renderToStaticMarkup(React.createElement(icons[n]))]))));' | & node | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0) { throw 'Icon source render failed' }
} finally { Pop-Location }
$destination = Join-Path $root 'app/src/main/res/drawable'
New-Item -ItemType Directory -Force -Path $destination | Out-Null
foreach ($icon in $icons.PSObject.Properties) {
    [xml]$svg = $icon.Value
    $doc = New-Object System.Xml.XmlDocument
    $vector = $doc.CreateElement('vector')
    $null = $vector.SetAttribute('xmlns:android', 'http://schemas.android.com/apk/res/android')
    foreach ($pair in @{width='24dp';height='24dp';viewportWidth='24';viewportHeight='24'}.GetEnumerator()) {
        $null = $vector.SetAttribute($pair.Key, 'http://schemas.android.com/apk/res/android', $pair.Value)
    }
    $null = $doc.AppendChild($vector)
    foreach ($shape in $svg.DocumentElement.ChildNodes) {
        $path = switch ($shape.LocalName) {
            'path' { $shape.GetAttribute('d') }
            'circle' {
                $x=[double]$shape.GetAttribute('cx');$y=[double]$shape.GetAttribute('cy');$r=[double]$shape.GetAttribute('r')
                "M $($x-$r),$y a $r,$r 0 1,0 $($r*2),0 a $r,$r 0 1,0 $(-$r*2),0"
            }
            'rect' {
                $x=[double]$shape.GetAttribute('x');$y=[double]$shape.GetAttribute('y');$w=[double]$shape.GetAttribute('width');$h=[double]$shape.GetAttribute('height');$r=[double]$shape.GetAttribute('rx')
                "M $($x+$r),$y H $($x+$w-$r) Q $($x+$w),$y $($x+$w),$($y+$r) V $($y+$h-$r) Q $($x+$w),$($y+$h) $($x+$w-$r),$($y+$h) H $($x+$r) Q $x,$($y+$h) $x,$($y+$h-$r) V $($y+$r) Q $x,$y $($x+$r),$y Z"
            }
            'line' { "M $($shape.GetAttribute('x1')),$($shape.GetAttribute('y1')) L $($shape.GetAttribute('x2')),$($shape.GetAttribute('y2'))" }
            'polyline' { 'M ' + $shape.GetAttribute('points') }
            default { throw "Unsupported icon shape: $($shape.LocalName)" }
        }
        $element = $doc.CreateElement('path')
        foreach ($pair in @{pathData=$path;fillColor='#00000000';strokeColor='#EAF0EE';strokeWidth='1.8';strokeLineCap='round';strokeLineJoin='round'}.GetEnumerator()) {
            $null = $element.SetAttribute($pair.Key, 'http://schemas.android.com/apk/res/android', $pair.Value)
        }
        $null = $vector.AppendChild($element)
    }
    $doc.Save((Join-Path $destination ('ic_' + $icon.Name.ToLowerInvariant() + '.xml')))
}
Copy-Item -LiteralPath (Join-Path $root 'internet-supervisor/web/node_modules/lucide-react/LICENSE') -Destination (Join-Path $root 'app/src/main/assets/LUCIDE_LICENSE.txt')
