"""按 SKILL.md / manifest.yaml 加载技能上下文。"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from src.services.skills.registry import SkillRecord, _parse_skill_md
from src.utils.logging_config import setup_logger

logger = setup_logger("SkillLoader")

_MAX_SKILL_CHARS = 28_000

_ROUTING_SECTION_RE = re.compile(
    r"## Routing protocol\b.*?(?=\n## [^\n]+|\Z)",
    re.DOTALL | re.IGNORECASE,
)
_READ_FILE_RE = re.compile(r"\bRead\s+(?:\[([^\]]+)\]|the mapped fragment[^\n]*|every file listed[^\n]*)", re.I)
_PLATFORM_ROUTING_REPLACEMENT = """## Routing protocol（ChronoPaper 平台改写）

manifest、core、Python 后端片段已由服务端预加载。需要更深层 reference 时，通过 **Skill Agent read 工具**（`<function=read>`）读取技能包内相对路径；平台会自动执行并回传内容。
作图/PPT 由后台 Python 脚本完成；你根据「技能多轮代码执行」结果向用户说明 PNG/PDF，勿列出磁盘绝对路径。
"""

# 平台 codegen 默认 Python 后端的技能
_PLATFORM_PYTHON_BACKEND_SKILLS = frozenset({"nature-figure"})


def _sanitize_skill_body_for_platform(body: str, skill_id: str) -> str:
    """Nature 等 SKILL 面向 Claude Agent 编写；在 ChronoPaper 中去掉会诱发工具幻觉的路由步骤。"""
    if _ROUTING_SECTION_RE.search(body):
        body = _ROUTING_SECTION_RE.sub(_PLATFORM_ROUTING_REPLACEMENT, body, count=1)
    body = _READ_FILE_RE.sub("（已由平台预加载，勿再读取）", body)
    body = re.sub(
        r"Do not try to apply the figure logic from memory or from this router\.[^\n]*",
        "平台已注入 figure 规则；勿在回复中重述路由步骤。",
        body,
        flags=re.I,
    )
    if skill_id in _PLATFORM_PYTHON_BACKEND_SKILLS:
        body = re.sub(
            r"If the user has \*\*not\*\* explicitly chosen[^\n]+stop\.[^\n]*",
            "本平台默认 backend=python（matplotlib），无需询问 Python/R。",
            body,
            flags=re.I,
        )
    return body


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


def load_skill_context(record: SkillRecord, *, platform: bool = True) -> str:
    skill_md = record.path / "SKILL.md"
    meta, body = _parse_skill_md(skill_md)
    if platform:
        body = _sanitize_skill_body_for_platform(body, record.id)
    sections = [f"# Skill: {record.name}\n\n{body}"]

    manifest = record.path / "manifest.yaml"
    if manifest.is_file():
        sections.extend(_load_manifest_fragments(record.path, manifest))

    if platform and record.id in _PLATFORM_PYTHON_BACKEND_SKILLS:
        py_frag = _read_fragment(record.path, "static/fragments/backend/python.md")
        if py_frag:
            sections.append(f"## Python backend（平台预加载）\n\n{py_frag}")

    shared_refs = re.findall(r"\.\./_shared/[^\s\)\]]+", body)
    for ref in shared_refs:
        text = _read_fragment(record.path, ref)
        if text:
            sections.append(text)

    combined = "\n\n---\n\n".join(s for s in sections if s.strip())
    return _truncate(combined)
