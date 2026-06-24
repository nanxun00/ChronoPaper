"""随 uvicorn 自动拉起/关闭 Celery worker 子进程。"""
from __future__ import annotations

import atexit
import os
import subprocess
import sys
from pathlib import Path

from src.settings import PROJECT_ROOT, get_settings
from src.utils.logging_config import setup_logger

logger = setup_logger("CelerySupervisor", console=True)

_celery_proc: subprocess.Popen | None = None


def _celery_pool_args() -> list[str]:
    if sys.platform == "win32":
        return ["--pool=solo"]
    return ["--concurrency=2"]


def start_celery_worker() -> bool:
    """启动 Celery worker 子进程；已运行则跳过。"""
    global _celery_proc

    settings = get_settings()
    if not settings.auto_start_celery_worker:
        logger.info("AUTO_START_CELERY_WORKER=false，跳过 Celery 自启动")
        return False

    if _celery_proc is not None and _celery_proc.poll() is None:
        logger.info("Celery worker 已在运行 (pid=%s)", _celery_proc.pid)
        return True

    cmd = [
        sys.executable,
        "-m",
        "celery",
        "-A",
        "src.workers.celery_app",
        "worker",
        "-l",
        "info",
        *_celery_pool_args(),
    ]
    env = os.environ.copy()
    env.setdefault("PYTHONNOUSERSITE", "1")
    env.setdefault("USE_TF", "0")
    env.setdefault("USE_TORCH", "1")

    cwd = str(PROJECT_ROOT)
    logger.info("Starting Celery worker: %s", " ".join(cmd))
    try:
        _celery_proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env,
        )
    except Exception as exc:
        logger.exception("Failed to start Celery worker: %s", exc)
        _celery_proc = None
        return False

    logger.info("Celery worker started (pid=%s)", _celery_proc.pid)
    return True


def stop_celery_worker() -> None:
    """终止 Celery worker 子进程。"""
    global _celery_proc
    if _celery_proc is None:
        return

    if _celery_proc.poll() is None:
        logger.info("Stopping Celery worker (pid=%s)", _celery_proc.pid)
        _celery_proc.terminate()
        try:
            _celery_proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            logger.warning("Celery worker did not exit in time, killing")
            _celery_proc.kill()
            _celery_proc.wait(timeout=5)
    _celery_proc = None


atexit.register(stop_celery_worker)
