"""抓取任务 API。"""
from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.deps import UserInDB, get_current_active_user, get_db
from src.models.crawl import CrawlTask, CrawlTaskRun
from src.schemas.task import CrawlTaskCreate, CrawlTaskUpdate
from src.services.crawl_service import is_task_running, run_task_async
from src.services.scheduler_service import refresh_scheduler

router = APIRouter(prefix="/tasks", tags=["tasks"])


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
    visibility_label = "公开文献" if t.visibility == "public" else "私有文献"
    sources = getattr(t, "sources", None) or "arxiv"
    return {
        "id": t.id,
        "name": t.name,
        "type": "crawl",
        "intent_text": t.intent_text,
        "sources": sources,
        "categories": t.categories,
        "openreview_venues": getattr(t, "openreview_venues", None) or "",
        "keywords": t.keywords,
        "visibility": t.visibility,
        "visibility_label": visibility_label,
        "schedule_time": t.schedule_time,
        "min_match_score": t.min_match_score,
        "max_papers_per_run": t.max_papers_per_run,
        "enabled": t.enabled,
        "status": status,
        "progress": progress,
        "created_at": t.created_at.strftime("%Y-%m-%d %H:%M:%S") if t.created_at else "",
        "last_run": t.last_run_at.strftime("%Y-%m-%d %H:%M:%S") if t.last_run_at else None,
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
    if "arxiv" in sources and not body.categories.strip():
        raise HTTPException(status_code=400, detail="已选择 arXiv，请填写分类")
    if "openreview" in sources and not body.openreview_venues.strip():
        raise HTTPException(status_code=400, detail="已选择 OpenReview，请选择会议/venue")


@router.post("/crawl")
def create_crawl_task(
    body: CrawlTaskCreate,
    current_user: UserInDB = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _validate_crawl_sources(body)

    row = CrawlTask(
        user_id=current_user.userid,
        name=body.name,
        intent_text=body.intent_text,
        sources=body.sources or "arxiv",
        categories=body.categories,
        openreview_venues=body.openreview_venues,
        keywords=body.keywords,
        visibility=body.visibility,
        schedule_time=body.schedule_time,
        min_match_score=body.min_match_score,
        max_papers_per_run=body.max_papers_per_run,
        enabled=body.enabled,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    refresh_scheduler()
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
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
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
    if not is_task_running(task_id):
        return {"message": "任务未在运行"}
    return {"message": "已请求取消（当前执行批次将完成后停止）"}
