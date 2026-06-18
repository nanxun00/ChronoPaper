"""文献列表条目 ORM。"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint

from src.models.base import Base


class LiteratureEntry(Base):
    __tablename__ = "literature_entries"
    __table_args__ = (
        UniqueConstraint("arxiv_id", "user_id", "visibility", name="uq_literature_scope"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    arxiv_id = Column(String(64), ForeignKey("papers.arxiv_id"), nullable=False, index=True)
    user_id = Column(String(255), nullable=False, default="", index=True)
    visibility = Column(String(16), nullable=False)
    match_score = Column(Float, nullable=True)
    semantic_score = Column(Float, nullable=True)
    quality_score = Column(Float, nullable=True)
    pool_type = Column(String(16), nullable=True)
    task_id = Column(Integer, ForeignKey("crawl_tasks.id"), nullable=True)
    run_id = Column(Integer, ForeignKey("crawl_task_runs.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
