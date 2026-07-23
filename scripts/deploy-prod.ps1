# v0.8 生产发布脚本（192.168.20.200）
# 用法：
#   powershell -ExecutionPolicy Bypass -File scripts/deploy-prod.ps1 -SshUser root
#   powershell -ExecutionPolicy Bypass -File scripts/deploy-prod.ps1 -SshUser root -SkipBuild
#
# 数据安全：就地覆盖代码；保留线上 .env / storage / *.db；只执行 alembic upgrade head。
param(
    [string]$ProdHost = "192.168.20.200",
    [string]$SshUser = "root",
    [int]$WebPort = 8088,
    [int]$H5Port = 8089,
    [string]$RemoteBase = "/opt/shengfei/apps",
    [switch]$SkipBuild,
    [switch]$SkipPack
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

function Require-Cmd($name) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        Write-Error "Missing command: $name"
    }
}

Require-Cmd ssh
Require-Cmd scp

$webDist = Join-Path $root "apps\web\dist"
$h5Dist = Join-Path $root "apps\mp\dist\build\h5"

if (-not $SkipBuild) {
    Write-Host "==> Build Web"
    Push-Location (Join-Path $root "apps\web"); npm run build; Pop-Location
    Write-Host "==> Build H5"
    Push-Location (Join-Path $root "apps\mp"); npm run build:h5; Pop-Location
}

if (-not $SkipPack) {
    Write-Host "==> Pack API"
    & (Join-Path $PSScriptRoot "pack-api-deploy.ps1")
}

$apiZip = Get-ChildItem (Join-Path $root "apps\api-deploy-*.zip") |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (-not $apiZip) { Write-Error "API zip not found" }
if (-not (Test-Path $webDist)) { Write-Error "Web dist missing: $webDist" }
if (-not (Test-Path $h5Dist)) { Write-Error "H5 dist missing: $h5Dist" }

$remote = "${SshUser}@${ProdHost}"
$stamp = Get-Date -Format "yyyyMMdd-HHmm"
$remoteTmp = "/tmp/ai-marketing-deploy-$stamp"
$remoteScript = Join-Path $PSScriptRoot "deploy-remote.sh"

Write-Host "==> Upload to ${remote}:${remoteTmp}"
ssh $remote "mkdir -p $remoteTmp"
scp $apiZip.FullName "${remote}:${remoteTmp}/api.zip"
scp -r $webDist "${remote}:${remoteTmp}/web-dist"
scp -r $h5Dist "${remote}:${remoteTmp}/h5-dist"
scp $remoteScript "${remote}:${remoteTmp}/deploy-remote.sh"

Write-Host "==> Deploy on server"
ssh $remote "chmod +x $remoteTmp/deploy-remote.sh && DEPLOY_TMP=$remoteTmp DEPLOY_STAMP=$stamp REMOTE_BASE=$RemoteBase bash $remoteTmp/deploy-remote.sh"

Write-Host ""
Write-Host "==> Smoke checks"
try {
    $crm = Invoke-WebRequest -Uri "http://${ProdHost}:${WebPort}/api/v1/crm/health" -UseBasicParsing -TimeoutSec 15
    Write-Host "CRM health: $($crm.StatusCode) $($crm.Content)"
} catch { Write-Warning "CRM health failed: $($_.Exception.Message)" }

try {
    $openapi = Invoke-WebRequest -Uri "http://${ProdHost}:${WebPort}/openapi.json" -UseBasicParsing -TimeoutSec 20
    if ($openapi.Content -match 'deal-funnel') { Write-Host "deal-funnel: OK" } else { Write-Warning "deal-funnel: NOT FOUND (may need cache/nginx reload)" }
} catch { Write-Warning "openapi failed: $($_.Exception.Message)" }

Write-Host ""
Write-Host "DONE"
Write-Host "Web : http://${ProdHost}:${WebPort}/"
Write-Host "H5  : http://${ProdHost}:${H5Port}/"
