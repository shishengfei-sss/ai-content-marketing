# 内容获客商城 · 本地演示一键准备：升库 → 种子 → 提示三端入口。
# 不杀已在跑的 Vite；API 用 scripts/restart-api.ps1 硬重启（另开窗口，避免本脚本被卡住）。
param(
    [switch]$ResetDemo,
    [switch]$StartApi,
    [switch]$FullVolume,
    [switch]$DemoServer
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$api = Join-Path $root "apps\api"
$py = Join-Path $api ".venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
    Write-Error "未找到 $py 。请先在 apps/api 创建 .venv 并安装依赖。"
}

if ($DemoServer) {
    $env:SHOP_DEMO_ENV = "demo201"
    $env:SHOP_DEMO_H5_ORIGIN = "http://192.168.20.201:8089"
    $env:SHOP_DEMO_WEB_ORIGIN = "http://192.168.20.201:8088"
    Write-Host "演示机链接模式：H5 $env:SHOP_DEMO_H5_ORIGIN · Web $env:SHOP_DEMO_WEB_ORIGIN"
}

Write-Host "== 1/3 alembic upgrade head =="
Push-Location $api
& $py -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }

if ($FullVolume) {
    Write-Host "== 2/3 seed_shop_demo_full（验收量级）=="
    $seedArgs = @("tests/seed_shop_demo_full.py")
    if ($ResetDemo) { $seedArgs += "--reset-volume" }
} else {
    Write-Host "== 2/3 seed_shop_demo =="
    $seedArgs = @("tests/seed_shop_demo.py")
    if ($ResetDemo) { $seedArgs += "--reset-demo" }
}
& $py @seedArgs
if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }
Pop-Location

Write-Host ""
Write-Host "== 3/3 启动三端（请各开一个终端，或已在跑则跳过）=="
Write-Host "  API :  本仓库 scripts\restart-api.ps1     → http://127.0.0.1:8003/health"
Write-Host "  Web :  cd apps\web ; npm run dev          → http://localhost:5173"
Write-Host "  买家:  cd apps\mp  ; npm run dev:h5       → http://localhost:5174"
Write-Host ""
Write-Host "平台超管  http://localhost:5173/admin/login   13800000000 / admin123456"
Write-Host "经营中商家 http://localhost:5173/login          13900000099 / test123456"
if ($FullVolume) {
    Write-Host "学院/咨询/资料  13900000201 / 202 / 203     demo123456"
}
Write-Host "账号全表见 docs/04-运维与手册/内容获客商城-本地演示启动.md"
Write-Host ""

if ($StartApi) {
    Write-Host "正在硬重启 API（前台占用本窗口）..."
    & (Join-Path $PSScriptRoot "restart-api.ps1")
}
