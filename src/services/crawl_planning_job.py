"""智能规划后台任务：创建任务后立即返回，规划在后台执行。"""
from __future__ import annotations

import threading

from src.models.base import SessionLocal
from src.models.crawl import CrawlTask
from src.services.crawl_planner import build_smart_plan_fields
from src.services.scheduler_service import refresh_scheduler
from src.utils.logging_config import setup_logger

logger = setup_logger("CrawlPlanningJob")

_planning_lock = threading.Lock()
_planning_tasks: set[int] = set()


def is_smart_planning(task_id: int) -> bool:
    with _planning_lock:
        return task_id in _planning_tasks


def run_smart_plan_for_task(task_id: int) -> None:
    with _planning_lock:
        _planning_tasks.add(task_id)
    session = SessionLocal()
    try:
        task = session.query(CrawlTask).filter(CrawlTask.id == task_id).first()
        if not task or not task.enable_smart_planning:
            return
        status = getattr(task, "planning_status", None) or "none"
        if status != "planning":
            return

        fields = build_smart_plan_fields(task.intent_text or "")

        session.refresh(task)
        if (getattr(task, "planning_status", None) or "none") != "planning":
            logger.info("Smart planning aborted for task %s (cancelled)", task_id)
            return

        suggested_name = fields.pop("suggested_name", "")
        for key, value in fields.items():
            setattr(task, key, value)
        if suggested_name and not (task.name or "").strip():
            task.name = suggested_name
        session.add(task)
        session.commit()
        logger.info("Smart planning ready for task %s", task_id)
        refresh_scheduler()
    except Exception as exc:
        logger.exception("Smart planning failed task_id=%s", task_id)
        session.rollback()
        task = session.query(CrawlTask).filter(CrawlTask.id == task_id).first()
        if task and (getattr(task, "planning_status", None) or "none") == "planning":
            task.planning_status = "failed"
            task.planning_error = str(exc)[:500]
            session.add(task)
            session.commit()
    finally:
        session.close()
        with _planning_lock:
            _planning_tasks.discard(task_id)


def cancel_smart_planning(task_id: int) -> bool:
    session = SessionLocal()
    try:
        task = session.query(CrawlTask).filter(CrawlTask.id == task_id).first()
        if not task:
            return False
        status = getattr(task, "planning_status", None) or "none"
        if status != "planning":
            return False
        task.planning_status = "cancelled"
        task.planning_error = "用户已取消"
        session.add(task)
        session.commit()
        return True
    finally:
        session.close()


def schedule_smart_planning(task_id: int) -> None:
    threading.Thread(target=run_smart_plan_for_task, args=[task_id], daemon=True).start()
