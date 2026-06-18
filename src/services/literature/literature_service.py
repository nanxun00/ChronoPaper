"""Literature list and detail business logic."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

import requests
from sqlalchemy.orm import Session

from src.integrations.openreview.fetcher import resolve_openreview_pdf_url
from src.models.literature import LiteratureEntry, Paper
from src.services.literature.paper_parse_service import (
    is_paper_parse_running,
    read_paper_full_text,
    schedule_paper_parse,
)
from src.services.literature.paper_quality_assessment import schedule_quality_assessment
from src.services.literature.pdf_download_service import try_download_paper_pdf
from src.utils.paths import (
    ensure_paper_dir,
    ensure_papers_dir,
    paper_pdf_path,
    remove_paper_storage,
    resolve_paper_md_file,
    resolve_paper_pdf_file,
)
from src.utils.pdf_metadata import abstract_from_markdown, metadata_from_markdown

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def resolve_pipeline_status(paper: Paper, entry: LiteratureEntry) -> str:
    """文献处理流水线状态（供前端「状态」列展示）。"""
    review = entry.review_status or "approved"
    ps = (paper.parse_status or "pending").lower()
    has_pdf = resolve_paper_pdf_path(paper) is not None

    if ps in ("download_failed", "download_retry"):
        return "download_failed"
    if review == "pending" and not has_pdf:
        return "download_failed"
    if review == "pending":
        return "pending_review"
    if review == "rejected":
        return "rejected"

    if ps == "parsing":
        return "parsing"
    if ps == "indexing":
        return "indexing"
    if ps == "indexed":
        return "indexed"
    if ps == "parsed":
        return "indexing"
    if ps == "parse_failed":
        return "parse_failed"
    if ps == "index_failed":
        return "index_failed"
    return "waiting_parse"


def _is_pdf_content(content: bytes) -> bool:
    return len(content) >= 4 and content[:4] == b"%PDF"


def _title_from_filename(filename: str) -> str:
    stem = Path(filename or "upload.pdf").stem
    return stem.strip() or "未命名文档"


def _overlay_mineru_metadata(paper: Paper, data: dict) -> None:
    """本地上传论文：优先用 MinerU content.md 展示标题/作者/摘要。"""
    if paper.source != "upload":
        if not (data.get("abstract") or "").strip():
            md_path = resolve_paper_md_file(paper.arxiv_id)
            if md_path:
                try:
                    data["abstract"] = abstract_from_markdown(Path(md_path).read_text(encoding="utf-8"))
                except OSError:
                    pass
        return

    md_path = resolve_paper_md_file(paper.arxiv_id)
    if not md_path:
        data["abstract"] = (paper.abstract or "").strip()
        return

    try:
        meta = metadata_from_markdown(Path(md_path).read_text(encoding="utf-8"))
    except OSError:
        data["abstract"] = (paper.abstract or "").strip()
        return

    if meta.get("title"):
        data["title"] = meta["title"]
    if meta.get("authors"):
        data["authors"] = meta["authors"]
    if meta.get("abstract"):
        data["abstract"] = meta["abstract"]
    elif (paper.abstract or "").strip():
        data["abstract"] = paper.abstract.strip()


def upload_paper_pdf(
    db: Session,
    *,
    user_id: str,
    visibility: str,
    filename: str,
    content: bytes,
    title: str | None = None,
) -> dict:
    """保存用户上传的 PDF，写入论文与文献条目并触发 MinerU 解析。"""
    if visibility not in ("public", "private"):
        raise ValueError("visibility 须为 public 或 private")
    if visibility == "private" and not user_id:
        raise ValueError("私有文献须登录用户上传")

    if not content:
        raise ValueError("文件为空")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("PDF 超过 50MB 大小限制")
    if not _is_pdf_content(content):
        raise ValueError("仅支持 PDF 文件")

    paper_id = f"upload-{uuid.uuid4().hex[:16]}"
    resolved_title = (title or "").strip() or _title_from_filename(filename)

    ensure_papers_dir()
    ensure_paper_dir(paper_id)
    dest_path = str(paper_pdf_path(paper_id).resolve())
    with open(dest_path, "wb") as f:
        f.write(content)

    paper = Paper(
        arxiv_id=paper_id,
        source="upload",
        title=resolved_title,
        authors=json.dumps([]),
        abstract="",
        categories=json.dumps([]),
        published_at=datetime.utcnow(),
        pdf_path=dest_path,
        pdf_url=None,
        parse_status="downloaded",
    )
    entry = LiteratureEntry(
        arxiv_id=paper_id,
        user_id=user_id if visibility == "private" else "",
        visibility=visibility,
        pool_type="upload",
        review_status="approved",
    )
    try:
        db.add(paper)
        db.commit()
        db.refresh(paper)
        db.add(entry)
        db.commit()
        db.refresh(entry)
    except Exception:
        db.rollback()
        remove_paper_storage(paper_id, dest_path)
        raise
    schedule_paper_parse([paper_id])
    return entry_to_dict(entry, paper)


def resolve_paper_pdf_path(paper: Paper) -> str | None:
    return resolve_paper_pdf_file(paper.arxiv_id, paper.pdf_path)


def _pdf_url_for_paper(paper: Paper) -> str | None:
    url = paper.pdf_url
    if paper.source == "openreview" or (url and str(url).strip().startswith("/")):
        return resolve_openreview_pdf_url(url, paper.openreview_id or "")
    return url or None


def ensure_paper_pdf_downloaded(db: Session, paper: Paper, *, trigger_parse: bool = False) -> str | None:
    """本地无文件时，按 pdf_url 拉取并缓存到 uploads/papers/{id}/paper.pdf。"""
    existing = resolve_paper_pdf_path(paper)
    if existing:
        if trigger_parse and paper.parse_status == "downloaded":
            schedule_paper_parse([paper.arxiv_id])
        return existing

    pdf_url = _pdf_url_for_paper(paper)
    if not pdf_url:
        return None

    ok, _msg = try_download_paper_pdf(db, paper, pdf_url=pdf_url)
    if ok:
        if trigger_parse:
            schedule_paper_parse([paper.arxiv_id])
        return resolve_paper_pdf_path(paper)
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
    data["review_status"] = entry.review_status or "approved"
    data["pipeline_status"] = resolve_pipeline_status(paper, entry)
    data["listed_at"] = entry.created_at.strftime("%Y-%m-%d") if entry.created_at else ""
    data["source"] = paper.source or "arxiv"
    _overlay_mineru_metadata(paper, data)
    data["has_pdf"] = resolve_paper_pdf_path(paper) is not None
    data["has_md"] = resolve_paper_md_file(paper.arxiv_id) is not None
    data["can_fetch_pdf"] = data["has_pdf"] or bool(_pdf_url_for_paper(paper))
    return data


def _apply_list_filters(
    query,
    *,
    source: str | None = None,
    min_semantic: float | None = None,
    min_quality: float | None = None,
    review_status: str | None = None,
):
    from sqlalchemy import and_, func, or_

    if source in ("arxiv", "openreview", "openalex", "upload"):
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
    if review_status in ("pending", "approved", "rejected"):
        query = query.filter(LiteratureEntry.review_status == review_status)
    return query


def _remove_paper_files(paper: Paper) -> int:
    return remove_paper_storage(paper.arxiv_id, paper.pdf_path)


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


def _unique_paper_ids(arxiv_ids: list[str]) -> list[str]:
    unique_ids: list[str] = []
    seen: set[str] = set()
    for paper_id in arxiv_ids:
        pid = (paper_id or "").strip()
        if not pid or pid in seen:
            continue
        seen.add(pid)
        unique_ids.append(pid)
    return unique_ids


def _start_post_approval_processing(db: Session, paper_ids: list[str]) -> list[str]:
    """通过后：确保 PDF 就绪并排队 MinerU 解析与 LLM 质量评估。"""
    queued: list[str] = []
    for paper_id in paper_ids:
        paper = db.query(Paper).filter(Paper.arxiv_id == paper_id).first()
        if not paper:
            continue
        pdf_path = resolve_paper_pdf_path(paper)
        if not pdf_path:
            pdf_path = ensure_paper_pdf_downloaded(db, paper, trigger_parse=False)
        if pdf_path and paper.parse_status in ("downloaded", "parse_failed", "pending"):
            schedule_paper_parse([paper_id])
            queued.append(paper_id)
        elif paper.parse_status == "parsed":
            from src.workers.index_tasks import index_paper_chunks_task

            index_paper_chunks_task.delay(paper_id)
            queued.append(paper_id)
    if queued:
        schedule_quality_assessment(queued)
    return queued


def approve_literature_entries(
    db: Session,
    user_id: str,
    *,
    arxiv_ids: list[str],
    visibility: str,
) -> dict:
    unique_ids = _unique_paper_ids(arxiv_ids)
    approved: list[str] = []
    already_approved: list[str] = []
    not_found: list[str] = []

    for paper_id in unique_ids:
        entry = _entry_query(db, paper_id, visibility, user_id).first()
        if not entry:
            not_found.append(paper_id)
            continue
        if entry.review_status == "approved":
            already_approved.append(paper_id)
            continue
        entry.review_status = "approved"
        db.add(entry)
        approved.append(paper_id)

    db.commit()
    queued = _start_post_approval_processing(db, approved)
    return {
        "approved": len(approved),
        "already_approved": already_approved,
        "queued_parse": len(queued),
        "not_found": not_found,
    }


def reject_literature_entries(
    db: Session,
    user_id: str,
    *,
    arxiv_ids: list[str],
    visibility: str,
) -> dict:
    unique_ids = _unique_paper_ids(arxiv_ids)
    rejected = 0
    not_found: list[str] = []

    for paper_id in unique_ids:
        entry = _entry_query(db, paper_id, visibility, user_id).first()
        if not entry:
            not_found.append(paper_id)
            continue
        if entry.review_status == "rejected":
            continue
        entry.review_status = "rejected"
        db.add(entry)
        rejected += 1

    db.commit()
    return {"rejected": rejected, "not_found": not_found}


def retry_literature_parse(
    db: Session,
    user_id: str,
    *,
    arxiv_ids: list[str],
    visibility: str,
) -> dict:
    """对待解析或解析失败的文献排队 MinerU 解析。"""
    unique_ids = _unique_paper_ids(arxiv_ids)
    queued: list[str] = []
    skipped: list[str] = []
    no_pdf: list[str] = []
    not_found: list[str] = []

    for paper_id in unique_ids:
        entry = _entry_query(db, paper_id, visibility, user_id).first()
        if not entry:
            not_found.append(paper_id)
            continue

        paper = db.query(Paper).filter(Paper.arxiv_id == paper_id).first()
        if not paper:
            not_found.append(paper_id)
            continue

        status = (paper.parse_status or "pending").lower()
        if status == "parsing":
            if is_paper_parse_running(paper_id):
                skipped.append(paper_id)
                continue
        elif status not in ("pending", "downloaded", "parse_failed"):
            skipped.append(paper_id)
            continue

        pdf_path = resolve_paper_pdf_path(paper)
        if not pdf_path:
            pdf_path = ensure_paper_pdf_downloaded(db, paper, trigger_parse=False)
        if not pdf_path:
            no_pdf.append(paper_id)
            continue

        queued.append(paper_id)

    if queued:
        schedule_paper_parse(queued)

    return {
        "queued": len(queued),
        "queued_ids": queued,
        "skipped": skipped,
        "no_pdf": no_pdf,
        "not_found": not_found,
    }


def fetch_literature_pdf(
    db: Session,
    user_id: str,
    *,
    arxiv_ids: list[str],
    visibility: str,
) -> dict:
    """重新拉取论文 PDF（OpenAlex 文献会刷新直链）。"""
    from src.integrations.openalex.fetcher import resolve_openalex_work_pdf_url

    unique_ids = _unique_paper_ids(arxiv_ids)
    fetched: list[str] = []
    failed: list[str] = []
    no_url: list[str] = []
    not_found: list[str] = []

    for paper_id in unique_ids:
        entry = _entry_query(db, paper_id, visibility, user_id).first()
        if not entry:
            not_found.append(paper_id)
            continue

        paper = db.query(Paper).filter(Paper.arxiv_id == paper_id).first()
        if not paper:
            not_found.append(paper_id)
            continue

        pdf_url = None
        if paper.source == "openalex":
            pdf_url = resolve_openalex_work_pdf_url(doi=paper.doi, openalex_id=paper.openalex_id)
            if pdf_url:
                paper.pdf_url = pdf_url
                db.add(paper)
                db.flush()

        if not pdf_url and not _pdf_url_for_paper(paper):
            no_url.append(paper_id)
            continue

        ok, _msg = try_download_paper_pdf(db, paper, pdf_url=pdf_url, force=True)
        if ok:
            fetched.append(paper_id)
        else:
            failed.append(paper_id)

    db.commit()
    return {
        "fetched": len(fetched),
        "fetched_ids": fetched,
        "failed": failed,
        "no_url": no_url,
        "not_found": not_found,
    }


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
    review_status: str | None = None,
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
    query = _apply_list_filters(
        query,
        source=source,
        min_semantic=min_semantic,
        min_quality=min_quality,
        review_status=review_status,
    )

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
    review_status: str | None = None,
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
    query = _apply_list_filters(
        query,
        source=source,
        min_semantic=min_semantic,
        min_quality=min_quality,
        review_status=review_status,
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


def enrich_cited_literature(
    db: Session,
    cited: list[dict] | None,
    *,
    user_id: str = "",
) -> list[dict]:
    """补全引用文献字段，并加载 MinerU content.md 全文供对话注入。"""
    if not cited:
        return []
    enriched: list[dict] = []
    for item in cited:
        data = dict(item)
        paper_id = data.get("arxiv_id") or data.get("paper_id")
        if not paper_id:
            enriched.append(data)
            continue

        if user_id:
            detail = get_paper_detail(db, paper_id, user_id)
            if not detail:
                enriched.append(data)
                continue
            for key in (
                "title",
                "abstract",
                "authors",
                "arxiv_id",
                "source",
                "categories",
                "published_at",
                "venue",
            ):
                if detail.get(key) is not None:
                    data[key] = detail[key]
        else:
            paper = db.query(Paper).filter(Paper.arxiv_id == paper_id).first()
            if not paper:
                enriched.append(data)
                continue
            for key in (
                "title",
                "abstract",
                "authors",
                "arxiv_id",
                "source",
                "categories",
                "published_at",
                "venue",
            ):
                current = data.get(key)
                if current is None or (isinstance(current, str) and not current.strip()):
                    val = paper.to_dict().get(key)
                    if val is not None:
                        data[key] = val
            _overlay_mineru_metadata(paper, data)

        paper = db.query(Paper).filter(Paper.arxiv_id == paper_id).first()
        if paper:
            try:
                data["full_text"] = read_paper_full_text(paper_id, paper.pdf_path)
            except FileNotFoundError:
                data["full_text"] = ""
            except Exception:
                data["full_text"] = ""
        enriched.append(data)
    return enriched


def build_cited_literature_context(cited: list[dict]) -> str:
    """将引用文献拼成模型上下文（优先 content.md 全文）。"""
    if not cited:
        return ""
    parts = []
    for i, item in enumerate(cited, 1):
        title = item.get("title") or "未知标题"
        paper_id = item.get("arxiv_id") or item.get("paper_id") or ""
        authors = item.get("authors") or ""
        full_text = (item.get("full_text") or "").strip()
        if full_text:
            parts.append(
                f"[引用文献 {i}] {title}\n"
                f"ID: {paper_id}\n"
                f"作者: {authors}\n"
                f"正文（MinerU Markdown 全文）:\n{full_text}"
            )
        else:
            abstract = (item.get("abstract") or "")[:3000]
            parts.append(
                f"[引用文献 {i}] {title}\n"
                f"ID: {paper_id}\n"
                f"作者: {authors}\n"
                f"摘要: {abstract}\n"
                f"（正文尚未解析，仅提供摘要）"
            )
    return (
        "以下为用户明确引用的文献，请结合正文回答，不要声称未看到文献：\n\n" + "\n\n".join(parts)
    )


def prepare_cited_literature_for_chat(
    db: Session,
    cited: list[dict] | None,
    *,
    user_id: str = "",
) -> tuple[list[dict], str]:
    """补全引用文献并生成上下文；full_text 不返回给前端 meta。"""
    enriched = enrich_cited_literature(db, cited, user_id=user_id)
    context = build_cited_literature_context(enriched)
    for item in enriched:
        item.pop("full_text", None)
    return enriched, context


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
    _overlay_mineru_metadata(paper, data)
    data["has_pdf"] = resolve_paper_pdf_path(paper) is not None
    data["has_md"] = resolve_paper_md_file(paper.arxiv_id) is not None
    data["can_fetch_pdf"] = data["has_pdf"] or bool(_pdf_url_for_paper(paper))
    if public:
        data["match_score"] = public.match_score
        data["visibility"] = "public"
    elif private:
        data["match_score"] = private.match_score
        data["visibility"] = "private"
    return data
