"""项目内静态资源路径（不依赖进程 cwd）。"""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPLOADS_DIR = PROJECT_ROOT / "uploads"
PAPERS_DIR = UPLOADS_DIR / "papers"


def ensure_papers_dir() -> Path:
    PAPERS_DIR.mkdir(parents=True, exist_ok=True)
    return PAPERS_DIR


def paper_pdf_filename(arxiv_id: str) -> str:
    safe_name = arxiv_id.replace("/", "_").replace(":", "_")
    return f"{safe_name}.pdf"


def paper_pdf_path(arxiv_id: str) -> Path:
    return PAPERS_DIR / paper_pdf_filename(arxiv_id)


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
