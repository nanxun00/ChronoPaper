"""抓取任务 API。"""
from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.deps import UserInDB, get_current_active_user, get_db
from src.models.crawl import CrawlTask, CrawlTaskRun
from src.schemas.task import CrawlPlanRequest, CrawlTaskCreate, CrawlTaskUpdate
from src.services.crawl.crawl_planner import generate_crawl_plan
from src.services.crawl.crawl_mode_presets import CRAWL_MODE_LABELS
from src.services.crawl.crawl_planning_job import cancel_smart_planning, is_smart_planning, schedule_smart_planning
from src.services.crawl.crawl_service import is_task_running, request_cancel_task, run_task_async
from src.services.scheduler import refresh_scheduler
from src.utils.datetime_fmt import format_display_datetime

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _default_task_name(task_id: int) -> str:
    return f"抓取任务 #{task_id}"


def _ensure_task_name(row: CrawlTask, db: Session) -> None:
    if not (row.name or "").strip():
        row.name = _default_task_name(row.id)
        db.add(row)
        db.commit()
        db.refresh(row)


def _task_to_dict(t: CrawlTask, db: Session) -> dict:
    latest_run = (
        db.query(CrawlTaskRun)
        .filter(CrawlTaskRun.task_id == t.id)
        .order_by(CrawlTaskRun.id.desc())
        .first()
    )
    status = "running" if is_task_running(t.id) else (latest_run.status if latest_run else "idle")
    progress = latest_run.progress if latest_run and status == "running" else (
        100 if latest_run and latest_run.status == "done" else 0
    )
    planning_status = getattr(t, "planning_status", None) or "none"
    if t.enable_smart_planning and planning_status == "planning":
        status = "planning"
        progress = 0
    elif t.enable_smart_planning and planning_status == "failed":
        status = "planning_failed"
        progress = 0
    elif t.enable_smart_planning and planning_status == "cancelled":
        status = "cancelled"
        progress = 0
    visibility_label = "公开文献" if t.visibility == "public" else "私有文献"
    sources = getattr(t, "sources", None) or "arxiv"
    execution_mode = "daily" if t.schedule_time else "once"
    execution_mode_label = (
        f"每日定时 {t.schedule_time}" if t.schedule_time else "单次执行"
    )
    return {
        "id": t.id,
        "name": t.name,
        "type": "crawl",
        "intent_text": t.intent_text,
        "sources": sources,
        "categories": t.categories,
        "openreview_venues": getattr(t, "openreview_venues", None) or "",
        "openalex_venue_types": getattr(t, "openalex_venue_types", None) or "conference,journal",
        "openalex_ccf_ranks": getattr(t, "openalex_ccf_ranks", None) or "A,B,C",
        "openalex_year_from": getattr(t, "openalex_year_from", None),
        "openalex_year_to": getattr(t, "openalex_year_to", None),
        "openalex_venue_names": getattr(t, "openalex_venue_names", None) or "",
        "keywords": t.keywords,
        "visibility": t.visibility,
        "visibility_label": visibility_label,
        "schedule_time": t.schedule_time,
        "execution_mode": execution_mode,
        "execution_mode_label": execution_mode_label,
        "min_match_score": getattr(t, "min_semantic_score", None) or t.min_match_score,
        "min_semantic_score": getattr(t, "min_semantic_score", None) or t.min_match_score,
        "min_quality_score": getattr(t, "min_quality_score", None) or 0.0,
        "enable_quality_filter": bool(getattr(t, "enable_quality_filter", False)),
        "enable_smart_planning": bool(getattr(t, "enable_smart_planning", False)),
        "crawl_mode": getattr(t, "crawl_mode", None) or ("smart" if t.enable_smart_planning else "latest"),
        "crawl_mode_label": CRAWL_MODE_LABELS.get(
            getattr(t, "crawl_mode", None) or ("smart" if t.enable_smart_planning else "latest"),
            "最新文献跟踪",
        ),
        "planning_status": planning_status,
        "planning_error": getattr(t, "planning_error", None) or "",
        "max_papers_per_run": t.max_papers_per_run,
        "enabled": t.enabled,
        "status": status,
        "progress": progress,
        "created_at": format_display_datetime(t.created_at),
        "last_run": format_display_datetime(t.last_run_at) or None,
        "log": latest_run.log_text if latest_run else "",
    }


