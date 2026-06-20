"""将引用文献 PDF / 页面图同步到技能工作目录，供 codegen 使用。"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from src.utils.logging_config import setup_logger
from src.utils.paths import paper_images_dir, paper_safe_id, resolve_paper_pdf_file

logger = setup_logger("SkillInputSync")

INPUT_SUBDIR = "input/papers"
FIGURES_SUBDIR = "output/assets/figures"
MAX_RENDER_PAGES = 24
RENDER_DPI = 120
MAX_PAGE_PIXEL = 1600


@dataclass
class SkillInputContext:
    paper_ids: list[str] = field(default_factory=list)
    pdf_rels: list[str] = field(default_factory=list)
    page_render_rels: list[str] = field(default_factory=list)
    figure_rels: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def has_assets(self) -> bool:
        return bool(self.pdf_rels or self.page_render_rels or self.figure_rels)

    def to_prompt_block(self) -> str:
        if not self.has_assets():
            return "（无同步文献资源）"
        lines = [
            "以下路径均相对于技能根目录（脚本 cwd），可直接用 pathlib.Path 读取：",
            "仅使用下列列出的路径；勿 glob 扫描 output/assets/figures/ 或 input/papers/ 全目录，"
            "以免混入历史轮次或其他文献的文件。",
        ]
        if self.pdf_rels:
            lines.append("PDF：")
            lines.extend(f"- {p}" for p in self.pdf_rels)
        if self.page_render_rels:
            lines.append("PDF 整页预览 PNG（仅供阅读参考，禁止作为幻灯片背景或全屏贴图）：")
            lines.extend(f"- {p}" for p in self.page_render_rels[:8])
            if len(self.page_render_rels) > 8:
                lines.append(f"- … 另有 {len(self.page_render_rels) - 8} 张整页预览")
        if self.figure_rels:
            lines.append(
                "论文配图（MinerU 解析或 PDF 渲染，可写入 Markdown 的 ![Fig](...) 或 PPT 结果页）："
            )
            lines.extend(f"- {p}" for p in self.figure_rels[:40])
            if len(self.figure_rels) > 40:
                lines.append(f"- … 另有 {len(self.figure_rels) - 40} 张")
        if self.notes:
            lines.append("说明：")
            lines.extend(f"- {n}" for n in self.notes)
        lines.append(
            "做 PPT 时：用 python-pptx 写中文标题与 bullet 要点；"
            "仅在结果页插入「论文配图 PNG」列表中的图；"
            "禁止把整页预览 PNG 全屏铺满幻灯片，禁止逐页截图拼 deck。"
        )
        lines.append(
            "做阅读稿（nature-reader）时：从 PDF/MinerU 配图路径写入 "
            "`output/runs/{run_id}/paper.md`，图表用 `output/assets/figures/*_mineru_*`。"
        )
        return "\n".join(lines)


def collect_paper_ids_from_meta(meta: dict) -> list[str]:
    """从聊天 meta 收集要同步的文献 ID。"""
    seen: set[str] = set()
    ids: list[str] = []
    for item in meta.get("cited_literature") or []:
        if not isinstance(item, dict):
            continue
        pid = item.get("arxiv_id") or item.get("paper_id")
        if pid:
            key = str(pid).strip()
            if key and key not in seen:
                seen.add(key)
                ids.append(key)
    bind = meta.get("bind_paper_id") or meta.get("bind_doc_id")
    if bind:
        key = str(bind).strip()
        if key and key not in seen:
            ids.append(key)
    return ids


def cleanup_stale_literature_assets(skill_root: Path, paper_ids: list[str]) -> None:
    """移除技能目录中不属于本轮引用文献的 PDF / 配图，避免多轮执行混用旧资源。"""
    skill_root = skill_root.resolve()
    safe_ids = {paper_safe_id(pid) for pid in paper_ids}

    papers_dir = skill_root / INPUT_SUBDIR
    if papers_dir.is_dir():
        for child in papers_dir.iterdir():
            if child.is_dir() and child.name not in safe_ids:
                try:
                    shutil.rmtree(child)
                except OSError as exc:
                    logger.warning("Remove stale paper dir %s: %s", child, exc)

    fig_dir = skill_root / FIGURES_SUBDIR
    if fig_dir.is_dir():
        for path in fig_dir.iterdir():
            if not path.is_file():
                continue
            if not any(path.name.startswith(f"{sid}_") for sid in safe_ids):
                try:
                    path.unlink()
                except OSError as exc:
                    logger.warning("Remove stale figure %s: %s", path, exc)


def sync_literature_to_skill(skill_root: Path, paper_ids: list[str]) -> SkillInputContext:
    """复制 PDF 并渲染页面图为 PNG 到技能目录。"""
    skill_root = skill_root.resolve()
    cleanup_stale_literature_assets(skill_root, paper_ids)
    ctx = SkillInputContext(paper_ids=list(paper_ids))

    for paper_id in paper_ids:
        safe = paper_safe_id(paper_id)
        pdf_src = resolve_paper_pdf_file(paper_id)
        if not pdf_src:
            ctx.notes.append(f"{paper_id}：本地无 PDF，已跳过")
            continue

        dest_pdf_dir = skill_root / INPUT_SUBDIR / safe
        dest_pdf_dir.mkdir(parents=True, exist_ok=True)
        dest_pdf = dest_pdf_dir / "paper.pdf"
        try:
            shutil.copy2(pdf_src, dest_pdf)
            rel_pdf = dest_pdf.relative_to(skill_root).as_posix()
            ctx.pdf_rels.append(rel_pdf)
        except OSError as exc:
            logger.warning("Copy PDF failed %s: %s", paper_id, exc)
            ctx.notes.append(f"{paper_id}：PDF 复制失败")
            continue

        ctx.page_render_rels.extend(_render_pdf_pages(skill_root, dest_pdf, safe))
        ctx.figure_rels.extend(_copy_mineru_images(skill_root, paper_id, safe))

    # 去重保持顺序
    ctx.page_render_rels = list(dict.fromkeys(ctx.page_render_rels))
    ctx.figure_rels = list(dict.fromkeys(ctx.figure_rels))
    if ctx.pdf_rels:
        logger.info(
            "Synced %d PDFs, %d page renders, %d figures to skill %s",
            len(ctx.pdf_rels),
            len(ctx.page_render_rels),
            len(ctx.figure_rels),
            skill_root.name,
        )
    return ctx


def _render_pdf_pages(skill_root: Path, pdf_path: Path, safe_id: str) -> list[str]:
    """用 PyMuPDF 将 PDF 各页渲染为 PNG。"""
    fig_dir = skill_root / FIGURES_SUBDIR
    fig_dir.mkdir(parents=True, exist_ok=True)
    rels: list[str] = []

    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.warning("PyMuPDF not installed, skip page render")
        return rels

    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        logger.warning("Open PDF failed %s: %s", pdf_path, exc)
        return rels

    try:
        page_count = min(len(doc), MAX_RENDER_PAGES)
        if len(doc) > MAX_RENDER_PAGES:
            logger.info("PDF %s has %d pages, rendering first %d", safe_id, len(doc), page_count)

        zoom = RENDER_DPI / 72.0
        mat = fitz.Matrix(zoom, zoom)

        for i in range(page_count):
            page = doc.load_page(i)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            if max(pix.width, pix.height) > MAX_PAGE_PIXEL:
                scale = MAX_PAGE_PIXEL / max(pix.width, pix.height)
                mat2 = fitz.Matrix(zoom * scale, zoom * scale)
                pix = page.get_pixmap(matrix=mat2, alpha=False)
            out = fig_dir / f"{safe_id}_p{i + 1:03d}.png"
            pix.save(str(out))
            rels.append(out.relative_to(skill_root).as_posix())
    finally:
        doc.close()

    return rels


def _copy_mineru_images(skill_root: Path, paper_id: str, safe_id: str) -> list[str]:
    """复制 MinerU 解析出的图片到 figures 目录。"""
    src_dir = paper_images_dir(paper_id)
    if not src_dir.is_dir():
        return []

    fig_dir = skill_root / FIGURES_SUBDIR
    fig_dir.mkdir(parents=True, exist_ok=True)
    rels: list[str] = []
    for src in sorted(src_dir.glob("*")):
        if not src.is_file():
            continue
        if src.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            continue
        dest = fig_dir / f"{safe_id}_mineru_{src.name}"
        try:
            shutil.copy2(src, dest)
            rels.append(dest.relative_to(skill_root).as_posix())
        except OSError:
            continue
    return rels
