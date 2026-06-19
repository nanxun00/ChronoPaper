"""文献删除时的向量与图谱级联清理。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.models.rag import TextChunk
from src.utils.logging_config import setup_logger

logger = setup_logger("LiteratureCleanup")


def _distinct_kb_ids_for_paper(db: Session, paper_id: str) -> list[str]:
    rows = (
        db.query(TextChunk.kb_id)
        .filter(TextChunk.paper_id == paper_id)
        .distinct()
        .all()
    )
    kb_ids = [r[0] for r in rows if r and r[0]]
    if kb_ids:
        return kb_ids
    try:
        from src.services.rag.startup import startup

        return [startup.dbm.get_default_public_kb_id()]
    except Exception:
        return []


def cascade_cleanup_paper_vectors_and_graph(db: Session, paper_id: str) -> dict:
    """清理论文在 Milvus/MySQL 中的分块向量，以及 Neo4j 图谱节点。"""
    chunks_removed = 0
    graph_papers_removed = 0
    errors: list[str] = []
    kb_ids = _distinct_kb_ids_for_paper(db, paper_id)

    try:
        from src.services.rag.indexing_pipeline import soft_delete_paper_chunks
        from src.services.rag.startup import startup

        kb = startup.dbm.knowledge_base if startup.dbm else None
        if kb:
            for kb_id in kb_ids:
                try:
                    chunks_removed += soft_delete_paper_chunks(
                        db, kb, kb_id=kb_id, paper_id=paper_id
                    )
                except Exception as exc:
                    logger.warning(
                        "vector cleanup failed paper=%s kb=%s: %s", paper_id, kb_id, exc
                    )
                    errors.append(f"vectors:{kb_id}")
    except Exception as exc:
        logger.warning("vector cleanup unavailable paper=%s: %s", paper_id, exc)
        errors.append("vectors")

    try:
        from src.services.graph.neo4j_store import PaperGraphStore
        from src.services.rag.startup import startup

        if startup.config.enable_knowledge_graph:
            graph_base = startup.dbm.graph_base if startup.dbm else None
            if graph_base and graph_base.driver:
                store = PaperGraphStore(graph_base.driver, graph_base.kgdb_name)
                for kb_id in kb_ids:
                    try:
                        result = store.delete_paper_graph(paper_id, kb_id)
                        graph_papers_removed += int(result.get("papers", 0))
                    except Exception as exc:
                        logger.warning(
                            "graph cleanup failed paper=%s kb=%s: %s", paper_id, kb_id, exc
                        )
                        errors.append(f"graph:{kb_id}")
    except Exception as exc:
        logger.warning("graph cleanup unavailable paper=%s: %s", paper_id, exc)
        errors.append("graph")

    return {
        "chunks_removed": chunks_removed,
        "graph_papers_removed": graph_papers_removed,
        "errors": errors,
    }
