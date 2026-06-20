"""通用文件存在性与大小检查。"""
from __future__ import annotations

from pathlib import Path

from src.services.skills.artifact_inspection.models import ArtifactInspectionResult


def inspect_generic_file(path: Path) -> ArtifactInspectionResult:
    rel = path.as_posix()
    if not path.is_file():
        return ArtifactInspectionResult(path=rel, kind="file", ok=False, errors=["文件不存在"])
    size = path.stat().st_size
    errors: list[str] = []
    if size < 64:
        errors.append("文件几乎为空")
    return ArtifactInspectionResult(
        path=rel,
        kind="file",
        ok=not errors,
        errors=errors,
        summary_lines=[f"大小 {size} bytes"],
    )
