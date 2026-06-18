"""基于 Embedding 余弦相似度的语义相关分（0~100）。"""
from __future__ import annotations

import math
from typing import Any

from src.services.crawl_embedding import get_crawl_embedder

BATCH_SIZE = 20


def build_interest_text(intent_text: str, keywords: str) -> str:
    parts: list[str] = []
    intent = (intent_text or "").strip()
    kw = (keywords or "").strip()
    if intent:
        parts.append(intent)
    if kw:
        parts.append(f"Research keywords: {kw.replace('，', ',')}")
    return "\n".join(parts)


def paper_text(meta: dict[str, Any]) -> str:
    title = (meta.get("title") or "").strip()
    abstract = (meta.get("abstract") or "").strip()
    return f"{title}\n{abstract}".strip()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def cosine_to_semantic_score(sim: float) -> float:
    """将余弦相似度 [-1,1] 映射到 0~100。"""
    sim = max(-1.0, min(1.0, sim))
    return round((sim + 1.0) / 2.0 * 100.0, 1)


def encode_interest_vector(intent_text: str, keywords: str) -> list[float]:
    embedder = get_crawl_embedder()
    text = build_interest_text(intent_text, keywords)
    if not text:
        raise ValueError("兴趣描述与关键词不能同时为空")
    vecs = embedder.encode_queries([text])
    if not vecs:
        raise RuntimeError("兴趣向量编码失败")
    return vecs[0]


def batch_semantic_scores(interest_vec: list[float], candidates: list[dict[str, Any]]) -> list[float]:
    if not candidates:
        return []

    embedder = get_crawl_embedder()
    texts = [paper_text(m) or " " for m in candidates]
    scores: list[float] = []

    for i in range(0, len(texts), BATCH_SIZE):
        batch_texts = texts[i : i + BATCH_SIZE]
        vecs = embedder.encode(batch_texts)
        for vec in vecs:
            scores.append(cosine_to_semantic_score(cosine_similarity(interest_vec, vec)))

    return scores
