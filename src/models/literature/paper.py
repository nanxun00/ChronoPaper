"""论文元数据 ORM。"""
import json
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from src.models.base import Base


class Paper(Base):
    __tablename__ = "papers"

    arxiv_id = Column(String(128), primary_key=True)
    source = Column(String(32), nullable=False, default="arxiv")
    title = Column(Text, nullable=False, default="")
    authors = Column(Text, nullable=False, default="[]")
    abstract = Column(Text, nullable=False, default="")
    categories = Column(Text, nullable=False, default="[]")
    published_at = Column(DateTime, nullable=True)
    abs_url = Column(String(512), nullable=True)
    pdf_url = Column(String(512), nullable=True)
    pdf_path = Column(String(512), nullable=True)
    parse_status = Column(String(32), nullable=False, default="pending")
    venue = Column(String(255), nullable=True)
    venue_type = Column(String(64), nullable=True)
    citation_count = Column(Integer, nullable=True)
    acceptance_status = Column(String(64), nullable=True)
    review_rating = Column(Float, nullable=True)
    openreview_id = Column(String(128), nullable=True)
    doi = Column(String(256), nullable=True)
    openalex_id = Column(String(64), nullable=True)
    venue_rank = Column(String(8), nullable=True)
    journal_if = Column(Float, nullable=True)
    jcr_quartile = Column(String(8), nullable=True)
    quality_score = Column(Float, nullable=True)
    llm_innovation_score = Column(Float, nullable=True)
    llm_experiment_score = Column(Float, nullable=True)
    quality_assessed_at = Column(DateTime, nullable=True)
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
            "paper_id": self.arxiv_id,
            "source": self.source or "arxiv",
            "title": self.title,
            "authors": ", ".join(self.authors_list()),
            "abstract": self.abstract,
            "categories": self.categories_list(),
            "published_at": pub.strftime("%Y-%m-%d") if pub else None,
            "year": pub.year if pub else None,
            "abs_url": self.abs_url,
            "pdf_url": self.pdf_url,
            "parse_status": self.parse_status,
            "venue": self.venue,
            "venue_type": self.venue_type,
            "citation_count": self.citation_count,
            "acceptance_status": self.acceptance_status,
            "review_rating": self.review_rating,
            "openreview_id": self.openreview_id,
            "doi": self.doi,
            "openalex_id": self.openalex_id,
            "venue_rank": self.venue_rank,
            "journal_if": self.journal_if,
            "jcr_quartile": self.jcr_quartile,
            "quality_score": self.quality_score,
            "llm_innovation_score": self.llm_innovation_score,
            "llm_experiment_score": self.llm_experiment_score,
            "listed_at": self.created_at.strftime("%Y-%m-%d") if self.created_at else None,
        }
