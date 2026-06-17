"""arXiv 论文抓取：RSS 增量 + API 元数据补全。"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from time import sleep
from typing import Any

import arxiv
import feedparser
from arxiv import Result as ArxivResult

ARXIV_ID_RE = re.compile(r"(\d{4}\.\d{4,5})(?:v\d+)?")


def parse_arxiv_id(entry_id: str) -> str:
    match = ARXIV_ID_RE.search(entry_id.replace("oai:arXiv.org:", ""))
    if not match:
        raise ValueError(f"Cannot parse arxiv_id from {entry_id}")
    return match.group(1)


def normalize_published_at(value: datetime | None) -> datetime | None:
    """转为 UTC naive datetime，便于写入 MySQL DATETIME。"""
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _normalize_categories(categories: list[str] | str | None) -> list[str]:
    if not categories:
        return []
    if isinstance(categories, str):
        return [c.strip() for c in categories.replace("，", ",").split(",") if c.strip()]
    return [c.strip() for c in categories if c and c.strip()]


def fetch_arxiv_candidates(categories: list[str] | str, *, debug_limit: int | None = None) -> list[ArxivResult]:
    cats = _normalize_categories(categories)
    if not cats:
        raise ValueError("至少需要一个 arXiv 分类，例如 cs.AI")

    query = "+".join(cats)
    feed = feedparser.parse(f"https://rss.arxiv.org/atom/{query}")
    if getattr(feed.feed, "title", "") and "Feed error" in feed.feed.title:
        raise ValueError(f"无效的 arXiv 分类: {query}")

    paper_ids = [
        entry.id.removeprefix("oai:arXiv.org:")
        for entry in feed.entries
        if entry.get("arxiv_announce_type", "new") == "new"
    ]
    if debug_limit:
        paper_ids = paper_ids[:debug_limit]

    client = arxiv.Client(num_retries=5, delay_seconds=5, page_size=20)
    results: list[ArxivResult] = []
    for i in range(0, len(paper_ids), 20):
        batch_ids = paper_ids[i : i + 20]
        search = arxiv.Search(id_list=batch_ids)
        for attempt in range(3):
            try:
                results.extend(list(client.results(search)))
                break
            except arxiv.HTTPError as exc:
                if exc.status == 429 and attempt < 2:
                    sleep(15 * (attempt + 1))
                else:
                    raise
        if i + 20 < len(paper_ids):
            sleep(3)
    return results


def arxiv_result_to_dict(raw: ArxivResult) -> dict[str, Any]:
    arxiv_id = parse_arxiv_id(raw.entry_id)
    published_at = normalize_published_at(raw.published)
    return {
        "arxiv_id": arxiv_id,
        "title": (raw.title or "").strip(),
        "authors": [a.name for a in raw.authors],
        "abstract": (raw.summary or "").strip(),
        "categories": list(raw.categories or []),
        "published_at": published_at,
        "abs_url": raw.entry_id,
        "pdf_url": raw.pdf_url,
    }
