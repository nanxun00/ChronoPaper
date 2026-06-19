from pydantic import BaseModel, Field
from typing import Literal


class CrawlPlanRequest(BaseModel):
    domain_description: str = Field(..., min_length=1, max_length=4000)
    existing_sources: str | None = Field(
        default=None,
        description="逗号分隔的已勾选数据源；若提供则 LLM 仅规划这些源",
    )


class CrawlPlanResponse(BaseModel):
    intent_text: str = ""
    keywords: str = ""
    sources: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    openreview_venues: list[str] = Field(default_factory=list)
    openalex_venue_types: list[str] = Field(default_factory=list)
    openalex_ccf_ranks: list[str] = Field(default_factory=list)
    openalex_year_from: int | None = None
    openalex_year_to: int | None = None
    openalex_venue_names: str = ""
    suggested_name: str = ""
    reasoning: str = ""
    plan_summary: str = ""


class CrawlTaskCreate(BaseModel):
    name: str = Field(default="", max_length=255, description="可选；留空则创建后自动命名为「抓取任务 #ID」")
    intent_text: str = Field(default="")
    sources: str = Field(default="arxiv", description="逗号分隔: arxiv,openreview,openalex")
    categories: str = Field(default="")
    openreview_venues: str = Field(default="")
    openalex_venue_types: str = Field(default="conference,journal")
    openalex_ccf_ranks: str = Field(default="A,B,C")
    openalex_year_from: int | None = None
    openalex_year_to: int | None = None
    openalex_venue_names: str = Field(default="")
    keywords: str = Field(default="")
    visibility: Literal["public", "private"] = Field(default="public")
    library_id: str | None = Field(default=None, description="私有文献库 ID，visibility=private 时必填")
    schedule_time: str | None = None
    auto_run: bool = Field(default=False, description="创建后立即执行；智能规划任务则在规划完成后执行")
    min_match_score: float = Field(default=50.0, ge=0, le=100, description="兼容旧字段，等同 min_semantic_score")
    min_semantic_score: float = Field(default=50.0, ge=0, le=100)
    min_quality_score: float = Field(default=0.0, ge=0, le=100)
    enable_quality_filter: bool = Field(default=False)
    enable_smart_planning: bool = Field(default=False)
    crawl_mode: Literal["latest", "explore", "smart", "manual"] = Field(default="latest")
    plan_summary: str = Field(default="")
    verified_suggestions_json: str = Field(default="")
    max_papers_per_run: int = Field(default=50, ge=1, le=200)
    enabled: bool = True


class CrawlTaskUpdate(BaseModel):
    name: str | None = None
    intent_text: str | None = None
    sources: str | None = None
    categories: str | None = None
    openreview_venues: str | None = None
    openalex_venue_types: str | None = None
    openalex_ccf_ranks: str | None = None
    openalex_year_from: int | None = None
    openalex_year_to: int | None = None
    openalex_venue_names: str | None = None
    keywords: str | None = None
    visibility: Literal["public", "private"] | None = None
    schedule_time: str | None = None
    min_match_score: float | None = None
    min_semantic_score: float | None = None
    min_quality_score: float | None = None
    enable_quality_filter: bool | None = None
    enable_smart_planning: bool | None = None
    crawl_mode: Literal["latest", "explore", "smart", "manual"] | None = None
    plan_summary: str | None = None
    max_papers_per_run: int | None = None
    enabled: bool | None = None
