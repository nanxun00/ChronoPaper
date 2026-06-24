"""项目内静态资源路径（不依赖进程 cwd）。"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPLOADS_DIR = PROJECT_ROOT / "uploads"
PAPERS_DIR = UPLOADS_DIR / "papers"

PAPER_PDF_NAME = "paper.pdf"
PAPER_MD_NAME = "content.md"
PAPER_IMAGES_DIR_NAME = "images"
MINERU_WORK_DIR_NAME = ".mineru_work"


def paper_safe_id(arxiv_id: str) -> str:
    return arxiv_id.replace("/", "_").replace(":", "_")


def paper_pdf_filename(arxiv_id: str) -> str:
    """旧版扁平布局文件名（兼容）。"""
    return f"{paper_safe_id(arxiv_id)}.pdf"


def paper_dir(arxiv_id: str) -> Path:
    return PAPERS_DIR / paper_safe_id(arxiv_id)


def paper_pdf_path(arxiv_id: str) -> Path:
    return paper_dir(arxiv_id) / PAPER_PDF_NAME


def paper_md_path(arxiv_id: str) -> Path:
    return paper_dir(arxiv_id) / PAPER_MD_NAME


def paper_images_dir(arxiv_id: str) -> Path:
    return paper_dir(arxiv_id) / PAPER_IMAGES_DIR_NAME


def legacy_paper_pdf_path(arxiv_id: str) -> Path:
    return PAPERS_DIR / paper_pdf_filename(arxiv_id)


def mineru_work_dir(arxiv_id: str) -> Path:
    return paper_dir(arxiv_id) / MINERU_WORK_DIR_NAME


def ensure_papers_dir() -> Path:
    PAPERS_DIR.mkdir(parents=True, exist_ok=True)
    return PAPERS_DIR


def ensure_paper_dir(arxiv_id: str) -> Path:
    root = paper_dir(arxiv_id)
    root.mkdir(parents=True, exist_ok=True)
    paper_images_dir(arxiv_id).mkdir(parents=True, exist_ok=True)
    return root


def resolve_existing_file(path: str | os.PathLike | None) -> str | None:
    if not path:
        return None
    raw = str(path).strip()
    if not raw:
        return None

    candidates: list[Path] = [Path(raw)]
    if not os.path.isabs(raw):
        candidates.append(PROJECT_ROOT / raw)
        candidates.append(PAPERS_DIR / Path(raw).name)

    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = str(candidate.resolve())
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        if os.path.isfile(resolved):
            return resolved
    return None


def resolve_paper_pdf_file(arxiv_id: str, stored_path: str | None = None) -> str | None:
    """解析论文 PDF 路径：优先新目录布局，再兼容 DB 记录与旧扁平文件。"""
    candidates: list[Path | str] = [
        paper_pdf_path(arxiv_id),
        legacy_paper_pdf_path(arxiv_id),
    ]
    if stored_path:
        candidates.insert(0, stored_path)

    seen: set[str] = set()
    for candidate in candidates:
        resolved = resolve_existing_file(candidate)
        if not resolved or resolved in seen:
            continue
        seen.add(resolved)
        return resolved
    return None


def resolve_paper_md_file(arxiv_id: str) -> str | None:
    return resolve_existing_file(paper_md_path(arxiv_id))


def migrate_legacy_pdf_to_paper_dir(arxiv_id: str, stored_path: str | None = None) -> str | None:
    """将旧版扁平 PDF 迁移到 uploads/papers/{id}/paper.pdf。"""
    existing = resolve_paper_pdf_file(arxiv_id, stored_path)
    if not existing:
        return None

    target = paper_pdf_path(arxiv_id)
    if existing == str(target.resolve()):
        return existing

    ensure_paper_dir(arxiv_id)
    shutil.copy2(existing, target)
    return str(target.resolve())


def remove_paper_storage(arxiv_id: str, stored_path: str | None = None) -> int:
    """删除论文本地存储（目录 + 旧版扁平 PDF）。返回删除的文件/目录数量。"""
    removed = 0
    root = paper_dir(arxiv_id)
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
        removed += 1

    for candidate in (stored_path, str(legacy_paper_pdf_path(arxiv_id))):
        resolved = resolve_existing_file(candidate)
        if not resolved:
            continue
        try:
            os.remove(resolved)
            removed += 1
        except OSError:
            pass
    return removed
