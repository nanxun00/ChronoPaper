"""Celery GraphRAG 入库任务。"""
from __future__ import annotations

from src.services.graph.graph_index_service import index_paper_graph
from src.services.literature.graph_index_status import set_paper_graph_index_status
from src.services.rag.startup import startup
from src.utils.logging_config import setup_logger
from src.workers.celery_app import celery_app

logger = setup_logger("GraphTasks")


def _apply_graph_result(paper_id: str, result: dict) -> dict:
    status = (result or {}).get("status") or "error"
    if status == "ok":
        set_paper_graph_index_status(paper_id, "ok")
        return result
    if status == "skipped":
        reason = result.get("reason") or "skipped"
        set_paper_graph_index_status(paper_id, "skipped", error=reason)
        return result
    reason = result.get("reason") or status
    set_paper_graph_index_status(paper_id, "failed", error=str(reason))
    logger.warning("graph_index_paper non-ok paper=%s result=%s", paper_id, result)
    return result


@celery_app.task(name="graph_index_paper", bind=True, max_retries=2, default_retry_delay=120)
def graph_index_paper_task(self, paper_id: str, kb_id: str | None = None, owner_user_id: str = "0"):
    if not startup.config.enable_knowledge_graph:
        logger.info("graph_index_paper skipped (disabled): %s", paper_id)
        set_paper_graph_index_status(paper_id, "skipped", error="graph disabled")
        return {"status": "skipped", "reason": "graph disabled"}

    set_paper_graph_index_status(paper_id, "indexing")
    try:
        result = index_paper_graph(paper_id, kb_id=kb_id, owner_user_id=owner_user_id)
        return _apply_graph_result(paper_id, result)
    except Exception as exc:
        logger.exception("graph_index_paper failed paper=%s: %s", paper_id, exc)
        if self.request.retries >= self.max_retries:
            set_paper_graph_index_status(paper_id, "failed", error=str(exc))
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
