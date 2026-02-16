#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: scripts/fetch_and_learn.sh <x_post_url> [browser] [proxy] [download_media] [manual_login]"
  echo "Example: scripts/fetch_and_learn.sh 'https://x.com/user/status/123' chromium http://172.18.96.1:7899 false true"
  exit 1
fi

URL="$1"
BROWSER="${2:-chromium}"
PROXY="${3:-}"
DOWNLOAD_MEDIA="${4:-false}"
MANUAL_LOGIN="${5:-false}"

ROOT="/home/sikai/ai-workspace/x-ops"
cd "$ROOT"

if [ ! -f ".venv/bin/activate" ]; then
  echo "Missing virtual env. Run setup first in $ROOT"
  exit 1
fi

source .venv/bin/activate

ARGS=("scripts/read_x_post.py" "$URL" "--browser" "$BROWSER" "--timeout" "180000")
if [ -n "$PROXY" ]; then
  ARGS+=("--proxy" "$PROXY")
fi
if [ "$DOWNLOAD_MEDIA" = "true" ]; then
  ARGS+=("--download-media")
fi
if [ "$MANUAL_LOGIN" = "true" ]; then
  ARGS+=("--manual-login")
fi

python "${ARGS[@]}"
python scripts/learn_from_capture.py --url "$URL"

STATUS_ID="$(echo "$URL" | sed -n 's#.*status/\([0-9]\+\).*#\1#p')"

if [ -n "$STATUS_ID" ]; then
  echo "Done. Files:"
  echo "- data/captured/${STATUS_ID}.json"
  echo "- data/captured/${STATUS_ID}.md"
  echo "- data/learned/${STATUS_ID}.md"
  echo "- data/knowledge/x_lessons.md"
else
  echo "Done. Check data/captured and data/learned."
fi
