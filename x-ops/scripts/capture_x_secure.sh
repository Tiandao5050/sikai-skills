#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: scripts/capture_x_secure.sh <x_post_url> [browser] [proxy]"
  echo "Example: scripts/capture_x_secure.sh 'https://x.com/user/status/123' chromium 'http://172.18.96.1:7899'"
  exit 1
fi

URL="$1"
BROWSER="${2:-chromium}"
PROXY="${3:-${X_PROXY:-}}"

ROOT="/home/sikai/ai-workspace/x-ops"
cd "$ROOT"

if [ ! -f ".venv/bin/activate" ]; then
  echo "Missing virtual env. Run setup first in $ROOT"
  exit 1
fi

source .venv/bin/activate

echo "Paste your x.com cookies (won't be echoed on screen)."
read -rsp "auth_token: " X_AUTH_TOKEN
echo ""
read -rsp "ct0: " X_CSRF_TOKEN
echo ""

export X_AUTH_TOKEN X_CSRF_TOKEN

ARGS=("scripts/read_x_post.py" "$URL" "--browser" "$BROWSER" "--timeout" "180000")
if [ -n "$PROXY" ]; then
  ARGS+=("--proxy" "$PROXY")
fi

python "${ARGS[@]}"

unset X_AUTH_TOKEN X_CSRF_TOKEN
echo "Done. Token env cleared."
