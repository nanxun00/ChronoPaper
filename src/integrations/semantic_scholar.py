"""Semantic Scholar Graph API（引用 / 被引网络）。"""
from __future__ import annotations

import re
import time
from typing import Any

import requests

from src.utils.logging_config import setup_logger

logger = setup_logger("SemanticScholar")

BASE_URL = "https://api.semanticscholar.org/graph/v1"
ARXIV_RE = re.compile(r"(\d{4}\.\d{4,5})")
_last_request_at = 0.0


def _throttle(min_interval: float = 3.0) -> None:
    global _last_request_at
    now = time.time()
    wait = min_interval - (now - _last_request_at)
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.time()


def _get_json(url: str, *, params: dict | None = None, timeout: int = 30, retries: int = 4) -> dict | None:
    for attempt in range(retries):
        _throttle()
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429:
                wait = min(30.0, 3.0 * (2**attempt))
                logger.warning("SS rate limited, retry in %.1fs url=%s", wait, url)
                time.sleep(wait)
                continue
            logger.warning("SS request status=%s url=%s", resp.status_code, url)
            return None
        except Exception as exc:
            logger.debug("SS request error: %s", exc)
            if attempt + 1 >= retries:
                return None
            time.sleep(2.0 * (attempt + 1))
    return None


def doi_to_paper_id(doi: str) -> str:
    d = (doi or "").strip()
    if d.lower().startswith("doi:"):
        d = d[4:]
    return f"doi:{d.replace('/', '_')}"


def paper_id_to_doi(paper_id: str, doi: str | None = None) -> str | None:
    if doi:
        d = doi.strip()
        return d[4:] if d.lower().startswith("doi:") else d
    if (paper_id or "").startswith("doi:"):
        return paper_id[4:].replace("_", "/")
    return None


def resolve_ss_paper_id(
    paper_id: str,
    *,
    doi: str | None = None,
    title: str = "",
) -> str | None:
    """解析 Semantic Scholar paperId。"""
    doi_val = paper_id_to_doi(paper_id, doi)
    if doi_val:
        body = _get_json(f"{BASE_URL}/paper/DOI:{doi_val}", params={"fields": "paperId"})
        if body:
            pid = body.get("paperId")
            if pid:
                return pid

    if paper_id and not paper_id.startswith("doi:") and not paper_id.startswith("ss:"):
        m = ARXIV_RE.search(paper_id)
        arxiv_id = m.group(1) if m else paper_id
        body = _get_json(f"{BASE_URL}/paper/arXiv:{arxiv_id}", params={"fields": "paperId"})
        if body:
            pid = body.get("paperId")
            if pid:
                return pid

    if title:
        body = _get_json(
            f"{BASE_URL}/paper/search",
            params={"query": title[:200], "limit": 1, "fields": "paperId,title"},
        )
        if body:
            data = body.get("data") or []
            if data:
                return data[0].get("paperId")
    return None


def fetch_paper_citation_graph(ss_paper_id: str) -> dict[str, Any]:
    """返回 references / citations 列表（含 externalIds）。"""
    fields = (
        "references.paperId,references.title,references.year,references.externalIds,"
        "citations.paperId,citations.title,citations.year,citations.externalIds"
    )
    body = _get_json(f"{BASE_URL}/paper/{ss_paper_id}", params={"fields": fields}, timeout=45)
    if not body:
        return {"references": [], "citations": []}
    return {
        "references": body.get("references") or [],
        "citations": body.get("citations") or [],
    }


def ss_ref_to_paper_id(ref: dict[str, Any]) -> str:
    ext = ref.get("externalIds") or {}
    doi = ext.get("DOI")
    if doi:
        return doi_to_paper_id(doi)
    arxiv = ext.get("ArXiv")
    if arxiv:
        return str(arxiv)
    ss_id = ref.get("paperId")
    if ss_id:
        return f"ss:{ss_id}"
    title = (ref.get("title") or "").strip()
    if title:
        slug = re.sub(r"[\s\-\.]+", "", title.lower())[:48]
        return f"sstitle:{slug}"
    return ""
