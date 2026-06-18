"""抓取任务执行：多数据源拉取、打分、去重、入库、下载 PDF。"""
from __future__ import annotations

import json
import os
import threading
import traceback
from datetime import datetime

import requests
from sqlalchemy.orm import Session

from src.integrations.arxiv.fetcher import arxiv_result_to_dict, fetch_arxiv_candidates
from src.integrations.arxiv.matcher import compute_match_score
from src.integrations.citations import fetch_citation_count
from src.integrations.openreview.fetcher import (
    fetch_openreview_candidates,
    fetch_review_rating,
    resolve_openreview_pdf_url,
)
from src.models.base import SessionLocal
from src.models.crawl import CrawlTask, CrawlTaskRun
from src.models.literature import LiteratureEntry
from src.models.paper import Paper
from src.services.literature_service import resolve_paper_pdf_path
from src.services.translate_service import prepare_crawl_match_query
from src.utils.paths import ensure_papers_dir, paper_pdf_path
from src.utils.logging_config import setup_logger

logger = setup_logger("CrawlService")

_running_tasks: set[int] = set()
_lock = threading.Lock()


def _append_log(run: CrawlTaskRun, line: str, session: Session) -> None:
    ts = datetime.utcnow().strftime("%H:%M:%S")
    run.log_text = (run.log_text or "") + f"[{ts}] {line}\n"
    session.add(run)
    session.commit()


def _download_pdf(pdf_url: str, dest_path: str) -> None:
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with requests.get(pdf_url, stream=True, timeout=(10, 120)) as resp:
        resp.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)


def _pdf_url_for_download(meta: dict) -> str | None:
    url = meta.get("pdf_url")
    forum_id = meta.get("openreview_id") or ""
    if meta.get("source") == "openreview" or (url and str(url).strip().startswith("/")):
        return resolve_openreview_pdf_url(url, forum_id)
    return url or None


def _try_download_paper_pdf(
    session: Session,
    paper: Paper,
    meta: dict,
    run: CrawlTaskRun,
    stats: dict,
) -> None:
    pdf_url = _pdf_url_for_download(meta)
    if not pdf_url:
        return
    if paper.pdf_url != pdf_url:
        paper.pdf_url = pdf_url
    pdf_path = str(paper_pdf_path(paper.arxiv_id))
    try:
        _download_pdf(pdf_url, pdf_path)
        paper.pdf_path = pdf_path
        paper.parse_status = "downloaded"
        session.add(paper)
        session.commit()
        _append_log(run, f"已下载 PDF: {paper.arxiv_id}", session)
    except Exception as exc:
        stats["download_failed"] += 1
        paper.parse_status = "download_failed"
        session.add(paper)
        session.commit()
        _append_log(run, f"PDF 下载失败 {paper.arxiv_id}: {exc}", session)


def _parse_csv_field(value: str) -> list[str]:
    return [v.strip() for v in (value or "").replace("，", ",").split(",") if v.strip()]


def _parse_sources(task: CrawlTask) -> list[str]:
    raw = getattr(task, "sources", None) or "arxiv"
    return _parse_csv_field(raw) or ["arxiv"]


def _literature_exists(session: Session, paper_id: str, visibility: str, user_id: str) -> bool:
    return (
        session.query(LiteratureEntry)
        .filter(
            LiteratureEntry.arxiv_id == paper_id,
            LiteratureEntry.visibility == visibility,
            LiteratureEntry.user_id == user_id,
        )
        .first()
        is not None
    )


def _meta_from_arxiv(raw) -> dict:
    meta = arxiv_result_to_dict(raw)
    meta["paper_id"] = meta["arxiv_id"]
    meta["source"] = "arxiv"
    return meta


def _collect_candidates(task: CrawlTask, run: CrawlTaskRun, session: Session) -> list[dict]:
    sources = _parse_sources(task)
    _append_log(run, f"抓取数据源: {', '.join(sources)}", session)
    candidates: list[dict] = []

    if "arxiv" in sources:
        categories = task.categories or ""
        if not categories.strip():
            raise ValueError("已选择 arXiv 源，请填写 arXiv 分类")
        raw_list = fetch_arxiv_candidates(categories)
        candidates.extend(_meta_from_arxiv(raw) for raw in raw_list)
        _append_log(run, f"从 arXiv 获取候选论文 {len(raw_list)} 篇", session)

    if "openreview" in sources:
        venues = getattr(task, "openreview_venues", None) or ""
        if not venues.strip():
            raise ValueError("已选择 OpenReview 源，请选择会议/venue")
        or_list = fetch_openreview_candidates(
            venues,
            max_per_venue=task.max_papers_per_run * 3,
            only_accepted=True,
        )
        candidates.extend(or_list)
        _append_log(
            run,
            f"从 OpenReview 获取已接收候选论文 {len(or_list)} 篇（已排除投稿中/拒稿/撤回）",
            session,
        )

    if not sources:
        raise ValueError("请至少选择一种抓取数据源")
    return candidates


def _enrich_openreview_meta(meta: dict) -> None:
    if meta.get("source") != "openreview":
        return
    forum_id = meta.get("openreview_id")
    meta["pdf_url"] = resolve_openreview_pdf_url(meta.get("pdf_url"), forum_id or "")
    if forum_id and meta.get("review_rating") is None:
        meta["review_rating"] = fetch_review_rating(forum_id)
    if meta.get("citation_count") is None:
        meta["citation_count"] = fetch_citation_count(meta["paper_id"], meta.get("title", ""))


def _upsert_paper(session: Session, meta: dict, run: CrawlTaskRun, stats: dict) -> Paper:
    paper_id = meta["paper_id"]
    paper = session.query(Paper).filter(Paper.arxiv_id == paper_id).first()
    if paper:
        if meta.get("published_at") and not paper.published_at:
            paper.published_at = meta["published_at"]
        if meta.get("venue") and not paper.venue:
            paper.venue = meta.get("venue")
        if meta.get("acceptance_status"):
            paper.acceptance_status = meta.get("acceptance_status")
        if meta.get("review_rating") is not None:
            paper.review_rating = meta.get("review_rating")
        if meta.get("citation_count") is not None:
            paper.citation_count = meta.get("citation_count")
        fixed_pdf = _pdf_url_for_download(meta)
        if fixed_pdf and paper.pdf_url != fixed_pdf:
            paper.pdf_url = fixed_pdf
        session.add(paper)
        session.commit()
        if paper.parse_status in ("pending", "download_failed") and not resolve_paper_pdf_path(paper):
            _try_download_paper_pdf(session, paper, meta, run, stats)
        else:
            _append_log(run, f"论文元数据已存在，更新扩展字段: {paper_id}", session)
        return paper

    fixed_pdf = _pdf_url_for_download(meta)
    paper = Paper(
        arxiv_id=paper_id,
        source=meta.get("source", "arxiv"),
        title=meta["title"],
        authors=json.dumps(meta.get("authors", []), ensure_ascii=False),
        abstract=meta.get("abstract", ""),
        categories=json.dumps(meta.get("categories", []), ensure_ascii=False),
        published_at=meta.get("published_at"),
        abs_url=meta.get("abs_url"),
        pdf_url=fixed_pdf,
        parse_status="pending",
        venue=meta.get("venue"),
        venue_type=meta.get("venue_type"),
        citation_count=meta.get("citation_count"),
        acceptance_status=meta.get("acceptance_status"),
        review_rating=meta.get("review_rating"),
        openreview_id=meta.get("openreview_id"),
    )
    session.add(paper)
    session.commit()
    stats["new_papers"] += 1

    if fixed_pdf:
        _try_download_paper_pdf(session, paper, meta, run, stats)
    return paper