@router.get("")
def list_tasks(
    current_user: UserInDB = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(CrawlTask)
        .filter(CrawlTask.user_id == current_user.userid)
        .order_by(CrawlTask.id.desc())
        .all()
    )
    return {"tasks": [_task_to_dict(t, db) for t in rows]}


def _validate_crawl_sources(body: CrawlTaskCreate) -> None:
    sources = [s.strip() for s in (body.sources or "arxiv").split(",") if s.strip()]
    if not sources:
        raise HTTPException(status_code=400, detail="请至少选择一种抓取数据源")
    needs_query = {"arxiv", "openreview", "openalex"} & set(sources)
    if needs_query and not (body.intent_text.strip() or body.keywords.strip()):
        raise HTTPException(status_code=400, detail="请填写研究兴趣描述或关键词，用于文献检索")
    if "openalex" in sources:
        if not body.openalex_venue_types.strip():
            raise HTTPException(status_code=400, detail="OpenAlex 请至少选择一种文献类型")
    if {"openreview", "openalex"} & set(sources) and not body.openalex_ccf_ranks.strip():
        raise HTTPException(status_code=400, detail="请至少选择一种 CCF 分级")


@router.post("/crawl-plan")
def plan_crawl_task(
    body: CrawlPlanRequest,
    current_user: UserInDB = Depends(get_current_active_user),
):
    del current_user
    existing = [s.strip() for s in (body.existing_sources or "").split(",") if s.strip()]
    try:
        plan = generate_crawl_plan(body.domain_description, existing_sources=existing or None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"智能规划失败: {exc}") from exc
    return plan


