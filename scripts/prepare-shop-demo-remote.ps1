# 从本机 SSH 到内网演示机灌商城演示数据（须已配置免密或交互输入密码）。
# 用法：
#   powershell -ExecutionPolicy Bypass -File scripts/prepare-shop-demo-remote.ps1
#   powershell -ExecutionPolicy Bypass -File scripts/prepare-shop-demo-remote.ps1 -SshUser admin -ResetDemo
param(
    [string]$DemoHost = "192.168.20.201",
    [string]$SshUser = "root",
    [string]$RemoteApiDir = "/opt/shengfei/apps/api",
    [string]$RemoteScript = "/opt/shengfei/ai-content-marketing/scripts/prepare-shop-demo-server.sh",
    [switch]$ResetDemo,
    [switch]$MinVolumeOnly
)

$ErrorActionPreference = "Stop"
if (-not (Get-Command ssh -ErrorAction SilentlyContinue)) {
    Write-Error "未找到 ssh 命令"
}

$full = if ($MinVolumeOnly) { "0" } else { "1" }
$reset = if ($ResetDemo) { "1" } else { "0" }

$remoteCmd = @"
set -e
export API_DIR='$RemoteApiDir'
export FULL_VOLUME=$full
export RESET=$reset
export SHOP_DEMO_ENV=demo201
if [ -f '$RemoteScript' ]; then
  bash '$RemoteScript'
else
  cd "`$API_DIR" && \
  export SHOP_DEMO_H5_ORIGIN=http://192.168.20.201:8089 && \
  export SHOP_DEMO_WEB_ORIGIN=http://192.168.20.201:8088 && \
  source .venv/bin/activate 2>/dev/null || source venv/bin/activate && \
  python -m alembic upgrade head && \
  if [ "`$FULL_VOLUME" = "1" ]; then \
    if [ "`$RESET" = "1" ]; then python tests/seed_shop_demo_full.py --reset-volume; else python tests/seed_shop_demo_full.py; fi; \
  else \
    if [ "`$RESET" = "1" ]; then python tests/seed_shop_demo.py --reset-demo; else python tests/seed_shop_demo.py; fi; \
  fi
fi
"@

Write-Host "==> SSH ${SshUser}@${DemoHost} 灌演示数据 (FULL_VOLUME=$full RESET=$reset) =="
ssh "${SshUser}@${DemoHost}" $remoteCmd
