"""Semantic Scholar 引用网络同步 → Neo4j CITE 关系。"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from src.integrations.semantic_scholar import (
    fetch_paper_citation_graph,
    resolve_ss_paper_id,
    ss_ref_to_paper_id,
)
from src.models.literature import Paper
from src.services.graph.neo4j_store import PaperGraphStore
from src.settings import get_settings
from src.utils.logging_config import setup_logger

logger = setup_logger("GraphCiteSync")


def _match_paper_in_mysql(session: Session, paper_id: str) -> Paper | None:
    row = session.query(Paper).filter(Paper.arxiv_id == paper_id).first()
    if row:
        return row
    if paper_id.startswith("doi:"):
        doi = paper_id[4:].replace("_", "/")
        return session.query(Paper).filter(Paper.doi == doi).first()
    return None


def _resolve_target(
    session: Session,
    ref: dict[str, Any],
    kb_id: str,
    store: PaperGraphStore,
    *,
    owner_user_id: str,
    is_private: bool,
) -> str | None:
    target_id = ss_ref_to_paper_id(ref)
    if not target_id:
        return None

    mysql_paper = _match_paper_in_mysql(session, target_id)
    title = (ref.get("title") or (mysql_paper.title if mysql_paper else ""))[:512]
    year = ref.get("year") or (
        mysql_paper.published_at.year if mysql_paper and mysql_paper.published_at else None
    )
    store.upsert_paper(
        paper_id=target_id,
        kb_id=kb_id,
        title=title,
        year=year,
        venue=mysql_paper.venue if mysql_paper else None,
        ccf_rank=mysql_paper.venue_rank if mysql_paper else "None",
        task_domain="",
        innovation_summary="",
        related_chunk_ids=[],
        is_private=is_private,
        owner_user_id=owner_user_id,
    )
    return target_id


def sync_paper_citations(
    store: PaperGraphStore,
    session: Session,
    paper: Paper,
    *,
    kb_id: str,
    owner_user_id: str = "0",
    is_private: bool = False,
) -> dict[str, Any]:
    settings = get_settings()
    if not getattr(settings, "enable_semantic_scholar_cite", True):
        return {"status": "skipped", "reason": "cite disabled"}

    ss_id = resolve_ss_paper_id(
        paper.arxiv_id,
        doi=paper.doi,
        title=paper.title or "",
    )
    if not ss_id:
        return {"status": "skipped", "reason": "no_ss_match", "outgoing": 0, "incoming": 0}

    graph = fetch_paper_citation_graph(ss_id)
    outgoing = 0
    incoming = 0

    for ref in graph.get("references") or []:
        target_id = _resolve_target(
            session,
            ref,
            kb_id,
            store,
            owner_user_id=owner_user_id,
            is_private=is_private,
        )
        if not target_id or target_id == paper.arxiv_id:
            continue
        store.merge_relationship(
            "CITE",
            source_label="Paper",
            target_label="Paper",
            source_key=paper.arxiv_id,
            target_key=target_id,
            source_match={},
            target_match={},
            kb_id=kb_id,
        )
        outgoing += 1

    for cit in graph.get("citations") or []:
        source_id = _resolve_target(
            session,
            cit,
            kb_id,
            store,
            owner_user_id=owner_user_id,
            is_private=is_private,
        )
        if not source_id or source_id == paper.arxiv_id:
            continue
        store.merge_relationship(
            "CITE",
            source_label="Paper",
            target_label="Paper",
            source_key=source_id,
            target_key=paper.arxiv_id,
            source_match={},
            target_match={},
            kb_id=kb_id,
        )
        incoming += 1

    logger.info(
        "cite sync paper=%s outgoing=%s incoming=%s",
        paper.arxiv_id,
        outgoing,
        incoming,
    )
    return {
        "status": "ok",
        "ss_paper_id": ss_id,
        "outgoing": outgoing,
        "incoming": incoming,
    }


def sync_kb_citations(
    kb_id: str,
    *,
    owner_user_id: str = "0",
    is_private: bool = False,
) -> dict[str, Any]:
    """批量同步知识库内所有论文的 Semantic Scholar 引用网络。"""
    settings = get_settings()
    if not getattr(settings, "enable_semantic_scholar_cite", True):
        return {"status": "skipped", "reason": "cite disabled"}

    from src.models.base import SessionLocal
    from src.models.rag import TextChunk
    from src.services.rag.startup import startup

    store = startup.dbm.graph_store
    if not store:
        return {"status": "skipped", "reason": "no graph store"}

    session = SessionLocal()
    synced = 0
    errors = 0
    total_out = 0
    total_in = 0
    try:
        rows = (
            session.query(TextChunk.paper_id)
            .filter(
                TextChunk.kb_id == kb_id,
                TextChunk.is_deleted == 0,
                TextChunk.paper_id.isnot(None),
            )
            .distinct()
            .all()
        )
        for (pid,) in rows:
            paper = session.query(Paper).filter(Paper.arxiv_id == pid).first()
            if not paper:
                continue
            try:
                result = sync_paper_citations(
                    store,
                    session,
                    paper,
                    kb_id=kb_id,
                    owner_user_id=owner_user_id,
                    is_private=is_private,
                )
                if result.get("status") == "ok":
                    synced += 1
                    total_out += int(result.get("outgoing") or 0)
                    total_in += int(result.get("incoming") or 0)
            except Exception as exc:
                logger.warning("cite sync kb=%s paper=%s: %s", kb_id, pid, exc)
                errors += 1
        return {
            "status": "ok",
            "papers_synced": synced,
            "errors": errors,
            "outgoing": total_out,
            "incoming": total_in,
        }
    finally:
        session.close()
