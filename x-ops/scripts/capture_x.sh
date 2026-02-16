#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: scripts/capture_x.sh <x_post_url> [chromium|chrome|edge] [proxy] [download_media]"
  exit 1
fi

URL="$1"
BROWSER="${2:-chromium}"
PROXY="${3:-${X_PROXY:-}}"
DOWNLOAD_MEDIA="${4:-false}"

ROOT="/home/sikai/ai-workspace/x-ops"
cd "$ROOT"

if [ ! -d ".venv" ]; then
  echo "Missing .venv. Run setup first:"
  echo "cd $ROOT && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && python -m playwright install"
  exit 1
fi

source .venv/bin/activate

ARGS=("scripts/read_x_post.py" "$URL" "--browser" "$BROWSER")
if [ -n "$PROXY" ]; then
  ARGS+=("--proxy" "$PROXY")
fi
if [ "$DOWNLOAD_MEDIA" = "true" ]; then
  ARGS+=("--download-media")
fi

python "${ARGS[@]}"
