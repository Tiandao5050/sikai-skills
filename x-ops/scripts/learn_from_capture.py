from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CAPTURE_DIR = DATA_DIR / "captured"
LEARNED_DIR = DATA_DIR / "learned"
KB_PATH = DATA_DIR / "knowledge" / "x_lessons.md"


def _extract_status_id(url: str) -> str:
    m = re.search(r"/status/(\d+)", url or "")
    return m.group(1) if m else ""


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _sentences(text: str) -> List[str]:
    text = text.replace("\r", "\n")
    parts: List[str] = []
    for chunk in re.split(r"[\n。！？!?;；]+", text):
        line = _clean(chunk)
        if not line:
            continue
        if len(line) < 8:
            continue
        parts.append(line)
    return parts


def _score_sentence(s: str) -> int:
    score = 0
    # Practical cues
    keywords = [
        "step", "steps", "how", "why", "tip", "tips", "avoid", "pitfall", "issue",
        "方法", "步骤", "建议", "注意", "避坑", "技巧", "原理", "安装", "配置", "实测",
        "must", "should", "best", "first", "then",
    ]
    lower = s.lower()
    for k in keywords:
        if k in lower:
            score += 2

    # Numeric indicators often imply concrete instructions.
    if re.search(r"\b\d+\b", s):
        score += 1

    # Prefer concise but informative sentences.
    length = len(s)
    if 20 <= length <= 180:
        score += 2
    elif 10 <= length <= 240:
        score += 1

    return score


def _top_points(texts: List[str], limit: int = 8) -> List[str]:
    all_sents: List[str] = []
    for t in texts:
        all_sents.extend(_sentences(t))

    ranked: List[Tuple[int, str]] = []
    seen = set()
    for s in all_sents:
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        ranked.append((_score_sentence(s), s))

    ranked.sort(key=lambda x: x[0], reverse=True)
    points = [s for _, s in ranked[:limit] if s]

    # Fallback: ensure not empty.
    if not points and all_sents:
        points = all_sents[: min(limit, len(all_sents))]

    return points


def _render_learning_md(data: Dict, points: List[str]) -> str:
    main = data.get("main", {})
    thread = data.get("thread", [])
    url = data.get("url", "")
    sid = data.get("target_status_id", "")

    lines: List[str] = []
    lines.append(f"# Learned Note {sid}")
    lines.append("")
    lines.append(f"- source_url: {url}")
    lines.append(f"- author: {main.get('author', '')}")
    lines.append(f"- handle: @{main.get('author_handle', '')}" if main.get("author_handle") else "- handle: ")
    lines.append(f"- captured_at: {data.get('captured_at', '')}")
    lines.append(f"- thread_count: {len(thread)}")
    lines.append("")

    lines.append("## Original")
    lines.append(main.get("text", ""))
    lines.append("")

    articles = data.get("articles", [])
    if articles:
        lines.append("## Long Article")
        for idx, a in enumerate(articles, 1):
            lines.append(f"### {idx}")
            lines.append(f"- url: {a.get('url', '')}")
            lines.append(f"- status: {a.get('status', '')}")
            lines.append(f"- title: {a.get('title', '')}")
            lines.append("")
            lines.append(a.get("text", ""))
            lines.append("")

    main_media = main.get("media_urls", [])
    downloaded = data.get("downloaded_media", [])
    if main_media or downloaded:
        lines.append("## Media")
        if main_media:
            lines.append("- source_media_urls:")
            for u in main_media:
                lines.append(f"  - {u}")
        if downloaded:
            lines.append("- downloaded_media_files:")
            for p in downloaded:
                lines.append(f"  - {p}")
        lines.append("")

    lines.append("## Key Learnings")
    if points:
        for p in points:
            lines.append(f"- {p}")
    else:
        lines.append("- (no key points extracted)")
    lines.append("")

    lines.append("## Reusable Angles")
    lines.append("- What problem does this solve and for whom?")
    lines.append("- What is the fastest path from zero to working?")
    lines.append("- What pitfalls should be avoided in production?")
    lines.append("")

    lines.append("## Next Actions")
    lines.append("- Convert top 3 learnings into one short post + one checklist post.")
    lines.append("- Keep source URL for attribution and verification.")
    lines.append("")

    return "\n".join(lines)


def _ensure_paths(capture_path: Path, learned_dir: Path, kb_path: Path) -> None:
    if not capture_path.exists():
        raise FileNotFoundError(f"Capture not found: {capture_path}")
    learned_dir.mkdir(parents=True, exist_ok=True)
    kb_path.parent.mkdir(parents=True, exist_ok=True)


def _append_kb(kb_path: Path, data: Dict, points: List[str], learned_path: Path) -> bool:
    sid = data.get("target_status_id", "")
    marker = f"<!-- status_id:{sid} -->"

    if kb_path.exists():
        existing = kb_path.read_text(encoding="utf-8")
        if marker in existing:
            return False
    else:
        kb_path.write_text("# X Lessons KB\n\n", encoding="utf-8")

    main = data.get("main", {})
    lines: List[str] = []
    lines.append(marker)
    lines.append(f"## {sid}")
    lines.append(f"- source_url: {data.get('url', '')}")
    lines.append(f"- author: {main.get('author', '')}")
    lines.append(f"- learned_note: {learned_path}")
    if points:
        lines.append("- top_points:")
        for p in points[:5]:
            lines.append(f"  - {p}")
    lines.append("")

    with kb_path.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines))
        f.write("\n")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate learning notes from captured X post")
    parser.add_argument("--url", default="", help="X post URL; used to infer capture file")
    parser.add_argument("--capture", default="", help="Path to captured json file")
    parser.add_argument("--output", default="", help="Path to learned markdown output")
    parser.add_argument("--max-points", type=int, default=8)
    parser.add_argument("--kb", default=str(KB_PATH), help="Knowledge base markdown file")
    args = parser.parse_args()

    capture_path: Path
    sid = ""

    if args.capture:
        capture_path = Path(args.capture)
        sid = _extract_status_id(capture_path.name)
    elif args.url:
        sid = _extract_status_id(args.url)
        if not sid:
            raise SystemExit("Cannot infer status id from --url")
        capture_path = CAPTURE_DIR / f"{sid}.json"
    else:
        raise SystemExit("Provide --url or --capture")

    learned_dir = LEARNED_DIR
    kb_path = Path(args.kb)

    _ensure_paths(capture_path, learned_dir, kb_path)

    data = json.loads(capture_path.read_text(encoding="utf-8"))

    texts = [data.get("main", {}).get("text", "")]
    texts.extend(item.get("text", "") for item in data.get("thread", []))
    texts.extend(item.get("text", "") for item in data.get("articles", []))
    texts = [t for t in texts if _clean(t)]

    points = _top_points(texts, limit=args.max_points)
    content = _render_learning_md(data, points)

    if args.output:
        out_path = Path(args.output)
    else:
        status_id = data.get("target_status_id", sid) or "unknown"
        out_path = learned_dir / f"{status_id}.md"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")

    appended = _append_kb(kb_path, data, points, out_path)

    result = {
        "capture": str(capture_path),
        "learned": str(out_path),
        "kb": str(kb_path),
        "kb_appended": appended,
        "points": len(points),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
