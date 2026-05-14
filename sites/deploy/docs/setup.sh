#!/usr/bin/env bash
# Deploy cnb docs as static files under /docs/ on the existing server.
# Run as root from the repo root.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "FATAL: run as root on the server" >&2
  exit 2
fi

DOCS_DIR=/opt/cnb-docs

echo "=== 1. create docs directory ==="
mkdir -p "$DOCS_DIR"

echo "=== 2. patch nginx — add /docs/ location ==="
NGINX_CONF=""
if [[ -f /etc/nginx/sites-available/cnb-blog ]]; then
  NGINX_CONF=/etc/nginx/sites-available/cnb-blog
elif [[ -f /etc/nginx/conf.d/cnb-blog.conf ]]; then
  NGINX_CONF=/etc/nginx/conf.d/cnb-blog.conf
else
  echo "ERROR: cannot find cnb-blog nginx config" >&2
  exit 1
fi

if grep -q '/docs/' "$NGINX_CONF"; then
  echo "  /docs/ location already exists, skipping"
else
  # Insert docs location before the catch-all proxy location
  sed -i '/location \/ {/i \
    location /docs/ {\
        alias /opt/cnb-docs/;\
        index index.html;\
        try_files $uri $uri/ =404;\
    }\
' "$NGINX_CONF"
  echo "  added /docs/ location to $NGINX_CONF"
fi

nginx -t && systemctl reload nginx

echo ""
echo "=== DONE ==="
echo "Docs will be served at /docs/ on the existing server."
echo ""
echo "Next steps:"
echo "  1. Build: cd docs-site && npm ci && npm run build"
echo "  2. Upload: rsync -azP --delete docs-site/out/ root@<SERVER_IP>:$DOCS_DIR/"
echo ""
