from pydantic import BaseModel, Field
from typing import Literal


class CrawlTaskCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    intent_text: str = Field(default="")
    categories: str = Field(...)
    keywords: str = Field(default="")
    visibility: Literal["public", "private"] = Field(default="public")
    schedule_time: str | None = None
    min_match_score: float = Field(default=40.0, ge=0, le=100)
    max_papers_per_run: int = Field(default=50, ge=1, le=200)
    enabled: bool = True


class CrawlTaskUpdate(BaseModel):
    name: str | None = None
    intent_text: str | None = None
    categories: str | None = None
    keywords: str | None = None
    visibility: Literal["public", "private"] | None = None
    schedule_time: str | None = None
    min_match_score: float | None = None
    max_papers_per_run: int | None = None
    enabled: bool | None = None
