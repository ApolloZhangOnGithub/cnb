#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "FATAL: run as root on the server" >&2
  exit 2
fi

SOURCE_DIR="${CNB_SYNC_SOURCE_DIR:-/opt/cnb-sync/source}"
DATA_DIR="${CNB_SYNC_DATA_DIR:-/var/lib/cnb-sync}"
ENV_DIR="/etc/cnb-sync"
ENV_FILE="$ENV_DIR/env"
SERVICE_DIR="/etc/systemd/system"

mkdir -p /opt/cnb-sync "$DATA_DIR" "$ENV_DIR" /var/backups/cnb-sync-git
if ! id -u cnb-sync >/dev/null 2>&1; then
  useradd --system --home-dir "$DATA_DIR" --shell /usr/sbin/nologin cnb-sync
fi

if [[ "$(pwd)" != "$SOURCE_DIR" ]]; then
  rm -rf "$SOURCE_DIR"
  mkdir -p "$SOURCE_DIR"
  tar --exclude .git -C "$(pwd)" -cf - . | tar -C "$SOURCE_DIR" -xf -
fi

chown -R cnb-sync:cnb-sync "$DATA_DIR"
chown -R cnb-sync:cnb-sync /var/backups/cnb-sync-git
chmod 700 "$DATA_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
  install -m 600 tools/cnb-sync-gateway/env.example "$ENV_FILE"
  token="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
)"
  sed -i "s/replace-with-a-long-random-token/$token/" "$ENV_FILE"
  echo "Created $ENV_FILE. Edit backup remote and GPG recipient before enabling backup."
else
  chmod 600 "$ENV_FILE"
fi

install -m 644 tools/cnb-sync-gateway/cnb-sync-gateway.service "$SERVICE_DIR/cnb-sync-gateway.service"
install -m 644 tools/cnb-sync-gateway/cnb-sync-backup.service "$SERVICE_DIR/cnb-sync-backup.service"
install -m 644 tools/cnb-sync-gateway/cnb-sync-backup.timer "$SERVICE_DIR/cnb-sync-backup.timer"
chmod +x "$SOURCE_DIR/bin/cnb-sync-gateway" "$SOURCE_DIR/tools/cnb-sync-gateway/"*.sh

systemctl daemon-reload
systemctl enable --now cnb-sync-gateway.service

echo "CNB sync gateway installed."
echo "Check service: systemctl status cnb-sync-gateway.service"
echo "Enable backup after editing $ENV_FILE and importing the public GPG key:"
echo "  systemctl enable --now cnb-sync-backup.timer"
