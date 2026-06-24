"""DOCX 产物解析与质检。"""
from __future__ import annotations

from pathlib import Path

from src.services.skills.artifact_inspection.models import ArtifactInspectionResult


def inspect_docx(path: Path) -> ArtifactInspectionResult:
    rel = path.as_posix()
    if not path.is_file():
        return ArtifactInspectionResult(path=rel, kind="docx", ok=False, errors=["文件不存在"])

    try:
        from docx import Document

        doc = Document(str(path))
        paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    except Exception as exc:
        return ArtifactInspectionResult(
            path=rel,
            kind="docx",
            ok=False,
            errors=[f"无法读取 DOCX：{exc}"],
        )

    errors: list[str] = []
    summary = [f"段落数 {len(paras)}", f"总字数约 {sum(len(p) for p in paras)}"]
    if len(paras) < 8:
        errors.append("段落过少，专利文稿可能不完整（建议至少 8 段实质性内容）")
    if sum(len(p) for p in paras) < 500:
        errors.append("总字数过少，可能仅为占位模板")

    preview = " | ".join(paras[:3])[:200]
    if preview:
        summary.append(f"开头：{preview}")

    return ArtifactInspectionResult(
        path=rel,
        kind="docx",
        ok=not errors,
        errors=errors,
        summary_lines=summary,
    )
