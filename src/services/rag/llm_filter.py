"""LLM 抽取 Milvus 业务 filter 参数（不生成 filter 语法）。"""
from __future__ import annotations

import json
import re
from typing import Any

from src.settings import get_settings
from src.utils.logging_config import setup_logger

logger = setup_logger("RagLlmFilter")

_DEFAULT = {
    "year_start": None,
    "year_end": None,
    "ccf_rank": [],
    "section_type": None,
    "block_type": None,
    "keywords": [],
    "task_domain": None,
}


def _parse_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def llm_extract_filter_cond(query: str) -> dict[str, Any]:
    """从自然语言问题抽取结构化 filter JSON；失败返回空约束。"""
    q = (query or "").strip()
    if not q:
        return dict(_DEFAULT)

    settings = get_settings()
    if not settings.deepseek_api_key:
        return dict(_DEFAULT)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.deepseek_api_key, base_url="https://api.deepseek.com")
        model = settings.translate_model or "deepseek-chat"
        prompt = (
            "Extract structured search filters from the user question. "
            "Return ONLY JSON with keys: year_start, year_end, ccf_rank (array), "
            "section_type, block_type, keywords (array), task_domain. "
            "Use null/[] when unknown."
        )
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": q},
            ],
            temperature=0.0,
            stream=False,
        )
        data = _parse_json(resp.choices[0].message.content or "")
    except Exception as exc:
        logger.warning("LLM filter extract failed: %s", exc)
        return dict(_DEFAULT)

    out = dict(_DEFAULT)
    for key in out:
        if key in data:
            out[key] = data[key]
    return out
