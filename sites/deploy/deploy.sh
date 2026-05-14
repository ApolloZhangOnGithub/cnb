#!/usr/bin/env bash
# Deploy cnb services to Alibaba Cloud ECS.
# Automatically backs up before overwriting. Supports rollback.
#
# Usage:
#   deploy/deploy.sh blog          # deploy blog code
#   deploy/deploy.sh docs          # build + deploy docs
#   deploy/deploy.sh site          # deploy main site
#   deploy/deploy.sh rollback blog # rollback blog to last backup
set -euo pipefail

SERVER="root@47.106.190.199"
BACKUP_KEEP=5

backup() {
  local name=$1 remote_dir=$2
  local ts=$(date +%Y%m%d%H%M%S)
  local backup_dir="/opt/backups/${name}/${ts}"
  echo "=== backup ${name} → ${backup_dir} ==="
  ssh "$SERVER" "mkdir -p ${backup_dir} && cp -a ${remote_dir}/. ${backup_dir}/"
  # prune old backups, keep latest $BACKUP_KEEP
  ssh "$SERVER" "cd /opt/backups/${name} && ls -1d */ 2>/dev/null | sort | head -n -${BACKUP_KEEP} | xargs -r rm -rf"
  echo "OK backed up. Recent backups:"
  ssh "$SERVER" "ls -1d /opt/backups/${name}/*/ 2>/dev/null | tail -${BACKUP_KEEP}"
}

rollback() {
  local name=$1 remote_dir=$2
  local latest=$(ssh "$SERVER" "ls -1d /opt/backups/${name}/*/ 2>/dev/null | tail -1")
  if [[ -z "$latest" ]]; then
    echo "ERROR: no backups found for ${name}" >&2
    exit 1
  fi
  echo "=== rollback ${name} ← ${latest} ==="
  ssh "$SERVER" "rm -rf ${remote_dir}/* && cp -a ${latest}/. ${remote_dir}/"
  echo "OK rolled back to ${latest}"
}

deploy_blog() {
  local remote="/opt/cnb-blog/lib"
  backup blog "$remote"
  echo "=== deploy blog ==="
  rsync -az lib/blog_db.py lib/blog_html.py lib/blog_server.py "$SERVER:${remote}/"
  ssh "$SERVER" "systemctl restart cnb-blog"
  echo "OK blog deployed and restarted"
}

deploy_docs() {
  local remote="/opt/cnb-docs/site"
  backup docs "$remote"
  echo "=== build docs ==="
  (cd sites/docs && rm -rf .next && npm run build)
  echo "=== deploy docs ==="
  rsync -az --delete sites/docs/out/ "$SERVER:${remote}/"
  echo "OK docs deployed"
}

deploy_site() {
  local remote="/opt/cnb-site"
  backup site "$remote"
  echo "=== deploy site ==="
  rsync -az sites/home/ "$SERVER:${remote}/"
  echo "OK site deployed"
}

cmd="${1:-}"
target="${2:-}"

case "$cmd" in
  blog) deploy_blog ;;
  docs) deploy_docs ;;
  site) deploy_site ;;
  rollback)
    case "$target" in
      blog) rollback blog /opt/cnb-blog/lib && ssh "$SERVER" "systemctl restart cnb-blog" ;;
      docs) rollback docs /opt/cnb-docs/site ;;
      site) rollback site /opt/cnb-site ;;
      *) echo "Usage: $0 rollback <blog|docs|site>" >&2; exit 1 ;;
    esac
    ;;
  *)
    echo "Usage: $0 <blog|docs|site|rollback>" >&2
    echo ""
    echo "  blog              deploy blog server code"
    echo "  docs              build + deploy docs site"
    echo "  site              deploy main site"
    echo "  rollback <target> rollback to last backup"
    exit 1
    ;;
esac
