# ChronoPaper Web 前端目录结构

```
src/
├── main.js                 # 应用入口
├── App.vue
│
├── api/                    # 后端 API 调用（按业务域）
│   ├── client.js           # fetch 封装、Token 注入
│   ├── tasks.js            # 抓取任务
│   ├── literature.js       # 文献管理
│   └── index.js
│
├── assets/                 # 静态资源、全局样式、主题
│
├── components/             # 可复用 UI 组件（按域分类）
│   ├── common/             # Header、Debug 等通用组件
│   ├── chat/               # 对话、引用展示
│   ├── graph/              # 图谱可视化
│   └── tools/              # PDF 工具、文本分块
│
├── composables/            # 组合式逻辑（useAuth 等）
│
├── layouts/                # 页面布局壳
│   ├── AppLayout.vue
│   └── BlankLayout.vue
│
├── router/                 # 路由
│   ├── index.js            # 汇总注册
│   └── modules/            # 按业务拆分路由
│       ├── auth.js
│       ├── chat.js
│       ├── literature.js
│       ├── tasks.js
│       ├── settings.js
│       ├── knowledge.js    # 自建知识库
│       ├── graph.js        # 知识图谱
│       ├── smartbi.js      # SmartBI
│       └── tools.js        # 文档工具
│
├── stores/                 # Pinia 状态
│   ├── modules/
│   │   ├── user.js
│   │   ├── config.js
│   │   └── database.js     # 知识库列表
│   ├── index.js
│   └── user.js             # 兼容 re-export
│
├── utils/                  # 纯工具
│
└── views/                  # 页面（按业务域）
    ├── auth/               # 登录注册
    ├── chat/
    ├── literature/
    ├── tasks/
    ├── knowledge/          # 知识库列表与详情
    ├── graph/              # 知识图谱
    ├── smartbi/            # SmartBI
    ├── personal/
    ├── settings/
    ├── tools/
    ├── home/
    └── error/
```

## 与后端对应关系

| 前端 | 后端 |
|------|------|
| `api/tasks.js` | `src/api/v1/tasks.py` |
| `api/literature.js` | `src/api/v1/literature.py` |
| `views/literature/` | 文献管理 |
| `views/tasks/` | 任务中心 |
| `views/knowledge/` | `src/api/v1/knowledge_base.py` (`/data`) |
| `views/graph/` | `/data/graph/*` + Neo4j |
| `views/smartbi/` | `src/api/v1/smartbi.py` |
| `views/tools/` | `src/api/v1/tools.py` |
| `views/chat/` | `src/api/v1/chat.py` |
| `views/settings/` | `src/api/v1/system.py` |

## 说明

- 路由按业务域拆分至 `router/modules/*.js`，`router/index.js` 仅做合并。
- Pinia store 统一从 `@/stores` 导入。
- 所有 HTTP 请求经 `api/client.js` 或各域 `api/xxx.js`。
