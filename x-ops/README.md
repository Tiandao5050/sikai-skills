# x-ops

Semi-automatic X ops pipeline (Asia time zone): generate a readable Markdown queue and push items into X drafts via browser automation.

## What you get
- `data/queue.md`: human-readable queue (Markdown)
- `scripts/queue_generate.py`: build 15 posts/day from seeds/sources
- `scripts/drafts_to_x.py`: open X, paste each item, save to drafts

## Quick start
1. Create a venv and install deps:

```bash
cd /home/sikai/ai-workspace/x-ops
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m playwright install
```

2. Add seeds and sources:
- `data/seeds.md` (daily links + notes)
- `data/sources.yaml` (optional RSS sources; if provided, they will be merged into the queue)

3. Generate the queue:

```bash
python scripts/queue_generate.py --date 2026-02-13 --limit 15
```

4. Push to X drafts (Chrome/Edge):

```bash
python scripts/drafts_to_x.py --queue data/queue.md --limit 15 --browser chrome
```

You will be asked to log in the first time. The session is stored under `data/profile`.

## Branch Feature: Read X post content accurately
Goal: paste one X URL and get the exact main post text + same-author thread saved locally.
Media is written into captured markdown as image URLs + markdown preview links.
For X long-form article mode, the script also extracts `/article/...` links and attempts article text capture.

Use browser login state (recommended):

```bash
python scripts/read_x_post.py "https://x.com/xxx/status/123" --browser chromium
```

If article content is login-gated, use manual login mode:

```bash
python scripts/read_x_post.py "https://x.com/xxx/status/123" --browser chromium --manual-login
```

For one-command pipeline with manual login:

```bash
scripts/fetch_and_learn.sh "https://x.com/xxx/status/123" chromium "" false true
```

If WSL cannot reach X directly, pass proxy explicitly:

```bash
python scripts/read_x_post.py "https://x.com/xxx/status/123" --browser chromium --proxy http://127.0.0.1:7890
```

One-command wrapper:

```bash
scripts/capture_x.sh "https://x.com/xxx/status/123" chromium
```

Proxy can be passed as arg 3 or env `X_PROXY`:

```bash
X_PROXY="http://172.18.96.1:7899" scripts/capture_x.sh "https://x.com/xxx/status/123" chromium
```

## Branch Feature: Fetch and Learn (one command)
Goal: paste one X URL and automatically generate a learning note + append to KB.

```bash
scripts/fetch_and_learn.sh "https://x.com/xxx/status/123" chromium
```

With proxy:

```bash
scripts/fetch_and_learn.sh "https://x.com/xxx/status/123" chromium "http://172.18.96.1:7899"
```

Optional media download (disabled by default):

```bash
scripts/fetch_and_learn.sh "https://x.com/xxx/status/123" chromium "" true
```

Output files:
- `data/captured/<status_id>.json`
- `data/captured/<status_id>.md`
- `data/learned/<status_id>.md`
- `data/knowledge/x_lessons.md`

Optional token mode (local env only, do not share in chat):

```bash
export X_AUTH_TOKEN='...'
export X_CSRF_TOKEN='...'
python scripts/read_x_post.py "https://x.com/xxx/status/123" --browser chromium
```

Interactive secure mode (recommended for beginners, token not shown in terminal):

```bash
scripts/capture_x_secure.sh "https://x.com/xxx/status/123" chromium "http://172.18.96.1:7899"
```

Or use one full cookie string:

```bash
export X_COOKIE_STRING='auth_token=...; ct0=...; twid=...'
python scripts/read_x_post.py "https://x.com/xxx/status/123" --browser chromium
```

Or load cookie string from file:

```bash
python scripts/read_x_post.py "https://x.com/xxx/status/123" --browser chromium --cookie-file data/x_cookie.txt
```

Output files:
- `data/captured/<status_id>.json`
- `data/captured/<status_id>.md`

If you also want non-author replies in output:

```bash
python scripts/read_x_post.py "https://x.com/xxx/status/123" --browser chromium --include-others
```

Custom save path:

```bash
python scripts/read_x_post.py "https://x.com/xxx/status/123" --output data/post.json
```

## Notes
- No X API usage. Drafts are created via browser automation only.
- If selectors change, run with `--debug` and adjust selectors in `scripts/drafts_to_x.py`.
- The generator can run without LLMs. If you want LLM rewrite, set `LLM_COMMAND` (see `scripts/queue_generate.py`).
