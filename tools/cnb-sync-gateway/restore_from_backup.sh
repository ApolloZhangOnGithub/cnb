#!/usr/bin/env bash
set -euo pipefail

if (( $# < 2 )); then
  echo "usage: restore_from_backup.sh BACKUP.tar.gz.gpg DATA_DIR" >&2
  exit 2
fi

backup="$1"
data_dir="$2"

if [[ ! -f "$backup" ]]; then
  echo "FATAL: backup not found: $backup" >&2
  exit 2
fi

tmp="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp"
}
trap cleanup EXIT

gpg --decrypt "$backup" | tar -C "$tmp" -xzf -
if [[ ! -f "$tmp/cnb-sync.db" ]]; then
  echo "FATAL: backup payload missing cnb-sync.db" >&2
  exit 2
fi

mkdir -p "$data_dir"
install -m 600 "$tmp/cnb-sync.db" "$data_dir/cnb-sync.db"
if [[ -d "$tmp/attachments" ]]; then
  rm -rf "$data_dir/attachments"
  cp -a "$tmp/attachments" "$data_dir/attachments"
fi
echo "Restored CNB sync data into $data_dir"
