import src.env_bootstrap  # noqa: F401 — USE_TF=0 before transformers
import os
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.settings import get_settings
from src.utils.logging_config import setup_logger
from src.models.base import init_db
from fastapi.staticfiles import StaticFiles
from src.services.scheduler import start_crawl_scheduler
from src.utils.paths import UPLOADS_DIR, ensure_papers_dir

get_settings()
# 须在 import router/startup 之前建表：startup 模块加载时会立即查询 knowledge_base
init_db()
from src.api import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_papers_dir()
    init_db()
    start_crawl_scheduler()
    from src.workers.celery_supervisor import start_celery_worker, stop_celery_worker

    start_celery_worker()
    yield
    stop_celery_worker()


app = FastAPI(limits={"max_file_size": 50 * 1024 * 1024}, lifespan=lifespan)
app.include_router(router)  # 创建路由模块，把多个路由统一管理
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

# CORS 设置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


logger = setup_logger("server:main")    # 记录日志


if __name__ == "__main__":
    # workers 须为 1，否则每个 worker 会各起一个 Celery 子进程
    uvicorn.run("src.main:app", host="127.0.0.1", port=8081, workers=1, reload=True, timeout_keep_alive=120)
