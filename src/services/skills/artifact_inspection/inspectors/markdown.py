"""Markdown / 文本产物解析与质检。"""
from __future__ import annotations

import re
from pathlib import Path

from src.services.skills.artifact_inspection.models import ArtifactInspectionResult

_HEADING_RE = re.compile(r"^#{1,3}\s+\S", re.MULTILINE)


def inspect_markdown(path: Path) -> ArtifactInspectionResult:
    rel = path.as_posix()
    if not path.is_file():
        return ArtifactInspectionResult(path=rel, kind="markdown", ok=False, errors=["文件不存在"])

    try:
        text = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError as exc:
        return ArtifactInspectionResult(
            path=rel,
            kind="markdown",
            ok=False,
            errors=[f"无法读取：{exc}"],
        )

    errors: list[str] = []
    headings = _HEADING_RE.findall(text)
    summary = [f"字数约 {len(text)}", f"标题数 {len(headings)}"]

    if len(text) < 800:
        errors.append("正文过短（<800 字），阅读稿/数据声明可能不完整")
    if len(headings) < 2:
        errors.append("缺少足够的章节标题（至少 2 个 # 标题）")

    first_line = text.split("\n", 1)[0][:120]
    summary.append(f"开头：{first_line}")

    return ArtifactInspectionResult(
        path=rel,
        kind="markdown",
        ok=not errors,
        errors=errors,
        summary_lines=summary,
    )
