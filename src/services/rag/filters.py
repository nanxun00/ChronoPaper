"""Milvus 标量 filter 生成（硬编码 kb_id + 权限，LLM 仅提供 JSON 参数）。"""
from __future__ import annotations

from typing import Any


from src.services.rag.owner_scope import milvus_owner_user_id


def build_milvus_filter(
    filter_json: dict[str, Any] | None,
    *,
    kb_id: str,
    user_id: int | str = 0,
) -> str:
    conds: list[str] = [
        f"kb_id == '{kb_id}'",
        f"(resource_type == 'public' or owner_user_id == {milvus_owner_user_id(user_id)})",
    ]
    data = filter_json or {}

    year_start = data.get("year_start")
    year_end = data.get("year_end")
    if year_start is not None:
        conds.append(f"year >= {int(year_start)}")
    if year_end is not None:
        conds.append(f"year <= {int(year_end)}")

    ccf_rank = data.get("ccf_rank") or []
    if isinstance(ccf_rank, list) and ccf_rank:
        ranks = ", ".join(f"'{str(r)}'" for r in ccf_rank)
        conds.append(f"ccf_rank in [{ranks}]")

    section_type = data.get("section_type")
    if section_type:
        conds.append(f"section_type == '{section_type}'")

    block_type = data.get("block_type")
    if block_type:
        conds.append(f"block_type == '{block_type}'")

    task_domain = data.get("task_domain")
    if task_domain:
        conds.append(f"task_domain == '{task_domain}'")

    keywords = data.get("keywords") or []
    if isinstance(keywords, list):
        for kw in keywords:
            kw = str(kw).strip()
            if kw:
                safe = kw.replace("'", "\\'")
                conds.append(f"array_contains(keywords, '{safe}')")

    return " and ".join(conds)
