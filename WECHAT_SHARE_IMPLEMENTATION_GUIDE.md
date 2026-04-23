# WECHAT_SHARE.md 对照实现说明

这份材料的目的，是把 [WECHAT_SHARE.md](WECHAT_SHARE.md) 里的每一块表述，落到当前仓库里的真实代码位置、关键实现、处理原因和整体流程上。

结论先说：

- `WECHAT_SHARE.md` 里大部分“主链路”已经有代码落地，尤其是 ingestion、hybrid retrieval、query rewrite、SSE、透明度面板。
- 但也有几处需要明确区分“当前已实现”和“文档中的理想形态”，最重要的是：
  - 当前默认 embedding 模型是 `embedding-2`，不是分享稿里写的 OpenAI 风格默认值。
  - Citation 的数据库模型和查询 API 已经有了，但聊天链路里目前没有把 citation 结果真正写回数据库。
  - Query rewrite 当前实现更准确地说是“启发式门控 + LLM 重写”，不是“启发式直接产出重写结果、LLM 只做兜底”。

## 1. 整体架构先看什么

如果你想先抓主干，建议按这个顺序读代码：

1. [sources/routes](./services/api/modules/sources/routes.py)
2. [ingestion/routes](./services/api/modules/ingestion/routes.py)
3. [worker](./services/worker/main.py)
4. [ingestion/orchestrator](./services/api/modules/ingestion/orchestrator.py)
5. [chat/routes](./services/api/modules/chat/routes.py)
6. [chat/service](./services/api/modules/chat/service.py)
7. [retrieval/service](./services/api/modules/retrieval/service.py)
8. [retrieval/hybrid](./services/api/modules/retrieval/hybrid.py)
9. [query/rewriter](./services/api/modules/query/rewriter.py)
10. [chat-stream](./apps/web/lib/chat-stream.ts)
11. [chat-panel](./apps/web/components/chat/chat-panel.tsx)

这 11 个文件基本串起了分享稿里最核心的故事线。

## 2. 两条主流程

### 2.1 Source Ingestion 流程

用户上传 source 之后，大致流程是：

1. 前端调用 source API 创建 source，source 归属某个 notebook。
2. 前端调用 ingestion enqueue API，把 source 放进队列。
3. Arq worker 取到任务，把 source 状态改成 `processing`。
4. Orchestrator 执行 `fetch -> parse -> chunk -> snapshot -> embedding -> save`。
5. 进度写回 `ingestion_jobs.progress`，前端轮询显示状态。
6. 成功后 source 变成 `ready`，chunks 和 embeddings 落库，后续可以检索。

对应代码：

- Source 创建与 notebook 归属：`services/api/modules/sources/routes.py`
- 入队与状态查询：`services/api/modules/ingestion/routes.py`
- Worker 执行与状态推进：`services/worker/main.py`
- 真正的 ingestion 编排：`services/api/modules/ingestion/orchestrator.py`

### 2.2 Chat 检索问答流程

用户提问之后，大致流程是：

1. 前端调用 `/api/notebooks/{id}/chat/stream`。
2. 后端先读取 notebook 最近聊天记录。
3. Query rewriter 判断是否需要重写，必要时调用 LLM 产出检索友好 query。
4. 用 embedding provider 对一个或多个 retrieval query 生成 query embedding。
5. 走 hybrid retrieval：vector search + BM25 + RRF。
6. 把检索结果包装成 evidence prompt，只允许模型基于 evidence 回答。
7. 后端通过 SSE 连续发 `status`、`metrics`、`query_rewrite`、`retrieval`、`answer_delta`、`citations`、`done`。
8. 前端边流式拼答案，边更新透明度面板、检索证据和 citation 卡片。

对应代码：

- SSE 入口：`services/api/modules/chat/routes.py`
- 问答编排：`services/api/modules/chat/service.py`
- 查询改写：`services/api/modules/query/rewriter.py`
- 检索：`services/api/modules/retrieval/service.py` 和 `services/api/modules/retrieval/hybrid.py`
- 前端 SSE 消费：`apps/web/lib/chat-stream.ts`
- 前端透明度和 citation UI：`apps/web/components/chat/chat-panel.tsx`

## 3. WECHAT_SHARE.md 各部分对应代码

### 3.1 一句话定位 / “Sources 定义真相边界”

分享稿对应表述：

- “以源文档为真相边界”
- “所有检索、回答都限定在 notebook_id 范围内”

对应代码位置：

