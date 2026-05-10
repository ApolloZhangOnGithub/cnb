#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${CNB_SYNC_ENV_FILE:-/etc/cnb-sync/env}"
if [[ -r "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

DATA_DIR="${CNB_SYNC_DATA_DIR:-/var/lib/cnb-sync}"
DB_PATH="${CNB_SYNC_DB_PATH:-$DATA_DIR/cnb-sync.db}"
BACKUP_REPO="${CNB_SYNC_BACKUP_REPO:-/var/backups/cnb-sync-git}"
BACKUP_BRANCH="${CNB_SYNC_BACKUP_BRANCH:-main}"
BACKUP_KEEP="${CNB_SYNC_BACKUP_KEEP:-96}"
REMOTE="${CNB_SYNC_BACKUP_GIT_REMOTE:-}"
RECIPIENT="${CNB_SYNC_BACKUP_GPG_RECIPIENT:-}"
GIT_USER_NAME="${CNB_SYNC_BACKUP_GIT_USER_NAME:-CNB Sync Backup}"
GIT_USER_EMAIL="${CNB_SYNC_BACKUP_GIT_USER_EMAIL:-cnb-sync-backup@local}"

if [[ -z "$REMOTE" ]]; then
  echo "FATAL: CNB_SYNC_BACKUP_GIT_REMOTE is required" >&2
  exit 2
fi
if [[ -z "$RECIPIENT" ]]; then
  echo "FATAL: CNB_SYNC_BACKUP_GPG_RECIPIENT is required" >&2
  exit 2
fi
if [[ ! -f "$DB_PATH" ]]; then
  echo "FATAL: database not found: $DB_PATH" >&2
  exit 2
fi

mkdir -p "$(dirname "$BACKUP_REPO")"
if [[ ! -d "$BACKUP_REPO/.git" ]]; then
  git clone "$REMOTE" "$BACKUP_REPO"
fi

cd "$BACKUP_REPO"
git config user.name "$GIT_USER_NAME"
git config user.email "$GIT_USER_EMAIL"
if git ls-remote --exit-code --heads origin "$BACKUP_BRANCH" >/dev/null 2>&1; then
  git fetch origin "$BACKUP_BRANCH"
  git checkout "$BACKUP_BRANCH" 2>/dev/null || git checkout -b "$BACKUP_BRANCH" "origin/$BACKUP_BRANCH"
  git pull --ff-only origin "$BACKUP_BRANCH"
else
  git checkout "$BACKUP_BRANCH" 2>/dev/null || git checkout -b "$BACKUP_BRANCH"
fi

tmp="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp"
}
trap cleanup EXIT

mkdir -p "$tmp/payload"
sqlite3 "$DB_PATH" ".backup '$tmp/payload/cnb-sync.db'"
if [[ -d "$DATA_DIR/attachments" ]]; then
  cp -a "$DATA_DIR/attachments" "$tmp/payload/attachments"
fi

cat > "$tmp/payload/metadata.json" <<EOF
{
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "source_host": "$(hostname -f 2>/dev/null || hostname)",
  "db_path": "$DB_PATH"
}
EOF

mkdir -p snapshots
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="snapshots/cnb-sync-$stamp.tar.gz.gpg"
tar -C "$tmp/payload" -czf - . | gpg --batch --yes --trust-model always --encrypt --recipient "$RECIPIENT" -o "$target"

if [[ "$BACKUP_KEEP" =~ ^[0-9]+$ ]] && (( BACKUP_KEEP > 0 )); then
  mapfile -t old_files < <(ls -1t snapshots/*.tar.gz.gpg 2>/dev/null | tail -n +"$((BACKUP_KEEP + 1))" || true)
  if (( ${#old_files[@]} > 0 )); then
    git rm -f "${old_files[@]}"
  fi
fi

git add "$target"
if git diff --cached --quiet; then
  echo "No backup changes to commit"
  exit 0
fi

git commit -m "backup cnb sync state $stamp"
git push origin "$BACKUP_BRANCH"
echo "Wrote encrypted backup: $target"
