# Purpose Routing

## Modes
- `tutorial`: capture + learned note + tutorial action plan.
- `viral`: capture + learned note + viral structure report.
- `batch`: process multiple links and output grouped note (optional Notion sync via existing batch script flags/env).

## Artifacts
- Capture: `/home/sikai/ai-workspace/x-ops/data/captured/<status_id>.json`
- Capture markdown: `/home/sikai/ai-workspace/x-ops/data/captured/<status_id>.md`
- Learned note: `/home/sikai/ai-workspace/x-ops/data/learned/<status_id>.md`
- Tutorial plan: `/home/sikai/ai-workspace/x-ops/data/action-plans/<status_id>.md`
- Viral report: `/home/sikai/ai-workspace/x-ops/data/structure/<status_id>.md`
- Batch note: `/home/sikai/ai-workspace/x-ops/data/batch-notes/<name>.md`

## Cookie Strategy
- Prefer `--cookie-file /home/sikai/ai-workspace/x-ops/data/x_cookie.txt`.
- Fallback to env vars `X_AUTH_TOKEN` and `X_CSRF_TOKEN`.
- Never ask user to paste secrets into chat.

## Validation Snippet
For single-link jobs, surface these fields from capture JSON:
- `main.status_id`
- `len(main.text)`
- `articles[0].status` (if exists)
- `len(articles[0].text)` (if exists)
