from __future__ import annotations

import argparse
import datetime as dt
import os
from pathlib import Path
from typing import Dict, List

import yaml
import feedparser

from queue_io import QueueItem, write_queue_md
from utils import SeedItem, fetch_metadata, infer_github_repo, parse_seeds, run_llm_command

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
TEMPLATE_DIR = DATA_DIR / "templates"


def load_config(path: Path) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_template(name: str) -> str:
    path = TEMPLATE_DIR / f"{name}.txt"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def truncate(text: str, limit: int = 280) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def fallback_text(item: SeedItem, lang: str) -> str:
    title = item.title or infer_github_repo(item.url) or "未命名内容"
    summary = item.summary or item.note or "简要更新"

    if item.section == "ai_hotspot":
        if lang == "en":
            text = f"AI update: {title}\nTL;DR: {summary}\nSource: {item.url}"
        else:
            text = f"【AI动态】{title}\n一句话：{summary}\n来源：{item.url}"
        return truncate(text)

    if item.section == "openclaw":
        if lang == "en":
            text = f"Openclaw notes: {title}\nKey points: {summary}\nSource: {item.url}"
        else:
            text = (
                f"【Openclaw 经验】{title}\n"
                f"要点：{summary}\n"
                f"来源：{item.url}"
            )
        return truncate(text)

    if item.section == "github_trending":
        repo = infer_github_repo(item.url) or title
        if lang == "en":
            text = f"GitHub trend: {repo}\nWhy: {summary}\nSource: {item.url}"
        else:
            text = f"【GitHub 热门】{repo}\n亮点：{summary}\n来源：{item.url}"
        return truncate(text)

    if lang == "en":
        return truncate(f"Update: {title}\n{summary}\nSource: {item.url}")

    return truncate(f"更新：{title}\n{summary}\n来源：{item.url}")


def render_with_llm(template_name: str, item: SeedItem, llm_cfg: Dict) -> str:
    if llm_cfg.get("mode") != "command":
        return ""
    command = llm_cfg.get("command")
    if not command:
        return ""

    template = load_template(template_name)
    if not template:
        return ""

    prompt = template.format(
        title=item.title,
        summary=item.summary,
        url=item.url,
        note=item.note,
    )
    return run_llm_command(command, prompt)


def build_items(sections: Dict[str, List[SeedItem]], llm_cfg: Dict, limit: int) -> List[QueueItem]:
    items: List[QueueItem] = []
    order = ["ai_hotspot", "openclaw", "github_trending"]
    merged: List[SeedItem] = []
    for key in order:
        merged.extend(sections.get(key, []))

    if not merged:
        return items

    for idx, seed in enumerate(merged[:limit]):
        lang = "zh"
        if (idx + 1) % 6 == 0:
            lang = "en"

        text = ""
        if seed.section == "ai_hotspot":
            text = render_with_llm("ai_hotspot", seed, llm_cfg)
        elif seed.section == "openclaw":
            text = render_with_llm("openclaw", seed, llm_cfg)
        elif seed.section == "github_trending":
            text = render_with_llm("github_trending", seed, llm_cfg)

        if not text:
            text = fallback_text(seed, lang)

        items.append(
            QueueItem(
                item_id=idx + 1,
                status="pending",
                type=seed.section,
                lang=lang,
                source=seed.url,
                note=seed.note,
                text=text,
            )
        )

    return items


def enrich_seeds(sections: Dict[str, List[SeedItem]]) -> None:
    for items in sections.values():
        for item in items:
            meta = fetch_metadata(item.url)
            item.title = meta.get("title", "") or item.title
            item.summary = meta.get("summary", "") or item.summary


def add_rss_seeds(sections: Dict[str, List[SeedItem]], rss_urls: List[str], per_feed: int = 5) -> None:
    if not rss_urls:
        return
    items = sections.setdefault("ai_hotspot", [])
    existing = {item.url for item in items}
    for url in rss_urls:
        feed = feedparser.parse(url)
        for entry in feed.entries[:per_feed]:
            link = entry.get("link", "")
            if not link or link in existing:
                continue
            seed = SeedItem(
                section="ai_hotspot",
                url=link,
                note=entry.get("title", ""),
                title=entry.get("title", ""),
                summary=entry.get("summary", "") or entry.get("description", ""),
            )
            items.append(seed)
            existing.add(link)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="", help="YYYY-MM-DD")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--queue", default=str(DATA_DIR / "queue.md"))
    parser.add_argument("--seeds", default=str(DATA_DIR / "seeds.md"))
    parser.add_argument("--config", default=str(DATA_DIR / "sources.yaml"))
    args = parser.parse_args()

    config = load_config(Path(args.config))
    limit = args.limit or int(config.get("posts_per_day", 15))
    date_str = args.date or dt.date.today().isoformat()

    sections = parse_seeds(args.seeds)
    rss_urls = (
        config.get("sections", {})
        .get("ai_hotspot", {})
        .get("rss", [])
    )
    add_rss_seeds(sections, rss_urls)
    enrich_seeds(sections)

    llm_cfg = config.get("llm", {})
    items = build_items(sections, llm_cfg, limit)

    header_lines = [
        f"# X Queue - {date_str}",
        f"timezone: {config.get('timezone', 'Asia/Shanghai')}",
        f"posts_per_day: {limit}",
    ]

    write_queue_md(args.queue, header_lines, items)
    print(f"Wrote {len(items)} items to {args.queue}")


if __name__ == "__main__":
    main()
