#!/usr/bin/env bash
# Deploy cnb blog alongside cnb-sync-gateway on Alibaba Cloud ECS.
# Run as root from the repo root.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "FATAL: run as root on the server" >&2
  exit 2
fi

APP_DIR=/opt/cnb-blog
DATA_DIR=$APP_DIR/data

# ── detect package manager ──
if command -v apt-get &>/dev/null; then
  PKG="apt-get install -y -qq"
  apt-get update -qq
elif command -v dnf &>/dev/null; then
  PKG="dnf install -y -q"
elif command -v yum &>/dev/null; then
  PKG="yum install -y -q"
else
  echo "FATAL: no supported package manager (apt/dnf/yum)" >&2
  exit 2
fi

echo "=== 1. install dependencies ==="
$PKG python3 nginx

echo "=== 2. create user and directories ==="
if ! id -u cnb-blog &>/dev/null; then
  useradd --system --home-dir "$DATA_DIR" --shell /usr/sbin/nologin cnb-blog
fi
mkdir -p "$APP_DIR" "$DATA_DIR"
chown -R cnb-blog:cnb-blog "$DATA_DIR"

echo "=== 3. copy application files ==="
mkdir -p "$APP_DIR/bin" "$APP_DIR/lib"
cp bin/blog-server "$APP_DIR/bin/"
cp lib/blog_db.py lib/blog_html.py lib/blog_server.py "$APP_DIR/lib/"
touch "$APP_DIR/lib/__init__.py"
chmod +x "$APP_DIR/bin/blog-server"

echo "=== 4. install systemd service ==="
install -m 644 deploy/blog/cnb-blog.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now cnb-blog

echo "=== 5. install nginx config ==="
# nginx config dir varies by distro
if [[ -d /etc/nginx/sites-available ]]; then
  install -m 644 deploy/blog/nginx-blog.conf /etc/nginx/sites-available/cnb-blog
  ln -sf /etc/nginx/sites-available/cnb-blog /etc/nginx/sites-enabled/
else
  install -m 644 deploy/blog/nginx-blog.conf /etc/nginx/conf.d/cnb-blog.conf
fi
nginx -t && systemctl enable --now nginx && systemctl reload nginx

echo ""
echo "=== DONE ==="
echo "Blog is running on http://127.0.0.1:8090 behind nginx."
echo ""
echo "Next steps:"
echo "  1. Point GoDaddy DNS A record for c-n-b.space → this server's public IP"
echo "  2. Install certbot and get HTTPS:"
echo "     $PKG certbot python3-certbot-nginx"
echo "     certbot --nginx -d c-n-b.space -d www.c-n-b.space"
echo ""
echo "Useful commands:"
echo "  systemctl status cnb-blog"
echo "  journalctl -u cnb-blog -f"
echo ""
echo "Existing services on this machine:"
systemctl is-active cnb-sync-gateway 2>/dev/null && echo "  cnb-sync-gateway: running (:8765)" || true
echo "  cnb-blog: running (:8090 → nginx :80)"
