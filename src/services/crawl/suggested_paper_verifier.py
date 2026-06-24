"""核验 LLM 推荐的论文标题：API 命中视为真实，未命中视为幻觉。"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from src.integrations.paper_search.title_resolver import resolve_paper_by_title
from src.utils.logging_config import setup_logger

logger = setup_logger("SuggestedPaperVerifier")

MAX_SUGGESTIONS = 6


def _serialize_meta(meta: dict) -> dict:
    safe = dict(meta)
    pub = safe.get("published_at")
    if pub is not None and hasattr(pub, "isoformat"):
        safe["published_at"] = pub.isoformat()
    return safe


def _deserialize_meta(meta: dict) -> dict:
    safe = dict(meta)
    pub = safe.get("published_at")
    if isinstance(pub, str) and pub:
        try:
            safe["published_at"] = datetime.fromisoformat(pub.replace("Z", "+00:00")[:19])
        except ValueError:
            safe["published_at"] = None
    return safe


def _parse_suggestion(item: Any) -> dict[str, str] | None:
    if isinstance(item, str):
        title = item.strip()
        return {"title": title, "reason": ""} if title else None
    if isinstance(item, dict):
        title = (item.get("title") or "").strip()
        if not title:
            return None
        return {"title": title, "reason": (item.get("reason") or "").strip()}
    return None


def verify_suggested_papers(suggestions: list[Any]) -> dict:
    """逐条 API 检索推荐标题，返回命中与幻觉列表。"""
    verified: list[dict] = []
    hallucinated: list[dict] = []
    seen_titles: set[str] = set()

    for raw in suggestions[:MAX_SUGGESTIONS]:
        parsed = _parse_suggestion(raw)
        if not parsed:
            continue
        query_title = parsed["title"]
        key = query_title.lower()
        if key in seen_titles:
            continue
        seen_titles.add(key)

        try:
            hit = resolve_paper_by_title(query_title)
        except Exception as exc:
            logger.warning("Title resolve failed for %r: %s", query_title[:80], exc)
            hit = None

        if hit:
            hit = dict(hit)
            hit["meta"] = _serialize_meta(hit["meta"])
            verified.append({**hit, "reason": parsed["reason"]})
        else:
            hallucinated.append({
                "query_title": query_title,
                "reason": parsed["reason"],
                "status": "not_found",
            })

    total = len(verified) + len(hallucinated)
    return {
        "total": total,
        "hit": len(verified),
        "missed": len(hallucinated),
        "verified": verified,
        "hallucinated": hallucinated,
        "summary": f"{len(verified)}/{total} 命中" if total else "0/0",
    }


def load_verified_metas(verified_json: str) -> list[dict]:
    """从任务存储的 JSON 中取出可抓取的论文 meta。"""
    raw = (verified_json or "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []

    metas: list[dict] = []
    seen: set[str] = set()
    for item in data.get("verified") or []:
        meta = item.get("meta")
        if not meta:
            continue
        meta = _deserialize_meta(meta)
        pid = meta.get("paper_id")
        if not pid or pid in seen:
            continue
        seen.add(pid)
        enriched = dict(meta)
        enriched["llm_suggested_verified"] = True
        enriched.setdefault("pool_type", enriched.get("source", "openalex"))
        metas.append(enriched)
    return metas
