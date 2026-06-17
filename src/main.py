import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.settings import get_settings
from src.utils.logging_config import setup_logger
from src.routers import router
from fastapi.staticfiles import StaticFiles

get_settings()

app = FastAPI(limits={"max_file_size": 50 * 1024 * 1024})
app.include_router(router)  # 创建路由模块，把多个路由统一管理
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

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
    uvicorn.run("main:app", host="127.0.0.1", port=8080, workers=10, reload=True,timeout_keep_alive=120)
