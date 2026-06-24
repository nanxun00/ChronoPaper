"""抓取相关性过滤：排除主题词 + 批量 LLM 严格同领域精过滤。"""
from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from src.services.crawl.semantic_matcher import paper_text
from src.settings import get_settings
from src.utils.logging_config import setup_logger

logger = setup_logger("CrawlRelevanceFilter")

LLM_FILTER_BATCH = 10
ABSTRACT_SNIPPET = 800


def _deepseek_client() -> OpenAI:
    settings = get_settings()
    api_key = settings.deepseek_api_key
    if not api_key:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY")
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


def _paper_blob(meta: dict[str, Any]) -> str:
    title = (meta.get("title") or "").strip()
    abstract = (meta.get("abstract") or "").strip()
    if isinstance(meta.get("authors"), list):
        authors = ", ".join(meta["authors"])
    else:
        authors = (meta.get("authors") or "").strip()
    parts = [title, authors, abstract]
    return "\n".join(p for p in parts if p).lower()


def abstract_has_suggested_keyword(meta: dict[str, Any], keyword_list: list[str]) -> bool:
    """标题+摘要是否包含 LLM 建议的任一关键词（不区分大小写）。"""
    if not keyword_list:
        return False
    blob = _paper_blob(meta)
    for kw in keyword_list:
        term = (kw or "").strip().lower()
        if len(term) >= 3 and term in blob:
            return True
        for piece in term.split():
            if len(piece) >= 4 and piece in blob:
                return True
    return False


def has_negative_keyword(meta: dict[str, Any], negative_keywords: list[str]) -> bool:
    if not negative_keywords:
        return False
    blob = _paper_blob(meta)
    hits = 0
    for kw in negative_keywords:
        term = (kw or "").strip().lower()
        if len(term) >= 4 and term in blob:
            hits += 1
    return hits >= 2


def batch_llm_relevance_filter(
    *,
    intent_text: str,
    keyword_list: list[str],
    negative_keywords: list[str],
    papers: list[dict[str, Any]],
) -> list[bool]:
    """批量判断论文是否与用户兴趣严格同领域。返回与 papers 等长的 bool 列表。"""
    if not papers:
        return []

    settings = get_settings()
    model = settings.translate_model or "deepseek-chat"
    client = _deepseek_client()

    lines = []
    for i, meta in enumerate(papers, 1):
        title = (meta.get("title") or "")[:200]
        abstract = (meta.get("abstract") or paper_text(meta))[:ABSTRACT_SNIPPET]
        venue = (meta.get("venue") or meta.get("categories") or "")[:120]
        venue_line = f"\n    Venue/Categories: {venue}" if venue else ""
        lines.append(f"[{i}] Title: {title}\n    Abstract: {abstract}{venue_line}")

    kw_text = ", ".join(keyword_list[:15]) if keyword_list else "(none)"
    neg_text = ", ".join(negative_keywords[:10]) if negative_keywords else "(none)"

    prompt = f"""The user is looking for papers in ONE specific research subfield. Their interest:

{intent_text[:1200]}

Core topic keywords: {kw_text}
Explicitly excluded topics: {neg_text}

For EACH paper below, decide whether it belongs to the SAME research subfield as the user's interest.

KEEP only if ALL of the following hold:
- The paper's PRIMARY problem, method, and evaluation target are in the same subfield (not merely "uses ML" or shares generic terms).
- The main contribution directly addresses what the user wants to read/follow in this field.
- It is not merely adjacent, tangential, or a general tool/method paper applied elsewhere.

REJECT if ANY of the following hold:
- Different task or application domain (e.g. generation vs segmentation, NLP vs vision-only, theory vs systems-only when user wants applied X).
- Only keyword overlap without same subfield focus (shared backbone/dataset names but different research goal).
- Broad survey/tutorial spanning many areas without centering on the user's subfield.
- Mainly about excluded topics above.
- Unclear or weak fit — when in doubt, REJECT.

Papers:
{chr(10).join(lines)}

Output ONLY JSON: {{"keep": [1, 3]}} with 1-based indices of papers to KEEP. Use an empty list if none match strictly."""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a strict academic subfield classifier for literature crawling. "
                        "Keep a paper only when it is clearly in the SAME subfield as the user's interest. "
                        "Reject borderline, adjacent, or keyword-only matches. Output JSON only."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            stream=False,
        )
        content = response.choices[0].message.content or ""
        data = _parse_llm_json(content)
        keep_indices: set[int] = set()
        for i in data.get("keep") or []:
            try:
                keep_indices.add(int(i))
            except (TypeError, ValueError):
                continue
    except Exception as exc:
        logger.warning("Batch LLM strict subfield filter failed: %s — rejecting batch", exc)
        return [False] * len(papers)

    result: list[bool] = []
    for i in range(1, len(papers) + 1):
        result.append(i in keep_indices)
    return result


def apply_keyword_and_llm_filter(
    *,
    intent_text: str,
    keyword_list: list[str],
    negative_keywords: list[str],
    ranked_candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """排除主题词后，全部候选经 LLM 严格同领域判定（无关键词直通）。"""
    if not ranked_candidates:
        return [], {"llm_reviewed": 0, "llm_pass": 0, "llm_reject": 0, "negative_reject": 0}

    need_llm: list[dict[str, Any]] = []
    negative_reject = 0

    for meta in ranked_candidates:
        if has_negative_keyword(meta, negative_keywords):
            negative_reject += 1
            continue
        need_llm.append(meta)

    llm_kept: list[dict[str, Any]] = []
    llm_reject = 0
    for i in range(0, len(need_llm), LLM_FILTER_BATCH):
        batch = need_llm[i : i + LLM_FILTER_BATCH]
        flags = batch_llm_relevance_filter(
            intent_text=intent_text,
            keyword_list=keyword_list,
            negative_keywords=negative_keywords,
            papers=batch,
        )
        for meta, keep in zip(batch, flags):
            if keep:
                if abstract_has_suggested_keyword(meta, keyword_list):
                    meta["relevance_source"] = "llm+keyword"
                else:
                    meta["relevance_source"] = "llm"
                llm_kept.append(meta)
            else:
                llm_reject += 1

    stats = {
        "llm_reviewed": len(need_llm),
        "llm_pass": len(llm_kept),
        "llm_reject": llm_reject,
        "negative_reject": negative_reject,
    }
    return llm_kept, stats
