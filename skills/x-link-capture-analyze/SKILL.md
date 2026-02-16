---
name: x-link-capture-analyze
description: Unified X link ingestion and analysis workflow. Use when user sends one or more X links and wants immediate capture + analysis without manually running terminal commands. Trigger for requests like “给你链接你直接抓并分析”, “目的1/2/3”, “批量学习笔记”, or “先抓再拆解结构/教程执行”.
---

# X Link Capture Analyze

## Overview
Run one command path for single-link or batch-link X workflows: capture content, generate learned artifacts, and route to the right analyzer by purpose.

## Input Contract
Ask for only the minimum fields:
- `url` for single link, or `links` list / links file for batch.
- `purpose`: `tutorial`, `viral`, or `batch`.
- Optional: `proxy`, `browser` (`chromium` default), `topic`.

If user says “目的1/2/3”, map as:
- `1` -> `tutorial`
- `2` -> `viral`
- `3` -> `batch`

## One Command
Use the dispatcher script:

```bash
python /home/sikai/ai-workspace/skills/x-link-capture-analyze/scripts/run_x_capture_analyze.py --url "<x_url>" --purpose viral
```

For batch:

```bash
python /home/sikai/ai-workspace/skills/x-link-capture-analyze/scripts/run_x_capture_analyze.py --purpose batch --links-file /home/sikai/ai-workspace/x-ops/data/inputs/links.txt
```

If proxy is required, append:

```bash
--proxy http://172.18.96.1:7899
```

If cookie injection is needed, append:

```bash
--cookie-file /home/sikai/ai-workspace/x-ops/data/x_cookie.txt
```

## Output Rules
Always report:
- capture status (`main_status_id`, `main_text_len`, `article_status`, `article_text_len` when available)
- generated files
- next action (ask for confirmation before generating final publishing copy in `viral` mode)

## References
- Purpose mapping and routing notes: `references/purpose-routing.md`
