"""图片类产物质检。"""
from __future__ import annotations

from pathlib import Path

from src.services.skills.artifact_inspection.models import ArtifactInspectionResult

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".pdf", ".tiff", ".tif"}


def inspect_image_file(path: Path) -> ArtifactInspectionResult:
    rel = path.as_posix()
    if not path.is_file():
        return ArtifactInspectionResult(path=rel, kind="image", ok=False, errors=["文件不存在"])

    size = path.stat().st_size
    errors: list[str] = []
    summary = [f"大小 {size} bytes"]

    if size < 1024:
        errors.append("文件过小，可能为空图或生成失败")

    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        try:
            from PIL import Image

            with Image.open(path) as img:
                summary.append(f"尺寸 {img.size[0]}×{img.size[1]}")
                if max(img.size) < 200:
                    errors.append("图片分辨率过低，不适合论文配图")
        except Exception as exc:
            errors.append(f"无法打开图片：{exc}")

    return ArtifactInspectionResult(
        path=rel,
        kind="image",
        ok=not errors,
        errors=errors,
        summary_lines=summary,
    )


def inspect_image_dir(dir_path: Path) -> list[ArtifactInspectionResult]:
    if not dir_path.is_dir():
        return []
    files = sorted(
        p for p in dir_path.rglob("*") if p.is_file() and p.suffix.lower() in _IMAGE_SUFFIXES
    )
    if not files:
        return [
            ArtifactInspectionResult(
                path=dir_path.as_posix(),
                kind="image",
                ok=False,
                errors=["目录下未找到 png/pdf/svg 等配图文件"],
            )
        ]
    # 检查最大的 3 个文件
    files.sort(key=lambda p: p.stat().st_size, reverse=True)
    return [inspect_image_file(p) for p in files[:3]]
