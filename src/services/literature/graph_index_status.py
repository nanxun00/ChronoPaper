"""论文 GraphRAG 入库状态读写。"""
from __future__ import annotations

from src.models.base import SessionLocal
from src.models.literature import Paper
from src.utils.logging_config import setup_logger

logger = setup_logger("PaperGraphStatus")


def set_paper_graph_index_status(
    paper_id: str,
    status: str,
    *,
    error: str | None = None,
) -> None:
    session = SessionLocal()
    try:
        paper = session.query(Paper).filter(Paper.arxiv_id == paper_id).first()
        if not paper:
            return
        paper.graph_index_status = status
        paper.graph_index_error = (error or "")[:512] if error else None
        session.add(paper)
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.warning("set graph_index_status failed paper=%s: %s", paper_id, exc)
    finally:
        session.close()
