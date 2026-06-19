"""按 SKILL.md / manifest.yaml 加载技能上下文。"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from src.services.skills.registry import SkillRecord, _parse_skill_md
from src.utils.logging_config import setup_logger

logger = setup_logger("SkillLoader")

_MAX_SKILL_CHARS = 28_000


def _read_fragment(skill_dir: Path, rel: str) -> str:
    rel = rel.strip().replace("\\", "/")
    if rel.startswith("../"):
        base = skill_dir.parent
        rel = rel[3:]
    else:
        base = skill_dir
    path = (base / rel).resolve()
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _load_manifest_fragments(skill_dir: Path, manifest_path: Path) -> list[str]:
    try:
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError):
        return []
    parts: list[str] = []
    for rel in data.get("always_load") or []:
        text = _read_fragment(skill_dir, str(rel))
        if text:
            parts.append(text)
    return parts


def _truncate(text: str, limit: int = _MAX_SKILL_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 80] + "\n\n…（技能上下文已截断）"


def load_skill_context(record: SkillRecord) -> str:
    skill_md = record.path / "SKILL.md"
    meta, body = _parse_skill_md(skill_md)
    sections = [f"# Skill: {record.name}\n\n{body}"]

    manifest = record.path / "manifest.yaml"
    if manifest.is_file():
        sections.extend(_load_manifest_fragments(record.path, manifest))

    shared_refs = re.findall(r"\.\./_shared/[^\s\)\]]+", body)
    for ref in shared_refs:
        text = _read_fragment(record.path, ref)
        if text:
            sections.append(text)

    combined = "\n\n---\n\n".join(s for s in sections if s.strip())
    return _truncate(combined)
