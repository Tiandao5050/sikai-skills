# Notion Sync

## Required Environment Variables
- `NOTION_TOKEN`: integration token with write permission.
- `NOTION_DATABASE_ID`: target database id.

## Optional
- `NOTION_TITLE_PROP`: title property name, default `Name`.

## Behavior
- Create one page per batch summary.
- Store full grouped markdown as page blocks.
- If Notion variables are missing, keep local-only output.
