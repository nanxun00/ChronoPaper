"""Celery GraphRAG 入库任务。"""
from __future__ import annotations

from src.services.graph.graph_index_service import index_paper_graph
from src.services.rag.startup import startup
from src.utils.logging_config import setup_logger
from src.workers.celery_app import celery_app

logger = setup_logger("GraphTasks")


@celery_app.task(name="graph_index_paper", bind=True, max_retries=2, default_retry_delay=120)
def graph_index_paper_task(self, paper_id: str, kb_id: str | None = None, owner_user_id: str = "0"):
    if not startup.config.enable_knowledge_graph:
        logger.info("graph_index_paper skipped (disabled): %s", paper_id)
        return {"status": "skipped", "reason": "graph disabled"}

    try:
        result = index_paper_graph(paper_id, kb_id=kb_id, owner_user_id=owner_user_id)
        return result
    except Exception as exc:
        logger.exception("graph_index_paper failed paper=%s: %s", paper_id, exc)
        raise self.retry(exc=exc)


@celery_app.task(name="sync_kb_citations", bind=True, max_retries=1, default_retry_delay=300)
def sync_kb_citations_task(self, kb_id: str, owner_user_id: str = "0"):
    if not startup.config.enable_knowledge_graph:
        return {"status": "skipped", "reason": "graph disabled"}
    if not getattr(startup.config, "enable_semantic_scholar_cite", True):
        return {"status": "skipped", "reason": "cite disabled"}

    from src.services.graph.cite_sync import sync_kb_citations

    try:
        return sync_kb_citations(kb_id, owner_user_id=owner_user_id)
    except Exception as exc:
        logger.exception("sync_kb_citations failed kb=%s: %s", kb_id, exc)
        raise self.retry(exc=exc)
