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
    seen_entities: set[tuple[str, str]] = set()
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
            if not raw or key in seen_entities:
                continue
            seen_entities.add(key)
            merged["raw_entities"].append(ent)

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

    merged["innovation_summary"] = "；".join(summaries[:3])
    return merged


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
