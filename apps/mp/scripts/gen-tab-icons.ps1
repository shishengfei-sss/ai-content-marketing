$dir = Join-Path $PSScriptRoot "..\src\static\tab"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
Add-Type -AssemblyName System.Drawing

$Gray = [System.Drawing.Color]::FromArgb(153, 153, 153)
$Blue = [System.Drawing.Color]::FromArgb(22, 119, 255)
$White = [System.Drawing.Color]::White
$Size = 81

function Add-RoundRect($path, $x, $y, $w, $h, $r) {
  $path.AddArc($x, $y, $r * 2, $r * 2, 180, 90)
  $path.AddArc($x + $w - $r * 2, $y, $r * 2, $r * 2, 270, 90)
  $path.AddArc($x + $w - $r * 2, $y + $h - $r * 2, $r * 2, $r * 2, 0, 90)
  $path.AddArc($x, $y + $h - $r * 2, $r * 2, $r * 2, 90, 90)
  $path.CloseFigure()
}

function Save-Icon {
  param([string]$Path, [scriptblock]$Draw)
  $bmp = New-Object System.Drawing.Bitmap $Size, $Size
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
  $g.Clear([System.Drawing.Color]::FromArgb(0, 0, 0, 0))
  & $Draw $g
  $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
  $g.Dispose()
  $bmp.Dispose()
}

Save-Icon "$dir\home.png" {
  param($g)
  $p = New-Object System.Drawing.Pen $Gray, 5
  $p.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round
  $g.DrawLines($p, @(
    [System.Drawing.Point]::new(16, 36),
    [System.Drawing.Point]::new(40, 14),
    [System.Drawing.Point]::new(64, 36)
  ))
  $brush = New-Object System.Drawing.SolidBrush $Gray
  $path = New-Object System.Drawing.Drawing2D.GraphicsPath
  Add-RoundRect $path 18 34 44 36 6
  $g.FillPath($brush, $path)
  $p.Dispose(); $brush.Dispose(); $path.Dispose()
}

Save-Icon "$dir\home-active.png" {
  param($g)
  $brush = New-Object System.Drawing.SolidBrush $Blue
  $g.FillEllipse($brush, 8, 8, 65, 65)
  $p = New-Object System.Drawing.Pen $White, 4.5
  $p.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round
  $g.DrawLines($p, @(
    [System.Drawing.Point]::new(22, 38),
    [System.Drawing.Point]::new(40, 20),
    [System.Drawing.Point]::new(58, 38)
  ))
  $body = New-Object System.Drawing.SolidBrush $White
  $path = New-Object System.Drawing.Drawing2D.GraphicsPath
  Add-RoundRect $path 26 38 28 24 4
  $g.FillPath($body, $path)
  $brush.Dispose(); $p.Dispose(); $body.Dispose(); $path.Dispose()
}

Save-Icon "$dir\todo.png" {
  param($g)
  $p = New-Object System.Drawing.Pen $Gray, 4.5
  $p.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round
  $path = New-Object System.Drawing.Drawing2D.GraphicsPath
  Add-RoundRect $path 18 16 45 50 8
  $g.DrawPath($p, $path)
  $g.DrawLine($p, 28, 32, 53, 32)
  $g.DrawLine($p, 28, 44, 53, 44)
  $g.DrawLine($p, 28, 56, 44, 56)
  $p.Dispose(); $path.Dispose()
}

Save-Icon "$dir\todo-active.png" {
  param($g)
  $brush = New-Object System.Drawing.SolidBrush $Blue
  $path = New-Object System.Drawing.Drawing2D.GraphicsPath
  Add-RoundRect $path 16 14 49 54 10
  $g.FillPath($brush, $path)
  $p = New-Object System.Drawing.Pen $White, 4
  $g.DrawLine($p, 28, 32, 53, 32)
  $g.DrawLine($p, 28, 44, 53, 44)
  $g.DrawLine($p, 28, 56, 44, 56)
  $brush.Dispose(); $p.Dispose(); $path.Dispose()
}

Save-Icon "$dir\create.png" {
  param($g)
  $p = New-Object System.Drawing.Pen $Gray, 4.5
  $p.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round
  $path = New-Object System.Drawing.Drawing2D.GraphicsPath
  Add-RoundRect $path 16 16 49 49 14
  $g.DrawPath($p, $path)
  $g.DrawLine($p, 40, 28, 40, 54)
  $g.DrawLine($p, 27, 41, 53, 41)
  $p.Dispose(); $path.Dispose()
}

Save-Icon "$dir\create-active.png" {
  param($g)
  $brush = New-Object System.Drawing.SolidBrush $Blue
  $path = New-Object System.Drawing.Drawing2D.GraphicsPath
  Add-RoundRect $path 12 12 57 57 16
  $g.FillPath($brush, $path)
  $p = New-Object System.Drawing.Pen $White, 5
  $p.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
  $p.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
  $g.DrawLine($p, 40, 24, 40, 58)
  $g.DrawLine($p, 23, 41, 57, 41)
  $brush.Dispose(); $p.Dispose(); $path.Dispose()
}

Save-Icon "$dir\mine.png" {
  param($g)
  $p = New-Object System.Drawing.Pen $Gray, 4.5
  $g.DrawEllipse($p, 28, 14, 25, 25)
  $g.DrawArc($p, 16, 42, 49, 28, 0, 180)
  $p.Dispose()
}

Save-Icon "$dir\mine-active.png" {
  param($g)
  $brush = New-Object System.Drawing.SolidBrush $Blue
  $g.FillEllipse($brush, 8, 8, 65, 65)
  $p = New-Object System.Drawing.Pen $White, 4
  $g.DrawEllipse($p, 30, 22, 21, 21)
  $g.DrawArc($p, 20, 46, 41, 22, 0, 180)
  $brush.Dispose(); $p.Dispose()
}

Write-Output "Tab icons saved to $dir"
