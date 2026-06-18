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
from src.integrations.citations import fetch_citation_count
from src.integrations.openreview.fetcher import (
    fetch_openreview_candidates,
    fetch_review_rating,
    resolve_openreview_pdf_url,
)
from src.integrations.openalex.fetcher import fetch_openalex_candidates
from src.models.base import SessionLocal
from src.models.crawl import CrawlTask, CrawlTaskRun
from src.models.literature import LiteratureEntry
from src.models.paper import Paper
from src.services.literature_service import resolve_paper_pdf_path
from src.services.paper_quality_assessment import schedule_quality_assessment
from src.services.quality_scorer import compute_quality_score, merge_paper_quality_signals
from src.services.semantic_matcher import batch_semantic_scores, build_interest_text, encode_interest_vector
from src.services.translate_service import prepare_crawl_match_query
from src.utils.datetime_fmt import format_display_datetime
from src.utils.paths import ensure_papers_dir, paper_pdf_path
from src.utils.logging_config import setup_logger

logger = setup_logger("CrawlService")

_running_tasks: set[int] = set()
_cancel_requested: set[int] = set()
_lock = threading.Lock()


class TaskCancelledError(Exception):
    """用户主动取消抓取任务。"""


def _check_cancelled(task_id: int) -> None:
    with _lock:
        if task_id in _cancel_requested:
            raise TaskCancelledError("用户已取消任务")


def _append_log(run: CrawlTaskRun, line: str, session: Session) -> None:
    ts = format_display_datetime(datetime.utcnow(), fmt="%H:%M:%S")
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
    meta["pool_type"] = "arxiv"
    return meta


def _task_semantic_threshold(task: CrawlTask) -> float:
    val = getattr(task, "min_semantic_score", None)
    if val is not None and val >= 0:
        return float(val)
    return float(task.min_match_score or 50.0)


def _task_quality_threshold(task: CrawlTask) -> float:
    return float(getattr(task, "min_quality_score", None) or 0.0)


def _quality_filter_enabled(task: CrawlTask) -> bool:
    return bool(getattr(task, "enable_quality_filter", False))


def _collect_candidate_pools(task: CrawlTask, run: CrawlTaskRun, session: Session) -> dict[str, list[dict]]:
    """分层候选池：arxiv=前沿预印本，openreview=顶会录用。"""
    sources = _parse_sources(task)
    _append_log(run, f"抓取数据源: {', '.join(sources)}", session)
    pools: dict[str, list[dict]] = {"arxiv": [], "openreview": [], "openalex": []}

    if "arxiv" in sources:
        categories = task.categories or ""
        if not categories.strip():
            raise ValueError("已选择 arXiv 源，请填写 arXiv 分类")
        raw_list = fetch_arxiv_candidates(categories)
        pools["arxiv"] = [_meta_from_arxiv(raw) for raw in raw_list]
        _append_log(run, f"[预印本池] 从 arXiv 获取候选 {len(pools['arxiv'])} 篇", session)

    if "openreview" in sources:
        venues = getattr(task, "openreview_venues", None) or ""
        if not venues.strip():
            raise ValueError("已选择 OpenReview 源，请选择会议/venue")
        or_list = fetch_openreview_candidates(
            venues,
            max_per_venue=task.max_papers_per_run * 3,
            only_accepted=True,
        )
        for meta in or_list:
            meta["pool_type"] = "openreview"
        pools["openreview"] = or_list
        _append_log(
            run,
            f"[顶会池] 从 OpenReview 获取已接收候选 {len(or_list)} 篇",
            session,
        )

    if "openalex" in sources:
        search_q = build_interest_text(task.intent_text or "", task.keywords or "")
        year_from = getattr(task, "openalex_year_from", None)
        year_to = getattr(task, "openalex_year_to", None)
        if year_to is None:
            year_to = datetime.utcnow().year
        if year_from is None:
            year_from = year_to - 2
        oa_list = fetch_openalex_candidates(
            search_q,
            venue_types=getattr(task, "openalex_venue_types", None) or "conference,journal",
            ccf_ranks=getattr(task, "openalex_ccf_ranks", None) or "A,B,C",
            year_from=year_from,
            year_to=year_to,
            venue_names=getattr(task, "openalex_venue_names", None) or "",
            max_results=task.max_papers_per_run * 3,
        )
        pools["openalex"] = oa_list
        _append_log(
            run,
            f"[综合期刊/会议池] 从 OpenAlex 获取 CCF 过滤后候选 {len(oa_list)} 篇（{year_from}-{year_to}）",
            session,
        )

    if not sources:
        raise ValueError("请至少选择一种抓取数据源")
    return pools


