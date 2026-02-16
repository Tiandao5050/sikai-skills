#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

XOPS_DIR = Path("/home/sikai/ai-workspace/x-ops")
CAPTURE_DIR = XOPS_DIR / "data" / "captured"
OUT_DIR = XOPS_DIR / "data" / "action-plans"

STEP_HINTS = [
    "step", "first", "then", "next", "finally", "install", "setup", "configure", "run", "start",
    "validate", "debug", "fix", "error", "第一", "第二", "然后", "最后", "安装", "配置", "运行", "启动", "验证", "排查",
]

COMMAND_RE = re.compile(
    r"(`[^`]+`|(pip|python|python3|npm|pnpm|yarn|uv|git|docker|docker-compose|go|cargo|apt|brew|chmod|bash|sh)\s+[^\n]+)",
    re.IGNORECASE,
)


def extract_status_id(text: str) -> str:
    m = re.search(r"/status/(\d+)", text or "")
    return m.group(1) if m else ""


def split_sentences(text: str) -> List[str]:
    raw = re.split(r"[\n。！？!?;；]+", text or "")
    out: List[str] = []
    for item in raw:
        s = re.sub(r"\s+", " ", item).strip()
        if len(s) >= 6:
            out.append(s)
    return out


def collect_text(data: Dict) -> List[str]:
    parts = []
    main = data.get("main", {})
    if main.get("text"):
        parts.append(main["text"])
    for t in data.get("thread", []):
        if t.get("text"):
            parts.append(t["text"])
    return parts


def extract_commands(texts: List[str]) -> List[str]:
    found: List[str] = []
    seen = set()
    for txt in texts:
        for m in COMMAND_RE.finditer(txt):
            cmd = m.group(1).strip("`").strip()
            if cmd and cmd not in seen:
                seen.add(cmd)
                found.append(cmd)
    return found


def extract_steps(texts: List[str], limit: int = 12) -> List[str]:
    scored: List[Tuple[int, str]] = []
    seen = set()
    for txt in texts:
        for s in split_sentences(txt):
            key = s.lower()
            if key in seen:
                continue
            seen.add(key)
            low = s.lower()
            score = 0
            for h in STEP_HINTS:
                if h in low:
                    score += 1
            if re.search(r"\b\d+\b", s):
                score += 1
            if 20 <= len(s) <= 180:
                score += 1
            scored.append((score, s))

    scored.sort(key=lambda x: x[0], reverse=True)
    selected = [s for score, s in scored if score > 0][:limit]
    if not selected:
        selected = [s for _, s in scored[: min(limit, len(scored))]]
    return selected


def build_markdown(data: Dict, steps: List[str], commands: List[str]) -> str:
    main = data.get("main", {})
    sid = data.get("target_status_id", "")
    lines: List[str] = []
    lines.append(f"# Tutorial Action Plan {sid}")
    lines.append("")
    lines.append(f"- source_url: {data.get('url', '')}")
    lines.append(f"- author: {main.get('author', '')}")
    lines.append(f"- timestamp: {main.get('timestamp', '')}")
    lines.append("")

    lines.append("## Plan Steps")
    if steps:
        for i, s in enumerate(steps, 1):
            lines.append(f"{i}. {s}")
    else:
        lines.append("1. No clear steps extracted. Review source manually.")
    lines.append("")

    lines.append("## Candidate Commands")
    if commands:
        for cmd in commands:
            lines.append(f"- `{cmd}`")
    else:
        lines.append("- No explicit commands found in source text.")
    lines.append("")

    lines.append("## Execution Contract")
    lines.append("- Confirm environment and target directory before running commands.")
    lines.append("- Run one step at a time and verify output.")
    lines.append("- Stop on first failure unless user asks to continue.")
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
    parser = argparse.ArgumentParser(description="Build execution plan from captured X tutorial")
    parser.add_argument("--url", default="", help="X URL to infer capture file")
    parser.add_argument("--capture", default="", help="Captured json file path")
    parser.add_argument("--output", default="", help="Output markdown path")
    args = parser.parse_args()

    cap = resolve_capture(args.url, args.capture)
    data = json.loads(cap.read_text(encoding="utf-8"))

    texts = collect_text(data)
    steps = extract_steps(texts)
    commands = extract_commands(texts)

    sid = data.get("target_status_id", extract_status_id(data.get("url", ""))) or "unknown"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = Path(args.output) if args.output else OUT_DIR / f"{sid}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_markdown(data, steps, commands), encoding="utf-8")

    print(json.dumps({"capture": str(cap), "output": str(out), "steps": len(steps), "commands": len(commands)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
