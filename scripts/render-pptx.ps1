<#
  render-pptx.ps1
  Uses Microsoft PowerPoint, only if it is already installed, to either
  - render every slide of a .pptx/.ppt/.odp file to PNG, or
  - save a copy of a .ppt/.odp file as .pptx (with -SaveAsPptx).
  The source file is opened read-only and never saved. Athena calls this
  from athena/render.py when LibreOffice is not installed.

  Usage:
    powershell -NoProfile -ExecutionPolicy Bypass -File render-pptx.ps1 -Source <file> -OutDir <dir> [-Width 1440]
    powershell -NoProfile -ExecutionPolicy Bypass -File render-pptx.ps1 -Source <file> -OutDir <dir> -SaveAsPptx <copy.pptx>
  Rendering writes <OutDir>\slide-001.png, slide-002.png, ... and prints the slide count.
#>
param(
    [Parameter(Mandatory = $true)][string]$Source,
    [Parameter(Mandatory = $true)][string]$OutDir,
    [int]$Width = 1440,
    [string]$SaveAsPptx = ''
)

$ErrorActionPreference = 'Stop'
$app = $null
$pres = $null
try {
    New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
    $app = New-Object -ComObject PowerPoint.Application
    # Open(FileName, ReadOnly=msoTrue, Untitled=msoFalse, WithWindow=msoFalse)
    $pres = $app.Presentations.Open($Source, -1, 0, 0)
    if ($SaveAsPptx) {
        # 24 = ppSaveAsOpenXMLPresentation. Writes a new file; the source is untouched.
        $pres.SaveCopyAs($SaveAsPptx, 24)
        Write-Output $pres.Slides.Count
        exit 0
    }
    $ratio = $pres.PageSetup.SlideHeight / $pres.PageSetup.SlideWidth
    $height = [int][math]::Round($Width * $ratio)
    $count = $pres.Slides.Count
    for ($i = 1; $i -le $count; $i++) {
        $target = Join-Path $OutDir ('slide-{0:D3}.png' -f $i)
        $pres.Slides.Item($i).Export($target, 'PNG', $Width, $height)
    }
    Write-Output $count
    exit 0
} catch {
    Write-Error ('PowerPoint step failed: ' + $_.Exception.Message)
    exit 1
} finally {
    if ($null -ne $pres) { try { $pres.Close() } catch { } }
    if ($null -ne $app) {
        try { if ($app.Presentations.Count -eq 0) { $app.Quit() } } catch { }
        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($app)
    }
    [GC]::Collect()
}
