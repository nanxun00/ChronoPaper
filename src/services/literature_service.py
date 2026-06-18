"""Literature list and detail business logic."""
from __future__ import annotations

import os

import requests
from sqlalchemy.orm import Session

from src.integrations.openreview.fetcher import resolve_openreview_pdf_url
from src.models.literature import LiteratureEntry
from src.models.paper import Paper
from src.utils.paths import (
    PAPERS_DIR,
    ensure_papers_dir,
    paper_pdf_path,
    resolve_existing_file,
)


def resolve_paper_pdf_path(paper: Paper) -> str | None:
    for path in _paper_pdf_candidates(paper):
        resolved = resolve_existing_file(path)
        if resolved:
            return resolved
    return None


def _pdf_url_for_paper(paper: Paper) -> str | None:
    url = paper.pdf_url
    if paper.source == "openreview" or (url and str(url).strip().startswith("/")):
        return resolve_openreview_pdf_url(url, paper.openreview_id or "")
    return url or None


def ensure_paper_pdf_downloaded(db: Session, paper: Paper) -> str | None:
    """本地无文件时，按 pdf_url 拉取并缓存到 uploads/papers/。"""
    existing = resolve_paper_pdf_path(paper)
    if existing:
        return existing

    pdf_url = _pdf_url_for_paper(paper)
    if not pdf_url:
        return None

    dest_path = str(paper_pdf_path(paper.arxiv_id))
    ensure_papers_dir()

    try:
        with requests.get(pdf_url, stream=True, timeout=(10, 120)) as resp:
            resp.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
        paper.pdf_path = dest_path
        paper.pdf_url = pdf_url
        paper.parse_status = "downloaded"
        db.add(paper)
        db.commit()
        return dest_path
    except Exception:
        paper.parse_status = "download_failed"
        if pdf_url != paper.pdf_url:
            paper.pdf_url = pdf_url
        db.add(paper)
        db.commit()
        return None


def _can_access_paper(db: Session, arxiv_id: str, user_id: str) -> bool:
    return get_paper_detail(db, arxiv_id, user_id) is not None


def resolve_accessible_paper_pdf(db: Session, arxiv_id: str, user_id: str) -> str | None:
    if not _can_access_paper(db, arxiv_id, user_id):
        return None
    paper = db.query(Paper).filter(Paper.arxiv_id == arxiv_id).first()
    if not paper:
        return None
    path = resolve_paper_pdf_path(paper)
    if path:
        return path
    return ensure_paper_pdf_downloaded(db, paper)


def entry_to_dict(entry: LiteratureEntry, paper: Paper) -> dict:
    data = paper.to_dict()
    sem = entry.semantic_score if entry.semantic_score is not None else entry.match_score
    qual = entry.quality_score if entry.quality_score is not None else paper.quality_score
    data["entry_id"] = entry.id
    data["semantic_score"] = sem
    data["quality_score"] = qual
    data["match_score"] = sem
    data["pool_type"] = entry.pool_type or paper.source or "arxiv"
    data["visibility"] = entry.visibility
    data["listed_at"] = entry.created_at.strftime("%Y-%m-%d") if entry.created_at else ""
    data["source"] = paper.source or "arxiv"
    data["has_pdf"] = resolve_paper_pdf_path(paper) is not None
    data["can_fetch_pdf"] = data["has_pdf"] or bool(_pdf_url_for_paper(paper))
    return data


def _apply_list_filters(
    query,
    *,
    source: str | None = None,
    min_semantic: float | None = None,
    min_quality: float | None = None,
):
    from sqlalchemy import and_, func, or_

    if source in ("arxiv", "openreview", "openalex"):
        query = query.filter(
            or_(
                LiteratureEntry.pool_type == source,
                and_(LiteratureEntry.pool_type.is_(None), Paper.source == source),
            )
        )
    if min_semantic is not None:
        query = query.filter(
            func.coalesce(LiteratureEntry.semantic_score, LiteratureEntry.match_score, 0) >= min_semantic
        )
    if min_quality is not None:
        query = query.filter(
            func.coalesce(LiteratureEntry.quality_score, Paper.quality_score, 0) >= min_quality
        )
    return query


def _paper_pdf_candidates(paper: Paper) -> list[str]:
    paths: list[str] = []
    if paper.pdf_path:
        paths.append(paper.pdf_path)
    paths.append(str(paper_pdf_path(paper.arxiv_id)))
    unique: list[str] = []
    seen: set[str] = set()
    for path in paths:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


def _safe_remove_pdf(pdf_path: str) -> bool:
    if not pdf_path:
        return False
    abs_papers = str(PAPERS_DIR.resolve())
    resolved = resolve_existing_file(pdf_path)
    if not resolved:
        return False
    abs_path = os.path.abspath(resolved)
    if not abs_path.startswith(abs_papers + os.sep) and abs_path != abs_papers:
        return False
    os.remove(abs_path)
    return True


