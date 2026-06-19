from typing import Literal

from pydantic import BaseModel, Field


class LiteratureLibraryCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)


class LiteratureDeleteRequest(BaseModel):
    arxiv_ids: list[str] = Field(..., min_length=1, max_length=200)
    visibility: Literal["public", "private"]


class LiteratureReviewRequest(BaseModel):
    arxiv_ids: list[str] = Field(..., min_length=1, max_length=200)
    visibility: Literal["public", "private"]