def _enrich_openreview_meta(meta: dict) -> None:
    if meta.get("source") != "openreview":
        return
    forum_id = meta.get("openreview_id")
    meta["pdf_url"] = resolve_openreview_pdf_url(meta.get("pdf_url"), forum_id or "")
    if forum_id and meta.get("review_rating") is None:
        meta["review_rating"] = fetch_review_rating(forum_id)
    if meta.get("citation_count") is None:
        meta["citation_count"] = fetch_citation_count(meta["paper_id"], meta.get("title", ""))


def _merge_existing_paper_signals(session: Session, meta: dict) -> dict:
    paper = session.query(Paper).filter(Paper.arxiv_id == meta["paper_id"]).first()
    return merge_paper_quality_signals(meta, paper)


def _score_candidate_pool(
    pool_name: str,
    candidates: list[dict],
    *,
    interest_vec: list[float],
    task: CrawlTask,
    session: Session,
    run: CrawlTaskRun,
) -> list[tuple[float, float, dict]]:
    if not candidates:
        return []

    min_sem = _task_semantic_threshold(task)
    min_qual = _task_quality_threshold(task)
    use_quality_filter = _quality_filter_enabled(task)

    for meta in candidates:
        if meta.get("source") == "openreview":
            _enrich_openreview_meta(meta)
        meta.update(_merge_existing_paper_signals(session, meta))

    semantic_scores = batch_semantic_scores(interest_vec, candidates)
    scored: list[tuple[float, float, dict]] = []
    rejected_sem = 0
    rejected_qual = 0

    for meta, sem in zip(candidates, semantic_scores):
        meta["semantic_score"] = sem
        qual = compute_quality_score(meta)
        meta["quality_score"] = qual
        if sem < min_sem:
            rejected_sem += 1
            continue
        if use_quality_filter and qual < min_qual:
            rejected_qual += 1
            continue
        scored.append((sem, qual, meta))

    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    scored = scored[: task.max_papers_per_run]
    qual_hint = f"，质量≥{min_qual}" if use_quality_filter else "（未启用质量过滤）"
    reject_detail = f"语义未通过 {rejected_sem} 篇"
    if use_quality_filter:
        reject_detail += f"，质量未通过 {rejected_qual} 篇"
    _append_log(
        run,
        f"[{pool_name}] 门槛: 语义≥{min_sem}{qual_hint} → 入选 {len(scored)} 篇（{reject_detail}）",
        session,
    )
    return scored


def _score_verified_suggestions(
    candidates: list[dict],
    *,
    interest_vec: list[float],
    session: Session,
    run: CrawlTaskRun,
) -> list[tuple[float, float, dict]]:
    """LLM 推荐且 API 核验命中的论文：跳过阈值，强制纳入。"""
    if not candidates:
        return []

    for meta in candidates:
        if meta.get("source") == "openreview":
            _enrich_openreview_meta(meta)
        meta.update(_merge_existing_paper_signals(session, meta))

    semantic_scores = batch_semantic_scores(interest_vec, candidates)
    scored: list[tuple[float, float, dict]] = []
    for meta, sem in zip(candidates, semantic_scores):
        meta["semantic_score"] = sem
        qual = compute_quality_score(meta)
        meta["quality_score"] = qual
        scored.append((sem, qual, meta))

    _append_log(run, f"[LLM推荐核验] API 命中 {len(scored)} 篇，将强制纳入", session)
    return scored


