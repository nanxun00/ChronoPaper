"""Celery 向量入库任务。"""
from __future__ import annotations

from src.models.base import SessionLocal
from src.models.literature import Paper
from src.models.rag import KnowledgeBaseFile, KnowledgeBaseRecord
from src.services.rag.indexing import chunk_paper_content_list, load_content_list
from src.services.rag.indexing_pipeline import index_chunk_rows
from src.services.rag.knowledgebase import KnowledgeBase
from src.services.rag import mineru_indexing
from src.services.rag.startup import startup
from src.utils.logging_config import setup_logger
from src.workers.celery_app import celery_app

logger = setup_logger("IndexTasks")


def _kb_or_raise(session, kb_id: str) -> KnowledgeBaseRecord:
    row = session.query(KnowledgeBaseRecord).filter(KnowledgeBaseRecord.kb_id == kb_id).first()
    if not row:
        raise ValueError(f"Knowledge base not found: {kb_id}")
    return row


@celery_app.task(name="index_paper_chunks", bind=True, max_retries=2, default_retry_delay=60)
def index_paper_chunks_task(self, paper_id: str, kb_id: str | None = None, owner_user_id: str = "0"):
    session = SessionLocal()
    try:
        paper = session.query(Paper).filter(Paper.arxiv_id == paper_id).first()
        if not paper:
            logger.warning("paper not found for indexing: %s", paper_id)
            return {"status": "missing_paper"}

        if not kb_id:
            kb_id = startup.dbm.get_default_public_kb_id()

        _kb_or_raise(session, kb_id)
        paper.parse_status = "indexing"
        session.add(paper)
        session.commit()

        content_list_path = mineru_indexing.resolve_paper_content_list_path(paper_id)
        if not content_list_path:
            content_list_path = mineru_indexing.parse_paper_pdf_to_content_list(paper_id)

        blocks = load_content_list(content_list_path)
        year = paper.published_at.year if paper.published_at else None
        rows = chunk_paper_content_list(
            blocks,
            kb_id=kb_id,
            paper_id=paper_id,
            resource_type="private" if owner_user_id not in ("", "0") else "public",
            owner_user_id=owner_user_id or "0",
            year=year,
            ccf_rank=paper.venue_rank,
            task_domain=None,
            keywords=paper.categories_list() if hasattr(paper, "categories_list") else [],
        )
        kb = startup.dbm.knowledge_base
        count = index_chunk_rows(session, kb, rows)
        paper.parse_status = "indexed"
        if startup.config.enable_knowledge_graph:
            paper.graph_index_status = "pending"
            paper.graph_index_error = None
        else:
            paper.graph_index_status = "skipped"
        session.add(paper)
        session.commit()
        logger.info("indexed paper %s chunks=%s kb=%s", paper_id, count, kb_id)
        if startup.config.enable_knowledge_graph:
            from src.workers.graph_tasks import graph_index_paper_task

            graph_index_paper_task.delay(paper_id, kb_id, owner_user_id)
        return {"status": "ok", "chunks": count}
    except Exception as exc:
        logger.exception("index_paper_chunks failed paper=%s: %s", paper_id, exc)
        try:
            paper = session.query(Paper).filter(Paper.arxiv_id == paper_id).first()
            if paper and paper.parse_status == "indexing":
                paper.parse_status = "index_failed"
                session.add(paper)
                session.commit()
        except Exception:
            pass
        raise self.retry(exc=exc)
    finally:
        session.close()


@celery_app.task(name="index_kb_document", bind=True, max_retries=2, default_retry_delay=60)
def index_kb_document_task(self, kb_id: str, doc_id: str, file_path: str, file_id: str):
    session = SessionLocal()
    kb_file = None
    try:
        kb_row = _kb_or_raise(session, kb_id)
        kb_file = (
            session.query(KnowledgeBaseFile)
            .filter(KnowledgeBaseFile.kb_id == kb_id, KnowledgeBaseFile.file_id == file_id)
            .first()
        )
        if kb_file:
            kb_file.status = "processing"
            kb_file.parse_status = "processing"
            session.commit()

        content_list_path = mineru_indexing.parse_upload_file_to_content_list(file_path)
        blocks = load_content_list(content_list_path)
        rows = chunk_paper_content_list(
            blocks,
            kb_id=kb_id,
            doc_id=doc_id,
            resource_type="private",
            owner_user_id=kb_row.owner_user_id or "0",
        )
        kb = KnowledgeBase(startup.config, startup.dbm.embed_model)
        count = index_chunk_rows(session, kb, rows)
        if kb_file:
            kb_file.status = "done"
            kb_file.parse_status = "done"
            kb_file.index_status = "done"
            session.commit()
        logger.info("indexed kb doc %s chunks=%s", doc_id, count)
        return {"status": "ok", "chunks": count}
    except Exception as exc:
        if kb_file:
            kb_file.status = "failed"
            kb_file.index_status = "failed"
            session.commit()
        logger.exception("index_kb_document failed doc=%s: %s", doc_id, exc)
        raise self.retry(exc=exc)
    finally:
        session.close()
