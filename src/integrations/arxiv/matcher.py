"""任务兴趣描述与论文摘要的相似度打分。"""
from __future__ import annotations

import re

TOKEN_RE = re.compile(r"[a-zA-Z0-9\u4e00-\u9fff]+")


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in TOKEN_RE.findall(text) if len(t) >= 2}


def _split_keywords(keywords: str) -> list[str]:
    if not keywords:
        return []
    return [k.strip() for k in keywords.replace("，", ",").split(",") if k.strip()]


def compute_match_score(
    *,
    intent_text: str,
    keywords: str,
    categories: str,
    title: str,
    abstract: str,
    paper_categories: list[str],
) -> float:
    body = f"{title} {abstract}".lower()
    intent_tokens = _tokens(intent_text)
    body_tokens = _tokens(body)

    overlap = len(intent_tokens & body_tokens)
    token_score = min(50.0, overlap * 4.0)

    kw_score = 0.0
    for kw in _split_keywords(keywords):
        if kw.lower() in body:
            kw_score += 12.0
    kw_score = min(30.0, kw_score)

    cat_score = 0.0
    task_cats = [c.strip() for c in categories.replace("，", ",").split(",") if c.strip()]
    paper_cat_set = {c.lower() for c in paper_categories}
    for cat in task_cats:
        if cat.lower() in paper_cat_set:
            cat_score += 10.0
    cat_score = min(20.0, cat_score)

    return round(min(100.0, token_score + kw_score + cat_score), 1)
