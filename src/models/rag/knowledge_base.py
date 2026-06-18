"""知识库配置（MySQL，替代 database.json）。"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from src.models.base import Base


class KnowledgeBaseRecord(Base):
    __tablename__ = "knowledge_base"
    __table_args__ = {
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }

    kb_id = Column(String(32), primary_key=True)
    name = Column(String(255), nullable=False, default="")
    description = Column(Text, nullable=False, default="")
    db_type = Column(String(32), nullable=False, default="knowledge")
    metaname = Column(String(128), nullable=False, unique=True, index=True)
    embed_model = Column(String(64), nullable=False, default="zhipu-embedding-3")
    dimension = Column(Integer, nullable=False, default=2048)
    owner_user_id = Column(String(255), nullable=False, default="")
    is_system = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self, *, row_count: int = 0, metadata: dict | None = None) -> dict:
        meta = dict(metadata or {})
        meta.setdefault("collection_name", "paper_text_chunk")
        meta["row_count"] = row_count
        return {
            "kb_id": self.kb_id,
            "db_id": self.kb_id,
            "name": self.name,
            "description": self.description,
            "db_type": self.db_type,
            "metaname": self.metaname,
            "embed_model": self.embed_model,
            "dimension": self.dimension,
            "owner_user_id": self.owner_user_id,
            "is_system": bool(self.is_system),
            "metadata": meta,
            "files": [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @staticmethod
    def metaname_for(kb_id: str) -> str:
        return f"k{kb_id[-12:]}"
