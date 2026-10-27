"""Fetch and strip public web pages for evidence extraction.

Only public http(s) URLs are fetched. SSRF protection rejects private /
loopback destinations. Pages are size- and time-limited, and HTML is reduced
to readable text so extraction models see evidence, not markup.
"""
from __future__ import annotations

import logging
import re
from typing import Any

import requests

from ..config import Config
from ..utils import is_safe_public_url

logger = logging.getLogger(__name__)

MAX_BYTES = 500_000
FETCH_TIMEOUT = 8.0
USER_AGENT = (
    "SellerFinderBot/1.0 (+local research; respectful crawler; contact admin)"
)

_TAG_RE = re.compile(r"<(script|style|noscript|svg)[^>]*>.*?</\1>", re.I | re.S)
_HTML_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\r\f\v]+")
_BLANK_RE = re.compile(r"\n{3,}")


def html_to_text(html: str) -> str:
    text = _TAG_RE.sub(" ", html or "")
    text = _HTML_RE.sub("\n", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    text = _WS_RE.sub(" ", text)
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join(line for line in lines if line)
    return _BLANK_RE.sub("\n\n", text).strip()


def fetch_page(url: str, *, timeout: float = FETCH_TIMEOUT) -> dict[str, Any]:
    """Fetch *url* and return ``{url, ok, title, text, error}``.

    Never raises for network problems; errors are structured.
    """
    if not is_safe_public_url(url):
        return {"url": url, "ok": False, "title": "", "text": "", "error": "unsafe_url"}

    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
            stream=True,
            allow_redirects=True,
        )
        response.raise_for_status()
        content_type = (response.headers.get("Content-Type") or "").lower()
        if content_type and "html" not in content_type and "text" not in content_type:
            return {"url": url, "ok": False, "title": "", "text": "", "error": "unsupported_content_type"}

        raw = b""
        for chunk in response.iter_content(chunk_size=65_536):
            raw += chunk
            if len(raw) >= MAX_BYTES:
                break
        encoding = response.encoding or "utf-8"
        html = raw[:MAX_BYTES].decode(encoding, errors="replace")
    except requests.exceptions.RequestException as exc:
        logger.info("Page fetch failed for %s: %s", url, exc)
        return {"url": url, "ok": False, "title": "", "text": "", "error": "request_failed"}

    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    title = html_to_text(title_match.group(1))[:200] if title_match else ""
    text = html_to_text(html)
    if not text:
        return {"url": url, "ok": False, "title": title, "text": "", "error": "empty_page"}
    return {"url": url, "ok": True, "title": title, "text": text[:40_000], "error": None}


def fetch_pages(urls: list[str], *, limit: int | None = None) -> list[dict[str, Any]]:
    """Fetch up to *limit* unique safe URLs. Order is preserved."""
    max_pages = limit if limit is not None else Config.RESEARCH_MAX_PAGES
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for url in urls:
        if len(out) >= max_pages:
            break
        if not url or url in seen:
            continue
        seen.add(url)
        page = fetch_page(url)
        if page.get("ok"):
            out.append(page)
    return out
