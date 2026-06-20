"""分块双写：MySQL text_chunks + Milvus paper_text_chunk。"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from src.models.rag import TextChunk
from src.services.rag.knowledgebase import KnowledgeBase
from src.utils.logging_config import setup_logger

logger = setup_logger("IndexingPipeline")


def upsert_text_chunks_mysql(session: Session, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        chunk_id = row["chunk_id"]
        existing = session.query(TextChunk).filter(TextChunk.chunk_id == chunk_id).first()
        if existing:
            for key in (
                "chunk_text",
                "page_num",
                "bbox",
                "section_type",
                "block_type",
                "year",
                "ccf_rank",
                "keywords",
                "task_domain",
                "paper_id",
                "doc_id",
                "resource_type",
                "owner_user_id",
                "kb_id",
                "text_hash",
            ):
                setattr(existing, key, row.get(key))
            existing.is_deleted = 0
        else:
            session.add(
                TextChunk(
                    chunk_id=chunk_id,
                    chunk_text=row.get("chunk_text") or "",
                    page_num=row.get("page_num"),
                    bbox=row.get("bbox"),
                    section_type=row.get("section_type"),
                    block_type=row.get("block_type"),
                    year=row.get("year"),
                    ccf_rank=row.get("ccf_rank"),
                    keywords=row.get("keywords") if isinstance(row.get("keywords"), str) else json.dumps(row.get("keywords") or [], ensure_ascii=False),
                    task_domain=row.get("task_domain"),
                    paper_id=row.get("paper_id"),
                    doc_id=row.get("doc_id"),
                    resource_type=row.get("resource_type") or "public",
                    owner_user_id=str(row.get("owner_user_id") or "0"),
                    kb_id=row["kb_id"],
                    text_hash=row.get("text_hash") or "",
                    is_deleted=0,
                )
            )
    session.commit()


def index_chunk_rows(
    session: Session,
    kb: KnowledgeBase,
    rows: list[dict[str, Any]],
) -> int:
    if not rows:
        return 0
    # 先写 Milvus（含 Embedding）；失败则不 commit MySQL，避免「有分块无向量」
    kb.upsert_vectors(rows)
    upsert_text_chunks_mysql(session, rows)
    return len(rows)


def soft_delete_kb_chunks(session: Session, kb: KnowledgeBase, kb_id: str) -> None:
    rows = (
        session.query(TextChunk.chunk_id)
        .filter(TextChunk.kb_id == kb_id, TextChunk.is_deleted == 0)
        .all()
    )
    chunk_ids = [r[0] for r in rows]
    session.query(TextChunk).filter(TextChunk.kb_id == kb_id).update({"is_deleted": 1})
    session.commit()
    kb.delete_by_kb_id(kb_id)


def soft_delete_paper_chunks(
    session: Session,
    kb: KnowledgeBase,
    *,
    kb_id: str,
    paper_id: str,
) -> int:
    """软删除指定论文在知识库中的分块，并清理 Milvus 向量。"""
    rows = (
        session.query(TextChunk.chunk_id)
        .filter(
            TextChunk.kb_id == kb_id,
            TextChunk.paper_id == paper_id,
            TextChunk.is_deleted == 0,
        )
        .all()
    )
    chunk_ids = [r[0] for r in rows]
    if not chunk_ids:
        return 0
    session.query(TextChunk).filter(
        TextChunk.kb_id == kb_id,
        TextChunk.paper_id == paper_id,
    ).update({"is_deleted": 1})
    session.commit()
    kb.delete_by_chunk_ids(chunk_ids)
    logger.info("soft deleted paper chunks paper=%s kb=%s count=%s", paper_id, kb_id, len(chunk_ids))
    return len(chunk_ids)


def fetch_chunks_by_ids(session: Session, chunk_ids: list[str]) -> list[TextChunk]:
    if not chunk_ids:
        return []
    return session.query(TextChunk).filter(TextChunk.chunk_id.in_(chunk_ids), TextChunk.is_deleted == 0).all()
