#!/usr/bin/env bash
# 在 192.168.20.200 上执行一次，配置 git push deploy master 自动发布。
# 数据安全原则：
#   1) 只 alembic upgrade head（禁止 downgrade / drop / recreate）
#   2) 永不覆盖/删除 .env、.venv、storage、*.db
#   3) PostgreSQL / SQLite 业务数据均不触碰
set -euo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/opt/shengfei/ai-content-marketing}"
GIT_REPO_DIR="${GIT_REPO_DIR:-/opt/git/ai-content-marketing.git}"
WEB_DIR="${WEB_DIR:-/opt/shengfei/apps/web}"
H5_DIR="${H5_DIR:-/opt/shengfei/apps/mp}"
API_DIR="${API_DIR:-/opt/shengfei/apps/api}"
API_SERVICE="${API_SERVICE:-ai-marketing-api}"

mkdir -p "$(dirname "$GIT_REPO_DIR")" "$DEPLOY_DIR"
if [ ! -d "$GIT_REPO_DIR/HEAD" ]; then
  git init --bare "$GIT_REPO_DIR"
fi

cat > "$GIT_REPO_DIR/hooks/post-receive" << EOF
#!/bin/bash
set -e
DEPLOY_DIR='$DEPLOY_DIR'
WEB_DIR='$WEB_DIR'
H5_DIR='$H5_DIR'
API_DIR='$API_DIR'
API_SERVICE='$API_SERVICE'
GIT_REPO='$GIT_REPO_DIR'

while read -r oldrev newrev ref; do
  branch="\${ref#refs/heads/}"
  [ "\$branch" = "master" ] || continue
  echo "[deploy] checkout \$branch -> \$DEPLOY_DIR"
  git --work-tree="\$DEPLOY_DIR" --git-dir="\$GIT_REPO" checkout -f "\$branch"

  echo "[deploy] sync API code (preserve .env / .venv / storage / *.db)"
  mkdir -p "\$API_DIR"
  # 先把线上配置与数据护住，再同步代码
  if [ ! -f "\$API_DIR/.env" ] && [ -f "\$DEPLOY_DIR/apps/api/.env" ]; then
    cp "\$DEPLOY_DIR/apps/api/.env" "\$API_DIR/.env"
  fi
  if [ ! -f "\$API_DIR/.env" ]; then
    echo "[deploy] ERROR: missing \$API_DIR/.env — refuse deploy to protect database" >&2
    exit 1
  fi
  rsync -a \\
    --exclude '.env' \\
    --exclude '.venv' \\
    --exclude 'venv' \\
    --exclude 'storage/' \\
    --exclude '*.db' \\
    --exclude '*.db-journal' \\
    --exclude '__pycache__/' \\
    --exclude '.pytest_cache/' \\
    "\$DEPLOY_DIR/apps/api/" "\$API_DIR/"

  echo "[deploy] alembic upgrade head (additive only; NEVER wipe / downgrade)"
  cd "\$API_DIR"
  if [ -d .venv ]; then source .venv/bin/activate
  elif [ -d venv ]; then source venv/bin/activate
  elif [ -d "\$DEPLOY_DIR/apps/api/.venv" ]; then source "\$DEPLOY_DIR/apps/api/.venv/bin/activate"
  fi
  pip install -r requirements.txt -q
  # 禁止：alembic downgrade / drop_all / 删除 db 文件 / 重建库
  alembic upgrade head
  alembic current

  echo "[deploy] Web build"
  cd "\$DEPLOY_DIR/apps/web"
  [ -f .env.production ] || echo 'VITE_API_BASE_URL=' > .env.production
  npm ci --silent || npm install --silent
  npm run build
  mkdir -p "\$WEB_DIR"
  rsync -a --delete dist/ "\$WEB_DIR/"

  echo "[deploy] H5 build"
  cd "\$DEPLOY_DIR/apps/mp"
  [ -f .env.production ] || echo 'VITE_API_BASE_URL=http://192.168.20.200:8088' > .env.production
  npm ci --silent || npm install --silent
  npm run build:h5
  mkdir -p "\$H5_DIR"
  rsync -a --delete dist/build/h5/ "\$H5_DIR/"

  if systemctl list-unit-files 2>/dev/null | grep -q "\$API_SERVICE"; then
    systemctl restart "\$API_SERVICE"
  else
    pkill -f 'uvicorn app.main:app' || true
    sleep 1
    cd "\$API_DIR"
    source .venv/bin/activate
    nohup python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2 > /var/log/ai-marketing-api.log 2>&1 &
  fi
  nginx -t && systemctl reload nginx || true
  echo "[deploy] done — database data preserved"
done
EOF
chmod +x "$GIT_REPO_DIR/hooks/post-receive"
echo "OK: bare repo at $GIT_REPO_DIR"
echo "Data safety: upgrade-only migrations; .env/storage/*.db never overwritten"
echo "Next: add developer SSH public key to authorized_keys"
echo "Then on dev machine: git push deploy master"