@router.post("/crawl")
def create_crawl_task(
    body: CrawlTaskCreate,
    current_user: UserInDB = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    async_smart_plan = bool(body.enable_smart_planning)
    crawl_mode = body.crawl_mode or ("smart" if async_smart_plan else "latest")
    if body.auto_run and body.schedule_time:
        raise HTTPException(status_code=400, detail="单次执行与每日定时不能同时开启")
    if not body.auto_run and not body.schedule_time:
        raise HTTPException(status_code=400, detail="请选择单次执行或设置每日定时时间")
    if not async_smart_plan:
        _validate_crawl_sources(body)

    semantic_threshold = body.min_semantic_score if body.min_semantic_score is not None else body.min_match_score
    library_id = None
    if body.visibility == "private":
        from src.services.literature.library_service import resolve_private_library_id

        try:
            library_id = resolve_private_library_id(
                db, current_user.userid, body.library_id, required=True
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    row = CrawlTask(
        user_id=current_user.userid,
        name=(body.name or "").strip(),
        intent_text=body.intent_text,
        sources="" if async_smart_plan else (body.sources or "arxiv"),
        categories="" if async_smart_plan else body.categories,
        openreview_venues="" if async_smart_plan else "",
        openalex_venue_types=body.openalex_venue_types if not async_smart_plan else "conference,journal",
        openalex_ccf_ranks=body.openalex_ccf_ranks if not async_smart_plan else "A,B,C",
        openalex_year_from=body.openalex_year_from,
        openalex_year_to=body.openalex_year_to,
        openalex_venue_names="" if async_smart_plan else body.openalex_venue_names,
        keywords="" if async_smart_plan else body.keywords,
        visibility=body.visibility,
        library_id=library_id,
        schedule_time=body.schedule_time if not body.auto_run else None,
        auto_run_on_ready=bool(body.auto_run and async_smart_plan),
        min_match_score=semantic_threshold,
        min_semantic_score=semantic_threshold,
        min_quality_score=body.min_quality_score,
        enable_quality_filter=body.enable_quality_filter,
        enable_smart_planning=body.enable_smart_planning,
        crawl_mode=crawl_mode,
        plan_summary="" if async_smart_plan else (body.plan_summary or "").strip(),
        verified_suggestions_json=None if async_smart_plan else ((body.verified_suggestions_json or "").strip() or None),
        planning_status="planning" if async_smart_plan else "none",
        planning_error="",
        max_papers_per_run=body.max_papers_per_run,
        enabled=body.enabled,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    _ensure_task_name(row, db)

    if async_smart_plan:
        schedule_smart_planning(row.id)
        refresh_scheduler()
        return {
            "message": "任务已创建，智能规划正在后台进行"
            + ("，完成后将自动执行" if body.auto_run else ""),
            "task": _task_to_dict(row, db),
        }

    refresh_scheduler()
    if body.auto_run:
        run_task_async(row.id, trigger_type="manual")
        return {"message": "任务已创建并已开始执行", "task": _task_to_dict(row, db)}

    return {"message": "任务创建成功", "task": _task_to_dict(row, db)}


@router.get("/{task_id}")
def get_task(
    task_id: int,
    current_user: UserInDB = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    row = db.query(CrawlTask).filter(CrawlTask.id == task_id, CrawlTask.user_id == current_user.userid).first()
    if not row:
        raise HTTPException(status_code=404, detail="任务不存在")
    latest_runs = (
        db.query(CrawlTaskRun)
        .filter(CrawlTaskRun.task_id == task_id)
        .order_by(CrawlTaskRun.id.desc())
        .limit(5)
        .all()
    )
    data = _task_to_dict(row, db)
    data["runs"] = [
        {
            "id": r.id,
            "status": r.status,
            "trigger_type": r.trigger_type,
            "progress": r.progress,
            "stats": json.loads(r.stats_json or "{}"),
            "started_at": format_display_datetime(r.started_at) or None,
            "finished_at": format_display_datetime(r.finished_at) or None,
            "log": r.log_text,
        }
        for r in latest_runs
    ]
    return data


@router.patch("/{task_id}")
def update_task(
    task_id: int,
    body: CrawlTaskUpdate,
    current_user: UserInDB = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    row = db.query(CrawlTask).filter(CrawlTask.id == task_id, CrawlTask.user_id == current_user.userid).first()
    if not row:
        raise HTTPException(status_code=404, detail="任务不存在")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    row.updated_at = datetime.utcnow()
    db.add(row)
    db.commit()
    refresh_scheduler()
    return {"message": "更新成功", "task": _task_to_dict(row, db)}


@router.delete("/{task_id}")
def delete_task(
    task_id: int,
    current_user: UserInDB = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    row = db.query(CrawlTask).filter(CrawlTask.id == task_id, CrawlTask.user_id == current_user.userid).first()
    if not row:
        raise HTTPException(status_code=404, detail="任务不存在")
    if is_task_running(task_id):
        raise HTTPException(status_code=400, detail="任务运行中，无法删除")
    db.delete(row)
    db.commit()
    refresh_scheduler()
    return {"message": "已删除"}


@router.post("/{task_id}/run")
def run_task_now(
    task_id: int,
    current_user: UserInDB = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    row = db.query(CrawlTask).filter(CrawlTask.id == task_id, CrawlTask.user_id == current_user.userid).first()
    if not row:
        raise HTTPException(status_code=404, detail="任务不存在")
    planning_status = getattr(row, "planning_status", None) or "none"
    if row.enable_smart_planning and planning_status == "planning":
        raise HTTPException(status_code=400, detail="智能规划进行中，请稍候再执行")
    if row.enable_smart_planning and planning_status == "failed":
        err = getattr(row, "planning_error", None) or "未知错误"
        raise HTTPException(status_code=400, detail=f"智能规划失败，无法执行：{err}")
    if row.enable_smart_planning and planning_status == "cancelled":
        raise HTTPException(status_code=400, detail="智能规划已取消，请重新创建任务")
    if is_task_running(task_id):
        raise HTTPException(status_code=400, detail="任务正在执行中")
    run_task_async(task_id, trigger_type="manual")
    return {"message": "已触发立即执行"}


@router.post("/{task_id}/cancel")
def cancel_task(
    task_id: int,
    current_user: UserInDB = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    row = db.query(CrawlTask).filter(CrawlTask.id == task_id, CrawlTask.user_id == current_user.userid).first()
    if not row:
        raise HTTPException(status_code=404, detail="任务不存在")

    planning_status = getattr(row, "planning_status", None) or "none"
    if row.enable_smart_planning and planning_status == "planning":
        if cancel_smart_planning(task_id):
            db.refresh(row)
            return {"message": "已取消智能规划", "task": _task_to_dict(row, db)}
        raise HTTPException(status_code=400, detail="无法取消该任务")

    if is_task_running(task_id):
        request_cancel_task(task_id)
        return {"message": "已请求取消，抓取将在当前步骤完成后停止"}

    if is_smart_planning(task_id):
        if cancel_smart_planning(task_id):
            return {"message": "已取消智能规划"}
        raise HTTPException(status_code=400, detail="无法取消该任务")

    raise HTTPException(status_code=400, detail="任务未在运行或规划中，无法取消")