def execute_crawl_run(task_id: int, trigger_type: str = "manual") -> int:
    with _lock:
        if task_id in _running_tasks:
            raise RuntimeError("任务正在执行中")
        _running_tasks.add(task_id)

    session = SessionLocal()
    run = CrawlTaskRun(
        task_id=task_id,
        status="running",
        trigger_type=trigger_type,
        progress=0,
        started_at=datetime.utcnow(),
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    run_id = run.id

    try:
        _run_crawl(session, task_id, run)
        run.status = "done"
        run.progress = 100
    except Exception as exc:
        logger.exception("crawl run failed task_id=%s", task_id)
        run.status = "failed"
        _append_log(run, f"执行失败: {exc}", session)
        _append_log(run, traceback.format_exc(), session)
    finally:
        run.finished_at = datetime.utcnow()
        session.add(run)
        task = session.query(CrawlTask).filter(CrawlTask.id == task_id).first()
        if task:
            task.last_run_at = run.finished_at
            session.add(task)
        session.commit()
        session.close()
        with _lock:
            _running_tasks.discard(task_id)

    return run_id


def _run_crawl(session: Session, task_id: int, run: CrawlTaskRun) -> None:
    task = session.query(CrawlTask).filter(CrawlTask.id == task_id).first()
    if not task:
        raise ValueError("任务不存在")

    stats = {
        "candidates": 0,
        "matched": 0,
        "new_entries": 0,
        "skipped_dup": 0,
        "new_papers": 0,
        "download_failed": 0,
    }

    _append_log(run, f"开始执行任务: {task.name}（入库目标: {'公开文献' if task.visibility == 'public' else '私有文献'}）", session)

    run.progress = 10
    session.add(run)
    session.commit()

    candidates = _collect_candidates(task, run, session)
    stats["candidates"] = len(candidates)
    categories = task.categories or ""

    except_translation = False
    try:
        match_query = prepare_crawl_match_query(task.intent_text or "", task.keywords or "")
    except Exception as exc:
        except_translation = True
        match_query = {
            "intent_text": task.intent_text or "",
            "keywords": task.keywords or "",
            "translated": False,
            "translated_fields": [],
            "original_intent": task.intent_text or "",
            "original_keywords": task.keywords or "",
        }
        _append_log(run, f"中文自动翻译失败，将使用原文匹配（{exc}）", session)

    intent_for_match = match_query["intent_text"]
    keywords_for_match = match_query["keywords"]
    if not except_translation and match_query["translated"]:
        _append_log(run, "检测到中文输入，已自动翻译为英文用于论文匹配：", session)
        if "intent" in match_query["translated_fields"]:
            _append_log(run, f"  兴趣原文: {match_query['original_intent'][:120]}", session)
            _append_log(run, f"  兴趣译文: {intent_for_match[:200]}", session)
        if "keywords" in match_query["translated_fields"]:
            _append_log(run, f"  关键词原文: {match_query['original_keywords']}", session)
            _append_log(run, f"  关键词译文: {keywords_for_match}", session)
    elif not except_translation:
        _append_log(run, "使用原始兴趣/关键词进行英文论文匹配", session)

    scored: list[tuple[float, dict]] = []
    for meta in candidates:
        score = compute_match_score(
            intent_text=intent_for_match,
            keywords=keywords_for_match,
            categories=categories,
            title=meta.get("title", ""),
            abstract=meta.get("abstract", ""),
            paper_categories=meta.get("categories", []),
        )
        if score >= task.min_match_score:
            scored.append((score, meta))

    scored.sort(key=lambda x: x[0], reverse=True)
    scored = scored[: task.max_papers_per_run]
    stats["matched"] = len(scored)
    _append_log(run, f"相似度 >= {task.min_match_score} 的论文 {len(scored)} 篇", session)

    run.progress = 40
    session.add(run)
    session.commit()

    owner_id = "" if task.visibility == "public" else task.user_id

    for idx, (score, meta) in enumerate(scored):
        _enrich_openreview_meta(meta)
        paper_id = meta["paper_id"]

        if _literature_exists(session, paper_id, task.visibility, owner_id):
            stats["skipped_dup"] += 1
            paper = session.query(Paper).filter(Paper.arxiv_id == paper_id).first()
            if paper and not resolve_paper_pdf_path(paper) and paper.parse_status in (
                "pending",
                "download_failed",
            ):
                _try_download_paper_pdf(session, paper, meta, run, stats)
            _append_log(run, f"跳过已存在: {paper_id} {meta['title'][:60]}", session)
            continue

        _upsert_paper(session, meta, run, stats)

        entry = LiteratureEntry(
            arxiv_id=paper_id,
            user_id=owner_id,
            visibility=task.visibility,
            match_score=score,
            task_id=task.id,
            run_id=run.id,
        )
        session.add(entry)
        session.commit()
        stats["new_entries"] += 1

        progress = 40 + int((idx + 1) / max(len(scored), 1) * 55)
        run.progress = min(progress, 95)
        session.add(run)
        session.commit()

    run.stats_json = json.dumps(stats, ensure_ascii=False)
    _append_log(run, f"完成。统计: {json.dumps(stats, ensure_ascii=False)}", session)
    session.add(run)
    session.commit()


def run_task_async(task_id: int, trigger_type: str = "manual") -> None:
    thread = threading.Thread(target=execute_crawl_run, args=(task_id, trigger_type), daemon=True)
    thread.start()


def is_task_running(task_id: int) -> bool:
    with _lock:
        return task_id in _running_tasks


def cancel_task_run(task_id: int) -> bool:
    with _lock:
        return task_id in _running_tasks
