from __future__ import annotations

import argparse
import re
import time
from pathlib import Path
from typing import List

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from queue_io import QueueItem, parse_queue_md, write_queue_md

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PROFILE_DIR = DATA_DIR / "profile"


def click_first(page, selectors: List[str], timeout: int = 2000) -> bool:
    for sel in selectors:
        try:
            locator = page.locator(sel)
            if locator.count() > 0:
                locator.first.click(timeout=timeout)
                return True
        except Exception:
            continue
    return False


def click_by_role(page, names: List[str], timeout: int = 2000) -> bool:
    for name in names:
        try:
            button = page.get_by_role("button", name=re.compile(name))
            if button.count() > 0:
                button.first.click(timeout=timeout)
                return True
        except Exception:
            continue
    return False


def open_compose(page) -> None:
    page.goto("https://x.com/compose/tweet", wait_until="domcontentloaded")
    page.wait_for_selector('div[role="textbox"]', timeout=20000)


def fill_text(page, text: str) -> None:
    textbox = page.locator('div[role="textbox"]')
    textbox.first.click()
    try:
        textbox.first.fill(text)
    except Exception:
        textbox.first.type(text, delay=10)


def save_draft(page) -> None:
    close_selectors = [
        'button[data-testid="AppTabBar_Close_Button"]',
        'button[data-testid="app-bar-close"]',
        'button[aria-label="Close"]',
        'button[aria-label="关闭"]',
    ]
    if not click_first(page, close_selectors):
        page.keyboard.press("Escape")

    # Confirmation dialog: Save / Discard
    if click_by_role(page, ["Save", "保存", "Draft", "草稿"]):
        return

    confirm_selectors = [
        'button[data-testid="confirmationSheetConfirm"]',
        'button[data-testid="confirm"]',
    ]
    click_first(page, confirm_selectors)


def trim_text(text: str, limit: int = 280) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", default=str(DATA_DIR / "queue.md"))
    parser.add_argument("--limit", type=int, default=15)
    parser.add_argument("--browser", default="chrome", choices=["chrome", "edge", "chromium"])
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--mark", action="store_true")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    header_lines, items = parse_queue_md(args.queue)
    pending = [i for i in items if i.status == "pending" and i.text.strip()]
    to_process = pending[: args.limit]

    if not to_process:
        print("No pending items.")
        return

    channel = None
    if args.browser == "chrome":
        channel = "chrome"
    elif args.browser == "edge":
        channel = "msedge"

    with sync_playwright() as p:
        browser_type = p.chromium
        context = browser_type.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            channel=channel,
            headless=args.headless,
        )
        page = context.new_page()

        for item in to_process:
            text = trim_text(item.text)
            try:
                open_compose(page)
                fill_text(page, text)
                time.sleep(0.5)
                save_draft(page)
                time.sleep(1.0)
                item.status = "drafted"
                print(f"Drafted Item {item.item_id:03d}")
            except PlaywrightTimeoutError:
                print(f"Timeout on Item {item.item_id:03d} - skipped")
                if args.debug:
                    page.screenshot(path=str(DATA_DIR / f"error_{item.item_id:03d}.png"))
            except Exception as e:
                print(f"Error on Item {item.item_id:03d}: {e}")
                if args.debug:
                    page.screenshot(path=str(DATA_DIR / f"error_{item.item_id:03d}.png"))

        context.close()

    if args.mark:
        write_queue_md(args.queue, header_lines, items)


if __name__ == "__main__":
    main()
