"""评分与分级：把「证据强弱」折成一个 0–100 的排序分。

这是启发式，不是验证。权重集中在这里，方便按自己的数据调。
"""
from __future__ import annotations

import re
from typing import Iterable

EVIDENCE_BASE = {"official": 40, "third_party": 30, "inferred": 10}

ROLE_WORDS = {
    "info", "kontakt", "contact", "contatti", "contacto", "hello", "hallo",
    "office", "sales", "service", "support", "team", "mail", "post", "admin",
    "webmaster", "presse", "press", "media", "jobs", "job", "karriere",
    "careers", "hr", "marketing", "event", "events", "booking", "bookings",
    "boxoffice", "ticket", "tickets", "reservation", "reservations", "anfrage",
    "direktion", "geschaeftsfuehrung", "verwaltung", "bestellung", "order",
    "orders", "shop", "datenschutz", "legal", "impressum", "newsletter",
    "welcome", "hi", "contactus", "customer", "customers", "customerservice",
    "enquiries", "enquiry", "inquiries", "inquiry", "reception", "front",
    "buero", "bureau", "sekretariat", "verwaltung", "marketing",
}

FREEMAIL = {
    "gmail.com", "gmx.de", "gmx.net", "gmx.at", "gmx.ch", "web.de", "t-online.de",
    "outlook.com", "hotmail.com", "hotmail.de", "hotmail.fr", "live.com", "yahoo.com",
    "yahoo.de", "yahoo.fr", "icloud.com", "me.com", "aol.com", "protonmail.com",
    "orange.fr", "free.fr", "wanadoo.fr", "laposte.net", "libero.it", "virgilio.it",
    "wp.pl", "o2.pl", "interia.pl", "seznam.cz", "bluewin.ch", "aon.at", "chello.at",
}

_PERSON = re.compile(r"^[a-z]{2,}([.\-_][a-z]{2,}){0,2}$", re.I)


def classify(local: str) -> str:
    """role（职能箱）还是 named（疑似具名）。"""
    if local in ROLE_WORDS:
        return "role"
    if any(ch.isdigit() for ch in local):
        # info2 / sales2024 之类，仍然当职能箱
        stripped = re.sub(r"[0-9]+$", "", local)
        if stripped in ROLE_WORDS:
            return "role"
    if len(local) >= 3 and _PERSON.match(local):
        return "named"
    return "role"


def grade(score: int) -> str:
    if score >= 70:
        return "A"
    if score >= 45:
        return "B"
    return "C"


DNS_BONUS = {"mx": 10, "a_only": 3, "null_mx": -40, "dead": -40}


def score_address(email: str, evidence: str = "official",
                  sources: Iterable[str] = (), dns_state: str = "mx") -> int:
    local, _, host = email.partition("@")
    score = EVIDENCE_BASE.get(evidence, 10)
    score += 10 if classify(local) == "named" else 5
    score += min(20, max(0, len(list(sources)) - 1) * 5)
    score += DNS_BONUS.get(dns_state, 0)
    if host in FREEMAIL:
        score -= 10
    return max(0, min(100, score))
