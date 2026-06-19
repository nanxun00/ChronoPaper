"""LLM 分章节实体关系抽取。"""
from __future__ import annotations

import json
import re
from typing import Any

from src.integrations.llm.prompts import graph_extraction_prompt_template
from src.services.graph.entity_normalize import EntityAliasCache, normalize_entity
from src.utils.logging_config import setup_logger

logger = setup_logger("GraphExtraction")

GRAPH_SECTION_TYPES = frozenset({"abstract", "method", "experiment"})

PHASE1_REL_TYPES = frozenset(
    {"PROPOSE", "IMPROVE_FROM", "DIFFERENT_WITH", "USE_DATASET", "EVALUATE_BY", "EXTEND_FROM"}
)


def _parse_json_block(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    logger.warning("Failed to parse LLM graph JSON: %s", text[:200])
    return {}


def _format_chunks_for_prompt(chunks: list[dict[str, Any]]) -> str:
    parts = []
    for c in chunks:
        parts.append(f"[chunk_id={c['chunk_id']}]\n{c.get('chunk_text') or ''}")
    return "\n\n---\n\n".join(parts)


def extract_section_batch(
    model,
    *,
    paper_id: str,
    title: str,
    abstract: str,
    section_type: str,
    chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    if not chunks:
        return {}
    prompt = graph_extraction_prompt_template.format(
        paper_id=paper_id,
        section_type=section_type,
        title=title or "",
        abstract=(abstract or "")[:2000],
        chunks=_format_chunks_for_prompt(chunks),
    )
    response = model.predict(prompt)
    content = response.content if hasattr(response, "content") else str(response)
    data = _parse_json_block(content)
    data.setdefault("raw_entities", [])
    data.setdefault("relations_raw", [])
    data.setdefault("task_domain", None)
    data.setdefault("innovation_summary", "")
    return data


def merge_extraction_batches(batches: list[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {
        "task_domain": None,
        "innovation_summary": "",
        "raw_entities": [],
        "relations_raw": [],
    }
    summaries: list[str] = []
    entity_map: dict[tuple[str, str], dict[str, Any]] = {}
    seen_rels: set[tuple[str, str, str, str]] = set()

    for batch in batches:
        td = batch.get("task_domain")
        if td and not merged["task_domain"]:
            merged["task_domain"] = td
        summary = (batch.get("innovation_summary") or "").strip()
        if summary:
            summaries.append(summary)

        for ent in batch.get("raw_entities") or []:
            raw = (ent.get("raw_name") or "").strip()
            et = ent.get("entity_type") or "Model"
            key = (raw.lower(), et)
            if not raw:
                continue
            desc = (ent.get("description") or "").strip()
            if key not in entity_map:
                entity_map[key] = dict(ent)
                entity_map[key]["description"] = desc
                continue
            existing = entity_map[key]
            old_desc = (existing.get("description") or "").strip()
            if len(desc) > len(old_desc):
                existing["description"] = desc

        for rel in batch.get("relations_raw") or []:
            rel_type = rel.get("rel_type") or ""
            if rel_type not in PHASE1_REL_TYPES:
                continue
            key = (
                rel.get("source_raw") or "",
                rel.get("target_raw") or "",
                rel_type,
                rel.get("chunk_id") or "",
            )
            if key in seen_rels:
                continue
            seen_rels.add(key)
            merged["relations_raw"].append(rel)

    merged["raw_entities"] = list(entity_map.values())
    merged["innovation_summary"] = "；".join(summaries[:3])
    return merged


def fallback_entity_description(name: str, entity_type: str, task_domain: str | None) -> str:
    """LLM 未返回描述时的简要中文兜底（保证 tooltip 不为空）。"""
    label = (name or "该实体").strip()
    td = (task_domain or "相关").strip()
    if entity_type == "Metric":
        return f"{label} 是用于{td}任务的评价指标。"
    if entity_type == "Dataset":
        return f"{label} 是用于{td}的数据集或成像模态。"
    return f"{label} 是用于{td}的模型或方法。"


def collect_entities_for_upsert(
    paper_id: str,
    merged: dict[str, Any],
    relations_std: list[dict[str, Any]],
    *,
    extra_neighbors: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """收集需写入 Neo4j 的实体：含 raw_entities 与 relations 端点（避免只更新部分节点）。"""
    from src.services.graph.entity_normalize import normalize_entity

    desc_by_name: dict[str, str] = {}
    type_by_name: dict[str, str] = {}

    for ent in merged.get("raw_entities") or []:
        et = ent.get("entity_type") or "Model"
        if et not in {"Model", "Dataset", "Metric"}:
            continue
        std_name = normalize_entity(ent.get("std_name") or ent.get("raw_name") or "", et)
        if not std_name:
            continue
        desc = (ent.get("description") or "").strip()
        if desc:
            desc_by_name[std_name] = desc
        type_by_name[std_name] = et

    for rel in relations_std:
        for std_key, type_key in (("source_std", "source_type"), ("target_std", "target_type")):
            std = rel.get(std_key) or ""
            et = rel.get(type_key) or "Model"
            if not std or std == paper_id or et not in {"Model", "Dataset", "Metric"}:
                continue
            type_by_name.setdefault(std, et)

    for nb in extra_neighbors or []:
        std = (nb.get("std_name") or nb.get("name") or "").strip()
        et = nb.get("entity_type") or "Model"
        if std and et in {"Model", "Dataset", "Metric"}:
            type_by_name.setdefault(std, et)

    result: list[dict[str, Any]] = []
    for std_name, et in type_by_name.items():
        result.append(
            {
                "std_name": std_name,
                "entity_type": et,
                "description": desc_by_name.get(std_name, ""),
            }
        )
    return result


def build_std_relations(
    paper_id: str,
    merged: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[tuple[str, str, str]], dict[str, list[str]]]:
    """返回 relations_std、待持久化别名、实体 chunk 映射。"""
    cache = EntityAliasCache.get()
    alias_pairs: list[tuple[str, str, str]] = []
    entity_chunks: dict[str, list[str]] = {}
    relations_std: list[dict[str, Any]] = []

    def _entity_key(name: str, entity_type: str) -> str:
        if entity_type == "Paper":
            return paper_id
        std = normalize_entity(name, entity_type)
        return std

    for ent in merged.get("raw_entities") or []:
        raw = ent.get("raw_name") or ""
        et = ent.get("entity_type") or "Model"
        std = normalize_entity(raw, et)
        cleaned = ent.get("std_name") or std
        if raw and std:
            alias_pairs.append((raw, std, et))
        chunk_id = ent.get("chunk_id")
        if std and chunk_id:
            entity_chunks.setdefault(std, [])
            if chunk_id not in entity_chunks[std]:
                entity_chunks[std].append(chunk_id)

    seen_rel: set[tuple[str, str, str]] = set()
    for rel in merged.get("relations_raw") or []:
        rel_type = rel.get("rel_type") or ""
        if rel_type not in PHASE1_REL_TYPES:
            continue
        source_type = rel.get("source_type") or "Model"
        target_type = rel.get("target_type") or "Model"
        source_std = _entity_key(rel.get("source_raw") or "", source_type)
        target_std = _entity_key(rel.get("target_raw") or "", target_type)
        if not source_std or not target_std:
            continue
        key = (source_std, target_std, rel_type)
        if key in seen_rel:
            continue
        seen_rel.add(key)
        chunk_id = rel.get("chunk_id")
        if chunk_id:
            for node in (source_std, target_std):
                if node != paper_id:
                    entity_chunks.setdefault(node, [])
                    if chunk_id not in entity_chunks[node]:
                        entity_chunks[node].append(chunk_id)
        relations_std.append(
            {
                "source_std": source_std,
                "target_std": target_std,
                "rel_type": rel_type,
                "source_type": source_type,
                "target_type": target_type,
                "chunk_id": chunk_id,
            }
        )

    cache.persist_aliases(alias_pairs)
    return relations_std, alias_pairs, entity_chunks
