"""论文 PDF 下载与失败重试队列。"""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta

import requests
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from src.integrations.openreview.fetcher import resolve_openreview_pdf_url
from src.models.literature import Paper
from src.utils.logging_config import setup_logger
from src.utils.paths import ensure_paper_dir, paper_pdf_path, resolve_paper_pdf_file
from src.utils.pdf_validate import is_valid_pdf_file

logger = setup_logger("PdfDownloadService")

MAX_PDF_DOWNLOAD_ATTEMPTS = 8
RETRY_DELAYS_RATE_LIMIT_MIN = (30, 45, 60, 90, 120, 180, 240, 360)
RETRY_DELAYS_DEFAULT_MIN = (10, 20, 30, 60, 90, 120, 180, 240)
CRAWL_DOWNLOAD_GAP_SEC = 2.0
RETRY_JOB_BATCH_SIZE = 5
RETRY_JOB_GAP_SEC = 4.0


def _is_rate_limit_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "429" in text or "too many requests" in text


def _is_forbidden_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "403" in text or "forbidden" in text


def _retry_delay_minutes(attempt: int, exc: Exception) -> int:
    """attempt 为失败后的累计次数（从 1 起）。"""
    if _is_forbidden_error(exc):
        delays = (60, 120, 240, 480, 720, 720, 720, 720)
    elif _is_rate_limit_error(exc):
        delays = RETRY_DELAYS_RATE_LIMIT_MIN
    else:
        delays = RETRY_DELAYS_DEFAULT_MIN
    idx = min(max(attempt - 1, 0), len(delays) - 1)
    return delays[idx]


def resolve_pdf_download_url(paper: Paper) -> str | None:
    url = paper.pdf_url
    if paper.source == "openreview" or (url and str(url).strip().startswith("/")):
        return resolve_openreview_pdf_url(url, paper.openreview_id or "")
    return url or None


def download_pdf_to_path(pdf_url: str, dest_path: str, *, max_inline_retries: int = 2) -> None:
    """同步下载 PDF；对 429 做少量即时重试。"""
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    last_exc: Exception | None = None
    for attempt in range(max_inline_retries + 1):
        try:
            with requests.get(pdf_url, stream=True, timeout=(10, 120)) as resp:
                if resp.status_code == 429 and attempt < max_inline_retries:
                    time.sleep(3 * (attempt + 1))
                    continue
                resp.raise_for_status()
                with open(dest_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
            return
        except Exception as exc:
            last_exc = exc
            if _is_rate_limit_error(exc) and attempt < max_inline_retries:
                time.sleep(3 * (attempt + 1))
                continue
            raise
    if last_exc:
        raise last_exc


def _schedule_retry(paper: Paper, exc: Exception) -> None:
    paper.pdf_download_attempts = int(paper.pdf_download_attempts or 0) + 1
    paper.pdf_download_last_error = str(exc)[:500]
    if paper.pdf_download_attempts >= MAX_PDF_DOWNLOAD_ATTEMPTS:
        paper.parse_status = "download_failed"
        paper.pdf_download_next_retry_at = None
        return
    delay_min = _retry_delay_minutes(paper.pdf_download_attempts, exc)
    paper.parse_status = "download_retry"
    paper.pdf_download_next_retry_at = datetime.utcnow() + timedelta(minutes=delay_min)


def _mark_downloaded(paper: Paper, pdf_path: str, pdf_url: str) -> None:
    paper.pdf_path = pdf_path
    paper.pdf_url = pdf_url
    paper.parse_status = "downloaded"
    paper.pdf_download_attempts = 0
    paper.pdf_download_next_retry_at = None
    paper.pdf_download_last_error = None


def try_download_paper_pdf(
    session: Session,
    paper: Paper,
    *,
    pdf_url: str | None = None,
    throttle_sec: float = 0,
    force: bool = False,
) -> tuple[bool, str]:
    """尝试下载单篇论文 PDF。返回 (成功与否, 日志说明)。"""
    if throttle_sec > 0:
        time.sleep(throttle_sec)

    existing = resolve_paper_pdf_file(paper.arxiv_id, paper.pdf_path)
    if existing:
        if not force and is_valid_pdf_file(existing):
            return True, f"PDF 已存在: {paper.arxiv_id}"
        try:
            os.remove(existing)
        except OSError:
            pass

    url = pdf_url or resolve_pdf_download_url(paper)
    if not url:
        return False, f"无 PDF 链接: {paper.arxiv_id}"

    if paper.pdf_url != url:
        paper.pdf_url = url

    pdf_path = str(paper_pdf_path(paper.arxiv_id))
    try:
        ensure_paper_dir(paper.arxiv_id)
        download_pdf_to_path(url, pdf_path)
        if not is_valid_pdf_file(pdf_path):
            try:
                os.remove(pdf_path)
            except OSError:
                pass
            raise ValueError("下载内容不是有效的 PDF 文件（可能是 HTML 登录页）")
        _mark_downloaded(paper, pdf_path, url)
        session.add(paper)
        session.commit()
        return True, f"已下载 PDF: {paper.arxiv_id}"
    except Exception as exc:
        _schedule_retry(paper, exc)
        session.add(paper)
        session.commit()
        if paper.parse_status == "download_retry":
            retry_at = paper.pdf_download_next_retry_at
            eta = retry_at.strftime("%H:%M") if retry_at else "—"
            return (
                False,
                f"PDF 下载失败 {paper.arxiv_id}: {exc}；"
                f"已加入重试队列（{paper.pdf_download_attempts}/{MAX_PDF_DOWNLOAD_ATTEMPTS} 次，"
                f"约 {eta} UTC 再试）",
            )
        return False, f"PDF 下载失败 {paper.arxiv_id}: {exc}；已达最大重试次数"


def list_due_pdf_retries(session: Session, *, limit: int = RETRY_JOB_BATCH_SIZE) -> list[Paper]:
    now = datetime.utcnow()
    queued = and_(
        Paper.parse_status == "download_retry",
        Paper.pdf_download_next_retry_at.isnot(None),
        Paper.pdf_download_next_retry_at <= now,
    )
    legacy_failed = and_(
        Paper.parse_status == "download_failed",
        Paper.pdf_url.isnot(None),
        Paper.pdf_download_attempts < MAX_PDF_DOWNLOAD_ATTEMPTS,
        Paper.pdf_download_next_retry_at.is_(None),
    )
    return (
        session.query(Paper)
        .filter(
            Paper.pdf_download_attempts < MAX_PDF_DOWNLOAD_ATTEMPTS,
            or_(queued, legacy_failed),
        )
        .order_by(Paper.pdf_download_next_retry_at.asc())
        .limit(limit)
        .all()
    )


def run_pdf_download_retry_job(*, batch_size: int = RETRY_JOB_BATCH_SIZE) -> dict:
    """后台任务：处理到期的 PDF 下载重试。"""
    from src.models.base import SessionLocal

    session = SessionLocal()
    stats = {"checked": 0, "success": 0, "requeued": 0, "exhausted": 0}
    try:
        papers = list_due_pdf_retries(session, limit=batch_size)
        stats["checked"] = len(papers)
        for idx, paper in enumerate(papers):
            ok, msg = try_download_paper_pdf(
                session,
                paper,
                throttle_sec=RETRY_JOB_GAP_SEC if idx > 0 else 0,
            )
            if ok:
                stats["success"] += 1
                logger.info(msg)
            elif paper.parse_status == "download_retry":
                stats["requeued"] += 1
                logger.info(msg)
            else:
                stats["exhausted"] += 1
                logger.warning(msg)
        return stats
    finally:
        session.close()
