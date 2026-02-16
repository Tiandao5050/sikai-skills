#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: scripts/check_capture.sh <status_id>"
  exit 1
fi

STATUS_ID="$1"
JSON_PATH="/home/sikai/ai-workspace/x-ops/data/captured/${STATUS_ID}.json"

if [ ! -f "$JSON_PATH" ]; then
  echo "Not found: $JSON_PATH"
  exit 1
fi

python3 - <<'PY' "$JSON_PATH"
import json, sys
p = sys.argv[1]
d = json.load(open(p, "r", encoding="utf-8"))
main = d.get("main", {})
a = (d.get("articles") or [{}])[0]
print("main_status_id=", main.get("status_id", ""))
print("main_text_len=", len(main.get("text") or ""))
print("article_status=", a.get("status", ""))
print("article_text_len=", len(a.get("text") or ""))
PY
