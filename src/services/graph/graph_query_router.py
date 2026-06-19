"""图谱检索意图路由与结果组装。"""
from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import Any

from src.services.graph.entity_normalize import clean_entity_name, normalize_entity
from src.services.graph.relation_labels import rel_label_zh
from src.utils.logging_config import setup_logger

logger = setup_logger("GraphQueryRouter")

GRAPH_INTENTS = frozenset({
    "Model_Improve",
    "Dataset_Use",
    "Metric_Eval",
    "Compare_SOTA",
    "Citation_Relate",
    "General_Summary",
})

MAX_GRAPH_CHUNKS = 8
MAX_GRAPH_EDGES = 15
MAX_CHUNK_IDS_FETCH = 24
ENTITY_SIM_THRESHOLD = 0.7

_INTENT_CHUNK_CAP: dict[str, int] = {
    "Dataset_Use": 3,
    "Metric_Eval": 5,
    "Model_Improve": 5,
    "Citation_Relate": 3,
    "Compare_SOTA": 0,
    "General_Summary": 0,
}

_INTENT_EDGE_CAP: dict[str, int] = {
    "Model_Improve": 10,
    "Dataset_Use": 15,
    "Metric_Eval": 15,
    "Citation_Relate": 15,
    "Compare_SOTA": 0,
    "General_Summary": 0,
}

_INTENT_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("Citation_Relate", ("引用", "cite", "citation", "参考文献", "相关工作", "被引")),
    ("Metric_Eval", ("指标", "dice", "ssim", "assd", "hd95", "hausdorff", "评测", "评估", "metric")),
    ("Dataset_Use", ("数据集", "dataset", "brats", "模态", "flair", "vs dataset", "成像")),
    ("Compare_SOTA", ("sota", "对比", "优于", "基线", "benchmark", "比较", "difference")),
    ("Model_Improve", ("改进", "改进自", "基于", "提出", "improve", "extend", "延伸")),
]

_SECTION_BY_INTENT: dict[str, frozenset[str]] = {
    "Metric_Eval": frozenset({"experiment", "result"}),
    "Dataset_Use": frozenset({"experiment", "result"}),
    "Model_Improve": frozenset({"method", "intro"}),
    "Compare_SOTA": frozenset({"experiment", "method"}),
    "Citation_Relate": frozenset({"reference", "intro"}),
    "General_Summary": frozenset({"abstract", "intro", "method", "title"}),
}


def sanitize_entity_raw(name: str) -> str:
    """清洗 LLM 抽取实体中的乱码与不可打印字符。"""
    s = (name or "").strip()
    if not s:
        return ""
    s = s.replace("\ufffd", "")
    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", s):
        return ""
    printable = sum(1 for c in s if c.isprintable())
    if len(s) > 2 and printable / len(s) < 0.75:
        return ""
    # 乱码片段：连续非 CJK/拉丁/数字则丢弃
    cleaned = re.sub(r"[^\w\s\-\.·（）()a-zA-Z0-9\u4e00-\u9fff]", "", s)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) < 2:
        return ""
    return cleaned


def entity_match_score(token: str, candidate: str) -> float:
    a = clean_entity_name(token)
    b = clean_entity_name(candidate)
    if not a or not b:
        return 0.0
    if a == b or a in b or b in a:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def parse_typed_entities_raw(text: str) -> list[dict[str, str]]:
    text = (text or "").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
        items = data.get("entities") if isinstance(data, dict) else None
        if isinstance(items, list):
            out = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                raw = sanitize_entity_raw(str(item.get("raw_name") or ""))
                et = str(item.get("entity_type") or "Model").strip()
                if raw and et in {"Model", "Dataset", "Metric", "Paper"}:
                    out.append({"raw_name": raw, "entity_type": et})
            return out
    except json.JSONDecodeError:
        pass
    return []


def classify_intent_by_keywords(query: str) -> str:
    q = (query or "").lower()
    for intent, keys in _INTENT_KEYWORDS:
        if any(k.lower() in q for k in keys):
            return intent
    return "General_Summary"


def classify_graph_intent(query: str, model) -> str:
    from src.integrations.llm.prompts import graph_intent_prompt_template

    try:
        raw = model.predict(graph_intent_prompt_template.format(text=query), stream=False)
        label = (getattr(raw, "content", None) or str(raw)).strip()
        label = re.sub(r"[^A-Za-z_]", "", label)
        for intent in GRAPH_INTENTS:
            if intent.lower() in label.lower() or label == intent:
                return intent
    except Exception as exc:
        logger.debug("LLM intent classify failed: %s", exc)
    return classify_intent_by_keywords(query)


