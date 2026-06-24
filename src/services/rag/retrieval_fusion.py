"""双链路检索融合：向量主、图谱辅，带去重与分层 Prompt。"""
from __future__ import annotations

import hashlib
import re
from difflib import SequenceMatcher
from typing import Any

from src.services.graph.relation_labels import rel_label_zh

VECTOR_MAX_SLOTS = 5
GRAPH_MAX_SLOTS = 3
TOTAL_MAX_SLOTS = 8
TEXT_DEDUP_THRESHOLD = 0.8

# 架构/原理类：both 模式下不注入图谱
INTENTS_GRAPH_DISABLED = frozenset({"General_Summary"})

_RELATION_HINTS = {
    "IMPROVE_FROM": "（模型演进：后者改进自前者）",
    "DIFFERENT_WITH": "（实验对比基线：平行比较，非改进关系）",
    "USE_DATASET": "（论文使用数据集）",
    "EVALUATE_BY": "（论文采用评测指标）",
    "CITE": "（本文引用参考文献）",
}


def should_use_graph(intent: str, use_graph: bool) -> bool:
    if not use_graph:
        return False
    return (intent or "General_Summary") not in INTENTS_GRAPH_DISABLED


def simhash_similarity(a: str, b: str, bits: int = 64) -> float:
    """轻量 simhash，用于 chunk 去重。"""

    def _fingerprint(text: str) -> int:
        tokens = re.findall(r"\w+", (text or "").lower())
        if not tokens:
            return 0
        vec = [0] * bits
        for tok in tokens:
            h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
            for i in range(bits):
                vec[i] += 1 if (h >> i) & 1 else -1
        fp = 0
        for i in range(bits):
            if vec[i] > 0:
                fp |= 1 << i
        return fp

    fa, fb = _fingerprint(a), _fingerprint(b)
    if not fa and not fb:
        return 1.0
    dist = bin(fa ^ fb).count("1")
    return 1.0 - dist / bits


def _text_overlap(a: str, b: str) -> float:
    a, b = (a or "").strip(), (b or "").strip()
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 1.0
    return max(simhash_similarity(a, b), SequenceMatcher(None, a[:500], b[:500]).ratio())


def dedup_graph_chunks(
    graph_chunks: list[dict],
    kb_results: list[dict],
    *,
    threshold: float = TEXT_DEDUP_THRESHOLD,
) -> list[dict]:
    kb_texts = [str((r.get("entity") or {}).get("text") or "") for r in kb_results]
    kept: list[dict] = []
    for gc in graph_chunks or []:
        gtext = str(gc.get("chunk_text") or "")
        if any(_text_overlap(gtext, kt) >= threshold for kt in kb_texts):
            continue
        kept.append(gc)
    return kept


def _format_edge(edge: dict) -> str:
    rel_raw = edge.get("rel_type") or ""
    rel_zh = edge.get("type") or rel_label_zh(rel_raw)
    hint = _RELATION_HINTS.get(str(rel_raw).upper(), "")
    return (
        f"{edge.get('source_name')}和{edge.get('target_name')}"
        f"的关系是{rel_zh}{hint}"
    )


def build_fused_external(
    kb_results: list[dict],
    graph_results: dict,
    *,
    intent: str = "",
    use_graph: bool = True,
) -> str:
    """向量置顶、图谱补充置底，总量不超过 TOTAL_MAX_SLOTS 条 chunk 级素材。"""
    if not should_use_graph(intent, use_graph):
        graph_results = {}

    kb_slice = (kb_results or [])[:VECTOR_MAX_SLOTS]
    vector_parts: list[str] = []
    if kb_slice:
        kb_lines = [
            f"{r.get('id')}: {(r.get('entity') or {}).get('text', '')[:800]}"
            for r in kb_slice
        ]
        vector_parts.append("【主证据 · 知识库原文】\n" + "\n".join(kb_lines))

    graph_parts: list[str] = []
    chunks = dedup_graph_chunks(
        (graph_results.get("chunks") or [])[:GRAPH_MAX_SLOTS],
        kb_slice,
    )

    for key, title in (
        ("chain_summary", "模型时序链"),
        ("sota_summary", "领域SOTA"),
        ("cite_summary", "引用脉络（本文→参考文献）"),
    ):
        val = (graph_results.get(key) or "").strip()
        if val:
            graph_parts.append(f"【图谱补充 · {title}】\n{val}")

    edges = graph_results.get("edges") or []
    if edges:
        edge_text = "\n".join(_format_edge(e) for e in edges[:15])
        graph_parts.append("【图谱补充 · 关系】\n" + edge_text)

    if chunks:
        chunk_text = "\n".join(
            f"{c.get('chunk_id')}: {str(c.get('chunk_text') or '')[:600]}"
            for c in chunks[:GRAPH_MAX_SLOTS]
        )
        graph_parts.append("【图谱补充 · 原文片段】\n" + chunk_text)

    if not vector_parts and not graph_parts:
        return ""

    # 向量在上，图谱在下
    sections = vector_parts + graph_parts
    return "\n\n".join(sections)
