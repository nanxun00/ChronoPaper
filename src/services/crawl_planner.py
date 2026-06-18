"""LLM 智能抓取规划：根据自然语言描述生成可编辑的抓取方案。"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from openai import OpenAI

from src.integrations.crawl.catalog import (
    ARXIV_CATEGORIES,
    CRAWL_SOURCES,
    OPENALEX_CCF_RANKS,
    OPENALEX_VENUE_TYPES,
    OPENREVIEW_VENUES,
)
from src.settings import get_settings
from src.utils.logging_config import setup_logger

logger = setup_logger("CrawlPlanner")

CURRENT_YEAR = datetime.utcnow().year


def _deepseek_client() -> OpenAI:
    settings = get_settings()
    api_key = settings.deepseek_api_key
    if not api_key:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY，无法使用智能规划")
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


def _normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [v.strip() for v in value.replace("，", ",").split(",") if v.strip()]
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


def _filter_allowed(items: list[str], allowed: frozenset[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in allowed and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _clamp_year(value: Any, default: int) -> int:
    try:
        year = int(value)
    except (TypeError, ValueError):
        return default
    return max(1990, min(CURRENT_YEAR, year))


def _build_system_prompt(existing_sources: list[str] | None) -> str:
    if existing_sources:
        source_hint = (
            f"\nThe user has pre-selected data sources: {', '.join(existing_sources)}. "
            "Only plan parameters for these sources; do not recommend other sources."
        )
    else:
        source_hint = (
            "\nAll three data sources (arxiv, openreview, openalex) are available. "
            "You MUST choose which 1-3 sources to use in the \"sources\" array based on the domain. "
            "Do not default to arxiv only unless the domain is clearly preprint-focused."
        )

    arxiv_list = ", ".join(sorted(ARXIV_CATEGORIES))
    or_list = "\n".join(f"- {v}" for v in sorted(OPENREVIEW_VENUES))

    return f"""You are an expert academic literature crawl planner for AI/ML research.
Given a user's research domain description, output a JSON crawl plan. Do NOT invent paper titles or fake DOIs.
{source_hint}

Data source roles:
- arxiv: keyword search on preprints; categories are quality preferences only (optional)
- openreview: keyword search across venues; openreview_venues are quality preferences only (optional)
- openalex: journals/conferences with CCF rank; uses intent+keywords search

Allowed arXiv categories (use exact codes only): {arxiv_list}

Allowed OpenReview venue invitation IDs (use exact strings only):
{or_list}

Allowed sources: arxiv, openreview, openalex
Allowed openalex_venue_types: conference, journal
Allowed openalex_ccf_ranks: A, B, C

Output ONLY valid JSON with these keys:
{{
  "intent_text": "English research interest paragraph for semantic matching (2-4 sentences)",
  "keywords": "comma-separated English keywords for search and matching",
  "sources": ["arxiv", "openreview", "openalex"],
  "categories": ["cs.CL"],
  "openreview_venues": ["ICLR.cc/2025/Conference/-/Submission"],
  "openalex_venue_types": ["conference", "journal"],
  "openalex_ccf_ranks": ["A", "B", "C"],
  "openalex_year_from": {CURRENT_YEAR - 2},
  "openalex_year_to": {CURRENT_YEAR},
  "openalex_venue_names": "optional comma-separated venue names e.g. NeurIPS, IEEE TPAMI",
  "suggested_name": "short Chinese task name",
  "reasoning": "1-3 sentences in Chinese explaining source and parameter choices",
  "suggested_papers": [
    {{"title": "exact English paper title", "reason": "why relevant to the domain"}}
  ]
}}

Rules:
- Choose sources from arxiv, openreview, openalex (1-3 items); combine when useful e.g. arxiv+openreview for fast-moving ML topics, add openalex for journals/CCF coverage
- suggested_papers: 3-6 REAL, well-known papers in this field (exact official English titles only); we will verify via API — do NOT invent titles
- categories: 0-4 arXiv category codes as quality preferences (optional), only if arxiv in sources
- openreview_venues: 0-3 venue invitation IDs as quality preferences (optional), only if openreview in sources
- keywords: 5-12 English terms, include synonyms and method names
- intent_text must be English even if user writes Chinese
- reasoning must be Chinese"""


def _validate_plan(raw: dict, existing_sources: list[str] | None) -> dict:
    sources = _filter_allowed(_normalize_list(raw.get("sources")), CRAWL_SOURCES)
    if existing_sources:
        allowed = _filter_allowed(existing_sources, CRAWL_SOURCES)
        sources = [s for s in sources if s in allowed] or allowed
    if not sources:
        sources = ["arxiv"]

    categories = _filter_allowed(_normalize_list(raw.get("categories")), ARXIV_CATEGORIES)
    if "arxiv" in sources and not categories:
        categories = ["cs.AI", "cs.CL"]

    venues = _filter_allowed(_normalize_list(raw.get("openreview_venues")), OPENREVIEW_VENUES)
    if "openreview" in sources and not venues:
        venues = ["ICLR.cc/2025/Conference/-/Submission"]

    oa_types = _filter_allowed(_normalize_list(raw.get("openalex_venue_types")), OPENALEX_VENUE_TYPES)
    if "openalex" in sources and not oa_types:
        oa_types = ["conference", "journal"]

    oa_ranks = _filter_allowed(_normalize_list(raw.get("openalex_ccf_ranks")), OPENALEX_CCF_RANKS)
    if "openalex" in sources and not oa_ranks:
        oa_ranks = ["A", "B", "C"]

    year_to = _clamp_year(raw.get("openalex_year_to"), CURRENT_YEAR)
    year_from = _clamp_year(raw.get("openalex_year_from"), year_to - 2)
    if year_from > year_to:
        year_from = year_to - 2

    intent_text = (raw.get("intent_text") or "").strip()
    keywords = ", ".join(_normalize_list(raw.get("keywords")))
    reasoning = (raw.get("reasoning") or "").strip()
    suggested_name = (raw.get("suggested_name") or "").strip()
    venue_names = ", ".join(_normalize_list(raw.get("openalex_venue_names")))

    if "arxiv" not in sources:
        categories = []
    if "openreview" not in sources:
        venues = []
    if "openalex" not in sources:
        oa_types = []
        oa_ranks = []
        venue_names = ""

    return {
        "intent_text": intent_text,
        "keywords": keywords,
        "sources": sources,
        "categories": categories,
        "openreview_venues": venues,
        "openalex_venue_types": oa_types,
        "openalex_ccf_ranks": oa_ranks,
        "openalex_year_from": year_from if "openalex" in sources else None,
        "openalex_year_to": year_to if "openalex" in sources else None,
        "openalex_venue_names": venue_names,
        "suggested_name": suggested_name,
        "reasoning": reasoning,
    }


def format_plan_summary(plan: dict) -> str:
    """生成写入任务日志的简短摘要。"""
    parts = [
        f"数据源: {', '.join(plan.get('sources') or [])}",
    ]
    if plan.get("categories"):
        parts.append(f"arXiv 分类: {', '.join(plan['categories'])}")
    if plan.get("openreview_venues"):
        short_venues = [v.split("/")[0] for v in plan["openreview_venues"]]
        parts.append(f"OpenReview: {', '.join(short_venues)}")
    if plan.get("keywords"):
        parts.append(f"关键词: {plan['keywords']}")
    if plan.get("openalex_ccf_ranks"):
        parts.append(f"OpenAlex CCF: {','.join(plan['openalex_ccf_ranks'])}")
    if plan.get("reasoning"):
        parts.append(f"说明: {plan['reasoning']}")
    if plan.get("verification_summary"):
        parts.append(f"推荐论文核验: {plan['verification_summary']}")
    return " | ".join(parts)


def _parse_suggested_papers(raw: dict) -> list[dict]:
    items = raw.get("suggested_papers") or []
    out: list[dict] = []
    seen: set[str] = set()
    if not isinstance(items, list):
        return out
    for item in items:
        if isinstance(item, str):
            title = item.strip()
            reason = ""
        elif isinstance(item, dict):
            title = (item.get("title") or "").strip()
            reason = (item.get("reason") or "").strip()
        else:
            continue
        if not title:
            continue
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append({"title": title, "reason": reason})
        if len(out) >= 6:
            break
    return out


def build_smart_plan_fields(intent_text: str) -> dict:
    """执行 LLM 规划 + 推荐论文核验，返回可写入 CrawlTask 的字段。"""
    from src.services.suggested_paper_verifier import verify_suggested_papers

    plan = generate_crawl_plan(intent_text, existing_sources=None)
    verification = verify_suggested_papers(plan.get("suggested_papers") or [])
    plan_summary = plan["plan_summary"]
    if verification["total"]:
        plan_summary = f"{plan_summary} | 推荐论文核验: {verification['summary']}"
        for miss in verification.get("hallucinated") or []:
            logger.info("LLM suggested paper not found (hallucination): %s", miss.get("query_title"))

    return {
        "intent_text": plan["intent_text"] or intent_text,
        "keywords": plan["keywords"],
        "sources": ",".join(plan["sources"]),
        "categories": ", ".join(plan["categories"]),
        "openreview_venues": ",".join(plan["openreview_venues"]),
        "openalex_venue_types": ",".join(plan["openalex_venue_types"]),
        "openalex_ccf_ranks": ",".join(plan["openalex_ccf_ranks"]),
        "openalex_year_from": plan["openalex_year_from"],
        "openalex_year_to": plan["openalex_year_to"],
        "openalex_venue_names": plan["openalex_venue_names"],
        "plan_summary": plan_summary,
        "verified_suggestions_json": json.dumps(verification, ensure_ascii=False),
        "planning_status": "ready",
        "planning_error": "",
        "suggested_name": plan.get("suggested_name") or "",
    }


def apply_smart_plan_to_create(body: "CrawlTaskCreate") -> "CrawlTaskCreate":
    """同步规划（仅 /crawl-plan 等调试接口使用）。"""
    if not body.enable_smart_planning:
        return body

    fields = build_smart_plan_fields(body.intent_text)
    updates = {k: v for k, v in fields.items() if k not in ("planning_status", "planning_error", "suggested_name")}
    if fields.get("suggested_name") and not (body.name or "").strip():
        updates["name"] = fields["suggested_name"]
    return body.model_copy(update=updates)


def generate_crawl_plan(
    domain_description: str,
    *,
    existing_sources: list[str] | None = None,
) -> dict:
    """调用 DeepSeek 一次，返回校验后的抓取方案。"""
    desc = (domain_description or "").strip()
    if not desc:
        raise ValueError("请填写研究领域描述")

    constrained = None
    if existing_sources:
        constrained = _filter_allowed(existing_sources, CRAWL_SOURCES)
        if not constrained:
            constrained = None

    settings = get_settings()
    model = settings.translate_model or "deepseek-chat"
    client = _deepseek_client()

    user_content = desc
    if constrained:
        user_content += f"\n\n(用户已勾选数据源: {', '.join(constrained)}，请仅规划这些源的配置)"

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _build_system_prompt(constrained)},
            {"role": "user", "content": user_content},
        ],
        stream=False,
        temperature=0.3,
    )
    content = response.choices[0].message.content or ""
    raw = _parse_llm_json(content)
    if not raw:
        logger.warning("Crawl plan JSON parse failed: %s", content[:500])
        raise RuntimeError("智能规划返回格式异常，请重试")

    plan = _validate_plan(raw, constrained)
    plan["suggested_papers"] = _parse_suggested_papers(raw)
    plan["plan_summary"] = format_plan_summary(plan)
    return plan
