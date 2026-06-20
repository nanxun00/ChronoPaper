"""解析技能产物并生成可写回 LLM 的质检报告。"""
from __future__ import annotations

from pathlib import Path

from src.services.skills.artifact_inspection.inspectors.docx import inspect_docx
from src.services.skills.artifact_inspection.inspectors.generic import inspect_generic_file
from src.services.skills.artifact_inspection.inspectors.image import (
    inspect_image_dir,
    inspect_image_file,
)
from src.services.skills.artifact_inspection.inspectors.markdown import inspect_markdown
from src.services.skills.artifact_inspection.inspectors.pptx import inspect_pptx
from src.services.skills.artifact_inspection.models import (
    ArtifactInspectionResult,
    SkillInspectionReport,
)
from src.services.skills.artifact_inspection.registry import (
    get_deliverable_spec,
    resolve_deliverable_paths,
)
from src.services.skills.generated_runner import _FILE_OUTPUT_SKILLS

_INSPECTOR_BY_SUFFIX = {
    ".pptx": "pptx",
    ".docx": "docx",
    ".md": "markdown",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".svg": "image",
    ".pdf": "image",
    ".tif": "image",
    ".tiff": "image",
}


def skill_supports_artifact_inspection(skill_id: str) -> bool:
    return skill_id in _FILE_OUTPUT_SKILLS or get_deliverable_spec(skill_id) is not None


def _inspect_path(
    path: Path,
    *,
    inspector: str,
    query: str,
) -> ArtifactInspectionResult:
    if inspector == "pptx" or path.suffix.lower() == ".pptx":
        return inspect_pptx(path, query=query)
    if inspector == "docx" or path.suffix.lower() == ".docx":
        return inspect_docx(path)
    if inspector == "markdown" or path.suffix.lower() in {".md", ".txt"}:
        return inspect_markdown(path)
    if inspector == "image":
        if path.is_dir():
            results = inspect_image_dir(path)
            if not results:
                return ArtifactInspectionResult(
                    path=path.as_posix(),
                    kind="image",
                    ok=False,
                    errors=["目录为空"],
                )
            merged_errors: list[str] = []
            merged_summary: list[str] = []
            for r in results:
                merged_errors.extend(r.errors)
                merged_summary.extend(r.summary_lines)
            return ArtifactInspectionResult(
                path=path.as_posix(),
                kind="image",
                ok=not merged_errors,
                errors=merged_errors,
                summary_lines=merged_summary,
            )
        return inspect_image_file(path)
    return inspect_generic_file(path)


def _collect_paths(skill_root: Path, rel: str) -> list[Path]:
    skill_root = skill_root.resolve()
    target = skill_root / rel.replace("\\", "/")
    if target.is_file():
        return [target]
    if target.is_dir():
        files = [
            p
            for p in target.rglob("*")
            if p.is_file() and p.suffix.lower() in _INSPECTOR_BY_SUFFIX
        ]
        return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)
    return []


def inspect_skill_deliverables(
    skill_id: str,
    skill_root: Path,
    run_id: str,
    *,
    query: str = "",
) -> SkillInspectionReport:
    """解析主交付物，返回是否达标及可写回 prompt 的摘要。"""
    spec = get_deliverable_spec(skill_id)
    if spec is None:
        return SkillInspectionReport(skill_id=skill_id, run_id=run_id, ok=True)

    rel_paths = resolve_deliverable_paths(spec, run_id)
    results: list[ArtifactInspectionResult] = []
    missing: list[str] = []

    for rel in rel_paths:
        paths = _collect_paths(skill_root, rel)
        if not paths:
            if rel.endswith("/"):
                missing.append(f"{rel} 下无任何可检文件")
            else:
                missing.append(rel)
            continue

        inspector = spec.inspector
        if rel.endswith("/"):
            dir_path = skill_root / rel.rstrip("/")
            results.append(_inspect_path(dir_path, inspector=inspector, query=query))
        else:
            for path in paths[: spec.min_count if spec.min_count > 1 else 1]:
                results.append(
                    _inspect_path(path, inspector=inspector, query=query)
                )

    ok = not missing and all(r.ok for r in results)
    return SkillInspectionReport(
        skill_id=skill_id,
        run_id=run_id,
        ok=ok,
        results=results,
        missing_deliverables=missing,
    )
