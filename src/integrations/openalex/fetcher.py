"""OpenAlex Works API 抓取（免费额度，支持会议/期刊/引用/CCF 过滤）。"""
from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Any

import requests

from src.integrations.openalex.ccf_venues import match_ccf_rank, venue_matches_ccf_ranks
from src.settings import get_settings

OPENALEX_API = "https://api.openalex.org/works"
ARXIV_ID_RE = re.compile(r"(\d{4}\.\d{4,5})")


def _normalize_list(value: list[str] | str | None) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [v.strip() for v in value.replace("，", ",").split(",") if v.strip()]
    return [str(v).strip() for v in value if str(v).strip()]


def _api_params(extra: dict | None = None) -> dict[str, str]:
    settings = get_settings()
    params: dict[str, str] = {}
    if settings.openalex_api_key:
        params["api_key"] = settings.openalex_api_key
    if settings.openalex_mailto:
        params["mailto"] = settings.openalex_mailto
    if extra:
        params.update(extra)
    return params


def reconstruct_abstract(inverted_index: dict | None) -> str:
    if not inverted_index:
        return ""
    pairs: list[tuple[int, str]] = []
    for word, positions in inverted_index.items():
        for pos in positions:
            pairs.append((int(pos), word))
    pairs.sort(key=lambda x: x[0])
    return " ".join(w for _, w in pairs)


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d")
    except ValueError:
        return None


def _paper_id_from_work(work: dict) -> str:
    ids = work.get("ids") or {}
    arxiv_raw = ids.get("arxiv") or ""
    m = ARXIV_ID_RE.search(str(arxiv_raw))
    if m:
        return m.group(1)
    doi = ids.get("doi") or work.get("doi") or ""
    if doi:
        safe = str(doi).replace("https://doi.org/", "").replace("/", "_")
        return f"doi:{safe[:100]}"
    oa_id = str(work.get("id") or "").rstrip("/").split("/")[-1]
    return f"oa:{oa_id}"


def _pdf_url_from_work(work: dict) -> str | None:
    oa = work.get("open_access") or {}
    if oa.get("oa_url"):
        return oa["oa_url"]
    primary = work.get("primary_location") or {}
    if primary.get("pdf_url"):
        return primary["pdf_url"]
    for loc in work.get("locations") or []:
        if loc.get("pdf_url"):
            return loc["pdf_url"]
    doi = work.get("doi")
    if doi:
        return f"https://doi.org/{str(doi).replace('https://doi.org/', '')}"
    return None


def _journal_metrics_from_source(source: dict | None) -> tuple[float | None, str | None]:
    """从 source 提取影响因子代理与分区（OpenAlex 提供 2yr citedness 等）。"""
    if not source:
        return None, None
    stats = source.get("summary_stats") or {}
    citedness = stats.get("2yr_mean_citedness")
    journal_if = float(citedness) if citedness is not None else None
    # OpenAlex 无官方 JCR 分区，按 2yr citedness 粗映射
    quartile = None
    if journal_if is not None:
        if journal_if >= 10:
            quartile = "Q1"
        elif journal_if >= 5:
            quartile = "Q2"
        elif journal_if >= 2:
            quartile = "Q3"
        else:
            quartile = "Q4"
    return journal_if, quartile


def _work_to_candidate(work: dict) -> dict[str, Any]:
    primary = work.get("primary_location") or {}
    source = primary.get("source") or {}
    venue_name = (source.get("display_name") or "").strip()
    source_type = (source.get("type") or "").lower()
    venue_type = "journal" if source_type == "journal" else "conference" if source_type == "conference" else source_type

    journal_if, jcr_quartile = _journal_metrics_from_source(source)
    venue_rank = match_ccf_rank(venue_name)
    oa_short = str(work.get("id") or "").rstrip("/").split("/")[-1]

    authorships = work.get("authorships") or []
    authors = []
    for a in authorships:
        name = ((a.get("author") or {}).get("display_name") or "").strip()
        if name:
            authors.append(name)

    topics = [t.get("display_name", "") for t in (work.get("topics") or [])[:5] if t.get("display_name")]

    return {
        "paper_id": _paper_id_from_work(work),
        "source": "openalex",
        "pool_type": "openalex",
        "title": (work.get("display_name") or work.get("title") or "").strip(),
        "authors": authors,
        "abstract": reconstruct_abstract(work.get("abstract_inverted_index")),
        "categories": topics,
        "published_at": _parse_date(work.get("publication_date")),
        "abs_url": work.get("id"),
        "pdf_url": _pdf_url_from_work(work),
        "venue": venue_name,
        "venue_type": venue_type,
        "venue_rank": venue_rank,
        "journal_if": journal_if,
        "jcr_quartile": jcr_quartile,
        "citation_count": work.get("cited_by_count"),
        "acceptance_status": "accepted",
        "openalex_id": oa_short,
        "doi": (work.get("doi") or "").replace("https://doi.org/", "") or None,
        "open_access": bool((work.get("open_access") or {}).get("is_oa")),
    }


def _build_filters(
    *,
    venue_types: list[str],
    year_from: int | None,
    year_to: int | None,
) -> str:
    parts: list[str] = ["type:article", "type:!paratext"]
    if venue_types:
        types = "|".join(sorted(set(venue_types)))
        parts.append(f"primary_location.source.type:{types}")
    if year_from and year_to:
        parts.append(f"publication_year:{year_from}-{year_to}")
    elif year_from:
        parts.append(f"publication_year:>{year_from - 1}")
    elif year_to:
        parts.append(f"publication_year:<{year_to + 1}")
    return ",".join(parts)


def fetch_openalex_candidates(
    search_query: str,
    *,
    venue_types: list[str] | str | None = None,
    ccf_ranks: list[str] | str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    venue_names: list[str] | str | None = None,
    max_results: int = 300,
) -> list[dict[str, Any]]:
    """按关键词检索 OpenAlex，并按 CCF/venue 类型过滤。"""
    query = (search_query or "").strip()
    if not query:
        raise ValueError("OpenAlex 检索需要兴趣描述或关键词")

    vtypes = _normalize_list(venue_types) or ["conference", "journal"]
    ranks = {r.upper() for r in _normalize_list(ccf_ranks) or ["A", "B", "C"]}
    vnames = [n.lower() for n in _normalize_list(venue_names)]

    filters = _build_filters(venue_types=vtypes, year_from=year_from, year_to=year_to)
    per_page = min(200, max_results)
    cursor = "*"
    results: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    while len(results) < max_results and cursor:
        params = _api_params({
            "search": query,
            "filter": filters,
            "per_page": str(per_page),
            "cursor": cursor,
            "sort": "cited_by_count:desc",
        })
        resp = requests.get(OPENALEX_API, params=params, timeout=60)
        resp.raise_for_status()
        payload = resp.json()
        works = payload.get("results") or []

        for work in works:
            candidate = _work_to_candidate(work)
            pid = candidate["paper_id"]
            if pid in seen_ids:
                continue
            venue = candidate.get("venue") or ""
            if vnames and not any(n in venue.lower() for n in vnames):
                continue
            if ranks and not venue_matches_ccf_ranks(venue, ranks):
                continue
            seen_ids.add(pid)
            results.append(candidate)
            if len(results) >= max_results:
                break

        cursor = payload.get("meta", {}).get("next_cursor")
        if not works:
            break
        time.sleep(0.15)

    return results
