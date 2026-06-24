"""文本分块（MySQL 唯一长文本与溯源载体）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from src.models.base import Base


class TextChunk(Base):
    __tablename__ = "text_chunks"
    __table_args__ = {
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }

    chunk_id = Column(String(64), primary_key=True)
    chunk_text = Column(Text, nullable=False, default="")
    page_num = Column(Integer, nullable=True)
    bbox = Column(String(255), nullable=True)
    section_type = Column(String(32), nullable=True)
    block_type = Column(String(32), nullable=True)
    year = Column(Integer, nullable=True)
    ccf_rank = Column(String(8), nullable=True)
    keywords = Column(Text, nullable=False, default="[]")
    task_domain = Column(String(64), nullable=True)
    paper_id = Column(String(128), nullable=True, index=True)
    doc_id = Column(String(64), nullable=True, index=True)
    resource_type = Column(String(16), nullable=False, default="public")
    owner_user_id = Column(String(255), nullable=False, default="0")
    kb_id = Column(String(32), nullable=False, index=True)
    text_hash = Column(String(64), nullable=False, default="")
    is_deleted = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
