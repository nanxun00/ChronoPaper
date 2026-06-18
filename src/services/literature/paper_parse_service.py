"""使用 MinerU 将论文 PDF 解析为 Markdown + 图片。"""
from __future__ import annotations

import shutil
import threading
from pathlib import Path

from sqlalchemy.orm import Session

from src.models.base import SessionLocal
from src.models.literature import Paper
from src.settings import get_settings
from src.third_party.mineru_bootstrap import ensure_mineru_importable
from src.utils.gpu import has_gpu_accelerator
from src.utils.logging_config import setup_logger
from src.utils.paths import (
    PAPER_IMAGES_DIR_NAME,
    PAPER_MD_NAME,
    PAPER_PDF_NAME,
    ensure_paper_dir,
    migrate_legacy_pdf_to_paper_dir,
    mineru_work_dir,
    paper_md_path,
    paper_pdf_path,
    resolve_paper_md_file,
    resolve_paper_pdf_file,
)

logger = setup_logger("PaperParseService")

CONTENT_LIST_NAME = "content_list.json"

_parse_lock = threading.Lock()
_parsing_papers: set[str] = set()


def select_mineru_backend() -> str:
    """无 GPU 使用 pipeline；有 GPU 使用 hybrid-engine。"""
    settings = get_settings()
    if settings.mineru_backend:
        return settings.mineru_backend
    return "hybrid-engine" if has_gpu_accelerator() else "pipeline"


def _load_do_parse():
    ensure_mineru_importable()
    from mineru.cli.common import do_parse

    return do_parse


def _find_mineru_output_md(work_dir: Path) -> Path:
    matches = sorted(work_dir.rglob(f"{PAPER_PDF_NAME.rsplit('.', 1)[0]}.md"))
    if not matches:
        matches = sorted(work_dir.rglob("*.md"))
    if not matches:
        raise FileNotFoundError(f"MinerU 未生成 Markdown: {work_dir}")
    return matches[0]


def _copy_content_list(work_dir: Path, paper_root: Path) -> None:
    candidates = sorted(work_dir.rglob("*_content_list.json"))
    if not candidates:
        candidates = sorted(work_dir.rglob("content_list.json"))
    if candidates:
        shutil.copy2(candidates[0], paper_root / CONTENT_LIST_NAME)


def _finalize_mineru_output(work_dir: Path, paper_root: Path) -> None:
    md_src = _find_mineru_output_md(work_dir)
    images_src = md_src.parent / PAPER_IMAGES_DIR_NAME

    md_dest = paper_root / PAPER_MD_NAME
    images_dest = paper_root / PAPER_IMAGES_DIR_NAME
    images_dest.mkdir(parents=True, exist_ok=True)

    shutil.copy2(md_src, md_dest)

    if images_src.is_dir():
        for item in images_src.iterdir():
            if item.is_file():
                shutil.copy2(item, images_dest / item.name)

    _copy_content_list(work_dir, paper_root)


def _schedule_paper_index(arxiv_id: str) -> None:
    try:
        from src.workers.index_tasks import index_paper_chunks_task

        index_paper_chunks_task.delay(arxiv_id)
        logger.info("queued vector index task for paper=%s", arxiv_id)
    except Exception as exc:
        logger.warning("Failed to queue index task for %s: %s", arxiv_id, exc)


