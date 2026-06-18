from pydantic import BaseModel, Field


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000)
    target_lang: str = Field(default="zh", description="目标语言代码，如 zh / en")


class CrawlQueryTranslateRequest(BaseModel):
    intent_text: str = Field(default="")
    keywords: str = Field(default="")
