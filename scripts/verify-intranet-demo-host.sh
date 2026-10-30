#!/usr/bin/env bash
# 在内网开发机上验证 192.168.10.201 演示 / Git / GitLab 可达性（Cloud Agent 无法访问私网，须本地执行）。
set -euo pipefail

HOST="${INTRANET_DEMO_HOST:-192.168.10.201}"
WEB_PORT="${INTRANET_DEMO_WEB_PORT:-8088}"
H5_PORT="${INTRANET_DEMO_H5_PORT:-8089}"
GITLAB_PORT="${INTRANET_GITLAB_PORT:-80}"
SSH_USER="${INTRANET_DEMO_SSH_USER:-shengfei}"
DEPLOY_GIT="${INTRANET_DEPLOY_GIT:-${SSH_USER}@${HOST}:/opt/git/ai-content-marketing.git}"

fail=0
ok() { echo "[ok] $*"; }
warn() { echo "[warn] $*" >&2; }
bad() { echo "[fail] $*" >&2; fail=1; }

http_code() {
  curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 --max-time 8 "$1" 2>/dev/null || echo "000"
}

echo "=== 内网演示机自检 host=${HOST} ==="

code="$(http_code "http://${HOST}:${WEB_PORT}/login")"
if [[ "$code" =~ ^(200|301|302|304)$ ]]; then ok "Web :${WEB_PORT}/login HTTP ${code}"; else bad "Web :${WEB_PORT}/login HTTP ${code}"; fi

code="$(http_code "http://${HOST}:${H5_PORT}/")"
if [[ "$code" =~ ^(200|301|302|304)$ ]]; then ok "H5 :${H5_PORT}/ HTTP ${code}"; else bad "H5 :${H5_PORT}/ HTTP ${code}"; fi

code="$(http_code "http://${HOST}:${WEB_PORT}/health")"
if [[ "$code" == "200" ]]; then ok "API /health HTTP 200"; else warn "API /health HTTP ${code}（若未挂在此路径可忽略）"; fi

if git ls-remote "$DEPLOY_GIT" HEAD &>/dev/null; then ok "deploy 远程可读: ${DEPLOY_GIT}"; else bad "deploy 远程不可读: ${DEPLOY_GIT}"; fi

deploy_url="$(git config --get remote.deploy.url 2>/dev/null || true)"
if [[ -n "$deploy_url" ]]; then
  if [[ "$deploy_url" == *"${HOST}"* ]]; then ok "本机 remote.deploy 含 ${HOST}"; else bad "本机 remote.deploy=${deploy_url}，应含 ${HOST}"; fi
else
  warn "未配置 git remote deploy，可执行: git remote add deploy ${DEPLOY_GIT}"
fi

code="$(http_code "http://${HOST}:${GITLAB_PORT}/")"
if [[ "$code" =~ ^(200|301|302|304)$ ]]; then ok "GitLab http://${HOST}:${GITLAB_PORT}/ HTTP ${code}"; else warn "GitLab :${GITLAB_PORT} HTTP ${code}（HTTPS 或非 80 端口请设 INTRANET_GITLAB_PORT）"; fi

if bash "$(dirname "$0")/check-intranet-demo-ip-in-repo.sh" &>/dev/null; then
  ok "仓库无可操作旧地址 192.168.20.201"
else
  bad "仓库仍含可操作旧地址 192.168.20.201（运行 scripts/check-intranet-demo-ip-in-repo.sh）"
fi

if [[ "$fail" -ne 0 ]]; then
  echo "=== 自检未通过 ==="
  exit 1
fi
echo "=== 自检通过 ==="
