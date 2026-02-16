from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qs, urlparse

import requests
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PROFILE_DIR = DATA_DIR / "profile"
CAPTURE_DIR = DATA_DIR / "captured"
DEBUG_DIR = DATA_DIR / "debug"
MEDIA_DIR = DATA_DIR / "media"


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _extract_status_id(url_or_path: str) -> str:
    m = re.search(r"/status/(\d+)", url_or_path)
    return m.group(1) if m else ""


def _extract_handle(user_text: str) -> str:
    m = re.search(r"@([A-Za-z0-9_]{1,15})", user_text or "")
    return m.group(1).lower() if m else ""


def _parse_cookie_string(raw: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for part in (raw or "").split(";"):
        item = part.strip()
        if not item or "=" not in item:
            continue
        k, v = item.split("=", 1)
        k = k.strip()
        v = v.strip()
        if not k:
            continue
        out[k] = v
    return out


def _read_cookie_string_arg(cookie_string: str, cookie_file: str) -> str:
    if cookie_string.strip():
        return cookie_string.strip()

    env_cookie = os.getenv("X_COOKIE_STRING", "").strip()
    if env_cookie:
        return env_cookie

    file_path = cookie_file.strip() or os.getenv("X_COOKIE_FILE", "").strip()
    if not file_path:
        return ""
    p = Path(file_path)
    if not p.exists():
        return ""
    try:
        return p.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _inject_x_cookies(context, cookie_string: str = "", cookie_file: str = "") -> bool:
    cookie_map = _parse_cookie_string(_read_cookie_string_arg(cookie_string, cookie_file))
    # Explicit env values override cookie string values.
    env_override = {
        "auth_token": os.getenv("X_AUTH_TOKEN", "").strip(),
        "ct0": os.getenv("X_CSRF_TOKEN", "").strip(),
        "twid": os.getenv("X_TWID", "").strip(),
        "att": os.getenv("X_ATT", "").strip(),
        "lang": os.getenv("X_LANG", "").strip(),
    }
    for k, v in env_override.items():
        if v:
            cookie_map[k] = v

    auth = cookie_map.get("auth_token", "").strip()
    ct0 = cookie_map.get("ct0", "").strip()
    if not auth or not ct0:
        return False

    cookies = []
    # Put cookies on both domains because some flows still hit twitter.com endpoints.
    for domain in (".x.com", ".twitter.com"):
        for name, value in cookie_map.items():
            if not value:
                continue
            cookies.append(
                {
                    "name": name,
                    "value": value,
                    "domain": domain,
                    "path": "/",
                    "httpOnly": name in {"auth_token", "_twitter_sess"},
                    "secure": True,
                }
            )
    context.add_cookies(cookies)
    context.set_extra_http_headers(
        {
            "x-csrf-token": ct0,
            "x-twitter-active-user": "yes",
            "x-twitter-auth-type": "OAuth2Session",
        }
    )
    return True


def _article_status_links(article) -> List[Tuple[str, str]]:
    links: List[Tuple[str, str]] = []
    seen: Set[str] = set()
    a_nodes = article.locator('a[href*="/status/"]')
    count = a_nodes.count()
    for i in range(count):
        href = a_nodes.nth(i).get_attribute("href") or ""
        sid = _extract_status_id(href)
        if not sid:
            continue
        key = f"{sid}:{href}"
        if key in seen:
            continue
        seen.add(key)
        links.append((sid, href))
    return links


def _normalize_media_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    fmt = qs.get("format", [""])[0]
    if fmt and "name=" in url:
        url = re.sub(r"name=[^&]+", "name=orig", url)
    return url


def _extract_media(article) -> List[str]:
    media: List[str] = []
    seen: Set[str] = set()

    selectors = [
        'a[href*="/photo/"] img[src]',
        'div[data-testid="tweetPhoto"] img[src]',
        'video[poster]',
    ]

    for sel in selectors:
        nodes = article.locator(sel)
        count = nodes.count()
        for i in range(count):
            attr = "poster" if "video" in sel else "src"
            raw = nodes.nth(i).get_attribute(attr) or ""
            src = _normalize_media_url(raw)
            if not src:
                continue
            if not ("pbs.twimg.com/media/" in src or "pbs.twimg.com/ext_tw_video_thumb/" in src):
                continue
            if src in seen:
                continue
            seen.add(src)
            media.append(src)

    return media


def _normalize_article_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith("/"):
        url = f"https://x.com{url}"
    url = url.split("?", 1)[0]
    # Canonicalize article media links to base article path.
    if "/article/" in url and "/media/" in url:
        url = url.split("/media/", 1)[0]
    return url


def _extract_article_links(article) -> List[str]:
    urls: List[str] = []
    seen: Set[str] = set()
    nodes = article.locator('a[href*="/article/"]')
    count = nodes.count()
    for i in range(count):
        href = nodes.nth(i).get_attribute("href") or ""
        u = _normalize_article_url(href)
        if not u:
            continue
        if u in seen:
            continue
        seen.add(u)
        urls.append(u)
    return urls


def _collect_article_text(page) -> str:
    # Long-form articles are often rendered as plain text blocks in main/article containers.
    selectors = [
        "div[class*='longform-header-one']",
        "div[class*='longform-header-two']",
        "div[class*='longform-unstyled']",
        "div[class*='longform-blockquote']",
        "div[class*='longform-unordered-list-item']",
        "div[class*='longform-ordered-list-item']",
        ".public-DraftStyleDefault-block",
        "div[data-contents='true'] div[data-block='true']",
        "article p",
        "article div[dir='auto']",
        "main article div[dir='auto']",
        "main p",
    ]
    parts: List[str] = []
    seen: Set[str] = set()
    for sel in selectors:
        nodes = page.locator(sel)
        count = min(nodes.count(), 500)
        for i in range(count):
            t = _clean(nodes.nth(i).inner_text())
            if not t:
                continue
            # Filter login chrome noise.
            if t in {"Log in", "Sign up", "Sign in", "Sign up for X"}:
                continue
            if len(t) < 2:
                continue
            if t in seen:
                continue
            seen.add(t)
            parts.append(t)

    merged = "\n".join(parts).strip()
    return merged


def _collect_longform_text_via_dom(page) -> str:
    try:
        values = page.evaluate(
            """() => {
                const sels = [
                    "div[class*='longform-header-one']",
                    "div[class*='longform-header-two']",
                    "div[class*='longform-unstyled']",
                    "div[class*='longform-blockquote']",
                    "div[class*='longform-unordered-list-item']",
                    "div[class*='longform-ordered-list-item']",
                    ".public-DraftStyleDefault-block",
                    "div[data-contents='true'] div[data-block='true']",
                ];
                const out = [];
                const seen = new Set();
                for (const sel of sels) {
                    for (const n of document.querySelectorAll(sel)) {
                        const t = (n.innerText || "").replace(/\\s+/g, " ").trim();
                        if (!t || t.length < 2) continue;
                        if (seen.has(t)) continue;
                        seen.add(t);
                        out.push(t);
                    }
                }
                return out;
            }"""
        )
    except Exception:
        return ""
    if not values:
        return ""
    parts = [_clean(x) for x in values if _clean(x)]
    return "\n".join(parts).strip()


def _collect_jsonld_article_text(page) -> str:
    nodes = page.locator('script[type="application/ld+json"]')
    count = min(nodes.count(), 30)
    parts: List[str] = []
    seen: Set[str] = set()
    for i in range(count):
        raw = nodes.nth(i).text_content() or ""
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except Exception:
            continue

        stack: List[object] = [obj]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                for k, v in cur.items():
                    if isinstance(v, (dict, list)):
                        stack.append(v)
                    elif isinstance(v, str) and k in {"articleBody", "description", "text"}:
                        t = _clean(v)
                        if t and len(t) >= 20 and t not in seen:
                            seen.add(t)
                            parts.append(t)
            elif isinstance(cur, list):
                stack.extend(cur)
    return "\n".join(parts).strip()


def _extract_long_article(context, url: str, timeout_ms: int) -> Dict[str, str]:
    page = context.new_page()
    item = {
        "url": url,
        "final_url": "",
        "status": "unknown",
        "title": "",
        "text": "",
    }
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        page.wait_for_timeout(2500)
        item["final_url"] = page.url

        title = _clean(page.title())
        if title:
            item["title"] = title

        # Prefer h1 when available.
        h1 = page.locator("h1")
        if h1.count() > 0:
            h1_text = _clean(h1.first.inner_text())
            if h1_text:
                item["title"] = h1_text

        text = _collect_article_text(page)
        if not text:
            text = _collect_longform_text_via_dom(page)
        if not text:
            text = _collect_jsonld_article_text(page)
        if not text:
            try:
                meta_desc = _clean(
                    page.locator('meta[property="og:description"]').first.get_attribute("content") or ""
                )
                if len(meta_desc) >= 20:
                    text = meta_desc
            except Exception:
                pass
        item["text"] = text
        if len(text) >= 20:
            item["status"] = "ok"
            return item

        # X article pages may require login even when status card is visible.
        if "/login" in page.url or "/i/flow/" in page.url:
            item["status"] = "login_required"
            return item

        login_like = (
            page.locator('a[href="/login"]').count() > 0
            or page.locator('a[href*="/signup"]').count() > 0
            or "log in" in (page.content() or "").lower()
        )
        if login_like:
            item["status"] = "login_required"
        elif _clean(item.get("title", "")).lower() == "x":
            item["status"] = "access_limited"
        else:
            item["status"] = "no_text"
        return item
    except PlaywrightTimeoutError:
        item["status"] = "timeout"
        return item
    except Exception:
        item["status"] = "error"
        return item
    finally:
        try:
            page.close()
        except Exception:
            pass


def _status_from_time_permalink(article) -> Tuple[str, str]:
    try:
        t = article.locator("time").first
        if t.count() == 0:
            return "", ""
        a = t.locator("xpath=ancestor::a[1]").first
        if a.count() == 0:
            return "", ""
        href = a.get_attribute("href") or ""
        sid = _extract_status_id(href)
        return sid, href
    except Exception:
        return "", ""


def _extract_article(article) -> Dict[str, str]:
    text_parts: List[str] = []
    seen_text: Set[str] = set()

    def _append_text_from_selector(sel: str, limit: int = 600) -> None:
        nodes = article.locator(sel)
        count = min(nodes.count(), limit)
        for i in range(count):
            part = _clean(nodes.nth(i).inner_text())
            if not part:
                continue
            if part in seen_text:
                continue
            seen_text.add(part)
            text_parts.append(part)

    # Standard tweet text.
    _append_text_from_selector('[data-testid="tweetText"]')

    # X article mode content blocks rendered directly in status page.
    longform_selectors = [
        "[class*='longform-header-one']",
        "[class*='longform-header-two']",
        "[class*='longform-unstyled']",
        "[class*='longform-blockquote']",
        "[class*='longform-unordered-list-item']",
        "[class*='longform-ordered-list-item']",
        "div[data-contents='true'] [data-block='true']",
    ]
    for sel in longform_selectors:
        _append_text_from_selector(sel)

    text = "\n".join(text_parts).strip()

    user_text = ""
    author_handle = ""
    try:
        user_name = article.locator('div[data-testid="User-Name"]').first
        if user_name.count() > 0:
            user_text = _clean(user_name.inner_text())
            author_handle = _extract_handle(user_text)
    except Exception:
        pass

    timestamp = ""
    try:
        t = article.locator("time").first
        if t.count() > 0:
            timestamp = t.get_attribute("datetime") or ""
    except Exception:
        pass

    # Prefer timestamp permalink, because tweet body may contain many /status/ links.
    status_id, status_path = _status_from_time_permalink(article)
    if not status_id:
        links = _article_status_links(article)
        status_id = links[0][0] if links else ""
        status_path = links[0][1] if links else ""
    status_url = ""
    if status_path:
        if status_path.startswith("http"):
            status_url = status_path
        else:
            status_url = f"https://x.com{status_path}"

    return {
        "status_id": status_id,
        "status_url": status_url,
        "author": user_text,
        "author_handle": author_handle,
        "timestamp": timestamp,
        "text": text,
        "media_urls": _extract_media(article),
        "article_urls": _extract_article_links(article),
    }


def _find_target_article(page, status_id: str):
    articles = page.locator("main article")
    count = articles.count()
    if count == 0:
        raise RuntimeError("No tweet article found on page")

    if not status_id:
        return articles.first

    # Prefer exact match on time permalink status id.
    for i in range(count):
        art = articles.nth(i)
        sid, _ = _status_from_time_permalink(art)
        if sid and sid == status_id:
            return art

    # Fallback: any status link inside article.
    for i in range(count):
        art = articles.nth(i)
        links = _article_status_links(art)
        if any(link_sid == status_id for link_sid, _ in links):
            return art

    raise RuntimeError(f"Target status id not found on page: {status_id}")


def _find_target_article_with_retries(page, status_id: str):
    # X timeline is virtualized. The target post may be unmounted after scrolling.
    attempts = 8
    try:
        page.keyboard.press("Home")
        page.wait_for_timeout(500)
    except Exception:
        pass

    last_err: Optional[Exception] = None
    for i in range(attempts):
        try:
            return _find_target_article(page, status_id)
        except Exception as exc:
            last_err = exc
            if i == attempts - 1:
                break
            try:
                page.mouse.wheel(0, 1200)
                page.wait_for_timeout(700)
            except Exception:
                pass

    if last_err:
        raise last_err
    raise RuntimeError(f"Target status id not found on page: {status_id}")


def _collect_articles(page, max_articles: int) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    seen_ids: Set[str] = set()

    articles = page.locator("main article")
    count = min(articles.count(), max_articles)
    for i in range(count):
        data = _extract_article(articles.nth(i))
        sid = data.get("status_id", "")
        text = data.get("text", "")

        if sid:
            if sid in seen_ids:
                continue
            seen_ids.add(sid)
        else:
            # Skip empty nodes without id.
            if not text:
                continue

        items.append(data)
    return items


def _render_markdown(result: Dict) -> str:
    lines: List[str] = []
    lines.append(f"# X Capture {result.get('target_status_id', '')}")
    lines.append("")
    lines.append(f"- url: {result.get('url', '')}")
    lines.append(f"- captured_at: {result.get('captured_at', '')}")
    lines.append("")
    lines.append("## Main Post")
    main = result.get("main", {})
    lines.append(f"- author: {main.get('author', '')}")
    lines.append(f"- handle: @{main.get('author_handle', '')}" if main.get("author_handle") else "- handle: ")
    lines.append(f"- timestamp: {main.get('timestamp', '')}")
    lines.append(f"- status_url: {main.get('status_url', '')}")
    media_urls = main.get("media_urls", [])
    article_urls = main.get("article_urls", [])
    lines.append(f"- media_count: {len(media_urls)}")
    lines.append(f"- article_link_count: {len(article_urls)}")
    lines.append("")
    lines.append(main.get("text", ""))
    if article_urls:
        lines.append("")
        lines.append("article_links:")
        for u in article_urls:
            lines.append(f"- {u}")
    if media_urls:
        lines.append("")
        lines.append("media:")
        for u in media_urls:
            lines.append(f"- {u}")
        lines.append("")
        lines.append("media_preview:")
        for i, u in enumerate(media_urls, 1):
            lines.append(f"![main_{i}]({u})")
    lines.append("")

    lines.append("## Thread")
    thread = result.get("thread", [])
    if not thread:
        lines.append("- none")
    else:
        for idx, item in enumerate(thread, 1):
            lines.append("")
            lines.append(f"### {idx}")
            lines.append(f"- author: {item.get('author', '')}")
            lines.append(f"- handle: @{item.get('author_handle', '')}" if item.get("author_handle") else "- handle: ")
            lines.append(f"- timestamp: {item.get('timestamp', '')}")
            lines.append(f"- status_url: {item.get('status_url', '')}")
            item_media = item.get("media_urls", [])
            lines.append(f"- media_count: {len(item_media)}")
            lines.append("")
            lines.append(item.get("text", ""))
            if item_media:
                lines.append("")
                lines.append("media:")
                for u in item_media:
                    lines.append(f"- {u}")
                lines.append("")
                lines.append("media_preview:")
                for j, u in enumerate(item_media, 1):
                    lines.append(f"![thread_{idx}_{j}]({u})")

    lines.append("")
    lines.append("## Long Article")
    articles = result.get("articles", [])
    if not articles:
        lines.append("- none")
    else:
        for idx, item in enumerate(articles, 1):
            lines.append("")
            lines.append(f"### {idx}")
            lines.append(f"- url: {item.get('url', '')}")
            lines.append(f"- final_url: {item.get('final_url', '')}")
            lines.append(f"- status: {item.get('status', '')}")
            lines.append(f"- title: {item.get('title', '')}")
            lines.append("")
            lines.append(item.get("text", ""))

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture one X post and thread text")
    parser.add_argument("url", help="X post URL")
    parser.add_argument("--browser", default="chromium", choices=["chrome", "edge", "chromium"])
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--manual-login", action="store_true", help="Pause to allow manual login in opened browser")
    parser.add_argument("--timeout", type=int, default=90000)
    parser.add_argument("--proxy", default="", help="Playwright proxy server, e.g. http://127.0.0.1:7890")
    parser.add_argument("--cookie-string", default="", help="Raw cookie string from logged-in x.com session")
    parser.add_argument("--cookie-file", default="", help="Text file that stores one raw cookie string")
    parser.add_argument("--scrolls", type=int, default=4)
    parser.add_argument("--scroll-wait-ms", type=int, default=1200)
    parser.add_argument("--max-articles", type=int, default=50)
    parser.add_argument("--max-thread", type=int, default=20)
    parser.add_argument("--include-others", action="store_true", help="Include non-author posts in thread output")
    parser.add_argument("--hold-on-fail", action="store_true", help="Keep browser open on failure for manual inspection")
    parser.add_argument("--download-media", action="store_true", help="Download media files to local directory")
    parser.add_argument("--media-dir", default=str(MEDIA_DIR), help="Directory for downloaded media")
    parser.add_argument("--output", default="", help="Optional output JSON path")
    parser.add_argument("--output-dir", default=str(CAPTURE_DIR), help="Capture directory for auto files")
    args = parser.parse_args()

    channel = None
    if args.browser == "chrome":
        channel = "chrome"
    elif args.browser == "edge":
        channel = "msedge"

    target_status_id = _extract_status_id(args.url)

    with sync_playwright() as p:
        launch_kwargs = {
            "user_data_dir": str(PROFILE_DIR),
            "channel": channel,
            "headless": args.headless,
        }
        if args.proxy.strip():
            launch_kwargs["proxy"] = {"server": args.proxy.strip()}

        context = p.chromium.launch_persistent_context(
            **launch_kwargs,
        )

        cookie_injected = _inject_x_cookies(context, cookie_string=args.cookie_string, cookie_file=args.cookie_file)
        if cookie_injected:
            print("Cookie mode enabled (auth cookies injected).")

        page = context.new_page()
        try:
            if args.manual_login and not args.headless:
                print("Manual login mode: opening X login page...")
                page.goto("https://x.com/i/flow/login", wait_until="domcontentloaded", timeout=args.timeout)
                print(
                    "Please finish login in browser.\n"
                    "After login succeeds and homepage/feed is visible, press Enter to continue capture..."
                )
                try:
                    input()
                except EOFError:
                    pass
            page.goto(args.url, wait_until="domcontentloaded", timeout=args.timeout)
            if "/i/flow/login" in page.url:
                context.close()
                raise SystemExit("Not logged in. Please log in X in the opened browser, then rerun.")

            page.wait_for_selector("main", timeout=args.timeout)

            page.wait_for_selector("main article", timeout=args.timeout)

            target_article = _find_target_article_with_retries(page, target_status_id)
            main_post = _extract_article(target_article)
            if target_status_id and main_post.get("status_id") and main_post.get("status_id") != target_status_id:
                raise RuntimeError(
                    f"Captured status mismatch: expected={target_status_id}, actual={main_post.get('status_id')}"
                )

            for _ in range(max(0, args.scrolls)):
                page.mouse.wheel(0, 2800)
                page.wait_for_timeout(args.scroll_wait_ms)

            all_articles = _collect_articles(page, max_articles=args.max_articles)
            # Extract linked long-form article content when available.
            article_urls: List[str] = []
            seen_article_urls: Set[str] = set()
            for u in main_post.get("article_urls", []):
                if u and u not in seen_article_urls:
                    seen_article_urls.add(u)
                    article_urls.append(u)
            for node in all_articles:
                for u in node.get("article_urls", []):
                    if u and u not in seen_article_urls:
                        seen_article_urls.add(u)
                        article_urls.append(u)

            long_articles: List[Dict[str, str]] = []
            for u in article_urls:
                long_articles.append(_extract_long_article(context, u, args.timeout))

            # Fallback: if article page is access-limited but status page already has longform blocks,
            # preserve the extracted content from main post.
            if main_post.get("article_urls") and len((main_post.get("text") or "")) >= 120:
                for item in long_articles:
                    if item.get("status") in {"no_text", "access_limited", "login_required"} and not item.get("text"):
                        item["text"] = main_post.get("text", "")
                        item["status"] = "from_status_page"
        except PlaywrightTimeoutError:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            shot = DEBUG_DIR / f"timeout_{ts}.png"
            html = DEBUG_DIR / f"timeout_{ts}.html"
            try:
                page.screenshot(path=str(shot), full_page=True)
                html.write_text(page.content(), encoding="utf-8")
            except Exception:
                pass
            current = page.url
            if args.hold_on_fail:
                print(
                    "Timed out. Browser is kept open for inspection.\n"
                    f"current_url={current}\n"
                    f"Debug saved to {shot} and {html}\n"
                    "Press Enter to close browser..."
                )
                input()
            context.close()
            raise SystemExit(
                "Timed out loading X post. "
                f"current_url={current}. "
                f"Debug saved to {shot} and {html}."
            )
        except Exception as exc:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            shot = DEBUG_DIR / f"error_{ts}.png"
            html = DEBUG_DIR / f"error_{ts}.html"
            current = page.url
            try:
                page.screenshot(path=str(shot), full_page=True)
                html.write_text(page.content(), encoding="utf-8")
            except Exception:
                pass
            if args.hold_on_fail:
                print(
                    "Capture failed. Browser is kept open for inspection.\n"
                    f"error={exc}\n"
                    f"current_url={current}\n"
                    f"Debug saved to {shot} and {html}\n"
                    "Press Enter to close browser..."
                )
                try:
                    input()
                except EOFError:
                    pass
            context.close()
            raise SystemExit(
                f"Capture failed: {exc}. "
                f"current_url={current}. "
                f"Debug saved to {shot} and {html}."
            )

        context.close()

    main_sid = main_post.get("status_id", "")
    if not target_status_id:
        target_status_id = main_sid

    target_handle = (main_post.get("author_handle") or "").lower()
    thread: List[Dict[str, str]] = []
    for item in all_articles:
        sid = item.get("status_id", "")
        if sid and main_sid and sid == main_sid:
            continue

        if not args.include_others and target_handle:
            if (item.get("author_handle") or "").lower() != target_handle:
                continue

        if not item.get("text"):
            continue

        thread.append(item)
        if len(thread) >= args.max_thread:
            break

    captured_at = datetime.now(timezone.utc).isoformat()
    result = {
        "url": args.url,
        "target_status_id": target_status_id,
        "captured_at": captured_at,
        "main": main_post,
        "thread": thread,
        "thread_count": len(thread),
        "scan_count": len(all_articles),
        "articles": long_articles,
        "article_count": len(long_articles),
    }

    if args.download_media:
        media_dir = Path(args.media_dir)
        media_dir.mkdir(parents=True, exist_ok=True)
        downloaded: List[str] = []
        all_media: List[str] = []
        all_media.extend(main_post.get("media_urls", []))
        for item in thread:
            all_media.extend(item.get("media_urls", []))

        unique_media: List[str] = []
        seen_media: Set[str] = set()
        for u in all_media:
            if not u or u in seen_media:
                continue
            seen_media.add(u)
            unique_media.append(u)

        for idx, url in enumerate(unique_media, 1):
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            ext = qs.get("format", ["jpg"])[0] or "jpg"
            file_name = f"{target_status_id or 'capture'}_{idx:02d}.{ext}"
            out_path = media_dir / file_name
            try:
                r = requests.get(
                    url,
                    timeout=30,
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                r.raise_for_status()
                out_path.write_bytes(r.content)
                downloaded.append(str(out_path))
            except Exception:
                continue

        result["downloaded_media"] = downloaded
        result["downloaded_media_count"] = len(downloaded)

    output_json = json.dumps(result, ensure_ascii=False, indent=2)
    print(output_json)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(output_json + "\n", encoding="utf-8")

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    name = target_status_id or datetime.now().strftime("capture_%Y%m%d_%H%M%S")
    json_path = out_dir / f"{name}.json"
    md_path = out_dir / f"{name}.md"

    json_path.write_text(output_json + "\n", encoding="utf-8")
    md_path.write_text(_render_markdown(result), encoding="utf-8")


if __name__ == "__main__":
    main()
