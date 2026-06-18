"""抓取任务模式预设：最新跟踪 / 领域探索 / 智能规划。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

CrawlMode = Literal["latest", "explore", "smart", "manual"]

CRAWL_MODE_LABELS: dict[str, str] = {
    "latest": "最新文献跟踪",
    "explore": "领域探索",
    "smart": "智能规划",
    "manual": "手动设计",
}


def _current_year() -> int:
    return datetime.utcnow().year


def get_crawl_mode_preset(mode: str) -> dict[str, Any]:
    """返回某模式的推荐抓取配置（不含 name / intent / visibility / schedule）。"""
    year = _current_year()
    if mode == "latest":
        return {
            "enable_smart_planning": False,
            "sources": "arxiv",
            "categories": "cs.AI, cs.LG, cs.CL, cs.CV",
            "openreview_venues": "",
            "openalex_venue_types": "conference,journal",
            "openalex_ccf_ranks": "A,B,C",
            "openalex_year_from": year - 1,
            "openalex_year_to": year,
            "openalex_venue_names": "",
            "enable_quality_filter": False,
            "min_semantic_score": 48.0,
            "min_quality_score": 50.0,
            "max_papers_per_run": 60,
        }
    if mode == "explore":
        return {
            "enable_smart_planning": False,
            "sources": "openreview,openalex",
            "categories": "",
            "openreview_venues": "",
            "openalex_venue_types": "conference,journal",
            "openalex_ccf_ranks": "A,B,C",
            "openalex_year_from": year - 3,
            "openalex_year_to": year,
            "openalex_venue_names": "",
            "enable_quality_filter": True,
            "min_semantic_score": 50.0,
            "min_quality_score": 50.0,
            "max_papers_per_run": 40,
        }
    if mode == "smart":
        return {
            "enable_smart_planning": True,
            "sources": "",
            "categories": "",
            "openreview_venues": "",
            "openalex_venue_types": "conference,journal",
            "openalex_ccf_ranks": "A,B,C",
            "openalex_year_from": None,
            "openalex_year_to": None,
            "openalex_venue_names": "",
            "enable_quality_filter": False,
            "min_semantic_score": 55.0,
            "min_quality_score": 60.0,
            "max_papers_per_run": 50,
        }
    return {}
