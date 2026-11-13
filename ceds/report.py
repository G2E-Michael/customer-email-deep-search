"""输出：CSV / Markdown / JSON。"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import List

CSV_FIELDS = ["id", "company", "domain", "email", "local", "kind",
              "evidence", "source_count", "dns", "score", "grade", "sources"]


def write_csv(rows: List[dict], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            out = dict(row)
            out["sources"] = " | ".join(row["sources"])
            writer.writerow({k: out.get(k, "") for k in CSV_FIELDS})


def write_markdown(rows: List[dict], path: Path, summary: dict) -> None:
    lines: List[str] = []
    lines.append("# 客户邮箱清单")
    lines.append("")
    lines.append("共 %d 家 / %d 个域名 / %d 个地址（A %d，B %d，C %d）。"
                 % (summary["companies"], summary["domains"], summary["addresses"],
                    summary["grades"].get("A", 0), summary["grades"].get("B", 0),
                    summary["grades"].get("C", 0)))
    lines.append("")
    lines.append("> A/B/C 是**概率等级**，不是验证结果。判据是：地址是否出现在官方页面、被几个来源提到、"
                 "域名 MX 是否健康、具名还是职能箱。真值只有退信与回信。")
    lines.append("")

    grouped: dict = {}
    for row in rows:
        grouped.setdefault((row["id"], row["company"]), []).append(row)

    for (cid, company), items in grouped.items():
        domains = sorted({item["domain"] for item in items})
        lines.append("## %s %s" % (cid, company))
        lines.append("")
        lines.append("域名：%s ｜ 地址：%d" % ("、".join(domains), len(items)))
        lines.append("")
        lines.append("| 等级 | 分 | 邮箱 | 类型 | 证据 | 来源 |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for item in items:
            src = item["sources"][0] if item["sources"] else ""
            lines.append("| %s | %d | %s | %s | %s | %s |"
                         % (item["grade"], item["score"], item["email"],
                            item["kind"], item["evidence"], src))
        lines.append("")

    if summary.get("empty"):
        lines.append("## 无产出")
        lines.append("")
        lines.append("以下公司没挖到任何本域地址（官网可能是纯表单或整站被拦）：")
        for cid in summary["empty"]:
            lines.append("- %s" % cid)
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_json(summary: dict, path: Path) -> None:
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
