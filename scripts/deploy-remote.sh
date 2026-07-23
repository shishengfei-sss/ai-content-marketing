#!/usr/bin/env bash
# 生产机上执行：就地更新代码 + alembic upgrade。
# 硬约束：绝不清空业务数据（禁止覆盖/删除 .env、*.db、storage、.venv）。
set -euo pipefail

BASE="${REMOTE_BASE:-/opt/shengfei/apps}"
TMP="${DEPLOY_TMP:?DEPLOY_TMP required}"
STAMP="${DEPLOY_STAMP:?DEPLOY_STAMP required}"

mkdir -p "$BASE/api" "$BASE/web" "$BASE/mp"

# 前端可整目录替换；先备份便于回滚
for d in web mp; do
  if [ -d "$BASE/$d" ] && [ "$(ls -A "$BASE/$d" 2>/dev/null || true)" ]; then
    rm -rf "$BASE/${d}.bak-$STAMP"
    cp -a "$BASE/$d" "$BASE/${d}.bak-$STAMP"
  fi
done

# API：解压到临时目录，再 rsync 进现网目录（就地更新，不 mv 整个 api）
API_STAGE="$TMP/api-stage"
rm -rf "$API_STAGE"
mkdir -p "$API_STAGE"
unzip -oq "$TMP/api.zip" -d "$API_STAGE"

# 若现网尚无 .env，允许从备份包恢复一次；否则绝不覆盖
if [ ! -f "$BASE/api/.env" ]; then
  if [ -f "$TMP/api.env.bak" ]; then
    cp -a "$TMP/api.env.bak" "$BASE/api/.env"
  elif [ -f "$API_STAGE/.env" ]; then
    cp -a "$API_STAGE/.env" "$BASE/api/.env"
  else
    echo "[deploy] ERROR: missing $BASE/api/.env — refuse deploy to protect database" >&2
    exit 1
  fi
fi

rsync -a --delete \
  --exclude '.env' \
  --exclude '.venv' \
  --exclude 'venv' \
  --exclude 'storage/' \
  --exclude '*.db' \
  --exclude '*.db-journal' \
  --exclude '*.sqlite' \
  --exclude '*.sqlite3' \
  --exclude '__pycache__/' \
  --exclude '.pytest_cache/' \
  "$API_STAGE/" "$BASE/api/"

rsync -a --delete "$TMP/web-dist/" "$BASE/web/"
rsync -a --delete "$TMP/h5-dist/" "$BASE/mp/"

cd "$BASE/api"
if [ -d .venv ]; then source .venv/bin/activate
elif [ -d venv ]; then source venv/bin/activate
fi
python -m pip install -r requirements.txt -q
# 仅增量迁移；禁止 downgrade / drop / 重建库
alembic upgrade head
alembic current

if systemctl list-unit-files 2>/dev/null | grep -q ai-marketing-api; then
  systemctl restart ai-marketing-api
elif systemctl list-unit-files 2>/dev/null | grep -q shengfei-api; then
  systemctl restart shengfei-api
else
  pkill -f 'uvicorn app.main:app' || true
  sleep 1
  nohup python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2 > /var/log/ai-marketing-api.log 2>&1 &
fi

sleep 2
curl -fsS http://127.0.0.1:8000/health || curl -fsS http://127.0.0.1:8000/api/v1/crm/health
nginx -t && systemctl reload nginx || true
echo "[deploy] done — database data preserved"
