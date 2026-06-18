"""Literature list and detail business logic."""
from __future__ import annotations

import os

from sqlalchemy.orm import Session

from src.models.literature import LiteratureEntry
from src.models.paper import Paper

PAPERS_DIR = os.path.join("uploads", "papers")


def entry_to_dict(entry: LiteratureEntry, paper: Paper) -> dict:
    data = paper.to_dict()
    data["entry_id"] = entry.id
    data["match_score"] = entry.match_score
    data["visibility"] = entry.visibility
    data["listed_at"] = entry.created_at.strftime("%Y-%m-%d %H:%M:%S") if entry.created_at else ""
    data["source"] = paper.source or "arxiv"
    return data


def _paper_pdf_candidates(paper: Paper) -> list[str]:
    paths: list[str] = []
    if paper.pdf_path:
        paths.append(paper.pdf_path)
    safe_name = paper.arxiv_id.replace("/", "_").replace(":", "_")
    paths.append(os.path.join(PAPERS_DIR, f"{safe_name}.pdf"))
    return paths


def _safe_remove_pdf(pdf_path: str) -> bool:
    if not pdf_path:
        return False
    abs_papers = os.path.abspath(PAPERS_DIR)
    abs_path = os.path.abspath(pdf_path)
    if not abs_path.startswith(abs_papers + os.sep) and abs_path != abs_papers:
        return False
    if os.path.isfile(abs_path):
        os.remove(abs_path)
        return True
    return False


def _remove_paper_files(paper: Paper) -> int:
    removed = 0
    seen: set[str] = set()
    for path in _paper_pdf_candidates(paper):
        norm = os.path.abspath(path)
        if norm in seen:
            continue
        seen.add(norm)
        if _safe_remove_pdf(path):
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
    page: int = 1,
    page_size: int = 20,
) -> dict:
    query = (
        db.query(LiteratureEntry, Paper)
        .join(Paper, Paper.arxiv_id == LiteratureEntry.arxiv_id)
        .filter(LiteratureEntry.visibility == "public", LiteratureEntry.user_id == "")
        .order_by(Paper.published_at.desc(), LiteratureEntry.created_at.desc())
    )
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Paper.title.like(like)) | (Paper.abstract.like(like)) | (Paper.arxiv_id.like(like))
        )
    if category:
        query = query.filter(Paper.categories.like(f"%{category}%"))

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
    page: int = 1,
    page_size: int = 20,
) -> dict:
    query = (
        db.query(LiteratureEntry, Paper)
        .join(Paper, Paper.arxiv_id == LiteratureEntry.arxiv_id)
        .filter(LiteratureEntry.visibility == "private", LiteratureEntry.user_id == user_id)
        .order_by(Paper.published_at.desc(), LiteratureEntry.created_at.desc())
    )
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Paper.title.like(like)) | (Paper.abstract.like(like)) | (Paper.arxiv_id.like(like))
        )

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
    if public:
        data["match_score"] = public.match_score
        data["visibility"] = "public"
    elif private:
        data["match_score"] = private.match_score
        data["visibility"] = "private"
    return data
