"""抓取任务 ORM。"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text

from src.models.base import Base


class CrawlTask(Base):
    __tablename__ = "crawl_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    intent_text = Column(Text, nullable=False, default="")
    sources = Column(String(128), nullable=False, default="arxiv")
    categories = Column(String(512), nullable=False, default="")
    openreview_venues = Column(String(1024), nullable=False, default="")
    openalex_venue_types = Column(String(64), nullable=False, default="conference,journal")
    openalex_ccf_ranks = Column(String(32), nullable=False, default="A,B,C")
    openalex_year_from = Column(Integer, nullable=True)
    openalex_year_to = Column(Integer, nullable=True)
    openalex_venue_names = Column(String(1024), nullable=False, default="")
    keywords = Column(String(512), nullable=False, default="")
    visibility = Column(String(16), nullable=False, default="public")
    schedule_time = Column(String(8), nullable=True)
    auto_run_on_ready = Column(Boolean, nullable=False, default=False)
    min_match_score = Column(Float, nullable=False, default=40.0)
    min_semantic_score = Column(Float, nullable=False, default=50.0)
    min_quality_score = Column(Float, nullable=False, default=0.0)
    enable_quality_filter = Column(Boolean, nullable=False, default=False)
    enable_smart_planning = Column(Boolean, nullable=False, default=False)
    crawl_mode = Column(String(16), nullable=False, default="latest")
    plan_summary = Column(String(2048), nullable=False, default="")
    verified_suggestions_json = Column(Text, nullable=True)
    planning_status = Column(String(16), nullable=False, default="none")
    planning_error = Column(String(512), nullable=False, default="")
    max_papers_per_run = Column(Integer, nullable=False, default=50)
    enabled = Column(Boolean, nullable=False, default=True)
    last_run_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class CrawlTaskRun(Base):
    __tablename__ = "crawl_task_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("crawl_tasks.id"), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="waiting")
    trigger_type = Column(String(16), nullable=False, default="manual")
    progress = Column(Integer, nullable=False, default=0)
    stats_json = Column(Text, nullable=False, default="{}")
    log_text = Column(Text, nullable=False, default="")
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
