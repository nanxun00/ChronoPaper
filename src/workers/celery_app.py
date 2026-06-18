"""Celery 应用配置。"""
from __future__ import annotations

from celery import Celery

from src.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "chronopaper",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["src.workers.index_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
)
