"""HTTP 抓取：UA、超时、编码嗅探、gzip、robots.txt。

用标准库实现，避免为了一个脚本去装 requests。SSL 校验默认关闭——
中小企业站点证书链不完整是常态，抓公开页面不值得为此丢数据。
"""
from __future__ import annotations

import gzip
import re
import ssl
import urllib.error
import urllib.request
import zlib
from urllib.parse import urlparse

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

_ROBOTS: dict[str, list[tuple[str, bool]]] = {}


def _decode(raw: bytes, ctype: str) -> str:
    charset = "utf-8"
    m = re.search(r"charset=([\w\-]+)", ctype or "", re.I)
    if m:
        charset = m.group(1)
    for enc in (charset, "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", "replace")


def http_get(url: str, timeout: float = 12.0, max_bytes: int = 1_500_000) -> tuple[str, str]:
    """返回 (最终 URL, 文本)。失败抛异常。"""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
            "Accept-Language": "de,en;q=0.8,fr;q=0.6,es;q=0.6",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as resp:
        raw = resp.read(max_bytes)
        enc = (resp.headers.get("Content-Encoding") or "").lower()
        ctype = resp.headers.get("Content-Type") or ""
        final = resp.geturl()
    if "gzip" in enc:
        try:
            raw = gzip.decompress(raw)
        except OSError:
            pass
    elif "deflate" in enc:
        try:
            raw = zlib.decompress(raw, -zlib.MAX_WBITS)
        except zlib.error:
            pass
    return final, _decode(raw, ctype)


def _load_robots(base: str, timeout: float) -> list[tuple[str, bool]]:
    try:
        _, txt = http_get(base + "/robots.txt", timeout=timeout, max_bytes=200_000)
    except Exception:
        return []
    rules: list[tuple[str, bool]] = []
    applies = False
    for line in txt.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip().lower(), value.strip()
        if key == "user-agent":
            applies = value in ("*", "")
            continue
        if not applies:
            continue
        if key == "disallow" and value:
            rules.append((value, False))
        elif key == "allow" and value:
            rules.append((value, True))
    rules.sort(key=lambda r: len(r[0]), reverse=True)  # 最长前缀优先
    return rules


def robots_allows(url: str, timeout: float = 8.0) -> bool:
    parsed = urlparse(url)
    base = "%s://%s" % (parsed.scheme, parsed.netloc)
    if base not in _ROBOTS:
        _ROBOTS[base] = _load_robots(base, timeout)
    path = parsed.path or "/"
    for prefix, allow in _ROBOTS[base]:
        if path.startswith(prefix):
            return allow
    return True