def resolve_typed_entities(
    typed_entities: list[dict[str, str]],
    store,
    *,
    kb_id: str,
    user_id: str | int,
) -> dict[str, list[str]]:
    """将抽取实体映射到图谱标准名，并按相似度阈值过滤。"""
    buckets: dict[str, list[str]] = {
        "Model": [],
        "Dataset": [],
        "Metric": [],
        "Paper": [],
    }
    for item in typed_entities or []:
        raw = sanitize_entity_raw((item.get("raw_name") or "").strip())
        et = item.get("entity_type") or "Model"
        if not raw or et not in buckets:
            continue
        std = normalize_entity(raw, et)
        candidates = [std] if std else []
        if et == "Model":
            candidates.extend(store.find_models_by_keyword(raw, kb_id=kb_id, user_id=user_id, limit=3))
        else:
            candidates.extend(store.find_entities_by_keyword(et, raw, kb_id=kb_id, limit=3))
        best_name = ""
        best_score = 0.0
        for cand in candidates:
            score = entity_match_score(raw, cand)
            if score > best_score:
                best_score = score
                best_name = cand
        if best_name and best_score >= ENTITY_SIM_THRESHOLD:
            if best_name not in buckets[et]:
                buckets[et].append(best_name)
    return buckets


def _filter_chunks_by_section(chunks: list[dict], intent: str) -> list[dict]:
    allowed = _SECTION_BY_INTENT.get(intent)
    if not allowed:
        return chunks
    filtered = [
        c for c in chunks
        if (c.get("section_type") or "").lower() in allowed
        or (intent in {"Metric_Eval", "Dataset_Use"} and "<table>" in (c.get("chunk_text") or "").lower())
    ]
    return filtered or chunks


def _cap_chunk_ids(chunk_ids: list[str], limit: int = MAX_CHUNK_IDS_FETCH) -> list[str]:
    out: list[str] = []
    for cid in chunk_ids or []:
        if cid and cid not in out:
            out.append(cid)
        if len(out) >= limit:
            break
    return out


def _empty_results() -> dict[str, Any]:
    return {
        "nodes": [],
        "edges": [],
        "chunks": [],
        "chain_summary": "",
        "sota_summary": "",
        "cite_summary": "",
        "intent": "",
    }


def _assemble_response(
    *,
    intent: str,
    nodes: list[dict],
    edges: list[dict],
    chunk_ids: list[str],
    fetch_chunks_fn,
    chain_summary: str = "",
    sota_summary: str = "",
    cite_summary: str = "",
) -> dict[str, Any]:
    edge_cap = _INTENT_EDGE_CAP.get(intent, MAX_GRAPH_EDGES)
    chunk_cap = _INTENT_CHUNK_CAP.get(intent, MAX_GRAPH_CHUNKS)
    edges = edges[:edge_cap]
    if chunk_cap <= 0:
        chunk_ids = []
    else:
        chunk_ids = _cap_chunk_ids(chunk_ids)
    chunks = fetch_chunks_fn(chunk_ids) if chunk_ids else []
    chunks = _filter_chunks_by_section(chunks, intent)[:chunk_cap]
    return {
        "nodes": nodes,
        "edges": edges,
        "chunks": chunks,
        "chain_summary": chain_summary,
        "sota_summary": sota_summary,
        "cite_summary": cite_summary,
        "intent": intent,
    }


def run_intent_graph_query(
    store,
    query: str,
    intent: str,
    entities: dict[str, list[str]],
    *,
    kb_id: str,
    user_id: str | int,
    task_domain: str | None,
    fetch_chunks_fn,
) -> dict[str, Any]:
    models = entities.get("Model") or []
    datasets = entities.get("Dataset") or []
    metrics = entities.get("Metric") or []
    papers = entities.get("Paper") or []

    nodes: list[dict] = []
    edges: list[dict] = []
    chunk_ids: list[str] = []
    chain_summary = ""
    sota_summary = ""
    cite_summary = ""

    def add_node(nid: str, name: str, ntype: str) -> None:
        if not nid or any(n["id"] == nid for n in nodes):
            return
        nodes.append({"id": nid, "name": name, "type": ntype})

    def add_edge(src: str, tgt: str, rel_type: str, chunk_id: str | None = None) -> None:
        if not src or not tgt:
            return
        edges.append({
            "id": f"{src}-{tgt}-{rel_type}",
            "type": rel_label_zh(rel_type),
            "rel_type": rel_type,
            "source_id": src,
            "target_id": tgt,
            "source_name": src,
            "target_name": tgt,
        })
        if chunk_id and chunk_id not in chunk_ids:
            chunk_ids.append(chunk_id)

    paper_ids = list(papers)
    if models:
        paper_ids = list(dict.fromkeys(paper_ids + store.resolve_paper_ids_for_models(
            models, kb_id=kb_id, user_id=user_id,
        )))

    if intent == "Model_Improve":
        if not models:
            models = store.find_models_by_keyword(query, kb_id=kb_id, user_id=user_id, limit=3)
        graph_data = store.query_temporal_chain(models, kb_id=kb_id, user_id=user_id, limit=10)
        chain_parts = []
        for m in graph_data.get("models") or []:
            name = m.get("name")
            if name:
                add_node(name, name, "Model")
                if m.get("birth_year"):
                    chain_parts.append(f"{name}({m['birth_year']})")
        for e in graph_data.get("edges") or []:
            src, tgt = e.get("source"), e.get("target")
            if src:
                add_node(src, src, "Model")
            if tgt:
                add_node(tgt, tgt, "Model")
            add_edge(src, tgt, e.get("rel_type") or "IMPROVE_FROM", e.get("chunk_id"))
        for cid in graph_data.get("chunk_ids") or []:
            if cid not in chunk_ids:
                chunk_ids.append(cid)
        chain_summary = " → ".join(chain_parts)

    elif intent == "Dataset_Use":
        if not datasets and not models:
            datasets = store.find_entities_by_keyword("Dataset", query, kb_id=kb_id, limit=3)
        data = store.query_use_datasets(
            kb_id=kb_id,
            user_id=user_id,
            model_names=models,
            dataset_names=datasets,
            limit=MAX_GRAPH_EDGES,
        )
        for row in data.get("rows") or []:
            add_node(row.get("dataset_name", ""), row.get("dataset_name", ""), "Dataset")
            add_node(row.get("paper_id", ""), row.get("paper_name") or row.get("paper_id", ""), "Paper")
            add_edge(
                row.get("paper_name") or row.get("paper_id"),
                row.get("dataset_name"),
                "USE_DATASET",
                row.get("rel_chunk_id"),
            )
        for cid in data.get("chunk_ids") or []:
            if cid not in chunk_ids:
                chunk_ids.append(cid)

    elif intent == "Metric_Eval":
        if not metrics and not models:
            metrics = store.find_entities_by_keyword("Metric", query, kb_id=kb_id, limit=3)
        data = store.query_evaluate_metrics(
            kb_id=kb_id,
            user_id=user_id,
            model_names=models,
            metric_names=metrics,
            limit=MAX_GRAPH_EDGES,
        )
        for row in data.get("rows") or []:
            add_node(row.get("metric_name", ""), row.get("metric_name", ""), "Metric")
            add_node(row.get("paper_id", ""), row.get("paper_name") or row.get("paper_id", ""), "Paper")
            add_edge(
                row.get("paper_name") or row.get("paper_id"),
                row.get("metric_name"),
                "EVALUATE_BY",
                row.get("rel_chunk_id"),
            )
        for cid in data.get("chunk_ids") or []:
            if cid not in chunk_ids:
                chunk_ids.append(cid)

    elif intent == "Compare_SOTA":
        domain = task_domain or ""
        sota_data = store.query_sota_models(
            task_domain=domain,
            kb_id=kb_id,
            user_id=user_id,
            limit=20,
        ) if domain else {"models": [], "chunk_ids": []}
        if not sota_data.get("models") and domain:
            sota_data = store.query_sota_models(
                task_domain=domain,
                kb_id=kb_id,
                user_id=user_id,
                limit=20,
            )
        sota_lines = []
        for row in sota_data.get("models") or []:
            model = row.get("model")
            if not model:
                continue
            add_node(model, model, "Model")
            ds = ", ".join(d for d in (row.get("datasets") or []) if d)
            mets = ", ".join(x for x in (row.get("metrics") or []) if x)
            sota_lines.append(
                f"{model}({row.get('year') or '?'}) | 论文:{row.get('paper_title') or '-'} "
                f"| 数据集:{ds or '-'} | 指标:{mets or '-'}"
            )
            pid = row.get("paper_id")
            if pid:
                add_node(pid, row.get("paper_title") or pid, "Paper")
        sota_summary = "\n".join(sota_lines)

    elif intent == "Citation_Relate":
        if not paper_ids and models:
            paper_ids = store.resolve_paper_ids_for_models(models, kb_id=kb_id, user_id=user_id)
        cite_data = store.query_citation_network(
            paper_ids,
            kb_id=kb_id,
            user_id=user_id,
            hops=1,
            limit=MAX_GRAPH_EDGES,
            direction="outgoing",
        ) if paper_ids else {"papers": [], "edges": [], "chunk_ids": []}
        cite_lines = []
        for p in cite_data.get("papers") or []:
            pid = p.get("paper_id")
            pname = p.get("name") or p.get("title") or pid
            if pid:
                add_node(pid, pname, "Paper")
        for e in cite_data.get("edges") or []:
            src = e.get("source_name") or e.get("source")
            tgt = e.get("target_name") or e.get("target")
            cite_lines.append(f"{src} → 引用 → {tgt}")
            add_edge(src, tgt, "CITE")
        for cid in cite_data.get("chunk_ids") or []:
            if cid not in chunk_ids:
                chunk_ids.append(cid)
        cite_summary = "\n".join(cite_lines[:15])

    else:  # General_Summary — 不扩实体链，等同纯向量
        return _empty_results() | {"intent": intent}

    if not nodes and not edges and not chunk_ids:
        return _empty_results() | {"intent": intent}

    return _assemble_response(
        intent=intent,
        nodes=nodes,
        edges=edges,
        chunk_ids=chunk_ids,
        fetch_chunks_fn=fetch_chunks_fn,
        chain_summary=chain_summary,
        sota_summary=sota_summary,
        cite_summary=cite_summary,
    )
