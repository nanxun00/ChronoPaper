"""Skill 路由：显式选择 + LLM 自动分类。"""
from __future__ import annotations

import re

from src.services.skills.registry import SkillRecord
from src.utils.logging_config import setup_logger

logger = setup_logger("SkillRouter")


def _keyword_route(query: str, skills: list[SkillRecord]) -> str | None:
    q = (query or "").lower()
    rules: list[tuple[str, tuple[str, ...]]] = [
        ("nature-reader", ("读论文", "精读", "全文翻译", "中英文对照", "reader", "翻译这篇")),
        ("nature-polishing", ("润色", "polish", "学术英文", "nature style")),
        ("nature-writing", ("写摘要", "写引言", "manuscript", "论文写作", "起草")),
        ("nature-reviewer", ("审稿", "reviewer report", "预评审", "审稿意见")),
        ("nature-response", ("回复审稿", "rebuttal", "response letter", "逐点回复")),
        ("nature-citation", ("引用", "citation", "zotero", "参考文献检索")),
        ("nature-figure", ("作图", "figure", "投稿图", "scientific plot")),
        ("nature-paper2ppt", ("ppt", "汇报", "slides", "journal club")),
        ("nature-paper-to-patent", ("专利", "patent", "权利要求")),
        ("nature-academic-search", ("查文献", "literature search", "找论文", "doi")),
        ("nature-data", ("data availability", "数据可用性", "fair")),
    ]
    for skill_id, keys in rules:
        if not any(s.id == skill_id for s in skills):
            continue
        if any(k.lower() in q for k in keys):
            return skill_id
    return None


def resolve_skill_id(
    query: str,
    meta: dict,
    skills: list[SkillRecord],
    model=None,
) -> tuple[str | None, str]:
    """
    返回 (skill_id, route_mode)。
    route_mode: off | explicit | auto
    """
    mode = (meta.get("skill_mode") or "auto").strip().lower()
    explicit_id = (meta.get("skill_id") or "").strip() or None

    if mode == "off":
        return None, "off"

    enabled_ids = {s.id for s in skills if s.enabled}

    if mode == "explicit":
        if explicit_id and explicit_id in enabled_ids:
            return explicit_id, "explicit"
        return None, "off"

    # auto：用户在下拉里选了具体技能时仍走 explicit
    if explicit_id and explicit_id in enabled_ids:
        return explicit_id, "explicit"

    enabled = [s for s in skills if s.enabled]
    if not enabled:
        return None, "off"

    if model is not None:
        try:
            from src.integrations.llm.prompts import skill_route_prompt_template

            skill_lines = "\n".join(
                f"- {s.id}: {s.description[:280]}" for s in enabled
            )
            prompt = skill_route_prompt_template.format(
                skill_list=skill_lines,
                query=query,
            )
            raw = model.predict(prompt, stream=False)
            label = (getattr(raw, "content", None) or str(raw)).strip().lower()
            label = re.sub(r"[^a-z0-9\-_]", "", label.replace("none", ""))
            if label == "none" or not label:
                pass
            else:
                for s in enabled:
                    if s.id.lower() == label or label in s.id.lower():
                        return s.id, "auto"
        except Exception as exc:
            logger.debug("LLM skill route failed: %s", exc)

    kw = _keyword_route(query, enabled)
    if kw:
        return kw, "auto"
    return None, "off"
