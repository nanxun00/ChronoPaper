"""OpenReview 论文抓取（免费公开 API，无需 Key）。"""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any

import requests

OPENREVIEW_API = "https://api2.openreview.net/notes"
OPENREVIEW_BASE = "https://openreview.net"
RATING_RE = re.compile(r"^(\d+(?:\.\d+)?)")


def _content_value(content: dict, key: str, default: Any = "") -> Any:
    raw = content.get(key)
    if isinstance(raw, dict):
        return raw.get("value", default)
    return raw if raw is not None else default


def _parse_rating_text(text: str) -> float | None:
    if not text:
        return None
    match = RATING_RE.match(str(text).strip())
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def parse_acceptance_status(venue: str) -> str:
    v = (venue or "").lower()
    if not v:
        return "unknown"
    if "withdrawn" in v:
        return "withdrawn"
    if "desk reject" in v or "desk_reject" in v:
        return "desk_rejected"
    if "reject" in v:
        return "rejected"
    if "oral" in v:
        return "oral"
    if "spotlight" in v:
        return "spotlight"
    if "poster" in v:
        return "poster"
    if "submitted" in v:
        return "submitted"
    if any(k in v for k in ("iclr", "neurips", "icml", "acl", "emnlp", "cvpr", "eccv")):
        return "accepted"
    return venue


def parse_venue_type(venue: str) -> str:
    v = (venue or "").lower()
    if any(k in v for k in ("journal", "transactions", "nature", "science")):
        return "journal"
    if "workshop" in v:
        return "workshop"
    return "conference"


def _normalize_venues(venues: list[str] | str | None) -> list[str]:
    if not venues:
        return []
    if isinstance(venues, str):
        return [v.strip() for v in venues.replace("，", ",").split(",") if v.strip()]
    return [v.strip() for v in venues if v and v.strip()]


def resolve_openreview_pdf_url(pdf_raw: str | None, forum_id: str = "") -> str | None:
    """OpenReview 的 pdf 字段常为 /pdf/xxx.pdf 相对路径，需补全为绝对 URL。"""
    if pdf_raw:
        pdf = str(pdf_raw).strip()
        if pdf.startswith("http://") or pdf.startswith("https://"):
            return pdf
        if pdf.startswith("//"):
            return f"https:{pdf}"
        if pdf.startswith("/"):
            return f"{OPENREVIEW_BASE}{pdf}"
        return f"{OPENREVIEW_BASE}/{pdf.lstrip('/')}"
    if forum_id:
        return f"{OPENREVIEW_BASE}/pdf?id={forum_id}"
    return None


def _note_to_candidate(note: dict, invitation: str) -> dict[str, Any]:
    content = note.get("content") or {}
    forum = note.get("forum") or note.get("id") or ""
    title = str(_content_value(content, "title", "")).strip()
    abstract = str(_content_value(content, "abstract", "")).strip()
    authors_raw = _content_value(content, "authors", [])
    if isinstance(authors_raw, str):
        authors = [a.strip() for a in authors_raw.split(",") if a.strip()]
    elif isinstance(authors_raw, list):
        authors = [str(a).strip() for a in authors_raw if str(a).strip()]
    else:
        authors = []

    venue = str(_content_value(content, "venue", "")).strip()

    tcdate = note.get("tcdate") or note.get("cdate")
    published_at = None
    if tcdate:
        published_at = datetime.fromtimestamp(tcdate / 1000, tz=timezone.utc).replace(tzinfo=None)

    paper_id = f"or:{forum}"
    for key in ("arxiv", "arxiv_id", "arXiv"):
        val = _content_value(content, key, "")
        if val:
            m = re.search(r"(\d{4}\.\d{4,5})", str(val))
            if m:
                paper_id = m.group(1)
                break

    venue_display = venue or invitation.split("/")[0].replace(".cc", "").upper()

    return {
        "paper_id": paper_id,
        "source": "openreview",
        "title": title,
        "authors": authors,
        "abstract": abstract,
        "categories": [invitation.split("/")[0]],
        "published_at": published_at,
        "abs_url": f"{OPENREVIEW_BASE}/forum?id={forum}",
        "pdf_url": resolve_openreview_pdf_url(_content_value(content, "pdf", ""), forum),
        "venue": venue_display,
        "venue_display": venue_display,
        "venue_type": parse_venue_type(venue),
        "acceptance_status": parse_acceptance_status(venue),
        "openreview_id": forum,
        "openreview_invitation": invitation,
        "review_rating": None,
        "citation_count": None,
    }


def fetch_review_rating(forum_id: str) -> float | None:
    """拉取该投稿的官方评审均分（1-10）。"""
    try:
        resp = requests.get(
            OPENREVIEW_API,
            params={"forum": forum_id, "limit": 1000},
            timeout=30,
        )
        resp.raise_for_status()
        notes = resp.json().get("notes") or []
    except Exception:
        return None

    scores: list[float] = []
    for note in notes:
        invitations = note.get("invitations") or []
        if not any("Official_Review" in inv for inv in invitations):
            continue
        content = note.get("content") or {}
        for key in ("rating", "recommendation"):
            val = _content_value(content, key, "")
            score = _parse_rating_text(str(val))
            if score is not None:
                scores.append(score)
                break
    if not scores:
        return None
    return round(sum(scores) / len(scores), 2)


def fetch_openreview_candidates(
    venues: list[str] | str,
    *,
    max_per_venue: int = 300,
) -> list[dict[str, Any]]:
    """按 invitation 拉取 OpenReview 投稿列表。"""
    venue_ids = _normalize_venues(venues)
    if not venue_ids:
        raise ValueError("请至少选择一个 OpenReview 会议/venue")

    results: list[dict[str, Any]] = []
    seen_forums: set[str] = set()

    for invitation in venue_ids:
        offset = 0
        page_size = 1000
        fetched = 0
        while fetched < max_per_venue:
            limit = min(page_size, max_per_venue - fetched)
            resp = requests.get(
                OPENREVIEW_API,
                params={"invitation": invitation, "limit": limit, "offset": offset},
                timeout=60,
            )
            resp.raise_for_status()
            payload = resp.json()
            notes = payload.get("notes") or []
            if not notes:
                break
            for note in notes:
                forum = note.get("forum") or note.get("id")
                if not forum or forum in seen_forums:
                    continue
                seen_forums.add(forum)
                candidate = _note_to_candidate(note, invitation)
                if candidate["title"]:
                    results.append(candidate)
            fetched += len(notes)
            if len(notes) < limit:
                break
            offset += len(notes)
            time.sleep(0.3)

    return results
