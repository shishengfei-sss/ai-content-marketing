# Pack apps/api for deploy (excludes local dev artifacts)
param(
    [string]$OutZip = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$apiDir = Join-Path $root "apps\api"
if (-not (Test-Path $apiDir)) {
    Write-Error "api dir not found: $apiDir"
}

if (-not $OutZip) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmm"
    $OutZip = Join-Path $root "apps\api-deploy-$stamp.zip"
}

$staging = Join-Path $env:TEMP ("ai-marketing-api-pack-" + [guid]::NewGuid().ToString("n"))
New-Item -ItemType Directory -Path $staging -Force | Out-Null

try {
    $excludeDirs = @(".venv", ".ven", "__pycache__", ".pytest_cache", "storage", "node_modules")
    $excludeFiles = @("dev.db", ".env")

    Get-ChildItem -Path $apiDir -Force | ForEach-Object {
        if ($_.PSIsContainer) {
            if ($excludeDirs -contains $_.Name) { return }
        } else {
            if ($excludeFiles -contains $_.Name) { return }
        }
        Copy-Item -Path $_.FullName -Destination (Join-Path $staging $_.Name) -Recurse -Force
    }

    if (Test-Path $OutZip) { Remove-Item $OutZip -Force }
    Compress-Archive -Path (Join-Path $staging "*") -DestinationPath $OutZip -CompressionLevel Optimal

    $sizeMb = [math]::Round((Get-Item $OutZip).Length / 1MB, 2)
    Write-Host ""
    Write-Host "OK: $OutZip ($sizeMb MB)"
    Write-Host "Deploy to: /opt/shengfei/apps/api/"
} finally {
    Remove-Item -Path $staging -Recurse -Force -ErrorAction SilentlyContinue
}
