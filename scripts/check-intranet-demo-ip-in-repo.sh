#!/usr/bin/env bash
# CI / 本地：确认仓库未再引用旧演示机 IP（含 .gitignore 内的 .env / .cursor）。
set -eo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LEGACY="192.168.20.201"

check_pat() {
  local pat="$1"
  local hits
  hits="$(git -C "$ROOT" grep -nF "$pat" 2>/dev/null || true)"
  if [[ -n "$hits" ]]; then
    echo "仍发现旧演示机可操作地址 ${pat}:" >&2
    echo "$hits" >&2
    exit 1
  fi
}

check_pat "http://${LEGACY}"
check_pat "@${LEGACY}"
check_pat "shengfei@${LEGACY}"
echo "ok: no operational ${LEGACY} URLs in repo"
