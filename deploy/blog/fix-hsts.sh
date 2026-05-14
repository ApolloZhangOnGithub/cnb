#!/usr/bin/env bash
# One-shot fix: add HSTS header to the live nginx HTTPS config.
# Run as root on the ECS server.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "FATAL: run as root" >&2
  exit 2
fi

NGINX_CONF=""
if [[ -f /etc/nginx/sites-available/cnb-blog ]]; then
  NGINX_CONF=/etc/nginx/sites-available/cnb-blog
elif [[ -f /etc/nginx/conf.d/cnb-blog.conf ]]; then
  NGINX_CONF=/etc/nginx/conf.d/cnb-blog.conf
else
  echo "ERROR: cannot find cnb-blog nginx config" >&2
  exit 1
fi

if grep -q 'Strict-Transport-Security' "$NGINX_CONF"; then
  echo "OK HSTS header already present in $NGINX_CONF"
else
  sed -i '/listen 443/a\    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;' "$NGINX_CONF"
  echo "OK added HSTS header to $NGINX_CONF"
fi

# Ensure HTTP block redirects to HTTPS instead of proxying
if grep -A2 'listen 80' "$NGINX_CONF" | grep -q 'return 301'; then
  echo "OK HTTP→HTTPS redirect already present"
else
  echo "WARN: HTTP block still proxies instead of redirecting."
  echo "      Alibaba Cloud blocks HTTP anyway, but consider updating to 'return 301 https://...'"
fi

nginx -t && systemctl reload nginx
echo "OK nginx reloaded"
