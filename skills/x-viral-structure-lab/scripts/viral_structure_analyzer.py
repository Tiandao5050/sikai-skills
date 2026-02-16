#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List

XOPS_DIR = Path("/home/sikai/ai-workspace/x-ops")
CAPTURE_DIR = XOPS_DIR / "data" / "captured"
OUT_DIR = XOPS_DIR / "data" / "structure"


def extract_status_id(text: str) -> str:
    m = re.search(r"/status/(\d+)", text or "")
    return m.group(1) if m else ""


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def split_lines(text: str) -> List[str]:
    lines: List[str] = []
    for raw in (text or "").splitlines():
        s = clean(raw)
        if s:
            lines.append(s)
    return lines


def infer_hook(text: str) -> str:
    t = clean(text)
    if not t:
        return "unknown"
    head = t[:120]
    if "?" in head or "？" in head:
        return "question"
    if any(k in head for k in ["被低估", "别再", "真相", "误区", "千万", "必须", "不要"]):
        return "contrarian-or-warning"
    if re.search(r"\b\d+\b", head):
        return "result-or-list"
    return "statement"


def detect_structure(lines: List[str]) -> Dict:
    # Simple heuristic: count list markers and segment types.
    list_like = 0
    for l in lines:
        if re.match(r"^(\d+\.|[-*])\s+", l):
            list_like += 1

    return {
        "line_count": len(lines),
        "list_like_lines": list_like,
        "density": "high" if len(lines) >= 8 else "low",
    }


def build_report(data: Dict) -> Dict:
    main = data.get("main", {})
    text = main.get("text", "")
    if not clean(text):
        # Fallback to long-form article text when tweet body is empty.
        article_texts = [clean(a.get("text", "")) for a in data.get("articles", []) if clean(a.get("text", ""))]
        if article_texts:
            text = "\n".join(article_texts)
    lines = split_lines(text)

    report = {
        "url": data.get("url", ""),
        "target_status_id": data.get("target_status_id", ""),
        "author": main.get("author", ""),
        "timestamp": main.get("timestamp", ""),
        "hook_type": infer_hook(text),
        "first_140": clean(text)[:140],
        "structure": detect_structure(lines),
        "outline_guess": lines[: min(8, len(lines))],
        "cta_guess": "comment" if any(k in text for k in ["评论", "补充", "共创", "转发", "收藏"])
        else "none",
    }

    return report


def render_md(rep: Dict) -> str:
    lines: List[str] = []
    lines.append(f"# Viral Structure Report {rep.get('target_status_id','')}")
    lines.append("")
    lines.append(f"- url: {rep.get('url','')}")
    lines.append(f"- author: {rep.get('author','')}")
    lines.append(f"- timestamp: {rep.get('timestamp','')}")
    lines.append("")
    lines.append("## Hook")
    lines.append(f"- type: {rep.get('hook_type','')}")
    lines.append(f"- first_140: {rep.get('first_140','')}")
    lines.append("")
    lines.append("## Structure")
    s = rep.get("structure", {})
    lines.append(f"- line_count: {s.get('line_count','')}")
    lines.append(f"- list_like_lines: {s.get('list_like_lines','')}")
    lines.append(f"- density: {s.get('density','')}")
    lines.append("")
    lines.append("## Outline Guess")
    for o in rep.get("outline_guess", []):
        lines.append(f"- {o}")
    lines.append("")
    lines.append("## CTA Guess")
    lines.append(f"- {rep.get('cta_guess','')}")
    lines.append("")
    return "\n".join(lines)


def resolve_capture(url: str, capture_path: str) -> Path:
    if capture_path:
        p = Path(capture_path)
        if not p.exists():
            raise FileNotFoundError(f"Capture file not found: {p}")
        return p

    sid = extract_status_id(url)
    if not sid:
        raise ValueError("Cannot infer status id from URL. Provide --capture")

    p = CAPTURE_DIR / f"{sid}.json"
    if not p.exists():
        raise FileNotFoundError(f"Capture file not found: {p}. Run fetch_and_learn first.")
    return p


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze captured X post for viral structure")
    parser.add_argument("--url", default="", help="X URL to infer capture file")
    parser.add_argument("--capture", default="", help="Captured json file path")
    parser.add_argument("--output", default="", help="Output prefix path (without extension)")
    args = parser.parse_args()

    cap = resolve_capture(args.url, args.capture)
    data = json.loads(cap.read_text(encoding="utf-8"))
    rep = build_report(data)

    sid = rep.get("target_status_id") or extract_status_id(rep.get("url", "")) or "unknown"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base = Path(args.output) if args.output else (OUT_DIR / sid)

    (base.with_suffix(".json")).write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (base.with_suffix(".md")).write_text(render_md(rep), encoding="utf-8")

    print(json.dumps({"capture": str(cap), "out_json": str(base.with_suffix('.json')), "out_md": str(base.with_suffix('.md'))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
