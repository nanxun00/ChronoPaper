"""论文元数据 ORM。"""
import json
from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text

from src.models.base import Base


class Paper(Base):
    __tablename__ = "papers"

    arxiv_id = Column(String(64), primary_key=True)
    title = Column(Text, nullable=False, default="")
    authors = Column(Text, nullable=False, default="[]")
    abstract = Column(Text, nullable=False, default="")
    categories = Column(Text, nullable=False, default="[]")
    published_at = Column(DateTime, nullable=True)
    abs_url = Column(String(512), nullable=True)
    pdf_url = Column(String(512), nullable=True)
    pdf_path = Column(String(512), nullable=True)
    parse_status = Column(String(32), nullable=False, default="pending")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def authors_list(self) -> list[str]:
        try:
            return json.loads(self.authors or "[]")
        except json.JSONDecodeError:
            return []

    def categories_list(self) -> list[str]:
        try:
            return json.loads(self.categories or "[]")
        except json.JSONDecodeError:
            return []

    def to_dict(self) -> dict:
        pub = self.published_at
        return {
            "arxiv_id": self.arxiv_id,
            "title": self.title,
            "authors": ", ".join(self.authors_list()),
            "abstract": self.abstract,
            "categories": self.categories_list(),
            "published_at": pub.strftime("%Y-%m-%d %H:%M:%S") if pub else None,
            "year": pub.year if pub else None,
            "abs_url": self.abs_url,
            "pdf_url": self.pdf_url,
            "parse_status": self.parse_status,
            "listed_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }
