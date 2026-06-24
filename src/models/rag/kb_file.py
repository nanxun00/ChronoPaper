"""知识库上传文件登记。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, String

from src.models.base import Base


class KnowledgeBaseFile(Base):
    __tablename__ = "knowledge_base_files"
    __table_args__ = {
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }

    file_id = Column(String(64), primary_key=True)
    kb_id = Column(String(32), nullable=False, index=True)
    doc_id = Column(String(64), nullable=False, unique=True, index=True)
    filename = Column(String(512), nullable=False, default="")
    path = Column(String(1024), nullable=False, default="")
    file_type = Column(String(16), nullable=False, default="pdf")
    status = Column(String(32), nullable=False, default="waiting")
    parse_status = Column(String(32), nullable=False, default="pending")
    index_status = Column(String(32), nullable=False, default="pending")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
