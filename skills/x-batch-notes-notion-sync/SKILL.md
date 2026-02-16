---
name: x-batch-notes-notion-sync
description: Process a batch of X links, capture and summarize all posts, classify them into thematic categories, and produce one consolidated learning note with optional Notion sync. Use when user sends multiple X links and asks for grouped learning notes, category summaries, or Notion-linked knowledge management.
---

# X Batch Notes Notion Sync

## Overview
Handle multi-link X learning workflows end-to-end: capture, classify, summarize, and optionally sync to Notion.

## Workflow
1. Receive links in message or file.
2. Capture missing posts through `x-ops` pipeline.
3. Build one grouped note with category sections and uncategorized section.
4. Optionally sync grouped note to Notion.

## Step 1: Prepare Link File
Use one URL per line in a text file.
Example path:
- `/home/sikai/ai-workspace/x-ops/data/inputs/links.txt`

## Step 2: Run Batch Processor

```bash
python /home/sikai/ai-workspace/skills/x-batch-notes-notion-sync/scripts/batch_x_learning.py --links-file /home/sikai/ai-workspace/x-ops/data/inputs/links.txt
```

With proxy and live fetching:

```bash
python /home/sikai/ai-workspace/skills/x-batch-notes-notion-sync/scripts/batch_x_learning.py --links-file /home/sikai/ai-workspace/x-ops/data/inputs/links.txt --fetch --proxy http://172.18.96.1:7899
```

## Step 3: Optional Notion Sync
Set environment variables:
- `NOTION_TOKEN`
- `NOTION_DATABASE_ID`

Then run with `--notion`.

## Output
- Consolidated note: `/home/sikai/ai-workspace/x-ops/data/batch-notes/<name>.md`
- Optional Notion page id in command output JSON

## References
- Notion configuration: `references/notion_sync.md`
