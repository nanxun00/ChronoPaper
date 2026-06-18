"""引用数查询（Semantic Scholar 免费 API，无需 Key）。"""
from __future__ import annotations

import re
import time

import requests

ARXIV_RE = re.compile(r"(\d{4}\.\d{4,5})")
_last_request_at = 0.0


def _throttle(min_interval: float = 1.0) -> None:
    global _last_request_at
    now = time.time()
    wait = min_interval - (now - _last_request_at)
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.time()


def fetch_citation_count(paper_id: str, title: str = "") -> int | None:
    """按 arXiv ID 或标题查询引用数。"""
    arxiv_id = paper_id
    if paper_id.startswith("or:"):
        arxiv_id = ""
    else:
        m = ARXIV_RE.search(paper_id)
        arxiv_id = m.group(1) if m else paper_id

    if arxiv_id and not arxiv_id.startswith("or:"):
        _throttle()
        try:
            resp = requests.get(
                f"https://api.semanticscholar.org/graph/v1/paper/arXiv:{arxiv_id}",
                params={"fields": "citationCount"},
                timeout=15,
            )
            if resp.status_code == 200:
                count = resp.json().get("citationCount")
                return int(count) if count is not None else None
        except Exception:
            pass

    if title:
        _throttle()
        try:
            resp = requests.get(
                "https://api.semanticscholar.org/graph/v1/paper/search",
                params={"query": title[:200], "limit": 1, "fields": "citationCount,title"},
                timeout=15,
            )
            if resp.status_code == 200:
                data = (resp.json().get("data") or [])
                if data:
                    count = data[0].get("citationCount")
                    return int(count) if count is not None else None
        except Exception:
            pass
    return None
