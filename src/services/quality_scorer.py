"""综合质量分（0~100）：录用等级、引用、评审、LLM、机构权重。"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any

ACCEPTANCE_SCORES: dict[str, float] = {
    "oral": 100.0,
    "spotlight": 88.0,
    "poster": 72.0,
    "accepted": 78.0,
    "rejected": 15.0,
    "desk_rejected": 10.0,
    "withdrawn": 5.0,
    "submitted": 40.0,
    "unknown": 50.0,
}

TOP_INSTITUTION_KEYWORDS = (
    "stanford", "mit", "berkeley", "cmu", "carnegie mellon", "google", "deepmind",
    "openai", "microsoft", "meta", "facebook", "nvidia", "anthropic", "princeton",
    "harvard", "oxford", "cambridge", "eth zurich", "tsinghua", "peking", "zhejiang",
    "shanghai jiao tong", "fudan", "ucla", "caltech", "columbia", "cornell",
)


def _years_since(published_at: datetime | None) -> float:
    if not published_at:
        return 3.0
    delta = datetime.utcnow() - published_at
    return max(0.25, delta.days / 365.25)


def score_venue_rank(rank: str | None) -> float:
    return {"A": 95.0, "B": 80.0, "C": 65.0}.get((rank or "").upper(), 50.0)


def score_journal_if(journal_if: float | None) -> float:
    if journal_if is None:
        return 50.0
    return min(100.0, 40.0 + math.log10(float(journal_if) + 1) * 22.0)


def score_openalex_venue(meta: dict[str, Any], paper: Any | None = None) -> float:
    rank = meta.get("venue_rank") or (getattr(paper, "venue_rank", None) if paper else None)
    jif = meta.get("journal_if") if meta.get("journal_if") is not None else (
        getattr(paper, "journal_if", None) if paper else None
    )
    venue_type = (meta.get("venue_type") or (getattr(paper, "venue_type", None) if paper else None) or "").lower()
    vr = score_venue_rank(rank)
    ji = score_journal_if(jif)
    if venue_type == "journal":
        return vr * 0.35 + ji * 0.65
    return vr


def score_acceptance(status: str | None, source: str = "") -> float:
    key = (status or "").lower()
    if key in ACCEPTANCE_SCORES:
        return ACCEPTANCE_SCORES[key]
    if source == "arxiv":
        return 58.0
    return 50.0


def score_citation(count: int | None, published_at: datetime | None = None) -> float:
    if count is None:
        return 50.0
    c = max(0, int(count))
    if c == 0:
        return 35.0
    years = _years_since(published_at)
    velocity = c / years
    base = 30.0 + math.log10(c + 1) * 18.0
    vel_bonus = min(15.0, math.log10(velocity + 1) * 8.0)
    return min(100.0, base + vel_bonus)


def score_review(rating: float | None) -> float:
    if rating is None:
        return 50.0
    return min(100.0, max(0.0, float(rating) / 10.0 * 100.0))


def score_authors(authors: Any) -> float:
    if isinstance(authors, list):
        text = " ".join(str(a) for a in authors).lower()
    else:
        text = str(authors or "").lower()
    if not text:
        return 50.0
    hits = sum(1 for kw in TOP_INSTITUTION_KEYWORDS if kw in text)
    return min(100.0, 50.0 + hits * 12.0)


def score_llm_pair(innovation: float | None, experiment: float | None) -> float:
    if innovation is None and experiment is None:
        return 50.0
    inv = 50.0 if innovation is None else float(innovation)
    exp = 50.0 if experiment is None else float(experiment)
    return inv * 0.5 + exp * 0.5


def compute_quality_score(meta: dict[str, Any], paper: Any | None = None) -> float:
    """多维度加权质量分。"""
    source = meta.get("source") or (getattr(paper, "source", None) if paper else None) or "arxiv"
    if source == "openalex":
        acceptance = score_openalex_venue(meta, paper)
    else:
        acceptance = score_acceptance(
            meta.get("acceptance_status") or (getattr(paper, "acceptance_status", None) if paper else None),
            source=source,
        )
    published = meta.get("published_at") or (getattr(paper, "published_at", None) if paper else None)
    citation = score_citation(
        meta.get("citation_count") if meta.get("citation_count") is not None
        else (getattr(paper, "citation_count", None) if paper else None),
        published,
    )
    review = score_review(
        meta.get("review_rating") if meta.get("review_rating") is not None
        else (getattr(paper, "review_rating", None) if paper else None),
    )
    authors = meta.get("authors")
    if authors is None and paper is not None:
        authors = paper.authors_list() if hasattr(paper, "authors_list") else getattr(paper, "authors", "")
    author = score_authors(authors)

    llm_inv = meta.get("llm_innovation_score")
    llm_exp = meta.get("llm_experiment_score")
    if paper is not None:
        if llm_inv is None:
            llm_inv = getattr(paper, "llm_innovation_score", None)
        if llm_exp is None:
            llm_exp = getattr(paper, "llm_experiment_score", None)
    llm = score_llm_pair(llm_inv, llm_exp)

    total = acceptance * 0.25 + citation * 0.25 + review * 0.20 + llm * 0.20 + author * 0.10
    return round(min(100.0, max(0.0, total)), 1)


def merge_paper_quality_signals(meta: dict[str, Any], paper: Any | None) -> dict[str, Any]:
    """合并多源质量信号到 meta（arXiv 引用 + OpenReview 评审等）。"""
    merged = dict(meta)
    if paper is None:
        return merged
    for field in (
        "citation_count", "review_rating", "acceptance_status",
        "llm_innovation_score", "llm_experiment_score",
        "venue_rank", "journal_if", "jcr_quartile", "doi", "openalex_id",
    ):
        if merged.get(field) is None and getattr(paper, field, None) is not None:
            merged[field] = getattr(paper, field)
    return merged
