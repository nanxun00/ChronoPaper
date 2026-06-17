"""抓取任务执行：拉取、打分、去重、入库、下载 PDF。"""
from __future__ import annotations

import json
import os
import threading
import traceback
from datetime import datetime
from typing import Callable

import requests
from sqlalchemy.orm import Session

from src.models.base import SessionLocal
from src.models.crawl import CrawlTask, CrawlTaskRun
from src.models.literature import LiteratureEntry
from src.models.paper import Paper
from src.integrations.arxiv.fetcher import arxiv_result_to_dict, fetch_arxiv_candidates
from src.integrations.arxiv.matcher import compute_match_score
from src.utils.logging_config import setup_logger

logger = setup_logger("CrawlService")

PAPERS_DIR = os.path.join("uploads", "papers")
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


def _literature_exists(session: Session, arxiv_id: str, visibility: str, user_id: str) -> bool:
    return (
        session.query(LiteratureEntry)
        .filter(
            LiteratureEntry.arxiv_id == arxiv_id,
            LiteratureEntry.visibility == visibility,
            LiteratureEntry.user_id == user_id,
        )
        .first()
        is not None
    )


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

    categories = task.categories or ""
    if not categories.strip():
        raise ValueError("请填写 arXiv 分类，例如 cs.AI, cs.CL")

    run.progress = 10
    session.add(run)
    session.commit()

    candidates = fetch_arxiv_candidates(categories)
    stats["candidates"] = len(candidates)
    _append_log(run, f"从 arXiv 获取候选论文 {len(candidates)} 篇", session)

    scored: list[tuple[float, dict]] = []
    for raw in candidates:
        meta = arxiv_result_to_dict(raw)
        score = compute_match_score(
            intent_text=task.intent_text or "",
            keywords=task.keywords or "",
            categories=categories,
            title=meta["title"],
            abstract=meta["abstract"],
            paper_categories=meta["categories"],
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
        arxiv_id = meta["arxiv_id"]
        if _literature_exists(session, arxiv_id, task.visibility, owner_id):
            stats["skipped_dup"] += 1
            _append_log(run, f"跳过已存在: {arxiv_id} {meta['title'][:60]}", session)
            continue

        paper = session.query(Paper).filter(Paper.arxiv_id == arxiv_id).first()
        if not paper:
            paper = Paper(
                arxiv_id=arxiv_id,
                title=meta["title"],
                authors=json.dumps(meta["authors"], ensure_ascii=False),
                abstract=meta["abstract"],
                categories=json.dumps(meta["categories"], ensure_ascii=False),
                published_at=meta["published_at"],
                abs_url=meta["abs_url"],
                pdf_url=meta["pdf_url"],
                parse_status="pending",
            )
            session.add(paper)
            session.commit()
            stats["new_papers"] += 1

            if meta.get("pdf_url"):
                pdf_path = os.path.join(PAPERS_DIR, f"{arxiv_id}.pdf")
                try:
                    _download_pdf(meta["pdf_url"], pdf_path)
                    paper.pdf_path = pdf_path
                    paper.parse_status = "downloaded"
                    session.add(paper)
                    session.commit()
                    _append_log(run, f"已下载 PDF: {arxiv_id}", session)
                except Exception as exc:
                    stats["download_failed"] += 1
                    paper.parse_status = "download_failed"
                    session.add(paper)
                    session.commit()
                    _append_log(run, f"PDF 下载失败 {arxiv_id}: {exc}", session)
        else:
            if meta.get("published_at") and not paper.published_at:
                paper.published_at = meta["published_at"]
                session.add(paper)
                session.commit()
            _append_log(run, f"论文元数据已存在，仅新增文献条目: {arxiv_id}", session)

        entry = LiteratureEntry(
            arxiv_id=arxiv_id,
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
    """当前版本仅标记等待中的逻辑取消；运行中任务会自然结束。"""
    with _lock:
        return task_id in _running_tasks
