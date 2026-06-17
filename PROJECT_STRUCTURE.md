# ChronoPaper 项目结构约束

本文档约定**什么类型的代码放进哪个文件夹**。新增或移动代码前请先对照此表，避免逻辑散落、循环依赖和「旧新两套体系混写」。

---

## 一、仓库顶层

```
ChronoPaper/
├── src/                 # 后端（Python / FastAPI）
├── ChronoPaper_web/     # 前端（Vue 3 / Vite）
├── Requirements.md      # 业务需求（功能边界）
├── PROJECT_STRUCTURE.md # 本文件
├── requirements.txt     # 后端 Python 依赖
└── .env / .env.example  # 环境变量（禁止提交 .env）
```

| 放这里 | 不放这里 |
|--------|----------|
| 需求文档、结构说明、部署脚本 | 业务逻辑代码 |
| 全仓库级配置模板 | 具体 API Key、密码 |

---

## 二、后端 `src/` 分层规则

### 2.1 总原则

```
请求 → api/ → services/ → models/ + integrations/ + parsers/
                ↓
            workers/（异步执行）
```

| 层级 | 职责 | 禁止 |
|------|------|------|
| **api/** | HTTP 路由、参数校验、鉴权、返回 JSON | 写 arXiv 抓取、PDF 解析、Milvus 操作等业务 |
| **services/** | 业务编排：多步骤流程、事务、任务状态 | 直接 `requests.get` 调 arXiv；不定义 ORM 表 |
| **integrations/** | 对接外部系统（arXiv、Milvus、MinIO、LLM） | 业务判断（如「是否入私有库」） |
| **models/** | SQLAlchemy ORM、表结构 | HTTP、Pydantic 入参、复杂业务 |
| **schemas/** | Pydantic 请求/响应模型 | 数据库操作 |
| **domain/** | 枚举、值对象、纯数据结构 | IO、框架依赖 |
| **parsers/** | PDF / TeX 解析实现 | 路由、任务调度 |
| **workers/** | 后台线程/Celery 入口，调用 services | 复杂业务逻辑（应下沉到 services） |
| **services/rag/** | 自建知识库、Milvus RAG、Neo4j 图谱、Retriever | arXiv 抓取、MySQL 文献表 |
| **utils/** | 日志、密码、Token 等无业务工具 | 任何业务逻辑 |

---

### 2.2 `src/api/` — HTTP 层

```
api/
├── deps.py              # get_db、get_current_user 等 Depends
├── v1/                  # 正式业务 API（与 Requirements 对齐）
│   ├── auth.py          # 登录、注册、/users/me
│   ├── tasks.py         # 抓取 / 编译 / 时序任务
│   ├── literature.py    # 文献列表、详情、收藏
│   ├── chat.py          # 对话 RAG
│   ├── knowledge_base.py # 自建知识库 /data、图谱 /data/graph
│   ├── smartbi.py       # SmartBI 图表
│   ├── audio.py         # 语音转写（可选依赖 dashscope）
│   ├── image.py         # 图片 OCR
│   ├── search.py        # 关键词 / 语义 / 图文检索
│   ├── ideas.py         # Idea CRUD、匹配分
│   ├── timerag.py       # 时序分析任务
│   ├── latex.py         # LaTeX 项目与编译
│   ├── admin.py         # 管理员配置、限额
│   ├── tools.py         # 文档工具 HTTP 入口
│   └── system.py        # 健康检查、/config、/log
```

**什么代码进 api/v1：**

- `@router.get/post` 路由函数
- `Depends(get_current_active_user)` 鉴权
- 调用 `services.xxx()` 并返回结果
- 使用 `schemas/` 中的 Pydantic 模型做入参/出参

**什么代码不进 api：**

- arXiv RSS 拉取、相似度计算、PDF 下载
- Milvus insert/search
- 超过 10 行的业务 if/else 链 → 移到 `services/`

---

### 2.3 `src/services/` — 业务层

| 文件 | 负责 |
|------|------|
| `crawl_service.py` | 抓取任务创建、执行、日志、去重入库 |
| `literature_service.py` | 公开/私有文献列表、详情、权限判断 |
| `parse_service.py` | PDF 解析流水线、更新 `parse_status` |
| `vector_service.py` | 文本/图像向量写入与检索 |
| `rag_service.py` | 带溯源的 RAG 问答 |
| `idea_service.py` | Idea 匹配、每日重算 |
| `timerag_service.py` | 时序时间线生成 |
| `latex_service.py` | 编译队列与日志 |
| `scheduler_service.py` | 定时任务注册（APScheduler） |
| `services/rag/` | 自建知识库、Milvus 向量、Neo4j 图谱、对话 Retriever（见 `services/rag/README.md`） |

**规则：**

- 一个「用户可感知的业务流程」= 一个 service 方法
- 可注入 `Session`，可调用多个 `integrations/`
- **arXiv 抓取与 MySQL 文献** 写 `crawl_service` / `literature_service`，**不要**写入 `services/rag/database.json` 体系

---

### 2.4 `src/models/` — 数据库 ORM

| 文件 | 表 / 实体 |
|------|-----------|
| `base.py` | engine、SessionLocal、init_db |
| `user.py` | users |
| `paper.py` | papers（全局 arxiv 元数据） |
| `literature.py` | literature_entries（公开/私有列表） |
| `crawl.py` | crawl_tasks、crawl_task_runs |
| `idea.py` | ideas、idea_paper_scores |
| `favorite.py` | user_favorites |
| `private_doc.py` | 用户上传 PDF |
| `latex.py` | latex_projects、compile_runs |
| `chunk.py` | paper_chunks（解析块） |

**规则：**

- 一表一类文件（或强相关多表一类文件）
- 只有字段定义、`to_dict()` 等轻量方法
- **禁止** import FastAPI、requests、Milvus

---

### 2.5 `src/schemas/` — API 契约

- 请求体：`CrawlTaskCreate`、`XxxUpdate`
- 响应体：分页、统一包装
- **仅 Pydantic BaseModel**，不访问数据库

---

### 2.6 `src/integrations/` — 外部系统

```
integrations/
├── arxiv/       # fetcher.py、matcher.py
├── milvus/      # client.py、text_index.py、image_index.py
├── minio/       # storage.py
├── neo4j/       # graph.py
└── llm/         # chat.py、embedding.py、prompts.py、selector.py
```

| 进 integrations | 不进 integrations |
|-----------------|-------------------|
| HTTP/SDK 调用封装 | 「这篇论文是否入私有库」 |
| 连接池、重试、限速 | 用户权限判断 |
| 向量 encode/search 底层 | 任务状态机 |

---

### 2.7 `src/parsers/` — 文档解析

| 文件 | 内容 |
|------|------|
| `pdf_simple.py` | 简单全文提取（过渡） |
| `pdf_layout.py` | PyMuPDF + pdfplumber 版面解析 |
| `tex_source.py` | arXiv TeX 解压 |

只做「文件 → 结构化文本/块」，不做入库编排（编排放 `parse_service`）。

---

### 2.8 `src/workers/` — 异步执行入口

- `crawl_worker.py` → 调 `crawl_service.execute_crawl_run`
- `parse_worker.py` → 调 `parse_service`
- 线程/Celery 只放**启动与回调**，逻辑在 services

---

### 2.9 `src/services/rag/` — 知识库与 RAG

```
services/rag/
├── startup.py       # DataBaseManager、Retriever 初始化
├── database.py      # 知识库 CRUD、Milvus
├── retriever.py     # 对话检索编排
├── graphbase.py     # Neo4j
└── ...
```

| 允许 | 禁止 |
|------|------|
| 维护 `/data`、`/chat`、`/smartbi` 相关逻辑 | 新 arXiv 抓取、literature_entries 入库 |
| bugfix、逐步重构至 integrations/milvus | 在 api 层直接操作 Milvus |

---

### 2.10 `src/utils/`、`src/config/`、`src/settings.py`

| 路径 | 用途 |
|------|------|
| `settings.py` | .env 统一读取 |
| `config/` | 模型列表 yaml、运行时 Config 类 |
| `utils/` | logging、password、token、captcha |

**禁止** 在 utils 里写「抓取论文」「匹配 Idea」等业务。

---

## 三、前端 `ChronoPaper_web/src/` 分层规则

### 3.1 总原则

```
views/（页面） → components/（UI 块） + api/（请求） + stores/（状态）
```

| 层级 | 职责 | 禁止 |
|------|------|------|
| **views/** | 页面布局、表格/表单、调 api | 封装通用 fetch 客户端 |
| **components/** | 可复用 UI，接收 props / emit | 直接改路由、写业务 API URL 散落多处 |
| **api/** | 所有后端请求 | DOM 操作、页面布局 |
| **stores/** | 跨页面状态（用户、配置） | 单次页面专用逻辑 |
| **composables/** | 可复用组合逻辑（useAuth） | 整页 UI |
| **router/** | 路由表 | 业务逻辑 |

---

### 3.2 `src/api/` — 接口层

```
api/
├── client.js       # authHeaders、apiJson（唯一 fetch 封装）
├── tasks.js        # 任务相关 API
├── literature.js   # 文献相关 API
└── index.js
```

**规则：**

- **所有** `/api/...` 请求经 `api/client.js` 或各域 `api/xxx.js`
- views 里禁止裸写 `fetch('/api/...')`（遗留代码逐步迁移）
- 一个新后端模块 = 一个新 `api/xxx.js`

---

### 3.3 `src/views/` — 页面（按业务域）

```
views/
├── auth/           # 登录、注册
├── chat/           # 对话页
├── literature/     # 文献管理
├── tasks/          # 任务中心
├── knowledge/      # 自建知识库
├── graph/          # 知识图谱
├── smartbi/        # SmartBI
├── personal/       # 个人中心
├── settings/       # 系统设置
├── tools/          # 工具列表页
├── home/           # 首页
└── error/          # 404 等
```

| 进 views | 不进 views |
|----------|------------|
| 路由对应整页 | 可在多页复用的表格行、弹窗 |
| 页面级 loading、分页 | 通用 Header、Debug 面板 |

---

### 3.4 `src/components/` — 组件（按 UI 域）

```
components/
├── common/     # HeaderComponent、DebugComponent
├── chat/       # ChatComponent、RefsComponent
├── graph/      # GraphContainer
└── tools/      # TextChunking、ConvertToTxt
```

**规则：**

- 被 **2 个及以上** views 使用 → 抽到 components
- 仅单页使用的小块 → 可放 `views/xxx/components/`（Login 的表单即如此）
- 组件内调 api 仅当该组件高度内聚（如 Chat）；否则由 view 调 api 传 props

---

### 3.5 `src/stores/` — 全局状态

```
stores/
├── modules/
│   ├── user.js      # 登录态
│   ├── config.js    # 远程配置
│   └── database.js  # 知识库列表
└── index.js
```

| 进 Pinia store | 不进 store |
|----------------|------------|
| 多页共享、需持久化 | 单页表格 data、弹窗开关 |
| 用户、全局配置 | 一次性的任务列表（可直接 api + ref） |

---

### 3.6 `src/router/modules/` — 路由模块

- 每个业务域一个文件：`literature.js`、`tasks.js`、`knowledge.js`、`graph.js` …
- `router/index.js` 只做合并，不写具体 path

---

### 3.7 `src/assets/`、`src/layouts/`

| 路径 | 内容 |
|------|------|
| `assets/` | 图片、全局 CSS、theme.js |
| `layouts/` | AppLayout、BlankLayout（导航壳） |

静态资源引用优先用 `@/assets/...`，避免相对路径 `../assets`（组件移动易断）。

---

## 四、前后端对照（新功能放哪）

| 功能 | 后端 | 前端 |
|------|------|------|
| 抓取任务 | `api/v1/tasks.py` + `services/crawl_service.py` | `api/tasks.js` + `views/tasks/` |
| 文献列表 | `api/v1/literature.py` + `services/literature_service.py` | `api/literature.js` + `views/literature/` |
| arXiv 拉取 | `integrations/arxiv/` | — |
| PDF 解析 | `parsers/` + `services/parse_service.py` | — |
| 对话 RAG | `api/v1/chat.py` + `services/rag/` | `views/chat/` + `components/chat/` |
| 自建知识库 | `api/v1/knowledge_base.py` | `views/knowledge/` |
| 知识图谱 | `knowledge_base.py` `/data/graph` | `views/graph/` |
| SmartBI | `api/v1/smartbi.py` | `views/smartbi/` |
| 文档工具 | `api/v1/tools.py` | `views/tools/` |

---

## 五、禁止事项（硬性）

1. **新 arXiv 抓取/文献** 不得写入 `services/rag/database.json` 体系  
2. **api 路由** 不得直接操作 Milvus / MinIO（经 services → integrations）  
3. **models/** 不得 import FastAPI  
4. **前端 views** 不得新增裸 `fetch`（走 `api/`）  
5. **secrets** 只进 `.env`，不进代码、不进 yaml 提交  
6. **requirements*.txt** 注释只用英文（Windows pip GBK 兼容）

---

## 六、已删除的冗余路径（勿再创建）

| 旧路径 | 替代 |
|--------|------|
| `src/routers/*_router.py` | `src/api/v1/` |
| `src/modules/` | `src/services/` + `src/integrations/` |
| `src/login/user.py`、`user_sql.py` | `src/api/deps.py` + `src/models/user.py` |
| `src/models/chat_model.py`、`embedding.py` | `src/integrations/llm/` |
| `ChronoPaper_web/src/utils/api.js` | `src/api/client.js` |
| `ChronoPaper_web/src/stores/user.js` 等 shim | `src/stores/index.js` |

---

## 七、新增功能检查清单

添加代码前自问：

- [ ] 这是 HTTP 处理、业务逻辑、外部 IO 还是 UI？是否放对层？
- [ ] 后端是否落在 `api/v1`？
- [ ] 前端是否新增/扩展了对应 `api/xxx.js`？
- [ ] ORM 是否只在 `models/`，请求体是否在 `schemas/`？
- [ ] 是否有更合适的现有 service，避免重复实现？

---

## 八、相关文档

- 业务需求：`Requirements.md`（第十二～十七章为知识库/RAG 拓展能力）
- RAG 栈说明：`src/services/rag/README.md`
- 前端目录说明：`ChronoPaper_web/src/README.md`
