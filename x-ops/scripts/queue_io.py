from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class QueueItem:
    item_id: int
    status: str
    type: str
    lang: str
    source: str
    note: str
    text: str


HEADER_PREFIX = "# X Queue"


def parse_queue_md(path: str) -> Tuple[List[str], List[QueueItem]]:
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    header_lines: List[str] = []
    items: List[QueueItem] = []
    current: QueueItem | None = None
    in_text = False

    def flush_current():
        nonlocal current
        if current is not None:
            items.append(current)
            current = None

    for line in lines:
        if line.startswith("## Item "):
            flush_current()
            in_text = False
            # Format: ## Item 001 [pending]
            parts = line.split()
            item_id = int(parts[2])
            status = "pending"
            if "[" in line and "]" in line:
                status = line[line.index("[") + 1 : line.index("]")].strip()
            current = QueueItem(
                item_id=item_id,
                status=status,
                type="",
                lang="",
                source="",
                note="",
                text="",
            )
            continue

        if current is None:
            header_lines.append(line)
            continue

        if line.startswith("text:"):
            in_text = True
            current.text = ""
            continue

        if in_text:
            if current.text:
                current.text += "\n" + line
            else:
                current.text = line
            continue

        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if key == "type":
                current.type = value
            elif key == "lang":
                current.lang = value
            elif key == "source":
                current.source = value
            elif key == "note":
                current.note = value

    flush_current()
    return header_lines, items


def render_queue_md(header_lines: List[str], items: List[QueueItem]) -> str:
    out: List[str] = []
    if header_lines:
        out.extend(header_lines)
    else:
        out.append("# X Queue")

    for item in items:
        out.append("")
        out.append(f"## Item {item.item_id:03d} [{item.status}]")
        out.append(f"type: {item.type}")
        out.append(f"lang: {item.lang}")
        out.append(f"source: {item.source}")
        out.append(f"note: {item.note}")
        out.append("text:")
        if item.text:
            out.extend(item.text.splitlines())
    out.append("")
    return "\n".join(out)


def write_queue_md(path: str, header_lines: List[str], items: List[QueueItem]) -> None:
    content = render_queue_md(header_lines, items)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
