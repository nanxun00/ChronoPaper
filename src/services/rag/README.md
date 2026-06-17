# RAG 栈（知识库 + 检索 + 图谱）

本目录承载**自建知识库**相关的业务实现，与 `Requirements.md` 第十二～十三章对应。

## 模块说明

| 文件 | 职责 |
|------|------|
| `startup.py` | 应用启动时初始化 DataBaseManager、Retriever |
| `database.py` | 知识库 CRUD、Milvus 集合管理（`database.json` 元数据） |
| `knowledgebase.py` | 单库向量检索 |
| `retriever.py` | 对话 RAG 检索编排 |
| `graphbase.py` | Neo4j 图谱读写 |
| `indexing.py` | 文本分块 |
| `filereader.py` | PDF/纯文本读取 |
| `history.py` | 对话历史管理 |

## API 与前端

| 能力 | 后端 | 前端 |
|------|------|------|
| 知识库 | `api/v1/knowledge_base.py` (`/data`) | `views/knowledge/` |
| 图谱 | `knowledge_base.py` 内 `/data/graph/*` | `views/graph/` |
| 对话 RAG | `api/v1/chat.py` | `views/chat/` |
| SmartBI | `api/v1/smartbi.py` | `views/smartbi/` |

## 兼容

`src/core/__init__.py` 仍 re-export 本包，旧代码 `from src.core import startup` 可继续使用。

## 注意

- **新 arXiv 文献、抓取任务** 走 `services/crawl_service.py` + MySQL，**不要**写入本目录的 `database.json` 体系。
- 后续可将本栈逐步重构为 `services/knowledge_base_service.py` + `integrations/milvus/`，但 V1 功能需保持可用。
