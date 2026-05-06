# NotebookLX

源文档驱动的智能笔记本知识工作台。灵感来源于 Google NotebookLM —— AI 仅基于你上传的文档回答问题，每条回答都可追溯到具体来源段落。

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Next.js 14 (App Router) + Tailwind CSS + shadcn/ui |
| 后端 | FastAPI (Python) + Arq 异步 Worker |
| 数据库 | PostgreSQL + pgvector (HNSW 索引) |
| 队列 | Redis (Arq 任务后端) |
| 存储 | MinIO (本地开发) / S3 (生产) |
| AI | 智谱AI / OpenAI 兼容 LLM + Embedding |

## 快速启动

```bash
# 前置依赖: Python 3.11+, Node.js 18+, pnpm, Redis, PostgreSQL

# 1. 环境配置
cp .env.example .env          # 填入 API Key 和数据库连接

# 2. 后端
python3 -m venv venv && source venv/bin/activate
pip install -r services/api/requirements.txt 
alembic upgrade head

# 3. 启动服务（在仓库根目录执行）
./scripts/start-infra.sh      # Redis + MinIO
./scripts/start-api.sh        # API 服务 :8000
./scripts/start-worker.sh     # 异步摄入 Worker

# 4. 前端
cd apps/web && pnpm install && pnpm dev   # UI :3000
```

## 项目结构

```
notebooklx/
├── apps/web/                # Next.js 前端
│   ├── app/                 #   页面路由 (App Router)
│   ├── components/          #   组件 (ui/, chat/, evaluation/)
│   └── lib/                 #   API 客户端、SSE 流客户端
├── services/
│   ├── api/                 # FastAPI 后端
│   │   ├── core/            #   数据库、AI Provider、向量操作
│   │   └── modules/         #   notebooks, sources, ingestion, chunking,
│   │                        #   embeddings, retrieval, chat, citations,
│   │                        #   evaluation, snapshots
│   └── worker/              # Arq 异步任务 Worker
├── scripts/                 # 启动脚本 (start-api.sh 等)
└── docs/                    # 项目文档
```

## 核心数据流

**文档摄入：** 上传 -> 文本提取 (PDF/URL/Text) -> 语义分块 (300-800 tokens) -> 向量嵌入 (embedding-2: 1024维 / embedding-3: 2048维) -> pgvector

**智能问答：** 用户提问 -> 查询改写 -> 混合检索 (BM25 + 向量 + RRF 融合) -> 证据打包 -> LLM 生成带引用标记 [1][2] 的答案

关键约束：检索严格限定在当前笔记本范围内，暂不支持跨笔记本搜索。

## 运行测试

```bash
# 后端（仓库根目录，venv 已激活）
PYTHONPATH=$(pwd) pytest services/api/tests/ -v

# 前端
pnpm test --prefix apps/web
```

## 文档索引

| 文档 | 说明 |
|------|------|
| [CLAUDE.md](CLAUDE.md) | AI 开发助手规范、TDD 流程、编码标准 |
| [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) | 功能规划与验收标准 |
| [TASK_CHECKLIST.md](TASK_CHECKLIST.md) | Sprint 进度追踪 |
| [services/api/README.md](services/api/README.md) | 后端搭建、数据库迁移、测试、API 端点 |
| [apps/web/README.md](apps/web/README.md) | 前端搭建、路由、组件、设计系统 |
| [apps/web/DESIGN.md](apps/web/DESIGN.md) | 视觉设计系统（色彩、排版、布局） |
| [docs/PROJECT_SHARE.md](docs/PROJECT_SHARE.md) | 项目完整介绍（架构、数据模型、技术深潜） |
| [docs/DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md) | 数据库 Schema 全貌 |
| [docs/API_REFERENCE.md](docs/API_REFERENCE.md) | REST API 端点参考 |

## 开发规范

- **TDD**：先写测试再写代码。红 -> 绿 -> 重构。
- **所有命令在仓库根目录执行**，确保 `services.*` 导入路径正确。
- **Python 虚拟环境**：执行后端命令前先 `source venv/bin/activate`。
- 测试全绿后才提交，commit 格式：`feat: / fix: / docs:`。
