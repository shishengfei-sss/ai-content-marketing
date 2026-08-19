#!/usr/bin/env bash
# 演示机 Nginx：入驻/资质/课时视频上传。PRD 视频单文件 ≤2GB，默认 1m 会 413。
set -euo pipefail
CONF="/etc/nginx/conf.d/shengfei.conf"
if sudo grep -q 'client_max_body_size 2048m' "$CONF"; then
  echo "already 2048m"
else
  sudo sed -i 's/client_max_body_size 50m;/client_max_body_size 2048m;/g' "$CONF"
  sudo sed -i 's/client_max_body_size 1m;/client_max_body_size 2048m;/g' "$CONF"
  if ! sudo grep -q 'client_max_body_size' "$CONF"; then
    sudo sed -i 's/server_name _;/server_name _;\n\n    client_max_body_size 2048m;/g' "$CONF"
  fi
fi
if ! sudo grep -q 'proxy_read_timeout' "$CONF"; then
  sudo sed -i '/proxy_set_header X-Forwarded-Proto/a\        proxy_read_timeout 3600s;\n        proxy_send_timeout 3600s;' "$CONF"
fi
sudo nginx -t
sudo systemctl reload nginx
echo "nginx OK: client_max_body_size 2048m"
