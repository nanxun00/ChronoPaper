"""抓取任务定时调度。"""
from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.models.base import SessionLocal
from src.models.crawl import CrawlTask
from src.services.crawl_service import is_task_running, run_task_async
from src.utils.logging_config import setup_logger

logger = setup_logger("CrawlScheduler")

_scheduler: BackgroundScheduler | None = None


def _parse_schedule(schedule_time: str | None) -> tuple[str, str] | None:
    if not schedule_time:
        return None
    parts = schedule_time.strip().split(":")
    if len(parts) != 2:
        return None
    hour, minute = parts[0].zfill(2), parts[1].zfill(2)
    return hour, minute


def _job_run(task_id: int) -> None:
    if is_task_running(task_id):
        logger.info("skip scheduled run, task %s already running", task_id)
        return
    run_task_async(task_id, trigger_type="schedule")


def refresh_scheduler() -> None:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
        _scheduler.start()

    _scheduler.remove_all_jobs()
    session = SessionLocal()
    try:
        tasks = session.query(CrawlTask).filter(CrawlTask.enabled.is_(True)).all()
        for task in tasks:
            ps = getattr(task, "planning_status", None) or "none"
            if task.enable_smart_planning and ps not in ("none", "ready"):
                continue
            parsed = _parse_schedule(task.schedule_time)
            if not parsed:
                continue
            hour, minute = parsed
            _scheduler.add_job(
                _job_run,
                CronTrigger(hour=int(hour), minute=int(minute)),
                args=[task.id],
                id=f"crawl_task_{task.id}",
                replace_existing=True,
            )
            logger.info("scheduled crawl task %s at %s:%s", task.id, hour, minute)
    finally:
        session.close()


def start_crawl_scheduler() -> None:
    refresh_scheduler()
