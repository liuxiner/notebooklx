# NotebookLX -- AI 课程项目案例分享

> Source-Grounded Notebook Knowledge Workspace
> 灵感来源于 Google NotebookLM 的源文档驱动的智能笔记本知识工作台

---

## 一、项目定位与核心思想

### 1.1 一句话定位

NotebookLX 是一个**以源文档为真相边界的 AI 知识工作台**——用户将文档、网页、文本等材料添加到笔记本中，AI 仅基于这些材料回答问题，每一条回答都可追溯到具体的来源段落。

### 1.2 核心理念

| 原则 | 含义 |
| **Notebook 是一等公民** | 笔记本是组织知识的基本单元，所有操作围绕笔记本展开 |
| **Sources 定义真相边界** | AI 的知识范围严格限定在用户添加的源文档内，不使用外部知识 |
| **Answers 必须可追溯** | 每一条回答都附带引用标记 [1][2]，链接到具体文档段落 |
| **Derived Content 源于源头** | 生成的摘要、FAQ、学习指南等衍生内容始终绑定到源文档 |

### 1.3 与通用 AI 对话的区别

| 维度 | 通用 AI 助手 | NotebookLX |
|------|-------------|------------|
| 知识范围 | 整个训练语料 | 用户上传的文档 |
| 回答依据 | 模型参数 + 检索增强 | 严格限定在笔记本内的源文档 |
| 引用追溯 | 不支持或弱支持 | 双层引用系统（检索层 + 绑定层） |
| 幻觉风险 | 较高 | 大幅降低（答案限定在源文档范围内） |
| 透明度 | 黑盒 | 完整可见（检索过程、查询改写、Token 用量） |

---

## 二、系统架构

### 2.1 技术栈全景

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (Next.js)                      │
│  React + Tailwind CSS + shadcn/ui + SSE Streaming Client    │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP / SSE
┌──────────────────────────▼──────────────────────────────────┐
│                    Backend (FastAPI)                          │
│  ┌─────────┐ ┌──────────┐ ┌───────────┐ ┌───────────────┐  │
│  │ Notebook │ │  Source   │ │ Ingestion │ │    Chat /     │  │
│  │   CRUD   │ │  Upload   │ │ Pipeline  │ │  Grounded QA  │  │
│  └─────────┘ └──────────┘ └─────┬─────┘ └───────┬───────┘  │
│                               │               │            │
│  ┌──────────┐ ┌──────────┐   │   ┌───────────▼─────────┐  │
│  │ Chunking │ │ Embedding│◄──┘   │  Hybrid Retrieval   │  │
│  │          │ │ Service  │       │  (BM25 + Vector+RRF) │  │
│  └──────────┘ └──────────┘       └─────────────────────┘  │
│           core: AI Provider (ZhipuAI / OpenAI)              │
└───────┬──────────────┬──────────────┬──────────────────────┘
        │              │              │
   ┌────▼────┐   ┌─────▼────┐  ┌─────▼─────┐
   │PostgreSQL│  │  Redis   │  │MinIO / S3 │
   │+ pgvector│  │Task Queue│  │Object Store│
   └─────────┘  └──────────┘  └───────────┘
```

### 2.2 技术选型与理由

| 层级 | 技术 | 选型理由 |
|------|------|---------|
| **前端框架** | Next.js (App Router) | React SSR/SSG，适合内容型工作台应用 |
| **UI 库** | shadcn/ui + Tailwind CSS | 可定制、轻量、与设计系统无缝集成 |
| **后端框架** | FastAPI (Python) | 原生异步、自动文档、与 AI 生态紧密 |
| **数据库** | PostgreSQL + pgvector | 关系数据 + 向量检索一体化，避免多系统维护 |
| **任务队列** | Arq (Redis) | 比 Celery 更轻量，适合中小规模异步任务 |
| **对象存储** | MinIO (本地) / S3 (生产) | 兼容 S3 API，开发生产一致 |
| **AI Provider** | 智谱AI (默认) / OpenAI | 支持多供应商切换，抽象层解耦 |
| **向量索引** | HNSW (pgvector) | 高性能近似最近邻，查询延迟 < 200ms |

### 2.3 目录结构

```
notebooklx/
├── apps/web/                 # Next.js 前端应用
│   ├── app/                  #   页面路由 (App Router)
│   ├── components/           #   UI 组件
│   │   ├── ui/               #     基础组件 (button, card, dialog...)
│   │   ├── notebooks/        #     笔记本相关组件
│   │   ├── chat/             #     聊天面板组件
│   │   └── evaluation/       #     评估仪表板组件
│   └── lib/                  #   API 客户端、SSE 流客户端
├── services/
│   ├── api/                  # FastAPI 后端
│   │   ├── core/             #   数据库、AI Provider、向量操作
│   │   └── modules/          #   业务模块
│   │       ├── notebooks/    #     笔记本 CRUD
│   │       ├── sources/      #     源文档上传管理
│   │       ├── ingestion/    #     文档处理编排器
│   │       ├── chunking/     #     语义分块
│   │       ├── embeddings/   #     向量嵌入生成
│   │       ├── retrieval/    #     混合检索 (BM25 + Vector + RRF)
│   │       ├── query/        #     查询改写
│   │       ├── chat/         #     基于源文档的问答
│   │       ├── citations/    #     引用系统
│   │       └── evaluation/   #     评估指标
│   └── worker/               # Arq 异步任务 Worker
├── infra/
│   ├── docker/               # Docker 配置
│   └── sql/                  # 数据库迁移脚本
└── scripts/                  # 开发辅助脚本
```

---

## 三、核心数据流

### 3.1 文档摄入流程 (Ingestion Pipeline)

这是系统最核心的流水线，将原始文档转化为可检索的知识：

```
用户上传文件/URL/文本
        │
        ▼
  保存原始文件 (MinIO/S3)
        │
        ▼
  文本提取 (Parser)
   ├── PDF: PyMuPDF 提取
   ├── URL: 网页抓取 + 正文提取
   ├── Text: 直接读取
   ├── YouTube: 字幕/转录提取
   └── Google Docs: API 提取
        │
        ▼
  语义分块 (Chunking)
   ├── 按段落/标题自然边界切分
   ├── 目标: 300-800 tokens/块
   ├── 重叠: 50-120 tokens
   └── 保留元数据: 页码、标题层级、字符位置
        │
        ▼
  快照生成 (Snapshot)
   └── LLM 生成结构化摘要（概述、主题、关键词）
        │
        ▼
  向量嵌入 (Embedding)
   ├── 批量生成 (32-100 chunks/call)
   ├── 1536 维向量 (text-embedding-3-small)
   └── 指数退避重试 + 成本追踪
        │
        ▼
  存储到数据库
   ├── chunks + embeddings → PostgreSQL
   ├── HNSW 索引用于快速检索
   └── 状态标记: pending → processing → ready
                              └→ failed (带错误信息)
```

**关键设计决策：**

- **语义分块优于固定窗口**：尊重段落和标题的自然边界，确保每个块在语义上完整
- **重叠窗口**：相邻块有 50-120 token 重叠，避免关键信息被切在块边界
- **元数据保留**：页码、标题层级、字符位置——这些都是后续精确引用的基础
- **异步处理**：通过 Arq + Redis 异步执行，前端轮询状态，不阻塞用户操作
- **批量操作**：支持一次最多上传 50 个文件，批量摄入

### 3.2 检索与问答流程 (Retrieval-Augmented Generation)

```
用户提问: "这些文档中关于 X 的主要观点是什么？"
        │
        ▼
  ┌─────────────────────┐
  │   查询改写 (Query Rewrite)    │
  │  策略选择:                          │
  │  ├── no_rewrite (简单直接问题)     │
  │  ├── reference_resolution (代词)   │
  │  ├── standalone_expansion (模糊)   │
  │  └── keyword_enrichment (专业词)   │
  └─────────────┬───────┘
                │
                ▼
  ┌─────────────────────┐
  │   混合检索 (Hybrid Retrieval)  │
  │                                    │
  │  BM25 关键词检索 ──┐              │
  │                    ├── RRF 融合 ──► Top-K 候选
  │  向量相似度检索 ───┘              │
  │                                    │
  │  ⚠️ 始终限定在当前笔记本范围内     │
  └─────────────┬───────┘
                │
                ▼
  ┌─────────────────────┐
  │   证据打包 (Evidence Packing)  │
  │  格式化检索到的 chunks，附上     │
  │  引用索引，构成 evidence context │
  └─────────────┬───────┘
                │
                ▼
  ┌─────────────────────┐
  │   LLM 生成回答 (SSE 流式)    │
  │  - 仅基于 evidence 回答         │
  │  - 内嵌引用标记 [1][2]          │
  │  - 实时流式输出                  │
  └─────────────┬───────┘
                │
                ▼
  ┌─────────────────────┐
  │   引用解析 (Citation Parse)   │
  │  双层引用系统:                    │
  │  Layer 1: 检索证据层 (候选 chunks)│
  │  Layer 2: 答案绑定层 (标记→chunk)│
  └─────────────────────┘
```

### 3.3 双层引用系统 (Two-Layer Citation System)

这是本项目最核心的产品设计，区分于一般 RAG 系统：

**Layer 1 — 检索证据层 (Evidence Layer)**
- 检索引擎返回 Top-K 候选 chunks
- 每个 chunk 包含: chunkId, sourceId, sourceTitle, content, page, score
- 这层回答 "系统找到了哪些相关材料"

**Layer 2 — 答案绑定层 (Binding Layer)**
- LLM 生成结构化输出 `answer_blocks`，每个文本块关联 `citation_chunk_ids`
- 后端将 chunk IDs 映射为 UI 引用标记 [1][2][3]...
- 这层回答 "答案的每句话依据哪个源文档段落"

```
Evidence Layer:
  chunk_1 (source: "paper.pdf", page 12, score: 0.89)
  chunk_2 (source: "report.pdf", page 5,  score: 0.85)
  chunk_3 (source: "paper.pdf", page 15, score: 0.82)

Binding Layer:
  answer_block_1: "主要观点是 X..." → [chunk_1, chunk_3]  → UI 显示 [1][3]
  answer_block_2: "报告指出 Y..."   → [chunk_2]           → UI 显示 [2]
```

---

## 四、UI/UX 设计体系

### 4.1 设计原则

1. **Truth over flair（真相优于花哨）**：引用和来源边界是产品的核心，视觉服务于可信度
2. **Transparency builds trust（透明建立信任）**：检索、查询改写、流式处理状态全部对用户可见
3. **Calm by default（默认安静）**：大面积中性灰调，仅关键交互使用色彩强调
4. **Responsive reading（响应式阅读）**：移动端不是缩小版桌面，每个尺寸都是一等的阅读体验

### 4.2 页面结构

```
┌─────────────────────────────────────────────────┐
│              /notebooks — 笔记本列表              │
│                                                   │
│  ┌───────────────────────────────────────────┐   │
│  │ Hero Card: "Source-grounded workspace"     │   │
│  │ 活跃笔记本数 │ + 新建笔记本                    │   │
│  └───────────────────────────────────────────┘   │
│                                                   │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐            │
│  │ Notebook │ │ Notebook │ │ Notebook │  ...      │
│  │  Card 1  │ │  Card 2  │ │  Card 3  │            │
│  └─────────┘ └─────────┘ └─────────┘            │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│          /notebooks/[id] — 笔记本工作台            │
│                                                   │
│  Desktop (1200px+):     │ Chat Panel (Sticky)    │
│  ┌──────────────────┐   │ ┌──────────────────┐   │
│  │ Notebook Header   │   │ │ Grounded Chat    │   │
│  │ + Trust Boundary  │   │ │                  │   │
│  └──────────────────┘   │ │ [Messages...]     │   │
│  ┌──────────────────┐   │ │                  │   │
│  │ Source Management │   │ │ Transparency:    │   │
│  │ ┌──────────────┐ │   │ │ - Query Rewrite  │   │
│  │ │ Source 1 ✓   │ │   │ │ - Timing/Cost    │   │
│  │ │ Source 2 ⏳   │ │   │ │ - Evidence       │   │
│  │ │ Source 3 ❌   │ │   │ │ - Citations      │   │
│  │ └──────────────┘ │   │ │                  │   │
│  └──────────────────┘   │ │ [Input Area]     │   │
│                          │ └──────────────────┘   │
└─────────────────────────────────────────────────┘
```

### 4.3 透明度 UX — 差异化的产品设计

聊天面板不是简单的对话框，而是一个**可审计的 AI 交互界面**：

| 透明度面板 | 展示内容 | 用户价值 |
|-----------|---------|---------|
| **查询改写** | 原始问题 → 改写策略 → 搜索查询 | 理解 AI 如何理解你的问题 |
| **计时与用量** | 嵌入耗时、检索耗时、首 token 时间、Token 用量、估算成本 | 了解 AI 的工作成本 |
| **检索证据** | 所有候选 chunks 的来源、页码、相关度分数、引用原文 | 审查 AI "看到了什么" |
| **引用来源** | 答案中实际使用的 chunks，原文引用，交互式切换 | 验证 AI "引用了什么" |

### 4.4 引用交互设计

```
AI 回答: "根据研究，主要风险包括市场波动 [1] 和
         监管不确定性 [2]。报告还指出..."

                    ↓ 点击 [1] ↓

┌──────────────────────────────────────┐
│ [1] paper.pdf — 第 12 页  Score: 0.89│
│                                      │
│ "2024年市场波动率较上年增加了23%，    │
│  主要受地缘政治因素影响..."           │
└──────────────────────────────────────┘
```

引用标记 (amber 色小徽章) 嵌入在答案文本中，点击可展开查看完整原文引用、来源和页码。

---

## 五、关键技术实现详解

### 5.1 混合检索 (Hybrid Retrieval)

单一检索方式无法覆盖所有查询场景：

| 检索方式 | 擅长 | 弱点 |
|---------|------|------|
| **BM25 关键词** | 精确术语、专有名词、代码片段 | 语义理解弱，同义词匹配差 |
| **向量相似度** | 语义相似、自然语言描述 | 精确术语可能匹配不到 |

NotebookLX 使用 **Reciprocal Rank Fusion (RRF)** 融合两种检索结果：

```python
# RRF 公式
score_rrf(d) = Σ 1 / (k + rank_i(d))    # k=60

# 两种检索各自排序 → RRF 融合 → Top-K 候选
bm25_results  = bm25_search(query, notebook_id)
vector_results = vector_search(query_embedding, notebook_id)
final_results = rrf_fuse(bm25_results, vector_results, k=60)
```

**关键点：始终限定在 `notebook_id` 范围内**，跨笔记本检索是 v2 特性。

### 5.2 查询改写系统

查询改写是 RAG 系统容易被忽视但影响巨大的环节。本项目实现了**启发式优先、LLM 兜底**的策略：

```
用户输入
    │
    ▼
启发式分析器
├── 检测代词 (他、这个、那个) → reference_resolution
├── 检测追问模式 (还有呢、继续) → standalone_expansion
├── 检测摘要请求 → no_rewrite
├── 检测比较模式 → keyword_enrichment
└── 未匹配 → 传给 LLM 判断
    │
    ▼
LLM 改写 (仅在需要时调用)
├── 结合聊天历史提取上下文
├── 保护专业术语不被改写
├── 输出结构化 JSON (standalone question + search queries)
└── 降级解析兜底
```

### 5.3 SSE 流式协议

聊天使用 Server-Sent Events 实现实时流式输出，定义了完整的事件类型：

| 事件类型 | 内容 | 用途 |
|---------|------|------|
| `status` | 管道阶段状态 | 显示当前处理步骤 |
| `metrics` | 性能指标 | 实时更新计时和用量 |
| `query_rewrite` | 改写详情 | 展示查询理解过程 |
| `retrieval` | 检索结果 | 展示候选 chunks |
| `citations` | 引用对象 | 绑定引用到来源 |
| `answer_delta` | 增量文本 | 逐字流式输出答案 |
| `answer` | 完整答案 | 最终完整答案 |
| `done` | 完成信号 | 关闭流 |
| `error` | 错误信息 | 结构化错误 + 重试指导 |

### 5.4 成本追踪

每次对话自动追踪 AI 使用成本：

```
┌──────────────────────────────────────┐
│          Chat Timing & Usage          │
├────────────────┬─────────────────────┤
│ Model          │ glm-4               │
│ Embedding Time │ 0.8s               │
│ Embedding Cost │ ¥0.0001            │
│ Retrieval Time │ 0.3s               │
│ First Token    │ 1.2s               │
│ Stream Duration│ 3.5s               │
│ Prompt Tokens  │ 2,450              │
│ Completion     │ 890                │
│ Total Tokens   │ 3,340              │
│ Est. Cost      │ ¥0.012             │
└────────────────┴─────────────────────┘
```

### 5.5 多语言支持

系统自动检测用户输入的语言，并以相同语言回答：

- 中文问题 → 中文回答 + 中文引用描述
- 英文问题 → 英文回答 + 英文引用描述
- 查询改写也遵循原文语言

---

## 六、数据模型设计

### 6.1 核心实体关系

```
User
  │ 1:N
  ▼
Notebook ──────────────────────┐
  │ 1:N                        │ 1:N
  ├── Source                   │
  │     │ 1:N                  │
  │     ├── SourceChunk        │
  │     │     (vector: 1536d)  │
  │     └── SourceSnapshot     │
  │                            │
  ├── Message ◄──────┐        │
  │     │ 1:N         │        │
  │     └── Citation ─┘        │
  │                            │
  └── IngestionJob             │
                                │
  (未来) NotebookTopic ────────┘
  (未来) GeneratedAsset
  (未来) Note
```

### 6.2 关键设计决策

| 决策 | 理由 |
|------|------|
| UUID 作为所有主键 | 分布式友好，不暴露业务信息 |
| 软删除 Notebooks (deleted_at) | 支持恢复，数据安全 |
| 级联删除 Sources 和 Chunks | 孤儿数据无意义 |
| JSONB 存储灵活元数据 | chunks 的 metadata 结构多样 |
| pgvector + HNSW 索引 | 向量检索性能 < 200ms |
| 所有外键索引 | 查询性能保障 |

---

## 七、工程实践与方法论

### 7.1 测试驱动开发 (TDD)

项目严格执行 TDD 流程：

```
1. 阅读 DEVELOPMENT_PLAN.md 中的验收标准
       ↓
2. 为每个验收标准写测试 (测试应失败 — RED)
       ↓
3. 实现最小代码使测试通过 (GREEN)
       ↓
4. 重构 (保持测试通过 — REFACTOR)
       ↓
5. 在 TASK_CHECKLIST.md 中标记完成 ✓
       ↓
6. 只有当所有测试通过时才提交代码
```

### 7.2 开发工具链

```bash
# 后端测试
PYTHONPATH=$(pwd) pytest services/api/tests/ -v

# 前端测试
pnpm test --prefix apps/web

# 测试覆盖率
PYTHONPATH=$(pwd) pytest --cov=services.api --cov-report=html

# 启动全部开发服务
./scripts/start-dev.sh    # Redis + API + Worker

# 数据库迁移
alembic upgrade head
```

### 7.3 AI 辅助开发

项目使用 **Claude Code** 作为 AI 结对编程伙伴，通过 `CLAUDE.md` 定义工作规范：

- 严格的 TDD 流程约束
- 代码质量规则（无代码无测试、70%+ 覆盖率）
- 提交规范（`feat: / fix:` 前缀）
- 上下文管理（项目架构、数据模型、API 规范）

### 7.4 配套文档体系

| 文档 | 用途 |
|------|------|
| `CLAUDE.md` | AI 开发助手工作规范 |
| `apps/web/DESIGN.md` | 视觉设计系统 (v1.1) |
| `DEVELOPMENT_PLAN.md` | 1269 行功能规划与验收标准 |
| `TASK_CHECKLIST.md` | Sprint 进度追踪 |
| `DATABASE_SCHEMA.md` | 完整数据库 Schema |
| `API_REFERENCE.md` | REST API 规范文档 |

---

## 八、项目状态与路线图

### 8.1 已完成功能

| 模块 | 功能 |
|------|------|
| **笔记本管理** | CRUD、软删除、笔记本列表 UI |
| **源文档管理** | 上传 (PDF/URL/Text)、批量上传 (50个)、删除、快照预览 |
| **文档摄入** | 异步流水线 (Arq)、PDF/URL/Text/YouTube/Google Docs 解析 |
| **语义分块** | 300-800 token 块、50-120 token 重叠、元数据保留 |
| **向量嵌入** | 批量生成、成本追踪、指数退避重试 |
| **混合检索** | BM25 + Vector + RRF 融合、Notebook 范围限定 |
| **查询改写** | 启发式 + LLM 双策略、改写透明度展示 |
| **基于来源的问答** | SSE 流式输出、双层引用系统、引用交互 |
| **聊天防护** | 错误分类、重试引导、结构化错误信息 |
| **流式可观测** | 计时、Token 用量、检索诊断、查询改写透明度 |
| **评估仪表板** | 评估数据集管理、指标展示 |

### 8.2 开发中

- 离线安全的 Tokenizer 加载
- 源文档快照失败/状态可视化

### 8.3 规划中 (Phase 4-6)

- 笔记本自动摘要生成
- 关键主题提取
- 推荐问题生成
- 源文档交叉分析
- 衍生内容 (FAQ、学习指南、时间线、词汇表)
- Reranker 模型集成
- 用户认证与权限
- CI/CD 与生产部署

---

## 九、项目亮点与可讨论点

### 9.1 技术亮点

1. **双层引用系统**：不仅是 RAG 检索，还有答案级别的引用绑定，这是产品级的引用体验
2. **透明度即产品**：将 RAG 的内部工作过程（检索、改写、成本）变成用户可见的 UI 面板
3. **混合检索 + RRF**：BM25 和向量检索互补，RRF 融合避免调参困难
4. **启发式查询改写**：减少不必要的 LLM 调用，兼顾成本和效果
5. **完整的 SSE 流式协议**：不仅流式输出文本，还流式推送状态、指标、检索结果
6. **AI 辅助开发工作流**：通过 CLAUDE.md 等文档让 AI 助手理解项目上下文

### 9.2 可讨论的架构决策

| 决策 | 取舍 |
|------|------|
| **pgvector vs 独立向量数据库** | 减少运维复杂度 vs 向量特化性能 |
| **Arq vs Celery** | 轻量简单 vs 功能丰富 |
| **SQLite (开发) / PostgreSQL (生产)** | 零配置开发 vs 生产级性能 |
| **启发式查询改写优先** | 降低成本/延迟 vs 覆盖不全 |
| **严格 Notebook 范围限定** | 减少幻觉 vs 无法跨笔记本对比 |

### 9.3 可延展方向

- **多模态理解**：图片、表格、公式的解析与检索
- **Agent 能力**：让 AI 主动分析、对比、生成衍生内容
- **协作功能**：多用户共享笔记本、评论、标注
- **知识图谱**：从源文档中提取实体关系，构建领域知识图谱
- **评估框架**：自动化 RAG 评估流水线 (RAGAS 指标)

---

## 十、本地运行指南

### 前置依赖

- Python 3.14+
- Node.js 18+ / pnpm
- Redis (或通过 Docker)
- MinIO (可选，本地开发可用文件系统)

### 快速启动

```bash
# 1. 克隆项目
git clone <repo-url>
cd notebooklx

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 AI API Key

# 3. 启动基础设施 (Redis + MinIO)
./scripts/start-infra.sh

# 4. 启动后端 API
./scripts/start-api.sh

# 5. 启动异步 Worker
./scripts/start-worker.sh

# 6. 启动前端
cd apps/web && pnpm install && pnpm dev

# 7. 访问 http://localhost:3000
```

---

> 本文档为 NotebookLX 项目介绍，适合 AI 课程案例分享和技术讨论。
> 项目源码: <repo-url>
