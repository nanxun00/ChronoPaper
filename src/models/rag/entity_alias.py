"""实体别名映射（GraphRAG 预留，Phase 1 仅表结构）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, String

from src.models.base import Base


class EntityAlias(Base):
    __tablename__ = "entity_alias"
    __table_args__ = {
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }

    id = Column(String(32), primary_key=True)
    std_name = Column(String(255), nullable=False, index=True)
    raw_alias = Column(String(255), nullable=False, unique=True, index=True)
    entity_type = Column(String(32), nullable=False, default="Model")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