def _merge_verified_suggestions(
    scored: list[tuple[float, float, dict]],
    task: CrawlTask,
    *,
    interest_vec: list[float],
    session: Session,
    run: CrawlTaskRun,
) -> list[tuple[float, float, dict]]:
    if not getattr(task, "enable_smart_planning", False):
        return scored

    verified_json = getattr(task, "verified_suggestions_json", None) or ""
    if not verified_json.strip():
        return scored

    from src.services.suggested_paper_verifier import load_verified_metas

    try:
        vdata = json.loads(verified_json)
        _append_log(
            run,
            f"推荐论文核验: {vdata.get('summary', '')}（API 未命中/幻觉 {vdata.get('missed', 0)} 篇）",
            session,
        )
        for miss in vdata.get("hallucinated") or []:
            title = (miss.get("query_title") or "")[:100]
            _append_log(run, f"  未命中(幻觉): {title}", session)
    except json.JSONDecodeError:
        pass

    verified_metas = load_verified_metas(verified_json)
    if not verified_metas:
        return scored

    verified_scored = _score_verified_suggestions(
        verified_metas, interest_vec=interest_vec, session=session, run=run,
    )
    seen = {item[2]["paper_id"] for item in scored}
    for sem, qual, meta in verified_scored:
        pid = meta["paper_id"]
        if pid in seen:
            continue
        seen.add(pid)
        scored.append((sem, qual, meta))
        _append_log(run, f"  纳入推荐: {meta['title'][:80]}", session)
    return scored


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
        if meta.get("quality_score") is not None:
            paper.quality_score = meta.get("quality_score")
        for field in ("venue_rank", "journal_if", "jcr_quartile", "doi", "openalex_id", "venue_type"):
            val = meta.get(field)
            if val is not None and getattr(paper, field, None) in (None, ""):
                setattr(paper, field, val)
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
        doi=meta.get("doi"),
        openalex_id=meta.get("openalex_id"),
        venue_rank=meta.get("venue_rank"),
        journal_if=meta.get("journal_if"),
        jcr_quartile=meta.get("jcr_quartile"),
        quality_score=meta.get("quality_score"),
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
    except TaskCancelledError:
        run.status = "cancelled"
        run.progress = run.progress or 0
        _append_log(run, "任务已被用户取消", session)
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
            _cancel_requested.discard(task_id)

    return run_id


