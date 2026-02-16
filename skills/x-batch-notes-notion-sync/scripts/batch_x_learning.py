#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import requests

XOPS_DIR = Path("/home/sikai/ai-workspace/x-ops")
CAPTURE_DIR = XOPS_DIR / "data" / "captured"
OUT_DIR = XOPS_DIR / "data" / "batch-notes"

CATEGORY_RULES = {
    "install-debug": ["安装", "配置", "报错", "debug", "error", "setup", "deploy", "运行", "启动"],
    "architecture-principles": ["原理", "架构", "architecture", "protocol", "cdp", "机制", "design"],
    "security-risk": ["安全", "漏洞", "risk", "风控", "暴露", "认证", "权限", "攻击"],
    "growth-content": ["爆款", "内容", "运营", "流量", "选题", "结构", "转化", "自媒体"],
    "tools-release": ["发布", "更新", "release", "new", "模型", "功能", "版本"],
}


def extract_status_id(url: str) -> str:
    m = re.search(r"/status/(\d+)", url or "")
    return m.group(1) if m else ""


def load_links(path: Path) -> List[str]:
    links: List[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        links.append(line)
    return links


def capture_if_needed(url: str, browser: str, proxy: str, fetch: bool) -> Path:
    sid = extract_status_id(url)
    if not sid:
        raise ValueError(f"Invalid X link: {url}")

    cap = CAPTURE_DIR / f"{sid}.json"
    if cap.exists() or not fetch:
        return cap

    cmd = [str(XOPS_DIR / "scripts" / "fetch_and_learn.sh"), url, browser]
    if proxy:
        cmd.append(proxy)
    subprocess.run(cmd, cwd=str(XOPS_DIR), check=True)
    return cap


def categorize(text: str) -> str:
    low = text.lower()
    for cat, keys in CATEGORY_RULES.items():
        for k in keys:
            if k.lower() in low:
                return cat
    return "uncategorized"


def summarize(text: str, limit: int = 120) -> str:
    t = re.sub(r"\s+", " ", text or "").strip()
    if len(t) <= limit:
        return t
    return t[: limit - 1] + "…"


def build_grouped(items: List[Dict]) -> Dict[str, List[Dict]]:
    grouped: Dict[str, List[Dict]] = {k: [] for k in list(CATEGORY_RULES.keys()) + ["uncategorized"]}
    for it in items:
        grouped[it["category"]].append(it)
    return grouped


def render_md(grouped: Dict[str, List[Dict]], total: int, name: str) -> str:
    lines: List[str] = []
    lines.append(f"# X Batch Learning Note {name}")
    lines.append("")
    lines.append(f"- total_links: {total}")
    lines.append(f"- generated_at: {datetime.now().isoformat()}")
    lines.append("")

    for cat, posts in grouped.items():
        if not posts:
            continue
        lines.append(f"## {cat} ({len(posts)})")
        lines.append("")
        for p in posts:
            lines.append(f"### {p['status_id']}")
            lines.append(f"- url: {p['url']}")
            lines.append(f"- author: {p['author']}")
            lines.append(f"- summary: {p['summary']}")
            lines.append("")
    return "\n".join(lines)


def chunk_text(text: str, max_chars: int = 1800) -> List[str]:
    chunks: List[str] = []
    buf: List[str] = []
    size = 0
    for line in text.splitlines():
        add = len(line) + 1
        if size + add > max_chars and buf:
            chunks.append("\n".join(buf))
            buf = [line]
            size = add
        else:
            buf.append(line)
            size += add
    if buf:
        chunks.append("\n".join(buf))
    return chunks


def notion_create_page(title: str, markdown: str, token: str, db_id: str, title_prop: str) -> str:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    children = []
    for part in chunk_text(markdown):
        children.append(
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": part}}]
                },
            }
        )

    payload = {
        "parent": {"database_id": db_id},
        "properties": {
            title_prop: {
                "title": [{"type": "text", "text": {"content": title}}]
            }
        },
        "children": children,
    }

    r = requests.post("https://api.notion.com/v1/pages", headers=headers, json=payload, timeout=40)
    r.raise_for_status()
    data = r.json()
    return data.get("id", "")


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch X learning and optional Notion sync")
    parser.add_argument("--links-file", required=True, help="Text file with one X URL per line")
    parser.add_argument("--name", default="", help="Output note name")
    parser.add_argument("--fetch", action="store_true", help="Fetch links through x-ops if capture missing")
    parser.add_argument("--browser", default="chromium")
    parser.add_argument("--proxy", default="")
    parser.add_argument("--notion", action="store_true", help="Sync summary to Notion")
    args = parser.parse_args()

    links_file = Path(args.links_file)
    links = load_links(links_file)

    items: List[Dict] = []
    errors: List[str] = []

    for link in links:
        try:
            cap = capture_if_needed(link, args.browser, args.proxy, args.fetch)
            if not cap.exists():
                errors.append(f"missing capture: {link}")
                continue
            data = json.loads(cap.read_text(encoding="utf-8"))
            main = data.get("main", {})
            text = main.get("text", "")
            cat = categorize(text)
            items.append(
                {
                    "status_id": data.get("target_status_id") or extract_status_id(link),
                    "url": link,
                    "author": main.get("author", ""),
                    "summary": summarize(text),
                    "category": cat,
                }
            )
        except Exception as exc:
            errors.append(f"{link}: {exc}")

    grouped = build_grouped(items)
    name = args.name or datetime.now().strftime("batch_%Y%m%d_%H%M%S")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_md = OUT_DIR / f"{name}.md"
    md = render_md(grouped, len(links), name)
    out_md.write_text(md, encoding="utf-8")

    notion_page_id = ""
    if args.notion:
        token = os.getenv("NOTION_TOKEN", "").strip()
        db_id = os.getenv("NOTION_DATABASE_ID", "").strip()
        title_prop = os.getenv("NOTION_TITLE_PROP", "Name").strip() or "Name"
        if not token or not db_id:
            errors.append("Notion sync requested but NOTION_TOKEN or NOTION_DATABASE_ID missing")
        else:
            try:
                notion_page_id = notion_create_page(f"X Batch Learning {name}", md, token, db_id, title_prop)
            except Exception as exc:
                errors.append(f"Notion sync failed: {exc}")

    result = {
        "links": len(links),
        "processed": len(items),
        "output": str(out_md),
        "notion_page_id": notion_page_id,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
