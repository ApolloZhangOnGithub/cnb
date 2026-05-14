#!/usr/bin/env bash
# Usage: bash deploy/set-github-oauth.sh <client_id> <client_secret>
set -euo pipefail

if [ $# -ne 2 ]; then
  echo "Usage: $0 <client_id> <client_secret>"
  exit 1
fi

ssh root@47.106.190.199 "printf 'GITHUB_CLIENT_ID=%s\nGITHUB_CLIENT_SECRET=%s\n' '$1' '$2' > /opt/cnb-blog/.env && chmod 600 /opt/cnb-blog/.env && echo 'OK saved'"