- Notebook 是一等组织单元：`services/api/modules/notebooks/models.py`
- Source 归属 notebook：`services/api/modules/sources/models.py`
- Source API 先校验 notebook ownership：`services/api/modules/sources/routes.py`
- Chat API 先校验 notebook ownership：`services/api/modules/chat/routes.py`
- Vector search 按 `Source.notebook_id` 过滤：`services/api/modules/retrieval/service.py`
- BM25 index 只为单 notebook 构建：`services/api/modules/retrieval/hybrid.py`

关键实现：

- `Notebook` 是顶层容器，`Source.notebook_id` 把 source 绑定到 notebook。
- `VectorSearchService._search_with_pgvector()` 查询里显式 `where(Source.notebook_id == notebook_id)`。
- `BM25SearchService._build_index()` 只拉取某个 notebook 下的 chunks 建索引。
- Chat 路由 `_get_notebook_for_user()` 先校验 notebook 属于当前用户并且未删除。

为什么这么做：

- 这是最直接、最容易审计的“边界实现方式”，不是靠 prompt 提醒，而是靠数据层和查询层强约束。
- 即便模型有外部知识，当前问答链路也只给它 notebook 内部 evidence。

方案选择理由：

- 把 notebook 作为硬过滤条件，工程上比“给 prompt 说只能看这些 source”更可靠。
- 查询层做过滤，可以同时约束 vector search、BM25、chat history 和 source 列表。

### 3.2 参数表 1）语义分块（Chunking）

分享稿对应表述：

- `300-800 tokens`
- `50-120 tokens overlap`
- 保留页码、标题层级、字符位置

对应代码位置：

- `services/api/modules/chunking/chunker.py`
- `services/api/modules/chunking/models.py`
- `services/api/modules/parsers/base.py`
- `services/api/modules/parsers/pdf.py`

关键代码：

- `Chunker.__init__(min_tokens=300, max_tokens=800, overlap_tokens=75)`
- `Chunker.chunk_text()`
- `ChunkResult` 里保留 `token_count`、`char_start`、`char_end`、`page_number`、`page_numbers`、`heading_context`
- `SourceChunk.chunk_metadata` 落库存 `page/pages/headings/source_title`

为什么这么处理：

- 当前实现不是固定长度硬切，而是“先按句子切，再按 token 预算合并”，比纯字符窗口更接近语义边界。
- overlap 的作用是降低边界截断导致的信息丢失。
- `char_start/char_end + page/headings` 是后续 citation、snapshot、source preview 的基础。

方案选择理由：

- 句子级累加比纯 token 窗口更容易保持引用可读性。
- 直接在 chunk 结果里带元数据，后续 retrieval、citation、snapshot 不用再回源二次解析。
- `count_tokens()` 里保留了离线 fallback 估算逻辑，避免 tokenizer 资源缺失时整条链路不可用。

### 3.3 参数表 2）嵌入（Embeddings）

分享稿对应表述：

- 批量嵌入
- 重试
- 成本追踪
- provider 抽象

对应代码位置：

- `services/api/core/ai.py`
- `services/api/modules/embeddings/providers.py`
- `services/api/modules/embeddings/service.py`
- `services/api/modules/embeddings/utils.py`

关键代码：

- `get_ai_client_settings()` 统一解析 `ZAI_* / ZHIPUAI_* / OPENAI_*`
- `BigModelEmbeddingProvider.MODEL_DIMENSIONS`
- `BigModelEmbeddingProvider._create_embedding_response()` 实现 retry + backoff + rate limit
- `EmbeddingService.embed_batch()` 实现批量处理和 token/cost 汇总

当前实现要点：

- 默认运行时 embedding 模型来自 `services/api/core/ai.py` 的 `DEFAULT_BIGMODEL_EMBEDDING_MODEL = "embedding-2"`。
- `embedding-2 -> 1024 维`，`embedding-3 -> 2048 维`。
- `EmbeddingService.batch_size` 默认 `32`，合法范围 `1-100`。
- 默认重试 `3` 次，退避基数 `1.0s`，默认限速 `120 requests/minute`。
- 成本按 token 数估算，费率通过环境变量配置。

为什么这么处理：

- Provider 层负责“和供应商交互”，Service 层负责“批量、成本、汇总”，职责清晰。
- 把节流和退避放在 provider 层，能保护 snapshot/chat/embedding 共用供应商时的稳定性。
- 成本估算放在 service 层，方便前端透明度面板统一展示。

方案选择理由：

- 用 OpenAI-compatible client + BigModel base URL，切 provider 比直接写死 SDK 更便于替换。
- 批量大小放在 service 层，是吞吐和失败重试粒度之间的折中。

### 3.4 参数表 3）向量索引与数据库

分享稿对应表述：

- PostgreSQL + pgvector
- HNSW
- 同库管理关系数据和向量

对应代码位置：

- `services/api/core/vector.py`
- `services/api/modules/chunking/models.py`
- `services/api/alembic/versions/a7c9d2e1f4b6_enable_pgvector_for_source_chunks.py`
- `services/api/modules/retrieval/service.py`

关键代码：

- `EmbeddingVector`：PostgreSQL 用 `VECTOR`，SQLite 用 JSON
- migration 里 `CREATE EXTENSION IF NOT EXISTS vector`
- migration 里 `CREATE INDEX ... USING hnsw (embedding vector_cosine_ops)`
- `VectorSearchService._search_with_pgvector()` 用 `embedding <=> :query`

为什么这么处理：

- 生产链路用 PostgreSQL + pgvector 保证检索性能。
- 本地开发和测试保留 SQLite JSON fallback，降低运行门槛。
- 同库意味着 source/chunk/message/citation 和向量数据可以共享事务边界和删除级联。

方案选择理由：

- 这是“工程复杂度最低”的方案，不引入独立向量库就能把系统跑通。
- `EmbeddingVector` 做 cross-dialect 兼容，保证本地和生产逻辑尽量统一。

### 3.5 参数表 4）检索融合（Hybrid Retrieval）

分享稿对应表述：

- BM25
- Vector
- RRF
- `k=60`

对应代码位置：

- `services/api/modules/retrieval/hybrid.py`
- `services/api/modules/retrieval/service.py`
- `services/api/modules/chat/service.py`

关键代码：

- `BM25SearchService`
- `VectorSearchService`
- `reciprocal_rank_fusion(result_lists, k=60)`
- `HybridSearchService.search()`

为什么这么处理：

- Vector search 解决语义相近但词不完全匹配的问题。
- BM25 解决专有名词、文件名、错误栈、代码标识符这类 lexical match。
- RRF 不依赖分数归一化，直接用排名融合，避免手工调权重。

方案选择理由：

- 当前 BM25 实现是“按 notebook 构建内存索引”，而不是 PostgreSQL FTS。
- 这是偏务实的早期实现：逻辑简单、可测、可控，足够支撑单 notebook 规模的数据。
- 如果后面 source/chunk 数量继续增长，再迁移到数据库侧全文检索或外部 search engine 也比较自然。

### 3.6 参数表 5）查询改写（Query Rewrite）

分享稿对应表述：

- 代词消解
- 追问承接
- 模糊扩写
- 关键词补全

对应代码位置：

- `services/api/modules/query/rewriter.py`
- `services/api/modules/chat/routes.py`
- `services/api/modules/chat/service.py`
- `services/api/modules/chat/models.py`

关键代码：

- `choose_rewrite_strategy()`
- `build_rewrite_prompt()`
- `QueryRewriter.rewrite_for_retrieval()`
- `get_recent_chat_history()`

当前实现的准确描述：

- 不是“启发式先直接改写，LLM 只兜底”。
- 更准确是“启发式先判断是否需要重写，以及用哪种策略；一旦需要重写，就调用 LLM 生成结构化 rewrite 结果；如果不需要重写，则直接使用原 query”。

为什么这么处理：

- 代码/报错/文件名这类 query 往往已经很检索友好，直接跳过改写更稳。
- 对话式追问、代词指代和总结类问题，如果不带上下文，检索召回会明显变差。
- `protected_terms` 检查用于防止 LLM 重写时把关键标识符改丢。

方案选择理由：

- 让 heuristics 做“门控”和“约束”，让 LLM 做“自然语言重写”，兼顾稳定性和召回能力。
- `search_queries` 支持 1 到 3 个 retrieval query，便于一问多搜再合并。

查询改写的启发式优先实现集中在 services/api/modules/query/rewriter.py 的 choose_rewrite_strategy() 函数中。核心思路是用一组 if-elif 瀑布式规则按优先级逐层匹配，无需调用 LLM。

策略定义

4 种策略（rewriter.py:36-41）：
┌──────────────────────┬─────────────────────────────────┐
│         策略         │              含义               │
├──────────────────────┼─────────────────────────────────┤
│ no_rewrite           │ 原样使用，不改写                │
├──────────────────────┼─────────────────────────────────┤
│ reference_resolution │ 代词消解（it/this/that → 实体） │
├──────────────────────┼─────────────────────────────────┤
│ standalone_expansion │ 展开为独立完整问题              │
├──────────────────────┼─────────────────────────────────┤
│ keyword_enrichment   │ 补充检索关键词                  │
└──────────────────────┴─────────────────────────────────┘
优先级瀑布（从高到低）

choose_rewrite_strategy() [rewriter](./services/api/modules/query/rewriter.py) line:462-491 按以下顺序逐条判断：

