"""抓取候选重排：复用 BGE Reranker 对兴趣查询与论文摘要做交叉编码打分。"""
from __future__ import annotations

from typing import Any

from src.config import Config
from src.integrations.llm.embedding import Reranker
from src.services.crawl.semantic_matcher import paper_text
from src.utils.logging_config import setup_logger

logger = setup_logger("CrawlReranker")

_cached_reranker = None
_cached_reranker_name: str | None = None
RERANK_BATCH = 16


def get_crawl_reranker():
    """加载 Reranker（抓取专用，不依赖 enable_reranker 开关）。"""
    global _cached_reranker, _cached_reranker_name
    cfg = Config()
    name = cfg.reranker or "bge-reranker-v2-m3"
    if _cached_reranker is not None and _cached_reranker_name == name:
        return _cached_reranker
    try:
        _cached_reranker = Reranker(cfg)
        _cached_reranker_name = name
        logger.info("Crawl reranker ready: %s", name)
        return _cached_reranker
    except Exception as exc:
        logger.warning("Crawl reranker load failed: %s", exc)
        return None


def rerank_candidates(query: str, candidates: list[dict[str, Any]]) -> list[tuple[float, dict[str, Any]]]:
    """对候选论文按 rerank 分数降序排列。失败时退回原顺序并附语义分占位。"""
    if not candidates:
        return []

    reranker = get_crawl_reranker()
    query = (query or "").strip()
    if not reranker or not query:
        return [(float(m.get("semantic_score") or 0), m) for m in candidates]

    scored: list[tuple[float, dict[str, Any]]] = []
    for i in range(0, len(candidates), RERANK_BATCH):
        batch = candidates[i : i + RERANK_BATCH]
        pairs = [[query, paper_text(m) or (m.get("title") or " ")] for m in batch]
        try:
            scores = reranker.compute_score(pairs, normalize=True)
            if not isinstance(scores, list):
                scores = [scores]
        except Exception as exc:
            logger.warning("Rerank batch failed: %s", exc)
            for m in batch:
                scored.append((float(m.get("semantic_score") or 0), m))
            continue
        for m, score in zip(batch, scores):
            m["rerank_score"] = round(float(score) * 100, 1)
            scored.append((float(score), m))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored
