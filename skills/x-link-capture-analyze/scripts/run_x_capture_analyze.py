#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List

ROOT = Path("/home/sikai/ai-workspace")
XOPS_DIR = ROOT / "x-ops"
CAPTURE_DIR = XOPS_DIR / "data" / "captured"

READ_SCRIPT = XOPS_DIR / "scripts" / "read_x_post.py"
LEARN_SCRIPT = XOPS_DIR / "scripts" / "learn_from_capture.py"
TUTORIAL_SCRIPT = ROOT / "skills" / "x-tutorial-to-action" / "scripts" / "tutorial_plan.py"
VIRAL_SCRIPT = ROOT / "skills" / "x-viral-structure-lab" / "scripts" / "viral_structure_analyzer.py"
BATCH_SCRIPT = ROOT / "skills" / "x-batch-notes-notion-sync" / "scripts" / "batch_x_learning.py"


def _extract_status_id(text: str) -> str:
    m = re.search(r"/status/(\d+)", text or "")
    return m.group(1) if m else ""


def _normalize_purpose(purpose: str) -> str:
    p = (purpose or "").strip().lower()
    if p in {"1", "tutorial"}:
        return "tutorial"
    if p in {"2", "viral", "structure"}:
        return "viral"
    if p in {"3", "batch"}:
        return "batch"
    raise ValueError(f"Unsupported purpose: {purpose}")


def _run(cmd: List[str], cwd: Path) -> str:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if proc.returncode != 0:
        tail = "\n".join((proc.stdout or "").splitlines()[-30:])
        raise RuntimeError(f"command failed rc={proc.returncode}: {' '.join(cmd)}\n{tail}")
    return proc.stdout


def _capture_single(url: str, browser: str, proxy: str, cookie_file: str, timeout_ms: int, headless: bool) -> Dict:
    status_id = _extract_status_id(url)
    if not status_id:
        raise ValueError(f"Invalid X status URL: {url}")

    output_json = CAPTURE_DIR / f"{status_id}.json"
    cmd = [
        sys.executable,
        str(READ_SCRIPT),
        url,
        "--browser",
        browser,
        "--timeout",
        str(timeout_ms),
        "--output",
        str(output_json),
    ]
    if headless:
        cmd += ["--headless"]
    if proxy.strip():
        cmd += ["--proxy", proxy.strip()]
    cf = cookie_file.strip()
    if cf:
        p = Path(cf)
        if p.exists():
            cmd += ["--cookie-file", str(p)]

    try:
        out = _run(cmd, cwd=XOPS_DIR)
        return {"status_id": status_id, "capture_output_tail": "\n".join(out.splitlines()[-12:]), "capture_mode": "headless" if headless else "headed"}
    except RuntimeError as exc:
        if not headless:
            raise
        # Auto fallback: X occasionally returns feed error in headless mode.
        retry_cmd = [c for c in cmd if c != "--headless"]
        out2 = _run(retry_cmd, cwd=XOPS_DIR)
        return {
            "status_id": status_id,
            "capture_output_tail": "\n".join(out2.splitlines()[-12:]),
            "capture_mode": "headed-fallback",
            "capture_error_headless": str(exc),
        }


def _learn_single(url: str) -> str:
    cmd = [sys.executable, str(LEARN_SCRIPT), "--url", url]
    out = _run(cmd, cwd=XOPS_DIR)
    return "\n".join(out.splitlines()[-12:])


def _metrics_from_capture(status_id: str) -> Dict:
    cap = CAPTURE_DIR / f"{status_id}.json"
    if not cap.exists():
        return {}

    data = json.loads(cap.read_text(encoding="utf-8"))
    main = data.get("main", {})
    article = (data.get("articles") or [{}])[0]
    return {
        "status_id": main.get("status_id") or data.get("target_status_id") or status_id,
        "main_text_len": len(main.get("text") or ""),
        "article_status": article.get("status", ""),
        "article_text_len": len(article.get("text") or ""),
        "capture_json": str(cap),
        "capture_md": str(CAPTURE_DIR / f"{status_id}.md"),
    }


def _run_tutorial(url: str) -> str:
    cmd = [sys.executable, str(TUTORIAL_SCRIPT), "--url", url]
    out = _run(cmd, cwd=ROOT)
    return "\n".join(out.splitlines()[-12:])


def _run_viral(url: str) -> str:
    cmd = [sys.executable, str(VIRAL_SCRIPT), "--url", url]
    out = _run(cmd, cwd=ROOT)
    return "\n".join(out.splitlines()[-12:])


def _run_batch(links_file: str, browser: str, proxy: str, notion: bool) -> str:
    cmd = [
        sys.executable,
        str(BATCH_SCRIPT),
        "--links-file",
        links_file,
        "--fetch",
        "--browser",
        browser,
    ]
    if proxy.strip():
        cmd += ["--proxy", proxy.strip()]
    if notion:
        cmd += ["--notion"]
    out = _run(cmd, cwd=ROOT)
    return out


def _links_file_from_url(url: str) -> str:
    tmp = tempfile.NamedTemporaryFile(prefix="x_links_", suffix=".txt", delete=False, mode="w", encoding="utf-8")
    tmp.write(url.strip() + "\n")
    tmp.close()
    return tmp.name


def main() -> None:
    parser = argparse.ArgumentParser(description="Unified X capture + analyze dispatcher")
    parser.add_argument("--url", default="", help="Single X status URL")
    parser.add_argument("--purpose", required=True, help="tutorial|viral|batch|1|2|3")
    parser.add_argument("--links-file", default="", help="Batch mode links file (one URL per line)")
    parser.add_argument("--browser", default="chromium")
    parser.add_argument("--proxy", default="")
    parser.add_argument("--cookie-file", default="/home/sikai/ai-workspace/x-ops/data/x_cookie.txt")
    parser.add_argument("--timeout", type=int, default=180000)
    parser.add_argument("--headless", dest="headless", action="store_true", default=True)
    parser.add_argument("--headed", dest="headless", action="store_false")
    parser.add_argument("--notion", action="store_true")
    args = parser.parse_args()

    purpose = _normalize_purpose(args.purpose)
    result: Dict = {
        "purpose": purpose,
        "url": args.url,
        "browser": args.browser,
        "headless": args.headless,
        "proxy": args.proxy,
    }

    if purpose == "batch":
        links_file = args.links_file.strip()
        if not links_file:
            if not args.url.strip():
                raise SystemExit("batch mode requires --links-file or --url")
            links_file = _links_file_from_url(args.url)
            result["generated_links_file"] = links_file

        batch_output = _run_batch(links_file, args.browser, args.proxy, args.notion)
        result["batch_output"] = batch_output
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if not args.url.strip():
        raise SystemExit("single-link mode requires --url")

    capture_info = _capture_single(args.url, args.browser, args.proxy, args.cookie_file, args.timeout, args.headless)
    _learn_single(args.url)

    status_id = capture_info["status_id"]
    result["capture"] = _metrics_from_capture(status_id)

    if purpose == "tutorial":
        result["analysis"] = _run_tutorial(args.url)
        result["analysis_type"] = "tutorial_plan"
        result["analysis_file"] = f"/home/sikai/ai-workspace/x-ops/data/action-plans/{status_id}.md"
    elif purpose == "viral":
        result["analysis"] = _run_viral(args.url)
        result["analysis_type"] = "viral_structure"
        result["analysis_file"] = f"/home/sikai/ai-workspace/x-ops/data/structure/{status_id}.md"

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
