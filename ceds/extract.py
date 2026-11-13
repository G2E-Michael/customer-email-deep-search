"""邮箱地址的正则、归一化与过滤。

原则：只保留「在页面上真实出现过」的字符串，不做任何构造。
"""
from __future__ import annotations

import html
import re
from typing import Iterable

# 覆盖常见的 gTLD 与欧洲 ccTLD；够用即可，不做全量 PSL。
TLDS = (
    "com", "net", "org", "edu", "gov", "int", "info", "biz", "name", "pro",
    "aero", "coop", "museum", "travel", "jobs", "mobi", "tel", "asia", "cat",
    "shop", "store", "online", "site", "xyz", "top", "club", "app", "dev", "io",
    "co", "ai", "eu", "uk", "de", "at", "ch", "fr", "it", "es", "nl", "be", "lu",
    "dk", "se", "no", "fi", "is", "pl", "cz", "sk", "hu", "ro", "bg", "gr", "si",
    "hr", "rs", "lt", "lv", "ee", "ie", "pt", "mt", "cy", "ca", "us", "mx", "br",
    "ar", "cl", "au", "nz", "za", "jp", "kr", "cn", "hk", "tw", "sg", "in", "tr",
    "ru", "ua", "by", "kz", "wien", "berlin", "hamburg", "koeln", "bayern",
    "tirol", "amsterdam", "brussels", "paris", "london",
)

_TLD_ALT = "|".join(sorted(set(TLDS), key=len, reverse=True))

EMAIL_RE = re.compile(
    r"[A-Za-z0-9._%+\-]+@(?:[A-Za-z0-9\-]+\.)+(?:" + _TLD_ALT + r")(?![A-Za-z0-9])",
    re.I,
)

# 明显的占位符：出现在「邮箱格式示例」站（prospeo 一类）上的假地址
PLACEHOLDER_LOCALS = {
    "test", "email", "name", "yourname", "your.name", "yourname.yourlastname",
    "firstname", "lastname", "firstname.lastname", "vorname", "nachname",
    "max.mustermann", "m.mustermann", "john.doe", "j.doe", "jane.doe",
    "user", "username", "someone", "example", "sample", "demo",
}
PLACEHOLDER_FRAGMENTS = (
    "john.doe", "jane.doe", "max.mustermann", "beispiel", "your-email",
    "youremail", "your.name", "mustermann",
)
BAD_LOCALS = {
    "abuse", "postmaster", "noreply", "no-reply", "donotreply", "do-not-reply",
    "mailer-daemon", "bounce", "bounces", "unsubscribe", "privacy",
}
BAD_DOMAINS = {
    "example.com", "example.org", "example.net", "domain.com", "domain.de",
    "test.com", "email.com", "yourdomain.com", "sentry.io", "wixpress.com",
}
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js")

_AT_BRACKETS = re.compile(r"\s*[\(\[\{]\s*(?:at|ät|atsign|arroba)\s*[\)\]\}]\s*", re.I)
_DOT_BRACKETS = re.compile(r"\s*[\(\[\{]\s*(?:dot|punkt|point|punto)\s*[\)\]\}]\s*", re.I)


def normalize(text: str) -> str:
    """把 ``name [at] example [dot] de``、``&#64;``、``%40`` 之类还原成正常地址。"""
    if not text:
        return ""
    t = html.unescape(text)
    t = t.replace("\u00a0", " ").replace("\u200b", "").replace("\ufeff", "")
    t = _AT_BRACKETS.sub("@", t)
    t = _DOT_BRACKETS.sub(".", t)
    t = t.replace("%40", "@").replace("%2540", "@")
    return t


def _clean(raw: str) -> str:
    return raw.strip().strip(".,;:()<>\"'").lower().replace("\u00a0", "")


def is_plausible(email: str) -> bool:
    """剔除占位符、图片名、退信箱、明显不是地址的串。"""
    if email.count("@") != 1:
        return False
    local, _, domain = email.partition("@")
    if not local or not domain:
        return False
    if len(local) < 2 or len(local) > 64:
        return False
    if any(email.endswith(ext) for ext in IMAGE_EXTS):
        return False
    if domain in BAD_DOMAINS:
        return False
    if local in BAD_LOCALS:
        return False
    if local in PLACEHOLDER_LOCALS:
        return False
    if any(frag in email for frag in PLACEHOLDER_FRAGMENTS):
        return False
    if re.match(r"^[0-9a-f]{16,}$", local):  # 一串 hash，通常是追踪串
        return False
    return True


def belongs_to(email: str, domain: str) -> bool:
    """是否属于该公司域名（含子域）。"""
    _, _, host = email.partition("@")
    domain = domain.lower().strip(".")
    return host == domain or host.endswith("." + domain)


def extract(text: str, domain: str) -> list[str]:
    """从一段文本里抽出属于 ``domain`` 的地址，保序去重。"""
    out: list[str] = []
    seen: set[str] = set()
    for match in EMAIL_RE.finditer(normalize(text)):
        email = _clean(match.group(0))
        if email in seen or not belongs_to(email, domain) or not is_plausible(email):
            continue
        seen.add(email)
        out.append(email)
    return out


def extract_all(text: str) -> list[str]:
    """不限定域名，抽所有看起来像地址的串（用于统计第三方来源）。"""
    out: list[str] = []
    seen: set[str] = set()
    for match in EMAIL_RE.finditer(normalize(text)):
        email = _clean(match.group(0))
        if email in seen or not is_plausible(email):
            continue
        seen.add(email)
        out.append(email)
    return out


def merge_sources(existing: Iterable[str], new: Iterable[str]) -> list[str]:
    seen: list[str] = []
    for url in list(existing) + list(new):
        if url and url not in seen:
            seen.append(url)
    return seen