def _run_crawl(session: Session, task_id: int, run: CrawlTaskRun) -> None:
    task = session.query(CrawlTask).filter(CrawlTask.id == task_id).first()
    if not task:
        raise ValueError("任务不存在")

    planning_status = getattr(task, "planning_status", None) or "none"
    if task.enable_smart_planning and planning_status == "planning":
        raise ValueError("智能规划进行中，请稍候再执行")
    if task.enable_smart_planning and planning_status == "failed":
        err = getattr(task, "planning_error", None) or "未知错误"
        raise ValueError(f"智能规划失败，无法执行：{err}")

    stats = {
        "candidates": 0,
        "matched": 0,
        "new_entries": 0,
        "skipped_dup": 0,
        "new_papers": 0,
        "download_failed": 0,
        "arxiv_matched": 0,
        "openreview_matched": 0,
        "openalex_matched": 0,
    }

    _append_log(run, f"开始执行任务: {task.name}（入库目标: {'公开文献' if task.visibility == 'public' else '私有文献'}）", session)
    if getattr(task, "enable_smart_planning", False) and getattr(task, "plan_summary", ""):
        _append_log(run, f"智能规划摘要: {task.plan_summary}", session)
    _append_log(run, "匹配模式: Embedding 语义相关分 + 独立质量分", session)

    _check_cancelled(task_id)

    run.progress = 10
    session.add(run)
    session.commit()

    pools = _collect_candidate_pools(task, run, session)
    stats["candidates"] = sum(len(v) for v in pools.values())

    _check_cancelled(task_id)

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
        _append_log(run, f"中文自动翻译失败，将使用原文做语义向量（{exc}）", session)

    intent_for_match = match_query["intent_text"]
    keywords_for_match = match_query["keywords"]
    if not except_translation and match_query["translated"]:
        _append_log(run, "检测到中文输入，兴趣/关键词已译英后编码语义向量：", session)
        if "intent" in match_query["translated_fields"]:
            _append_log(run, f"  兴趣原文: {match_query['original_intent'][:120]}", session)
            _append_log(run, f"  兴趣译文: {intent_for_match[:200]}", session)
        if "keywords" in match_query["translated_fields"]:
            _append_log(run, f"  关键词原文: {match_query['original_keywords']}", session)
            _append_log(run, f"  关键词译文: {keywords_for_match}", session)

    interest_vec = encode_interest_vector(intent_for_match, keywords_for_match)
    _append_log(run, "已预计算兴趣+关键词联合 Embedding 向量", session)

    run.progress = 25
    session.add(run)
    session.commit()

    scored: list[tuple[float, float, dict]] = []
    if pools.get("arxiv"):
        arxiv_scored = _score_candidate_pool(
            "预印本池", pools["arxiv"], interest_vec=interest_vec, task=task, session=session, run=run,
        )
        stats["arxiv_matched"] = len(arxiv_scored)
        scored.extend(arxiv_scored)
    if pools.get("openreview"):
        or_scored = _score_candidate_pool(
            "顶会池", pools["openreview"], interest_vec=interest_vec, task=task, session=session, run=run,
        )
        stats["openreview_matched"] = len(or_scored)
        scored.extend(or_scored)
    if pools.get("openalex"):
        oa_scored = _score_candidate_pool(
            "综合期刊/会议池", pools["openalex"], interest_vec=interest_vec, task=task, session=session, run=run,
        )
        stats["openalex_matched"] = len(oa_scored)
        scored.extend(oa_scored)

    stats["matched"] = len(scored)
    _append_log(
        run,
        f"分层入选合计 {len(scored)} 篇（预印本 {stats['arxiv_matched']}，顶会 {stats['openreview_matched']}，OpenAlex {stats['openalex_matched']}）",
        session,
    )

    scored = _merge_verified_suggestions(
        scored, task, interest_vec=interest_vec, session=session, run=run,
    )
    stats["matched"] = len(scored)

    _check_cancelled(task_id)

    run.progress = 40
    session.add(run)
    session.commit()

    owner_id = "" if task.visibility == "public" else task.user_id
    new_paper_ids: list[str] = []

    for idx, (sem_score, qual_score, meta) in enumerate(scored):
        _check_cancelled(task_id)
        paper_id = meta["paper_id"]
        pool_type = meta.get("pool_type") or meta.get("source", "arxiv")

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
        new_paper_ids.append(paper_id)

        entry = LiteratureEntry(
            arxiv_id=paper_id,
            user_id=owner_id,
            visibility=task.visibility,
            match_score=sem_score,
            semantic_score=sem_score,
            quality_score=qual_score,
            pool_type=pool_type,
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

    if new_paper_ids:
        _append_log(run, f"已排队 LLM 质量评估 {len(new_paper_ids)} 篇（后台异步）", session)
        schedule_quality_assessment(new_paper_ids)

    run.stats_json = json.dumps(stats, ensure_ascii=False)
    _append_log(run, f"完成。统计: {json.dumps(stats, ensure_ascii=False)}", session)
    session.add(run)
    session.commit()


def run_task_async(task_id: int, trigger_type: str = "manual") -> None:
    thread = threading.Thread(target=execute_crawl_run, args=(task_id, trigger_type), daemon=True)
    thread.start()


def request_cancel_task(task_id: int) -> bool:
    """标记运行中的抓取任务为待取消。"""
    with _lock:
        if task_id not in _running_tasks:
            return False
        _cancel_requested.add(task_id)
        return True


def is_task_running(task_id: int) -> bool:
    with _lock:
        return task_id in _running_tasks


def cancel_task_run(task_id: int) -> bool:
    return request_cancel_task(task_id)
