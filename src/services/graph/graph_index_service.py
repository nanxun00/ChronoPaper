"""论文 GraphRAG 入库编排。"""
from __future__ import annotations

from typing import Any

from src.models.base import SessionLocal
from src.models.literature import Paper
from src.models.rag import TextChunk
from src.services.graph.extraction import (
    GRAPH_SECTION_TYPES,
    build_std_relations,
    collect_entities_for_upsert,
    extract_section_batch,
    fallback_entity_description,
    merge_extraction_batches,
    resolve_task_domain,
)
from src.services.graph.neo4j_store import PaperGraphStore
from src.services.rag.startup import startup
from src.utils.logging_config import setup_logger

logger = setup_logger("GraphIndexService")

LABEL_FOR_TYPE = {
    "Paper": "Paper",
    "Model": "Model",
    "Dataset": "Dataset",
    "Metric": "Metric",
    "Venue": "Venue",
}


def _group_chunks_by_section(chunks: list[TextChunk]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {s: [] for s in GRAPH_SECTION_TYPES}
    for chunk in chunks:
        section = (chunk.section_type or "").lower()
        if section not in GRAPH_SECTION_TYPES:
            continue
        groups[section].append({"chunk_id": chunk.chunk_id, "chunk_text": chunk.chunk_text})
    return groups


def _load_known_task_domains(session, kb_id: str, store: PaperGraphStore, owner_user_id: str) -> list[str]:
    """从图谱与向量库分块中汇总已收录领域，供抽取时对齐。"""
    domains: set[str] = set()
    try:
        for domain in store.list_task_domains(kb_id=kb_id, user_id=owner_user_id, limit=100):
            if domain and str(domain).strip():
                domains.add(str(domain).strip())
    except Exception as exc:
        logger.debug("list_task_domains skipped: %s", exc)

    rows = (
        session.query(TextChunk.task_domain)
        .filter(
            TextChunk.kb_id == kb_id,
            TextChunk.is_deleted == 0,
            TextChunk.task_domain.isnot(None),
            TextChunk.task_domain != "",
        )
        .distinct()
        .limit(100)
        .all()
    )
    for (domain,) in rows:
        if domain and str(domain).strip():
            domains.add(str(domain).strip())
    return sorted(domains)


def _backfill_task_domain(
    session,
    kb,
    paper_id: str,
    kb_id: str,
    task_domain: str | None,
) -> int:
    if not task_domain:
        return 0
    rows = (
        session.query(TextChunk)
        .filter(
            TextChunk.paper_id == paper_id,
            TextChunk.kb_id == kb_id,
            TextChunk.is_deleted == 0,
        )
        .all()
    )
    updated = 0
    patch_rows = []
    for row in rows:
        if row.task_domain == task_domain:
            continue
        row.task_domain = task_domain
        updated += 1
        patch_rows.append({"chunk_id": row.chunk_id, "task_domain": task_domain})
    if updated:
        session.commit()
        if kb and patch_rows:
            kb.patch_task_domain(patch_rows)
    return updated


def index_paper_graph(
    paper_id: str,
    kb_id: str | None = None,
    owner_user_id: str = "0",
    *,
    model=None,
) -> dict[str, Any]:
    if not startup.config.enable_knowledge_graph:
        return {"status": "skipped", "reason": "graph disabled"}

    graph_base = startup.dbm.graph_base
    if not graph_base or not graph_base.driver:
        return {"status": "skipped", "reason": "neo4j unavailable"}

    if not kb_id:
        kb_id = startup.dbm.get_default_public_kb_id()

    llm = model or startup.model
    store = PaperGraphStore(graph_base.driver, graph_base.kgdb_name)
    store.ensure_indexes()

    session = SessionLocal()
    try:
        paper = session.query(Paper).filter(Paper.arxiv_id == paper_id).first()
        if not paper:
            return {"status": "missing_paper"}

        chunks = (
            session.query(TextChunk)
            .filter(
                TextChunk.paper_id == paper_id,
                TextChunk.kb_id == kb_id,
                TextChunk.is_deleted == 0,
            )
            .all()
        )
        if not chunks:
            return {"status": "no_chunks"}

        is_private = any(c.resource_type == "private" for c in chunks)
        owner = owner_user_id or next((c.owner_user_id for c in chunks if c.owner_user_id), "0")
        section_groups = _group_chunks_by_section(chunks)
        known_task_domains = _load_known_task_domains(session, kb_id, store, owner)

        batches = []
        for section_type, section_chunks in section_groups.items():
            if not section_chunks:
                continue
            batch = extract_section_batch(
                llm,
                paper_id=paper_id,
                title=paper.title,
                abstract=paper.abstract,
                section_type=section_type,
                chunks=section_chunks,
                known_task_domains=known_task_domains,
            )
            batches.append(batch)

        merged = merge_extraction_batches(batches, known_task_domains=known_task_domains)
        relations_std, _, entity_chunks = build_std_relations(paper_id, merged)
        task_domain = resolve_task_domain(merged.get("task_domain"), known_task_domains)
        year = paper.published_at.year if paper.published_at else None

        all_chunk_ids = [c.chunk_id for c in chunks]
        store.upsert_paper(
            paper_id=paper_id,
            kb_id=kb_id,
            title=paper.title,
            year=year,
            venue=paper.venue,
            ccf_rank=paper.venue_rank,
            task_domain=task_domain,
            innovation_summary=merged.get("innovation_summary") or "",
            related_chunk_ids=all_chunk_ids,
            is_private=is_private,
            owner_user_id=owner,
            keywords=paper.categories_list() if hasattr(paper, "categories_list") else [],
        )

        for rel in relations_std:
            sl = LABEL_FOR_TYPE.get(rel.get("source_type") or "Model", "Model")
            tl = LABEL_FOR_TYPE.get(rel.get("target_type") or "Model", "Model")
            store.merge_relationship(
                rel["rel_type"],
                source_label=sl,
                target_label=tl,
                source_key=rel["source_std"],
                target_key=rel["target_std"],
                source_match={},
                target_match={},
                kb_id=kb_id,
                chunk_id=rel.get("chunk_id"),
            )

        neighbors = store.list_paper_neighbor_entities(paper_id, kb_id)
        for item in collect_entities_for_upsert(
            paper_id, merged, relations_std, extra_neighbors=neighbors
        ):
            et = item["entity_type"]
            std_name = item["std_name"]
            ref_ids = entity_chunks.get(std_name, [])
            llm_desc = (item.get("description") or "").strip()
            extra: dict[str, Any] = {}
            if llm_desc:
                extra["description"] = llm_desc
            else:
                extra["description"] = fallback_entity_description(std_name, et, task_domain)
                extra["__fill_description_only"] = True
            if et == "Model":
                extra["task_domain"] = task_domain or ""
                extra["birth_year"] = year
            elif et == "Dataset":
                extra["task"] = task_domain or ""
            elif et == "Metric":
                extra["applicable_task"] = task_domain or ""
            store.upsert_named_entity(et, name=std_name, kb_id=kb_id, ref_chunk_ids=ref_ids, extra=extra)

        store.write_static_metadata_relations(
            paper_id=paper_id,
            kb_id=kb_id,
            venue=paper.venue,
            venue_rank=paper.venue_rank,
            venue_type=paper.venue_type,
        )

        cite_result: dict = {"status": "skipped"}
        try:
            from src.services.graph.cite_sync import sync_paper_citations

            cite_result = sync_paper_citations(
                store,
                session,
                paper,
                kb_id=kb_id,
                owner_user_id=owner,
                is_private=is_private,
            )
        except Exception as exc:
            logger.warning("cite sync failed paper=%s: %s", paper_id, exc)
            cite_result = {"status": "error", "message": str(exc)}

        kb = startup.dbm.knowledge_base
        domain_updated = _backfill_task_domain(session, kb, paper_id, kb_id, task_domain)

        logger.info(
            "graph indexed paper=%s kb=%s relations=%s domain_updated=%s",
            paper_id,
            kb_id,
            len(relations_std),
            domain_updated,
        )
        return {
            "status": "ok",
            "relations": len(relations_std),
            "entities": len(merged.get("raw_entities") or []),
            "task_domain": task_domain,
            "domain_chunks_updated": domain_updated,
            "cites": cite_result,
        }
    except Exception as exc:
        logger.exception("graph index failed paper=%s: %s", paper_id, exc)
        raise
    finally:
        session.close()
