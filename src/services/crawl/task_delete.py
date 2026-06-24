"""抓取任务软删除。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from src.models.crawl import CrawlTask
from src.services.crawl.crawl_planning_job import cancel_smart_planning, is_smart_planning
from src.services.crawl.crawl_service import is_task_running, request_cancel_task


def active_task_query(db: Session, user_id: str):
    return db.query(CrawlTask).filter(
        CrawlTask.user_id == user_id,
        CrawlTask.is_deleted.is_(False),
    )


def get_active_task(db: Session, user_id: str, task_id: int) -> CrawlTask | None:
    return active_task_query(db, user_id).filter(CrawlTask.id == task_id).first()


def soft_delete_tasks(db: Session, user_id: str, task_ids: list[int]) -> dict:
    """标记删除任务；定时任务同时停用调度。"""
    unique_ids: list[int] = []
    seen: set[int] = set()
    for raw in task_ids:
        try:
            tid = int(raw)
        except (TypeError, ValueError):
            continue
        if tid <= 0 or tid in seen:
            continue
        seen.add(tid)
        unique_ids.append(tid)

    deleted: list[int] = []
    not_found: list[int] = []
    cancelled: list[int] = []

    for task_id in unique_ids:
        row = db.query(CrawlTask).filter(
            CrawlTask.id == task_id,
            CrawlTask.user_id == user_id,
        ).first()
        if not row or row.is_deleted:
            not_found.append(task_id)
            continue

        if is_task_running(task_id):
            request_cancel_task(task_id)
            cancelled.append(task_id)
        elif is_smart_planning(task_id) or (
            row.enable_smart_planning and (row.planning_status or "none") == "planning"
        ):
            cancel_smart_planning(task_id)
            cancelled.append(task_id)

        row.is_deleted = True
        row.deleted_at = datetime.utcnow()
        row.enabled = False
        db.add(row)
        deleted.append(task_id)

    if deleted:
        db.commit()

    return {
        "deleted": len(deleted),
        "deleted_ids": deleted,
        "not_found": not_found,
        "cancelled": cancelled,
    }
