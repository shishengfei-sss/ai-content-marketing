#!/usr/bin/env bash
# 内网演示机（192.168.20.201）灌商城演示数据：升库 → 种子 → 重启 API。
# 在演示机 API 目录或仓库根执行均可。
#
# 用法（演示机 shell）：
#   bash /opt/shengfei/apps/api/../../ai-content-marketing/scripts/prepare-shop-demo-server.sh
#   # 或仅部署了 API 时：
#   API_DIR=/opt/shengfei/apps/api bash prepare-shop-demo-server.sh
#
# 环境变量：
#   API_DIR          默认 /opt/shengfei/apps/api
#   FULL_VOLUME=1    验收量级（默认 1）；0=仅开箱最小集
#   RESET=1          1=重建演示数据（full 用 --reset-volume，最小集用 --reset-demo）
#   SHOP_DEMO_ENV=demo201  打印 8088/8089 买家链接（默认已设）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_DIR="${API_DIR:-/opt/shengfei/apps/api}"
FULL_VOLUME="${FULL_VOLUME:-1}"
RESET="${RESET:-0}"

export SHOP_DEMO_ENV="${SHOP_DEMO_ENV:-demo201}"
export SHOP_DEMO_H5_ORIGIN="${SHOP_DEMO_H5_ORIGIN:-http://192.168.20.201:8089}"
export SHOP_DEMO_WEB_ORIGIN="${SHOP_DEMO_WEB_ORIGIN:-http://192.168.20.201:8088}"

if [ ! -d "$API_DIR" ]; then
  echo "[prepare-demo] ERROR: API_DIR not found: $API_DIR" >&2
  exit 1
fi

cd "$API_DIR"
if [ -d .venv ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
elif [ -d venv ]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

echo "[prepare-demo] == 1/3 alembic upgrade head =="
python -m alembic upgrade head

echo "[prepare-demo] == 2/3 seed (FULL_VOLUME=$FULL_VOLUME RESET=$RESET) =="
if [ "$FULL_VOLUME" = "1" ]; then
  if [ "$RESET" = "1" ]; then
    python tests/seed_shop_demo_full.py --reset-volume
  else
    python tests/seed_shop_demo_full.py
  fi
else
  if [ "$RESET" = "1" ]; then
    python tests/seed_shop_demo.py --reset-demo
  else
    python tests/seed_shop_demo.py
  fi
fi

echo "[prepare-demo] == 3/3 restart API =="
if systemctl list-unit-files 2>/dev/null | grep -q '^ai-marketing-api\.service'; then
  systemctl restart ai-marketing-api
elif systemctl list-unit-files 2>/dev/null | grep -q '^shengfei-api\.service'; then
  systemctl restart shengfei-api
else
  pkill -f 'uvicorn app.main:app' || true
  sleep 1
  nohup python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2 > /var/log/ai-marketing-api.log 2>&1 &
fi

sleep 2
if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
  echo "[prepare-demo] health ok (8000)"
elif curl -fsS http://127.0.0.1:8003/health >/dev/null 2>&1; then
  echo "[prepare-demo] health ok (8003)"
else
  echo "[prepare-demo] WARN: health check failed — 请手动确认 API 进程" >&2
fi

echo ""
echo "[prepare-demo] 完成。Web ${SHOP_DEMO_WEB_ORIGIN} · H5 ${SHOP_DEMO_H5_ORIGIN}"
echo "  平台超管 ${SHOP_DEMO_WEB_ORIGIN}/admin/login  13800000000 / admin123456"
echo "  主商家     ${SHOP_DEMO_WEB_ORIGIN}/login          13900000099 / test123456"
echo "  买家链接见上方种子脚本输出（tenant_id / shop_id 以本次打印为准）。"
