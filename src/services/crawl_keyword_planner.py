"""抓取前 LLM 关键词规划：所有模式在检索前根据用户描述生成检索/匹配用词。"""
from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from src.settings import get_settings
from src.utils.logging_config import setup_logger

logger = setup_logger("CrawlKeywordPlanner")


def _deepseek_client() -> OpenAI:
    settings = get_settings()
    api_key = settings.deepseek_api_key
    if not api_key:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY，无法生成检索关键词")
    return OpenAI(api_key=api_key, base_url="https://api.deepseek.com")


def _parse_llm_json(text: str) -> dict:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _normalize_keyword_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        items = [v.strip() for v in value.replace("，", ",").split(",") if v.strip()]
    elif isinstance(value, list):
        items = [str(v).strip() for v in value if str(v).strip()]
    else:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def generate_search_keywords(
    user_input: str,
    existing_keywords: str = "",
) -> dict[str, Any]:
    """根据用户兴趣描述生成英文检索关键词与精炼兴趣句。

    返回:
        intent_text, keywords, keyword_list, negative_keywords
    """
    desc = (user_input or "").strip()
    hint = (existing_keywords or "").strip()
    if not desc and not hint:
        raise ValueError("兴趣描述与关键词不能同时为空")

    settings = get_settings()
    model = settings.translate_model or "deepseek-chat"
    client = _deepseek_client()

    user_content = desc or hint
    if desc and hint:
        user_content = f"{desc}\n\n(User also provided keywords as hints: {hint})"

    prompt = f"""You are an expert academic literature search assistant.
Given the user's research interest, output JSON for literature crawling and filtering.

Rules:
- intent_text: 2-4 sentences in English describing the precise research scope
- keywords: 6-15 English search terms (comma-separated), include core task names, methods, datasets, synonyms
- negative_keywords: 3-8 English terms for clearly UNRELATED topics to exclude (e.g. if user wants segmentation, include generation/synthesis terms)
- Be specific: distinguish fine-grained tasks (segmentation vs generation, detection vs synthesis)
- Output ONLY valid JSON

Example keys:
{{
  "intent_text": "...",
  "keywords": "semantic segmentation, instance segmentation, mask prediction, ...",
  "negative_keywords": "image generation, text-to-image, diffusion synthesis, ..."
}}

User interest:
{user_content}"""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Output JSON only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        stream=False,
    )
    raw = response.choices[0].message.content or ""
    data = _parse_llm_json(raw)

    intent_text = (data.get("intent_text") or desc or hint).strip()
    keyword_list = _normalize_keyword_list(data.get("keywords"))
    if not keyword_list and hint:
        keyword_list = _normalize_keyword_list(hint)
    negative_keywords = _normalize_keyword_list(data.get("negative_keywords"))
    keywords = ", ".join(keyword_list)

    return {
        "intent_text": intent_text,
        "keywords": keywords,
        "keyword_list": keyword_list,
        "negative_keywords": negative_keywords,
        "source": "llm",
    }


def fallback_keyword_profile(intent_text: str, keywords: str) -> dict[str, Any]:
    """LLM 不可用时的兜底配置。"""
    intent = (intent_text or "").strip()
    kw = (keywords or "").strip()
    keyword_list = _normalize_keyword_list(kw)
    return {
        "intent_text": intent,
        "keywords": kw,
        "keyword_list": keyword_list,
        "negative_keywords": [],
        "source": "fallback",
    }
