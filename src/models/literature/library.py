"""用户私有文献库（按领域分类）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text

from src.models.base import Base


class LiteratureLibrary(Base):
    __tablename__ = "literature_libraries"
    __table_args__ = {
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }

    library_id = Column(String(64), primary_key=True)
    user_id = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "library_id": self.library_id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description or "",
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }
