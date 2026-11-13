from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .dnsx import domain_health
from .pipeline import load_customers, run, summarize
from .report import write_csv, write_json, write_markdown


def _cmd_run(args: argparse.Namespace) -> int:
    customers = load_customers(args.customers)
    if not customers:
        print("客户清单为空：检查 %s 的表头（id,name,domains,country,notes）" % args.customers)
        return 2
    if args.limit:
        customers = customers[: args.limit]

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print("开始：%d 家公司 / %d 个域名" % (
        len(customers), len({d for c in customers for d in c["domains"]})))
    rows = run(
        customers,
        max_pages=args.max_pages,
        workers=args.workers,
        use_search=not args.local_only,
        respect_robots=not args.no_robots,
        api_key=args.api_key,
    )
    summary = summarize(rows, customers)
    write_csv(rows, out / "addresses.csv")
    write_markdown(rows, out / "report.md", summary)
    write_json(summary, out / "summary.json")

    print("")
    print("完成：%d 个地址（A %d / B %d / C %d）"
          % (summary["addresses"], summary["grades"].get("A", 0),
             summary["grades"].get("B", 0), summary["grades"].get("C", 0)))
    print("输出：%s" % out.resolve())
    return 0


def _cmd_dns(args: argparse.Namespace) -> int:
    domains = [d.strip().lower() for d in args.domains.replace(",", " ").split() if d.strip()]
    if not domains:
        print("用法：ceds dns --domains a.com,b.de")
        return 2
    for domain in domains:
        health = domain_health(domain)
        mx = ", ".join("%d %s" % (pref, host) for pref, host in health["mx"]) or "-"
        print("%-32s %-8s MX: %s" % (domain, health["state"], mx))
        if health.get("error"):
            print("  ! %s" % health["error"])
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ceds",
        description="按客户清单挖尽域名下的公开邮箱（不做 SMTP 验证）",
    )
    parser.add_argument("--version", action="version", version="ceds " + __version__)
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="跑完整流水线")
    run_p.add_argument("--customers", required=True, help="客户清单 CSV")
    run_p.add_argument("--out", default="out", help="输出目录（默认 out/）")
    run_p.add_argument("--max-pages", type=int, default=12, help="每个域名最多抓几页内页")
    run_p.add_argument("--workers", type=int, default=6, help="并发数")
    run_p.add_argument("--local-only", action="store_true",
                       help="只爬官网，不走 DeepSeek 搜索（零成本）")
    run_p.add_argument("--no-robots", action="store_true", help="忽略 robots.txt（不建议）")
    run_p.add_argument("--api-key", default=None, help="DeepSeek API key（默认读环境变量）")
    run_p.add_argument("--limit", type=int, default=0, help="只跑前 N 家，调试用")
    run_p.set_defaults(func=_cmd_run)

    dns_p = sub.add_parser("dns", help="只看域名 MX/A 健康")
    dns_p.add_argument("--domains", required=True, help="逗号分隔的域名")
    dns_p.set_defaults(func=_cmd_dns)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n已中断")
        return 130


if __name__ == "__main__":
    sys.exit(main())