def parse_paper_with_mineru(arxiv_id: str, pdf_path: str | None = None) -> str:
    """解析单篇论文 PDF，返回 content.md 路径。"""
    resolved_pdf = pdf_path or migrate_legacy_pdf_to_paper_dir(arxiv_id)
    if not resolved_pdf:
        resolved_pdf = resolve_paper_pdf_file(arxiv_id)
    if not resolved_pdf:
        raise FileNotFoundError(f"未找到论文 PDF: {arxiv_id}")

    paper_root = ensure_paper_dir(arxiv_id)
    canonical_pdf = paper_root / PAPER_PDF_NAME
    if resolved_pdf != str(canonical_pdf.resolve()):
        shutil.copy2(resolved_pdf, canonical_pdf)

    work_dir = mineru_work_dir(arxiv_id)
    if work_dir.exists():
        shutil.rmtree(work_dir, ignore_errors=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    backend = select_mineru_backend()
    settings = get_settings()
    pdf_bytes = canonical_pdf.read_bytes()
    pdf_stem = canonical_pdf.stem

    do_parse = _load_do_parse()
    logger.info("MinerU parse start paper=%s backend=%s", arxiv_id, backend)

    try:
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
    except Exception as exc:
        if backend != "pipeline":
            logger.warning(
                "MinerU backend %s failed for %s, fallback to pipeline: %s",
                backend,
                arxiv_id,
                exc,
            )
            if work_dir.exists():
                shutil.rmtree(work_dir, ignore_errors=True)
                work_dir.mkdir(parents=True, exist_ok=True)
            do_parse(
                str(work_dir),
                [pdf_stem],
                [pdf_bytes],
                [settings.mineru_lang or "en"],
                backend="pipeline",
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
        else:
            raise

    _finalize_mineru_output(work_dir, paper_root)
    shutil.rmtree(work_dir, ignore_errors=True)

    md_path = str(paper_md_path(arxiv_id).resolve())
    logger.info("MinerU parse done paper=%s md=%s", arxiv_id, md_path)
    return md_path


def _parse_one(session: Session, arxiv_id: str) -> bool:
    paper = session.query(Paper).filter(Paper.arxiv_id == arxiv_id).first()
    if not paper:
        return False

    if resolve_paper_md_file(arxiv_id):
        md_path = resolve_paper_md_file(arxiv_id)
        if paper.parse_status != "parsed":
            from src.utils.pdf_metadata import apply_upload_metadata_from_md

            if md_path:
                apply_upload_metadata_from_md(paper, md_path)
            paper.parse_status = "parsed"
            session.add(paper)
            session.commit()
        _schedule_paper_index(arxiv_id)
        return True

    pdf_path = resolve_paper_pdf_file(arxiv_id, paper.pdf_path)
    if not pdf_path:
        return False

    paper.parse_status = "parsing"
    session.add(paper)
    session.commit()

    try:
        md_path = parse_paper_with_mineru(arxiv_id, pdf_path)
        paper.pdf_path = str(paper_pdf_path(arxiv_id).resolve())
        paper.parse_status = "parsed"
        from src.utils.pdf_metadata import apply_upload_metadata_from_md

        apply_upload_metadata_from_md(paper, md_path)
        session.add(paper)
        session.commit()
        logger.info("paper parsed: %s -> %s", arxiv_id, md_path)
        _schedule_paper_index(arxiv_id)
        return True
    except Exception as exc:
        logger.exception("paper parse failed: %s", arxiv_id)
        paper.parse_status = "parse_failed"
        session.add(paper)
        session.commit()
        return False


def _parse_batch(paper_ids: list[str]) -> int:
    done = 0
    for arxiv_id in paper_ids:
        with _parse_lock:
            if arxiv_id in _parsing_papers:
                continue
            _parsing_papers.add(arxiv_id)
        session = SessionLocal()
        try:
            if _parse_one(session, arxiv_id):
                done += 1
        finally:
            session.close()
            with _parse_lock:
                _parsing_papers.discard(arxiv_id)
    return done


def schedule_paper_parse(paper_ids: list[str]) -> None:
    ids = [p for p in paper_ids if p]
    if not ids:
        return

    def _worker():
        try:
            count = _parse_batch(ids)
            logger.info("MinerU paper parse finished: %s papers", count)
        except Exception as exc:
            logger.exception("MinerU paper parse worker failed: %s", exc)

    threading.Thread(target=_worker, daemon=True, name="paper-parse").start()


def read_paper_full_text(arxiv_id: str, pdf_fallback_path: str | None = None) -> str:
    """优先读取 MinerU 生成的 content.md，否则回退到简易 PDF 提取。"""
    md_path = resolve_paper_md_file(arxiv_id)
    if md_path:
        return Path(md_path).read_text(encoding="utf-8")

    pdf_path = resolve_paper_pdf_file(arxiv_id, pdf_fallback_path)
    if not pdf_path:
        raise FileNotFoundError(f"未找到论文文本: {arxiv_id}")

    from src.parsers import pdf_simple

    return pdf_simple.pdf2txt(pdf_path, return_text=True)
