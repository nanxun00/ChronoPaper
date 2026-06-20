"""收集技能脚本在 output/ 下生成的产物，复制到 uploads 并生成访问 URL。"""
from __future__ import annotations

import mimetypes
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import quote

from src.utils.logging_config import setup_logger
from src.utils.paths import UPLOADS_DIR

logger = setup_logger("SkillArtifacts")

SKILL_ARTIFACTS_DIR = UPLOADS_DIR / "skills"
# nature-skills 常见产物目录：paper2ppt 用 output/，format-converter 默认 references/
# codegen 脚本有时 cwd=skill_root 却写入 .generated/output/runs/{run_id}/
SCAN_SUBDIRS = ("output", "references")
GENERATED_OUTPUT_SUBDIR = ".generated/output"
# 同步进技能目录的输入配图，不是脚本交付物
EXCLUDED_ARTIFACT_PREFIXES = ("output/assets/figures/",)
ALLOWED_SUFFIXES = frozenset(
    {
        ".pptx",
        ".png",
        ".pdf",
        ".docx",
        ".md",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".svg",
        ".bib",
        ".ris",
        ".nbib",
        ".json",
        ".csv",
        ".txt",
    }
)
IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"})
MAX_ARTIFACT_COUNT = 30
MAX_ARTIFACT_BYTES = 50 * 1024 * 1024


def _scan_roots(skill_root: Path) -> list[tuple[str, Path]]:
    skill_root = skill_root.resolve()
    roots: list[tuple[str, Path]] = []
    for sub in SCAN_SUBDIRS:
        path = skill_root / sub
        if path.is_dir():
            roots.append((sub, path))
    gen_output = skill_root / GENERATED_OUTPUT_SUBDIR
    if gen_output.is_dir():
        roots.append((GENERATED_OUTPUT_SUBDIR, gen_output))
    return roots


def _normalize_artifact_rel(rel: str) -> str:
    """对外 URL 使用 output/…，不暴露 .generated/ 前缀。"""
    normalized = rel.replace("\\", "/")
    prefix = f"{GENERATED_OUTPUT_SUBDIR}/"
    if normalized.startswith(prefix):
        return normalized[len(".generated/") :]
    return normalized


def snapshot_output_files(skill_root: Path) -> dict[str, float]:
    """记录各产物目录下已有文件的「子目录/相对路径」→ mtime。"""
    snap: dict[str, float] = {}
    for sub, root in _scan_roots(skill_root):
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in ALLOWED_SUFFIXES:
                continue
            rel = f"{sub}/{path.relative_to(root).as_posix()}"
            public_rel = _normalize_artifact_rel(rel)
            try:
                snap[public_rel] = path.stat().st_mtime
            except OSError:
                continue
    return snap


def _is_new_or_updated(rel: str, mtime: float, before: dict[str, float]) -> bool:
    prev = before.get(rel)
    if prev is None:
        return True
    return mtime > prev + 1e-6


def _artifact_kind(suffix: str) -> str:
    return "image" if suffix in IMAGE_SUFFIXES else "file"


def _public_url(user_id: str, run_id: str, rel_path: str) -> str:
    parts = [p for p in rel_path.replace("\\", "/").split("/") if p]
    encoded = "/".join(quote(p, safe="") for p in parts)
    safe_user = quote(user_id.replace("/", "_"), safe="")
    safe_run = quote(run_id.replace("/", "_"), safe="")
    return f"/uploads/skills/{safe_user}/{safe_run}/{encoded}"


def collect_skill_artifacts(
    skill_root: Path,
    before: dict[str, float],
    user_id: str,
    run_id: str,
    *,
    since_ts: float | None = None,
) -> list[dict[str, Any]]:
    """
    将 output/、references/ 中新增或更新的产物复制到 uploads/skills/{user}/{run_id}/。
    返回供 refs 使用的元数据列表。
    """
    scan_roots = _scan_roots(skill_root)
    if not scan_roots:
        return []

    dest_root = SKILL_ARTIFACTS_DIR / user_id.replace("/", "_") / run_id.replace("/", "_")
    dest_root.mkdir(parents=True, exist_ok=True)

    candidates: list[tuple[str, Path, float]] = []
    for sub, root in scan_roots:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            suffix = path.suffix.lower()
            if suffix not in ALLOWED_SUFFIXES:
                continue
            rel = f"{sub}/{path.relative_to(root).as_posix()}"
            public_rel = _normalize_artifact_rel(rel)
            if any(public_rel.startswith(prefix) for prefix in EXCLUDED_ARTIFACT_PREFIXES):
                continue
            try:
                mtime = path.stat().st_mtime
                size = path.stat().st_size
            except OSError:
                continue
            if size > MAX_ARTIFACT_BYTES:
                logger.warning("Skip oversized artifact %s (%s bytes)", public_rel, size)
                continue
            if since_ts is not None and mtime < since_ts - 1.0:
                continue
            if not _is_new_or_updated(public_rel, mtime, before):
                continue
            candidates.append((public_rel, path, mtime))

    candidates.sort(key=lambda x: x[2], reverse=True)
    artifacts: list[dict[str, Any]] = []

    for rel, src, _ in candidates[:MAX_ARTIFACT_COUNT]:
        dest = dest_root / Path(rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(src, dest)
        except OSError as exc:
            logger.warning("Copy artifact failed %s: %s", rel, exc)
            continue
        mime, _ = mimetypes.guess_type(src.name)
        artifacts.append(
            {
                "name": Path(rel).name,
                "path": rel,
                "url": _public_url(user_id, run_id, rel),
                "mime": mime or "application/octet-stream",
                "size": dest.stat().st_size,
                "kind": _artifact_kind(src.suffix.lower()),
            }
        )

    if artifacts:
        logger.info("Collected %d skill artifacts for run %s", len(artifacts), run_id)
    return artifacts


def artifacts_context_block(artifacts: list[dict[str, Any]]) -> str:
    if not artifacts:
        return ""
    lines = ["## 技能生成的文件", "以下文件已保存，可在对话引用区下载或预览："]
    for item in artifacts:
        lines.append(f"- {item['name']} ({item['kind']}, {item['size']} bytes): {item['url']}")
    return "\n".join(lines)