1. 空查询 → no_rewrite
2. 代码/错误模式（反引号、函数调用、文件路径、异常名）→ no_rewrite — 技术查询本身对检索友好，不需要改写
3. 有历史 + 含代词（it, its, this, that, they 等）→ reference_resolution
4. 有历史 + 追问短语（"what about", "how about", "why this" 等）→ standalone_expansion
5. 摘要类查询（"summarize", "recap", "overview" 及中文）→ 有历史时 standalone_expansion，否则 keyword_enrichment
6. 比较/证据类查询（"compare", "difference", "where", "mention"）→ 有实质词时 keyword_enrichment，否则 standalone_expansion
7. 短查询（token 数 ≤ 阈值，默认 10）且不检索友好 → 有历史时 standalone_expansion，否则 keyword_enrichment
8. 短查询 + 有历史（token ≤ max(4, threshold/2)）→ standalone_expansion
9. 其余全部 → no_rewrite

关键辅助判断

- _looks_search_friendly() (rewriter.py:443-459)：检查查询是否已有足够的检索特异性（受保护术语、有意义词汇、足够长度）。如果已经够好，就不改写。
- allowed_strategies 环境变量：即使启发式选了某策略，如果不在允许列表内也会降级为 no_rewrite（rewriter.py:949-955）。
- 正则模式 (rewriter.py:118-146)：PRONOUN_PATTERN、FOLLOW_UP_PATTERN、SUMMARY_PATTERN、COMPARISON_PATTERN、EVIDENCE_PATTERN、CODE_OR_ERROR_PATTERN 分别覆盖英文和中文场景。
- merge_retrieval_results真实链路是：
  - API 请求的默认 top_k 是 5，定义在 services/api/modules/chat/routes.py:53
  - chat 服务把这个 top_k 继续传给检索层，在 services/api/modules/chat/service.py:553
  - 检索层里，BM25 和 Vector 的候选数默认都是 2 * top_k，定义在 services/api/modules/retrieval/hybrid.py:392

  也就是这两行：

  vector_top_k = vector_top_k or (top_k * 2)
  bm25_top_k = bm25_top_k or (top_k * 2)


整体流程

用户查询
  ↓
choose_rewrite_strategy()  ← 纯规则，无 LLM 调用
  ↓  选出策略
如果 != no_rewrite
  ↓
build_rewrite_prompt() + LLM 调用
  ↓
_parse_llm_rewrite_result()  ← 解析、去重、受保护术语检查
  ↓
返回 { standalone_query, search_queries[] }
  ↓
多路检索 → merge_retrieval_results()

简言之，启发式优先 = 零成本的规则瀑布优先判断，只有规则决定需要改写时才调用 LLM。这样大部分已经足够清晰的查询直接跳过改写，省掉延迟和 token 开销。


### 3.7 参数表 6）流式交互协议（SSE）

分享稿对应表述：

- `status`
- `metrics`
- `query_rewrite`
- `retrieval`
- `citations`
- `answer_delta`
- `done`

对应代码位置：

- 后端 SSE 生产：`services/api/modules/chat/routes.py`
- 前端 SSE 消费：`apps/web/lib/chat-stream.ts`
- 前端状态与透明度展示：`apps/web/components/chat/chat-panel.tsx`

关键代码：

- `_format_sse_event()`
- `stream_grounded_chat()`
- `streamNotebookChat()`
- `ChatPanel.submitQuestion()`

为什么这么处理：

- SSE 非常适合“先出状态、再出部分答案、再出最终引用”的单向流式场景。
- 与 WebSocket 相比，这里不需要双向长连接协议复杂度。
- 事件被拆成结构化类型，前端可以精细控制 UI，而不是只会 append 文本。

方案选择理由：

- 当前业务是标准的 request -> stream response，SSE 比 WebSocket 更轻。
- `answer_delta` 和 `answer` 分开，便于前端做到“先流式展示，再稳定收口”。

SSE 流式交互协议 — 核心代码与 JSON 结构

  1. SSE 事件序列总览

  一次完整的 Chat 请求，后端按时间顺序发出以下事件：

  客户端 POST /api/notebooks/{id}/chat/stream
    │
    ├─ event: status          ─ 开始：正在嵌入查询
    ├─ event: metrics         ─ 嵌入/检索耗时
    ├─ event: query_rewrite   ─ 查询改写结果（可选）
    ├─ event: retrieval       ─ 检索到的候选证据 chunks
    ├─ event: status          ─ 等待模型首 token
    ├─ event: metrics         ─ TTFB (首 chunk 延迟)
    ├─ event: status          ─ 开始流式输出
    ├─ event: answer_delta    ─ 文本片段（重复多次）
    ├─ event: answer_delta    ─ ...
    ├─ event: metrics         ─ 流结束：总时长、chunk 数
    ├─ event: status          ─ 引用对齐阶段
    ├─ event: metrics         ─ Token 用量、估算成本
    ├─ event: citations       ─ 最终引用列表
    ├─ event: answer          ─ 完整答案文本
    └─ event: done            ─ 流结束

  ---
  2. 后端 SSE 序列化（1 行核心函数）

  services/api/modules/chat/routes.py:132-134:

  def _format_sse_event(event: str, data: dict) -> str:
      """Serialize a Server-Sent Event payload."""
      return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

  ---
  3. 各事件 JSON 结构

  status — 阶段通知

  {
    "stage": "embedding_query",
    "message": "Embedding your question for notebook retrieval"
  }

  stage 枚举值：embedding_query → waiting_model → streaming → grounding

  ---
  metrics — 计时与用量（渐进式，每阶段追加新字段）

  阶段 1 — 嵌入/检索完成后：
  {
    "model": "gpt-4o-mini",
    "query_embedding_seconds": 0.12,
    "query_embedding_model": "text-embedding-3-small",
    "query_embedding_token_count": 18,
    "query_embedding_estimated_cost_usd": 0.00001,
    "query_embedding_requests": 1,
    "retrieval_seconds": 0.34,
    "prepare_seconds": 0.52
  }

  阶段 2 — 首个 LLM delta 到达（TTFB）：
  {
    "time_to_first_delta_seconds": 1.23,
    "delta_chunks_received": 1,
    "stream_delivery": "streaming"
  }

  阶段 3 — LLM 流结束：
  {
    "llm_stream_seconds": 3.45,
    "delta_chunks_received": 42,
    "stream_delivery": "streaming"
  }

  阶段 4 — 最终 Token 用量：
  {
    "prompt_tokens": 3842,
    "completion_tokens": 512,
    "total_tokens": 4354,
    "cached_tokens": 1024,
    "usage_source": "stream_chunk",
    "estimated_cost_usd": 0.0021
  }

  ---
  query_rewrite — 查询改写（可选，仅当发生改写时发出）

  {
    "original_query": "它的核心结论是什么？",
    "standalone_query": "这篇文档的核心结论是什么？",
    "search_queries": [
      "核心结论 主要发现 研究结果",
      "这篇文档的核心结论是什么？"
    ],
    "strategy": "standalone_expansion",
    "used_llm": true,
    "rewritten": true
  }

  strategy 枚举值：no_rewrite | reference_resolution | standalone_expansion | keyword_enrichment

  ---
  retrieval — 检索到的候选证据

  {
    "chunk_count": 8,
    "source_count": 3,
    "chunks": [
      {
        "citation_index": 1,
        "chunk_id": "chk_uuid_abc",
        "source_id": "src_uuid_def",
        "source_title": "2024年年度报告.pdf",
        "chunk_index": 5,
        "page": "12",
        "quote": "公司全年营收增长23%，主要受益于...",
        "content": "公司全年营收增长23%，主要受益于海外市场的快速扩张以及新产品线的成功推出...",
        "score": 0.892
      }
    ]
  }

  ---
  answer_delta — 流式文本片段

  {
    "delta": "根据文档内容，"
  }

  ---
  citations — 最终引用对齐结果

  {
    "citations": [
      {
        "citation_index": 1,
        "chunk_id": "chk_uuid_abc",
        "source_id": "src_uuid_def",
        "source_title": "2024年年度报告.pdf",
        "chunk_index": 5,
        "page": "12",
        "quote": "公司全年营收增长23%...",
        "content": "公司全年营收增长23%，主要受益于...",
        "score": 0.892
      }
    ],
    "citation_indices": [1, 2, 3],
    "missing_citation_indices": [4]
  }

  missing_citation_indices — LLM 在答案中写了 [4] 但未在证据中找到对应的 chunk。

  ---
  answer — 完整答案

  {
    "answer": "根据文档内容，公司全年营收增长23%[1]，利润率提升了5个百分点[2]...",
    "raw_answer": "根据文档内容，公司全年营收增长23%[1]，利润率提升了5个百分点[2]..."
  }

  ---
  done — 流结束

  {
    "status": "complete"
  }

  ---
  error — 错误（任一阶段异常时发出，不中断连接）

  {
    "error": "quota_exhausted",
    "title": "对话额度已用尽",
    "message": "当前 Notebook 的对话次数已达上限，请稍后再试。",
    "hint": "可以尝试删除不需要的对话以释放额度",
    "retryable": true
  }

  error 枚举值：quota_exhausted | input_not_allowed | temporary_unavailable | internal_error

  ---
  4. 后端核心数据结构

  services/api/modules/chat/service.py:96-164:

  @dataclass(frozen=True)
  class EvidenceChunk:
      citation_index: int
      chunk_id: str
      source_title: str
      page: str | None
      quote: str
      content: str
      score: float
      source_id: str | None = None
      chunk_index: int | None = None

  @dataclass(frozen=True)
  class RetrievalDiagnostics:
      chunk_count: int
      source_count: int
      chunks: list[EvidenceChunk]

  @dataclass(frozen=True)
  class ChatTimingMetrics:
      model: str | None = None
      query_embedding_seconds: float | None = None
      retrieval_seconds: float | None = None
      time_to_first_delta_seconds: float | None = None
      llm_stream_seconds: float | None = None
      prompt_tokens: int | None = None
      completion_tokens: int | None = None
      total_tokens: int | None = None
      estimated_cost_usd: float | None = None
      # ... 完整字段见上文 metrics JSON

  ---
  5. 前端 TypeScript 事件类型（完整）

  apps/web/lib/chat-stream.ts:5-91:

  export interface ChatCitation {
    citation_index: number;
    chunk_id: string;
    source_id?: string | null;
    source_title: string;
    page: string | null;
    quote: string;
    content: string;
    score: number;
  }

  export interface ChatStatusEvent { stage: string; message: string; }
  export interface ChatCitationsEvent {
    citations: ChatCitation[];
    citation_indices: number[];
    missing_citation_indices: number[];
  }
  export interface ChatRetrievalEvent {
    chunk_count: number; source_count: number; chunks: ChatCitation[];
  }
  export interface ChatMetricsEvent {
    model?: string | null;
    query_embedding_seconds?: number | null;
    retrieval_seconds?: number | null;
    time_to_first_delta_seconds?: number | null;
    llm_stream_seconds?: number | null;
    prompt_tokens?: number | null;
    estimated_cost_usd?: number | null;
    // ...
  }
  export interface ChatQueryRewriteEvent {
    original_query: string;
    standalone_query: string;
    search_queries: string[];
    strategy: string;
    used_llm: boolean;
    rewritten: boolean;
  }
  export interface ChatAnswerDeltaEvent { delta: string; }
  export interface ChatDoneEvent { status: string; }
  export interface ChatErrorEvent {
    error: string; message: string;
    title?: string; hint?: string; retryable?: boolean;
  }

  ---
  6. 设计要点总结
  ┌─────────────────────┬───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │        维度         │                                                         说明                                                          │
  ├─────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 渐进式 metrics      │ metrics 事件不是一次性的，而是每完成一个阶段就追加新字段（嵌入→TTFB→流结束→Token 用量），前端通过 merge 累积          │
  ├─────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 可观测性 → 用户信任 │ retrieval 暴露候选 chunks 及分数，query_rewrite 暴露改写策略，用户能说"证据不对"而不是"你错了"                        │
  ├─────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 错误不中断连接      │ error 事件通过 _classify_chat_exception() 分类为结构化 guardrail payload，前端拿到 retryable 标记决定是否展示重试按钮 │
  ├─────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 两阶段引用          │ retrieval 是候选池（检索层），citations 是 LLM 实际引用的子集 + missing_citation_indices 标记悬空引用                 │
  └─────────────────────┴───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘


### 3.8 关键设计 2）双层引用系统

分享稿对应表述：

- Evidence layer
- Binding layer
- chunkId -> UI marker

对应代码位置：

- Evidence 打包：`services/api/modules/chat/service.py`
- Binding 解析：`services/api/modules/chat/service.py`
- 前端 marker/card：`apps/web/components/chat/message-bubble.tsx`
- Citation 模型和 API：`services/api/modules/citations/models.py`、`services/api/modules/citations/routes.py`

关键代码：

- `format_evidence_pack()`
- `build_grounded_messages()`
- `parse_grounded_answer_output()`
- `finalize_grounded_answer()`
- `renderAssistantContent()` 把 `[1][2]` 替换为可点击 marker

当前实现状态需要分开说：

- 已实现：
  - 检索结果编号成 `EvidenceChunk`
  - 模型回答中的 `[1][2]` 被解析并映射回 evidence
  - 前端可以点击 citation marker 和 citation card
- 未完全接线：
  - `Citation` 表和 `/api/messages/{message_id}/citations` 查询 API 已有
  - 但当前聊天流里 `_persist_chat_exchange()` 只写了 `Message`，没有同步写 `Citation` 行

为什么这么处理：

- 把检索 evidence 和最终 answer binding 分开，能区分“检索到了什么”和“答案实际引用了什么”。
- 对用户体验来说，这比只展示一个“候选检索列表”更有说服力。

方案选择理由：

- 先把运行时 citation 对齐链路跑通，再补审计持久化，是常见的分阶段实现方式。
- 当前 schema 和 API 已准备好，后续只差把 finalize 后的 citation 结果写库。

### 3.9 关键设计 3）透明度 UX

分享稿对应表述：

- 查询改写
- 耗时与 token/cost
- 检索证据
- 引用来源

对应代码位置：

- 后端透明度数据来源：`services/api/modules/chat/service.py`、`services/api/modules/chat/routes.py`
- 前端透明度面板：`apps/web/components/chat/chat-panel.tsx`
- SSE 事件协议：`apps/web/lib/chat-stream.ts`

关键代码：

- `ChatTimingMetrics`
- `build_retrieval_diagnostics()`
- Chat route 中连续发送 `metrics`、`query_rewrite`、`retrieval`
- `ChatPanel` 里 `mergeMetrics()`、`groupRetrievalChunks()`、`appendWorkflowEvent()`

为什么这么处理：

- 透明度不是日志副产品，而是产品能力。
- 后端提供结构化 payload，前端做“用户能看懂”的翻译和分组。
- 这让用户可以判断是 query rewrite、retrieval 还是 grounding 出了问题。

方案选择理由：

- 比起只输出模型答案，这种做法更利于 debug、评估和用户信任建立。
- 事件驱动面板也更容易被后续评估系统复用。

### 3.10 系统全景

分享稿对应表述：

- Next.js + FastAPI + PostgreSQL + pgvector + Redis + MinIO/S3 + provider abstraction

对应代码位置：

- API 入口与 router 装配：`services/api/main.py`
- Queue：`services/api/modules/ingestion/queue.py`
- Worker：`services/worker/main.py`
- Storage：`services/api/modules/sources/storage.py`
- Provider abstraction：`services/api/core/ai.py`

为什么这么处理：

- 前端和后端分层清楚，chat/ingestion 可以独立演进。
- Object storage 和 relational DB 分离，适合文件型 source。
- Queue + worker 让 ingestion 不阻塞 API 请求。

方案选择理由：

- 这是非常标准的“知识库/RAG 产品化”工程骨架，成本可控、易扩展。
- 当前又保留了 SQLite/local storage fallback，兼顾本地开发体验。

### 3.11 Ingestion 流水线

分享稿对应表述：

- 保存文件
- 文本提取
- 语义分块
- 快照
- 向量嵌入
- 入库与索引
- 状态机

对应代码位置：

- 文件存储：`services/api/modules/sources/routes.py`、`services/api/modules/sources/storage.py`
- 任务入队：`services/api/modules/ingestion/routes.py`
- Worker 执行：`services/worker/main.py`
- Orchestrator：`services/api/modules/ingestion/orchestrator.py`
- Snapshot：`services/api/modules/snapshots/service.py`

关键代码：

- `persist_source_bytes()`
- `enqueue_ingestion_job_for_source()`
- `ingest_source()`
- `IngestionOrchestrator.ingest()`
- `SourceSnapshotService.build_and_persist_snapshot()`

为什么这么处理：

- 把 ingestion 设计成明确的 step-by-step pipeline，方便状态展示、失败定位和重试。
- Snapshot 放在 embedding 之前，意味着 source 一旦 parse/chunk 完成，就能产出结构化摘要和导航信息。
- `PreparedSourceChunk` 先生成稳定 chunk ID，再 snapshot，再落库，保证 traceability。

方案选择理由：

- 这条链路服务的不只是“能问答”，还服务 snapshot preview、后续 evaluation、内容地图等能力。
- Worker 层专门处理 SQLite lock retry、cancelled 状态、source/notebook 删除中断，体现的是“先保证系统韧性”。

### 3.12 检索与问答

分享稿对应表述：

- 用户问题 -> 查询改写 -> 检索 -> 证据打包 -> LLM 生成 -> 引用绑定 -> SSE 展示

对应代码位置：

- `services/api/modules/chat/routes.py`
- `services/api/modules/chat/service.py`
- `services/api/modules/retrieval/hybrid.py`
- `services/api/modules/query/rewriter.py`

关键代码：

- `GroundedQAService.prepare_answer()`
- `build_grounded_messages()`
- `GroundedQAService.stream_answer()`
- `GroundedQAService.finalize_answer()`

为什么这么处理：

- `prepare_answer()` 先把 retrieval 和 prompt 准备好，流式阶段只负责 answer generation。
- 模型 prompt 明确要求“只能基于 evidence 回答”，没有 evidence 时返回“信息不足”。
- 对多条 rewritten query 的检索结果会再次 merge，降低单次重写偏差。

方案选择理由：

- 这是“retrieval 和 generation 解耦”的典型写法，便于分别调参和打指标。
- finalize 阶段做 citation 对齐，能把流式文本和最终结构化 answer 合并起来。

