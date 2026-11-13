"""DeepSeek Search 通道：每个域名一条 ``"@domain"`` 检索。

没有 key 就自动跳过（--local-only 完全离线）。
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import List, Optional

SEARCH_URL = "https://api.deepseek.com/v1/tools/search"


class SearchError(RuntimeError):
    pass


def load_api_key(explicit: Optional[str] = None) -> Optional[str]:
    if explicit:
        return explicit
    env = os.environ.get("DEEPSEEK_API_KEY")
    if env:
        return env.strip()
    for path in (Path.home() / ".dsh" / ".env", Path.home() / ".env", Path.cwd() / ".env"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("DEEPSEEK_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def search(query: str, count: int = 10, api_key: Optional[str] = None,
           timeout: float = 90.0) -> List[dict]:
    key = api_key or load_api_key()
    if not key:
        raise SearchError("缺少 DEEPSEEK_API_KEY：设环境变量，或写进 ~/.dsh/.env")
    body = json.dumps({"query": query, "count": count}).encode("utf-8")
    req = urllib.request.Request(
        SEARCH_URL,
        data=body,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:200]
        raise SearchError("HTTP %s %s" % (exc.code, detail)) from exc
    except urllib.error.URLError as exc:
        raise SearchError("网络错误: %s" % exc) from exc
    return payload.get("results") or []


def result_blob(item: dict) -> str:
    return " ".join(str(item.get(k) or "") for k in ("title", "summary", "snippet", "content"))
