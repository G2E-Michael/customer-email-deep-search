"""流水线：域名健康 → 官网爬取 →（可选）搜索通道 → 清洗 → 评分 → 输出。"""
from __future__ import annotations

import csv
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional

from .crawl import crawl_domain
from .dnsx import domain_health
from .extract import extract, merge_sources
from .score import classify, grade, score_address
from .search import SearchError, result_blob, search


def load_customers(path: str | Path) -> List[dict]:
    customers: List[dict] = []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            domains = [d.strip().lower().strip(".")
                       for d in re.split(r"[;,]", row.get("domains") or "")
                       if d.strip()]
            name = (row.get("name") or "").strip()
            if not name and not domains:
                continue
            customers.append({
                "id": (row.get("id") or "").strip(),
                "name": name,
                "domains": domains,
                "country": (row.get("country") or "").strip(),
                "notes": (row.get("notes") or "").strip(),
            })
    return customers


def run(customers: List[dict], max_pages: int = 12, workers: int = 6,
        use_search: bool = True, respect_robots: bool = True,
        api_key: Optional[str] = None, progress=print) -> List[dict]:
    domains = sorted({d for c in customers for d in c["domains"]})

    health: Dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(domain_health, d): d for d in domains}
        for fut in as_completed(futures):
            domain = futures[fut]
            try:
                health[domain] = fut.result()
            except Exception as exc:  # noqa: BLE001 - 单个域名失败不影响整体
                health[domain] = {"domain": domain, "mx": [], "a": [],
                                  "state": "dead", "error": str(exc)}

    found: Dict[str, Dict[str, dict]] = {d: {} for d in domains}

    def absorb(domain: str, mapping: Dict[str, List[str]], evidence: str) -> None:
        for email, sources in mapping.items():
            entry = found[domain].setdefault(email, {"sources": [], "evidence": evidence})
            entry["sources"] = merge_sources(entry["sources"], sources)
            if evidence == "official":
                entry["evidence"] = "official"

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(crawl_domain, d, max_pages, 12.0, respect_robots): d
                   for d in domains if health[d]["state"] != "dead"}
        for fut in as_completed(futures):
            domain = futures[fut]
            try:
                absorb(domain, fut.result(), "official")
            except Exception as exc:  # noqa: BLE001
                progress("  ! 爬取失败 %s: %s" % (domain, exc))
    for domain in domains:
        progress("  官网 %-32s %2d 个地址" % (domain, len(found[domain])))

    if use_search:
        for index, domain in enumerate(domains, 1):
            if health[domain]["state"] == "dead":
                continue
            query = '"@%s"' % domain
            try:
                results = search(query, count=10, api_key=api_key)
            except SearchError as exc:
                progress("  ! 搜索失败 %s: %s" % (domain, exc))
                continue
            mapping: Dict[str, List[str]] = {}
            for item in results:
                url = item.get("url") or ""
                for email in extract(result_blob(item), domain):
                    mapping.setdefault(email, []).append(url)
            absorb(domain, mapping, "third_party")
            progress("  搜索 %d/%d %-32s +%d 个" % (index, len(domains), domain, len(mapping)))

    rows: List[dict] = []
    for customer in customers:
        for domain in customer["domains"]:
            state = health.get(domain, {}).get("state", "dead")
            for email, entry in found.get(domain, {}).items():
                local = email.split("@", 1)[0]
                score = score_address(email, entry["evidence"], entry["sources"], state)
                rows.append({
                    "id": customer["id"],
                    "company": customer["name"],
                    "domain": domain,
                    "email": email,
                    "local": local,
                    "kind": classify(local),
                    "evidence": entry["evidence"],
                    "sources": entry["sources"],
                    "source_count": len(entry["sources"]),
                    "dns": state,
                    "score": score,
                    "grade": grade(score),
                })

    rows.sort(key=lambda r: (r["id"], r["company"], -r["score"], r["email"]))
    return rows


def summarize(rows: List[dict], customers: List[dict]) -> dict:
    per_company: Dict[str, int] = {}
    per_grade = {"A": 0, "B": 0, "C": 0}
    for row in rows:
        key = row["id"] or row["company"]
        per_company[key] = per_company.get(key, 0) + 1
        per_grade[row["grade"]] = per_grade.get(row["grade"], 0) + 1
    return {
        "companies": len(customers),
        "domains": len({d for c in customers for d in c["domains"]}),
        "addresses": len(rows),
        "grades": per_grade,
        "per_company": per_company,
        "empty": [c["id"] or c["name"] for c in customers
                  if not any(r["id"] == c["id"] and r["company"] == c["name"] for r in rows)],
    }
