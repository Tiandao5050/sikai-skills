from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup


@dataclass
class SeedItem:
    section: str
    url: str
    note: str
    title: str = ""
    summary: str = ""


def parse_seeds(md_path: str) -> Dict[str, List[SeedItem]]:
    sections: Dict[str, List[SeedItem]] = {}
    current_section: Optional[str] = None
    last_item: Optional[SeedItem] = None

    with open(md_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if line.startswith("## "):
                current_section = line.replace("## ", "").strip()
                sections.setdefault(current_section, [])
                last_item = None
                continue
            if line.startswith("- ") and current_section:
                url = line[2:].strip()
                item = SeedItem(section=current_section, url=url, note="")
                sections[current_section].append(item)
                last_item = item
                continue
            if line.startswith("note:") and last_item is not None:
                last_item.note = line.replace("note:", "", 1).strip()

    return sections


def _clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text


def fetch_metadata(url: str, timeout: int = 12) -> Dict[str, str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
    except Exception:
        return {"title": "", "summary": ""}

    soup = BeautifulSoup(resp.text, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""

    desc = ""
    for meta_name in ("description", "og:description", "twitter:description"):
        tag = soup.find("meta", attrs={"name": meta_name})
        if not tag:
            tag = soup.find("meta", attrs={"property": meta_name})
        if tag and tag.get("content"):
            desc = tag["content"]
            break

    return {"title": _clean_text(title), "summary": _clean_text(desc)}


def infer_github_repo(url: str) -> str:
    match = re.match(r"https?://github.com/([^/]+/[^/]+)", url)
    if match:
        return match.group(1)
    return ""


def run_llm_command(command: str, prompt: str, timeout: int = 60) -> str:
    try:
        result = subprocess.run(
            command,
            input=prompt,
            text=True,
            shell=True,
            capture_output=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            return ""
        return result.stdout.strip()
    except Exception:
        return ""
