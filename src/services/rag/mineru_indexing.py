"""MinerU 解析辅助：生成 content_list 供向量入库。"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from src.settings import get_settings
from src.third_party.mineru_bootstrap import ensure_mineru_importable
from src.utils.logging_config import setup_logger
from src.utils.paths import PAPER_PDF_NAME, ensure_paper_dir, mineru_work_dir, resolve_paper_pdf_file

logger = setup_logger("MineruIndexing")

CONTENT_LIST_NAME = "content_list.json"


def _load_do_parse():
    ensure_mineru_importable()
    from mineru.cli.common import do_parse

    return do_parse


def _run_mineru_on_pdf(pdf_path: Path, work_dir: Path) -> Path:
    settings = get_settings()
    pdf_bytes = pdf_path.read_bytes()
    pdf_stem = pdf_path.stem
    do_parse = _load_do_parse()
    if work_dir.exists():
        shutil.rmtree(work_dir, ignore_errors=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    backend = settings.mineru_backend or "pipeline"
    do_parse(
        str(work_dir),
        [pdf_stem],
        [pdf_bytes],
        [settings.mineru_lang or "en"],
        backend=backend,
        parse_method="auto",
        formula_enable=True,
        table_enable=True,
        f_draw_layout_bbox=False,
        f_draw_span_bbox=False,
        f_dump_middle_json=False,
        f_dump_model_output=False,
        f_dump_orig_pdf=False,
        f_dump_content_list=True,
    )
    candidates = sorted(work_dir.rglob(f"{pdf_stem}_content_list.json"))
    if not candidates:
        candidates = sorted(work_dir.rglob("*_content_list.json"))
    if not candidates:
        raise FileNotFoundError(f"MinerU content_list not found under {work_dir}")
    return candidates[0]


def resolve_paper_content_list_path(paper_id: str) -> str | None:
    paper_root = ensure_paper_dir(paper_id)
    dest = paper_root / CONTENT_LIST_NAME
    if dest.is_file():
        return str(dest)
    return None


def parse_paper_pdf_to_content_list(paper_id: str) -> str:
    pdf_path = resolve_paper_pdf_file(paper_id)
    if not pdf_path:
        raise FileNotFoundError(f"PDF not found for paper {paper_id}")
    paper_root = ensure_paper_dir(paper_id)
    work_dir = mineru_work_dir(paper_id)
    src = _run_mineru_on_pdf(Path(pdf_path), work_dir)
    dest = paper_root / CONTENT_LIST_NAME
    shutil.copy2(src, dest)
    return str(dest)


def parse_upload_file_to_content_list(file_path: str) -> str:
    src = Path(file_path)
    if not src.is_file():
        raise FileNotFoundError(file_path)
    if src.suffix.lower() != ".pdf":
        raise ValueError("Phase 1 知识库上传仅支持 PDF 走 MinerU 结构化分块")
    work_dir = src.parent / f".mineru_{src.stem}"
    content_src = _run_mineru_on_pdf(src, work_dir)
    dest = src.parent / f"{src.stem}_{CONTENT_LIST_NAME}"
    shutil.copy2(content_src, dest)
    return str(dest)
