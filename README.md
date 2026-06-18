# ChronoPaper

面向科研团队的论文智能化管理、时序溯源、AI 精读与 LaTeX 编译一体化系统。

更多说明见 [Requirements.md](Requirements.md)（业务需求）、[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)（代码结构）。

## 本地开发（Windows）

推荐使用独立 conda 环境 `chronopaper`（Python 3.12）。在 Windows 上请先设置 `PYTHONNOUSERSITE=1`，避免用户目录 `AppData\Roaming\Python` 下的包污染 conda 环境（否则 Celery worker 等子进程可能出现 `ModuleNotFoundError`，例如缺少 `idna`）。

```powershell
conda create -n chronopaper python=3.12 -y
conda activate chronopaper
cd xx\ChronoPaper

# 安装依赖
$env:PYTHONNOUSERSITE="1"
pip install -r requirements.txt

# 启动后端
$env:PYTHONNOUSERSITE="1"
uvicorn src.main:app --host 127.0.0.1 --port 8081
```

复制 `.env.example` 为 `.env` 并按需配置 MySQL、Redis、Milvus、Neo4j 等连接信息。若启用 Celery 异步任务，需保证 Redis 可用。

前端（另开终端）：

```powershell
cd ChronoPaper_web
npm install
npm run dev
```
