"""Literature list and detail business logic."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.models.literature import LiteratureEntry
from src.models.paper import Paper


def entry_to_dict(entry: LiteratureEntry, paper: Paper) -> dict:
    data = paper.to_dict()
    data["match_score"] = entry.match_score
    data["visibility"] = entry.visibility
    data["listed_at"] = entry.created_at.strftime("%Y-%m-%d %H:%M:%S") if entry.created_at else ""
    data["source"] = paper.source or "arxiv"
    return data


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