### 3.13 工程方法

分享稿对应表述：

- 文档驱动
- TDD
- 可观测

对应代码位置：

- 规则说明：`CLAUDE.md`
- 路线图：`DEVELOPMENT_PLAN.md`
- 进度记录：`TASK_CHECKLIST.md`
- 测试目录：`services/api/tests/` 和 `apps/web/**/*.test.tsx`

为什么这么处理：

- 这个仓库不是“先写一堆代码再解释”，而是先有计划和验收项，再推进实现。
- 透明度、SSE、query rewrite、snapshot 都有对应的测试文件和 checklist 记录。

方案选择理由：

- 对这种多模块耦合的 RAG 系统，文档驱动和测试驱动能明显降低“功能看起来都在、但链路对不上”的风险。

## 4. 当前实现与 WECHAT_SHARE.md 的关键差异

这部分建议你在对外讲时一定讲清楚，否则容易把“当前代码状态”和“方案愿景”混在一起。

### 4.1 Embedding 默认模型

分享稿写法：

- 倾向于把 embedding 描述成 `embedding-3` 或 OpenAI 风格默认值。

当前代码：

- `services/api/core/ai.py` 里默认是 `embedding-2`。
- `services/api/modules/embeddings/providers.py` 里定义了 `embedding-2 -> 1024`，`embedding-3 -> 2048`。

建议表述：

- “当前运行时默认使用 BigModel 的 `embedding-2`，也兼容切换到 `embedding-3` 或 OpenAI-compatible 配置。”

### 4.2 Query Rewrite 的真实策略

分享稿写法：

- “启发式优先，LLM 兜底”

当前代码：

- 启发式负责判定“要不要重写”和“应该用什么策略”
- 只要判定需要重写，就直接调用 LLM 生成结构化 rewrite 结果
- 不需要重写时才保留原 query

建议表述：

- “当前实现是启发式门控 + LLM 执行重写；无需重写时直接沿用原 query。”

### 4.3 双层引用系统的持久化状态

分享稿写法：

- 容易让人理解成“运行时引用链和审计存储都已完整接通”

当前代码：

- 运行时 evidence layer 和 binding layer 已有
- Citation 表和查询 API 已有
- 但 chat stream 完成后只写 `Message`，没有写 `Citation`

建议表述：

- “运行时引用绑定已经生效；citation 的持久化 schema 和 API 已准备好，但聊天链路的写库接线还差最后一步。”

### 4.4 BM25 的实现方式

分享稿读感：

- 容易让人默认这是 Elasticsearch 或 PostgreSQL FTS 那一类生产级 lexical retrieval

当前代码：

- 是 notebook 级别的内存 BM25 索引，缓存于 API 进程内

建议表述：

- “当前 lexical retrieval 采用轻量级 notebook 内存 BM25，实现简单、可测、足够支撑当前规模；后续可以无缝替换为数据库侧或专用搜索引擎。”

## 5. 最值得讲的几个“关键代码点”

如果你要对外讲解实现，我建议重点讲这 8 个点：

1. `Chunker.chunk_text()`：不是机械切块，而是句子级累加 + overlap。
2. `prepare_source_chunks()`：先生成稳定 chunk ID，为 snapshot 和 traceability 打底。
3. `EmbeddingService.embed_batch()`：批量、token、cost 汇总集中在 service 层。
4. `BigModelEmbeddingProvider._create_embedding_response()`：retry/backoff/rate limit 都在 provider 层。
5. `VectorSearchService.search()`：PostgreSQL 用 pgvector，SQLite 用手工 fallback。
6. `reciprocal_rank_fusion()`：RRF 融合让 vector 和 BM25 的组合足够简单可解释。
7. `QueryRewriter.rewrite_for_retrieval()`：先门控，后重写，还校验 protected terms。
8. `stream_grounded_chat()`：把 chat 过程拆成结构化 SSE 事件，直接支撑透明度 UX。

## 6. 如果你要把这份分享稿讲成“代码案例”

建议你用这条叙事线：

1. 先讲 Notebook 是真相边界，不是 prompt 约束，而是数据模型和查询约束。
2. 再讲 ingestion 是如何把 source 变成 chunk、snapshot 和 embedding 的。
3. 然后讲 chat 链路不是“用户问题直接喂给模型”，而是 rewrite + retrieval + grounded prompt。
4. 再讲透明度 UX，把 query rewrite、retrieval、metrics 都做成显性 UI。
5. 最后讲当前仍在演进的部分：citation 持久化、content-map、更强 lexical retrieval。

这样讲最符合当前仓库的真实完成度，也最容易让听众理解这套系统的工程价值。
