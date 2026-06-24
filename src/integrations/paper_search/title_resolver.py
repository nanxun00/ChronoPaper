"""按标题在学术 API 中检索论文（用于核验 LLM 推荐）。"""

from __future__ import annotations

import difflib
import re
import time
from typing import Any

import arxiv
import requests

from src.integrations.arxiv.fetcher import arxiv_result_to_dict
from src.integrations.openalex.fetcher import OPENALEX_API, _api_params, _work_to_candidate
from src.integrations.openreview.fetcher import (
    OPENREVIEW_API,
    _content_value,
    _note_to_candidate,
    is_openreview_accepted_candidate,
)

TITLE_MATCH_THRESHOLD = 0.82


def normalize_title(title: str) -> str:
    text = (title or "").lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def title_similarity(query: str, candidate: str) -> float:
    a = normalize_title(query)
    b = normalize_title(candidate)
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def _best_title_match(query: str, candidates: list[tuple[str, dict]]) -> tuple[dict, str, float] | None:
    best: tuple[dict, str, float] | None = None
    for found_title, meta in candidates:
        score = title_similarity(query, found_title)
        if score >= TITLE_MATCH_THRESHOLD and (best is None or score > best[2]):
            best = (meta, found_title, score)
    return best


def _meta_from_arxiv_result(raw: arxiv.Result) -> dict[str, Any]:
    data = arxiv_result_to_dict(raw)
    data["paper_id"] = data["arxiv_id"]
    data["source"] = "arxiv"
    data["pool_type"] = "arxiv"
    return data


def search_arxiv_by_title(title: str) -> tuple[dict[str, Any], str, float] | None:
    query_title = (title or "").strip()
    if not query_title:
        return None
    safe = query_title.replace('"', " ").strip()[:240]
    client = arxiv.Client(num_retries=3, delay_seconds=3, page_size=5)
    search = arxiv.Search(query=f'ti:"{safe}"', max_results=5)
    candidates: list[tuple[str, dict]] = []
    try:
        for result in client.results(search):
            candidates.append((result.title or "", _meta_from_arxiv_result(result)))
    except Exception:
        return None
    return _best_title_match(query_title, candidates)


def search_openalex_by_title(title: str) -> tuple[dict[str, Any], str, float] | None:
    query_title = (title or "").strip()
    if not query_title:
        return None
    try:
        resp = requests.get(
            OPENALEX_API,
            params=_api_params({"search": query_title, "per_page": "8"}),
            timeout=30,
        )
        resp.raise_for_status()
        works = resp.json().get("results") or []
    except Exception:
        return None

    candidates: list[tuple[str, dict]] = []
    for work in works:
        found = (work.get("display_name") or work.get("title") or "").strip()
        if found:
            candidates.append((found, _work_to_candidate(work)))
    time.sleep(0.15)
    return _best_title_match(query_title, candidates)


def search_openreview_by_title(title: str) -> tuple[dict[str, Any], str, float] | None:
    query_title = (title or "").strip()
    if not query_title:
        return None
    try:
        resp = requests.get(
            OPENREVIEW_API,
            params={"search": query_title, "limit": 8},
            timeout=30,
        )
        resp.raise_for_status()
        notes = resp.json().get("notes") or []
    except Exception:
        return None

    candidates: list[tuple[str, dict]] = []
    for note in notes:
        content = note.get("content") or {}
        found = str(_content_value(content, "title", "")).strip()
        if not found:
            continue
        invitations = note.get("invitations") or []
        invitation = invitations[0] if invitations else "openreview.net/Unknown/-/Submission"
        meta = _note_to_candidate(note, invitation)
        if is_openreview_accepted_candidate(meta):
            meta["pool_type"] = "openreview"
            candidates.append((found, meta))
    time.sleep(0.2)
    return _best_title_match(query_title, candidates)


def resolve_paper_by_title(title: str) -> dict[str, Any] | None:
    """按标题检索，OpenAlex → arXiv → OpenReview 依次尝试。"""
    for resolver, search_fn in (
        ("openalex", search_openalex_by_title),
        ("arxiv", search_arxiv_by_title),
        ("openreview", search_openreview_by_title),
    ):
        hit = search_fn(title)
        if not hit:
            continue
        meta, matched_title, score = hit
        return {
            "resolver": resolver,
            "query_title": title,
            "matched_title": matched_title,
            "match_score": round(score, 3),
            "meta": meta,
        }
    return None