def _remove_paper_files(paper: Paper) -> int:
    removed = 0
    seen: set[str] = set()
    for path in _paper_pdf_candidates(paper):
        resolved = resolve_existing_file(path)
        if not resolved or resolved in seen:
            continue
        seen.add(resolved)
        if _safe_remove_pdf(resolved):
            removed += 1
    return removed


def _entry_query(db: Session, arxiv_id: str, visibility: str, user_id: str):
    q = db.query(LiteratureEntry).filter(
        LiteratureEntry.arxiv_id == arxiv_id,
        LiteratureEntry.visibility == visibility,
    )
    if visibility == "private":
        q = q.filter(LiteratureEntry.user_id == user_id)
    else:
        q = q.filter(LiteratureEntry.user_id == "")
    return q


def delete_literature_entries(
    db: Session,
    user_id: str,
    *,
    arxiv_ids: list[str],
    visibility: str,
) -> dict:
    deleted = 0
    files_removed = 0
    papers_removed = 0
    not_found: list[str] = []

    unique_ids = []
    seen: set[str] = set()
    for paper_id in arxiv_ids:
        pid = (paper_id or "").strip()
        if not pid or pid in seen:
            continue
        seen.add(pid)
        unique_ids.append(pid)

    for paper_id in unique_ids:
        entry = _entry_query(db, paper_id, visibility, user_id).first()
        if not entry:
            not_found.append(paper_id)
            continue

        db.delete(entry)
        db.flush()
        deleted += 1

        remaining = db.query(LiteratureEntry).filter(LiteratureEntry.arxiv_id == paper_id).count()
        if remaining > 0:
            continue

        paper = db.query(Paper).filter(Paper.arxiv_id == paper_id).first()
        if not paper:
            continue

        files_removed += _remove_paper_files(paper)
        db.delete(paper)
        papers_removed += 1

    db.commit()
    return {
        "deleted": deleted,
        "files_removed": files_removed,
        "papers_removed": papers_removed,
        "not_found": not_found,
    }


def list_public_papers(
    db: Session,
    *,
    q: str | None = None,
    category: str | None = None,
    source: str | None = None,
    min_semantic: float | None = None,
    min_quality: float | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    query = (
        db.query(LiteratureEntry, Paper)
        .join(Paper, Paper.arxiv_id == LiteratureEntry.arxiv_id)
        .filter(LiteratureEntry.visibility == "public", LiteratureEntry.user_id == "")
        .order_by(LiteratureEntry.created_at.desc(), Paper.published_at.desc())
    )
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Paper.title.like(like)) | (Paper.abstract.like(like)) | (Paper.arxiv_id.like(like))
        )
    if category:
        query = query.filter(Paper.categories.like(f"%{category}%"))
    query = _apply_list_filters(query, source=source, min_semantic=min_semantic, min_quality=min_quality)

    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "papers": [entry_to_dict(entry, paper) for entry, paper in rows],
    }


def list_private_papers(
    db: Session,
    user_id: str,
    *,
    q: str | None = None,
    source: str | None = None,
    min_semantic: float | None = None,
    min_quality: float | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    query = (
        db.query(LiteratureEntry, Paper)
        .join(Paper, Paper.arxiv_id == LiteratureEntry.arxiv_id)
        .filter(LiteratureEntry.visibility == "private", LiteratureEntry.user_id == user_id)
        .order_by(LiteratureEntry.created_at.desc(), Paper.published_at.desc())
    )
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Paper.title.like(like)) | (Paper.abstract.like(like)) | (Paper.arxiv_id.like(like))
        )
    query = _apply_list_filters(query, source=source, min_semantic=min_semantic, min_quality=min_quality)

    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    papers = []
    for entry, paper in rows:
        item = entry_to_dict(entry, paper)
        item["status"] = paper.parse_status
        item["filename"] = f"{paper.arxiv_id}.pdf"
        item["created_at"] = item["listed_at"]
        papers.append(item)
    return {"total": total, "page": page, "page_size": page_size, "papers": papers}


def get_paper_detail(db: Session, arxiv_id: str, user_id: str) -> dict | None:
    paper = db.query(Paper).filter(Paper.arxiv_id == arxiv_id).first()
    if not paper:
        return None

    public = (
        db.query(LiteratureEntry)
        .filter(
            LiteratureEntry.arxiv_id == arxiv_id,
            LiteratureEntry.visibility == "public",
            LiteratureEntry.user_id == "",
        )
        .first()
    )
    private = (
        db.query(LiteratureEntry)
        .filter(
            LiteratureEntry.arxiv_id == arxiv_id,
            LiteratureEntry.visibility == "private",
            LiteratureEntry.user_id == user_id,
        )
        .first()
    )
    if not public and not private:
        return None

    data = paper.to_dict()
    data["has_pdf"] = resolve_paper_pdf_path(paper) is not None
    data["can_fetch_pdf"] = data["has_pdf"] or bool(_pdf_url_for_paper(paper))
    if public:
        data["match_score"] = public.match_score
        data["visibility"] = "public"
    elif private:
        data["match_score"] = private.match_score
        data["visibility"] = "private"
    return data
