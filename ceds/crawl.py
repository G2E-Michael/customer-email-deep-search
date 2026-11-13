"""站点爬取：首页 + 关键词页，提取本域邮箱并记录来源页面。"""
from __future__ import annotations

import re
import urllib.parse
from typing import Dict, List

from .extract import extract
from .fetch import http_get, robots_allows

# 这些路径名后面通常挂着邮箱
LINK_KEYS = (
    "impressum", "imprint", "impressi", "kontakt", "contact", "contatti",
    "contacto", "team", "ueber", "uber", "about", "ueber-uns", "presse",
    "press", "media", "karriere", "career", "jobs", "stellen", "service",
    "haendler", "handler", "dealer", "b2b", "wholesale", "partner", "legal",
    "mentions", "aviso", "agb", "datenschutz", "privacy", "newsletter",
)

_HREF = re.compile(r"""href\s*=\s*["']([^"'#]+)["']""", re.I)
_SKIP_SCHEMES = ("mailto:", "tel:", "javascript:", "data:", "#")


def _candidate_links(base: str, html: str, domain: str, limit: int) -> List[str]:
    urls: List[str] = []
    seen: set[str] = set()
    for href in _HREF.findall(html):
        low = href.lower().strip()
        if not low or low.startswith(_SKIP_SCHEMES):
            continue
        if not any(key in low for key in LINK_KEYS):
            continue
        url = urllib.parse.urljoin(base, href)
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            continue
        host = (parsed.hostname or "").lower()
        if host != domain and not host.endswith("." + domain):
            continue
        clean = url.split("#", 1)[0]
        if clean in seen:
            continue
        seen.add(clean)
        urls.append(clean)
        if len(urls) >= limit:
            break
    return urls


def crawl_domain(
    domain: str,
    max_pages: int = 12,
    timeout: float = 12.0,
    respect_robots: bool = True,
) -> Dict[str, List[str]]:
    """返回 {email: [来源 URL, ...]}。抓不到就返回空 dict，不抛异常。"""
    domain = domain.lower().strip().strip(".")
    found: Dict[str, List[str]] = {}

    base = page = None
    for scheme in ("https://", "http://"):
        url = scheme + domain + "/"
        try:
            page, html = http_get(url, timeout=timeout)
            base = page
            break
        except Exception:
            continue
    if not page or base is None:
        return found

    def record(text: str, source: str) -> None:
        for email in extract(text, domain):
            bucket = found.setdefault(email, [])
            if source not in bucket:
                bucket.append(source)

    record(html, page)

    links = _candidate_links(base, html, domain, limit=max_pages)
    for link in links:
        if respect_robots and not robots_allows(link):
            continue
        try:
            final, sub = http_get(link, timeout=timeout)
        except Exception:
            continue
        record(sub, final)
    return found
