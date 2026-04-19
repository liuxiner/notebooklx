# NotebookLX：把 AI 从“会说”做成“可追溯、可审计、可复盘”的知识工作台（案例分享）

如果你用过通用 AI 对话，你一定经历过这种尴尬时刻：它回答得很流畅、很肯定、甚至很有“逻辑”，但你心里只有一个问题——“你凭什么这么说？”

我们做 NotebookLX 的起点，就是把这句“凭什么”变成产品的第一原则：让 AI 的每句话，都能回到源文档中的某一段、某一页、某一处证据上；让检索、改写、耗时、成本、引用绑定都不再是黑盒；让你不仅能拿到答案，还能拿到“答案的来路”。

这篇分享不是“堆功能清单”，也不是“又一个 RAG demo”。我会用一篇足够干货、可以直接当作案例研究的长文，把 NotebookLX 的核心卖点、关键参数、系统取舍和可复用的工程方法，讲清楚——技术同学能抄作业，非技术同学也能看懂并愿意转发。

---

## 一句话定位（也是产品承诺）

NotebookLX 是一个“以源文档为真相边界”的 AI Notebook 工作台：你把文件/网页/文本等材料放进笔记本里，AI 只能基于这些材料回答；每条回答都带引用标记，点击即可回到具体来源段落；同时把“AI 是怎么得出这个回答的”公开给你看。

把它理解成：一个不是靠“想象力”工作，而是靠“证据链”工作的大模型助手。

---

## 你为什么会想要它（给非技术朋友的直觉版）

在学习、研究、写作、做方案时，我们真正稀缺的不是“灵感”，而是三件事：

1) 可信：看到一句结论，你想知道来源与上下文。  
2) 可控：你只想让 AI 使用你给的材料，而不是“引用互联网与训练记忆的混合物”。  
3) 可复用：今天的读书笔记、明天的写作素材、后天的复盘证据，能沉淀在同一个工作台里。

NotebookLX 试图解决一个更朴素的需求：当你在做重要判断时（写报告、做投研、写论文、做产品决策、准备面试），你不需要一个“会聊天的 AI”，你需要一个“能出示证据的 AI”。

---

## 这不是宣传话术：我们把“信任”拆成了可实现的系统设计

先把整套方案的亮点按“可复用/可讨论”的方式列出来（后面逐个展开）：

1) Sources 定义真相边界：所有检索、回答都被硬性限定在 `notebook_id` 范围内。  
2) 双层引用系统：不仅有“检索到的证据列表”，还有“答案语句与证据段落的绑定关系”。  
3) 混合检索 + RRF 融合：BM25 负责术语精确，向量负责语义相似，再用 RRF 融合避免手调权重。  
4) 查询改写：启发式优先、LLM 兜底，减少不必要调用，兼顾成本、延迟与可解释性。  
5) 透明度即产品：把检索、改写、耗时、Token、成本这些“系统内部过程”变成 UI 面板。  
6) Ingestion 流水线参数可解释：分块大小、重叠窗口、元数据保留、批量嵌入等都明确落到工程决策。  
7) SSE 流式协议：不仅流式输出答案，还流式推送状态、指标、检索证据、引用绑定。  
8) Provider 抽象：智谱 AI / OpenAI 可切换，核心链路与供应商解耦。  
9) PostgreSQL + pgvector：关系数据与向量检索一体化，配合 HNSW 索引保证交互级检索体验。  
10) 工程方法论：TDD + 文档驱动（`DEVELOPMENT_PLAN.md` / `TASK_CHECKLIST.md`）把“做对”变成流程。

如果你只想看“可抄参数”，下面这一段可以直接截图保存。

---

## 案例研究级参数表：我们到底怎么选的

说明：这些参数不是“唯一正确”，但它们是我们在“可追溯体验、成本、延迟、实现复杂度”之间做出的可解释取舍，足够你在自己的系统里当作起点。

### 1) 语义分块（Chunking）

- 分块策略：按段落/标题自然边界切分（优先语义完整，不用固定窗口硬切）  
- 目标块大小：`300–800 tokens/块` [1]（兼顾“证据段落可读性”与“检索召回”）  
- 相邻块重叠：`50–120 tokens` [2]（降低信息被切在边界导致的丢失）  
- 关键元数据：页码、标题层级、字符位置（为精确引用与 UI 定位服务）

为什么不是更大或更小？  
太小：证据碎片化，引用很多但上下文不够；太大：召回更难、上下文更贵、引用跳转体验变差。我们把“能被人读懂的一段”当作目标单位。

### 2) 嵌入（Embeddings）

- 向量维度：`1536`（以 `text-embedding-3-small` 为例）  
- 批量嵌入：`32–100 chunks/次调用`（吞吐与失败重试成本折中）  
- 重试策略：指数退避（避免短期抖动导致雪崩）  
- 成本追踪：每次对话/摄入记录 Token 与估算成本（成本可视化是产品的一部分）

### 3) 向量索引与数据库

- 存储：PostgreSQL + pgvector（关系模型与向量同库，减少多系统一致性维护）  
- ANN 索引：HNSW [3]（目标：向量检索延迟达到“交互可用”的水平）  
- 取舍：牺牲一些向量专用库的极致性能，换来部署简单、事务一致性与工程可控

### 4) 检索融合（Hybrid Retrieval）

- BM25：解决“专有名词/术语/代码片段”这类精确匹配  
- Vector：解决“自然语言描述/同义表达”这类语义匹配  
- 融合：RRF（Reciprocal Rank Fusion）[4]  
- RRF 公式：`score(d) = Σ 1 / (k + rank_i(d))`（两路检索各自给 rank，再融合）  
- RRF 参数：`k = 60`（降低头部名次波动对总分影响，避免权重调参的复杂性）

### 5) 查询改写（Query Rewrite）

- 策略：启发式优先，LLM 兜底  
- 常见触发：代词消解（这个/那个/他）、追问承接（还有呢/继续）、模糊扩写、关键词补全  
- 价值：少用一次 LLM 就少一笔成本、少一次延迟；改写过程可解释、可展示、可复盘

### 6) 流式交互协议（SSE）

- 不止 `answer_delta`：还包括 `status`、`metrics`、`query_rewrite`、`retrieval`、`citations`、`error`、`done`  
- 价值：把“系统内部过程”变成“用户可感知的信任线索”，同时为排障与评估留下结构化事件流

---

## 关键设计 1：Sources 定义真相边界（解决“你凭什么这么说”）

很多 RAG 产品的问题，不在“检索不准”，而在“边界不清”：用户以为 AI 只看了自己上传的资料，但实际上模型可能混入外部知识或幻觉式补全 [5]。

NotebookLX 的边界策略很直接：笔记本是隔离单元。检索、改写、回答都要带上 `notebook_id`，并在查询层面硬性限定。这样做带来的产品效果是：你可以清楚地知道“这段结论只来自这本笔记本里的这些 sources”，而不是来自一个不可见的世界。

边界清楚之后，可信度不再是一句“我觉得”，而是一个动作：你点开引用就能看到来源。

---

## 关键设计 2：双层引用系统（把引用从“装饰”升级为“证据链”）

我们把引用拆成了两层，因为它们回答的是两个不同的问题：

Layer 1：检索证据层（Evidence Layer）  
- 回答“系统找到了哪些材料”  
- 内容是候选 chunks 列表：来源、页码、相关度分数、原文片段

Layer 2：答案绑定层（Binding Layer）  
- 回答“答案这句话依据的是哪段材料”  
- LLM 输出结构化 `answer_blocks`，每个文本块关联 `citation_chunk_ids`  
- 后端把 chunkId 映射为 UI 引用标记 `[1][2][3]...`

为什么要做第二层？  
因为仅有检索列表并不能证明“答案用到了什么”。你需要的是“这句话 -> 这段证据”的映射。这个映射一旦建立，产品体验会从“我相信你检索到了”跃迁到“我确认你引用了” [6]。

---

## 关键设计 3：透明度 UX（把系统工程变成用户信任）

对技术同学来说，透明度是可观测性；对非技术用户来说，透明度是安心感。我们把它做成了一个可交互的面板，而不是藏在日志里。

透明度面板里会看到：

- 查询改写：原始问题 -> 选择的改写策略 -> 搜索查询  
- 计时与用量：嵌入耗时、检索耗时、首 token 时间、Token 用量、估算成本  
- 检索证据：候选 chunks 的来源、页码、相关度分数、原文引用  
- 引用来源：答案实际引用的 chunks，一键展开上下文

它带来的一个现实变化是：用户遇到“回答不满意”时，不再只能说“你错了”，而是能说“你引用的证据不对/漏了某个 source/改写把关键词误导了”。这让系统优化从“拍脑袋调参”变成“带证据的迭代”。

---

## 系统全景（给技术读者的架构速览）

```
Frontend: Next.js + Tailwind + shadcn/ui + SSE Client
    |
HTTP/SSE
    |
Backend: FastAPI
  - notebooks / sources / ingestion / chunking / embeddings
  - retrieval (BM25 + Vector + RRF)
  - query rewrite
  - chat (grounded QA)
  - citations (evidence + binding)
    |
PostgreSQL + pgvector (HNSW)
Redis (Arq task queue)
MinIO/S3 (source objects)
AI Provider abstraction (ZhipuAI / OpenAI)
```

为什么这套栈“适合作为案例研究”？  
因为它不是追求“最炫最全”，而是把每个组件的存在理由写清楚：数据一致性、可观测、可追溯、可迭代。这些东西比“又接了一个模型”更能复用。

---

## Ingestion 流水线：把“资料”变成“可检索、可引用的证据”

从用户体验上看是“上传文件 -> 等一会 -> 能问问题”；但从系统角度，这个“等一会”是一条明确的、可度量的流水线：

1) 保存原始文件（MinIO/S3）  
2) 文本提取（PDF/URL/Text/YouTube/Google Docs 等）  
3) 语义分块（带参数、带元数据）  
4) 快照生成（概述/主题/关键词，用于预览与导航）  
5) 向量嵌入（批量、重试、成本追踪）  
6) 入库与索引（chunks + embeddings + HNSW）  
7) 状态机：`pending -> processing -> ready / failed`（失败要有可解释错误）

这段流水线最关键的不是“能跑通”，而是它天然形成了可评估点：每一步都有耗时、错误类型、重试次数、成本。这是后面做“评估仪表板”的基础。

---

## 检索与问答：把“证据”变成“答案”（并且不给幻觉留空子）

NotebookLX 的问答链路里有一个硬原则：回答只允许基于 evidence context。  
这意味着你看到的答案，本质上是“证据段落的再组织”，而不是模型自由发挥。

典型链路是：

用户问题 -> 查询改写 -> 混合检索 -> RRF 融合 -> 证据打包 -> LLM 生成 -> 引用绑定 -> SSE 流式展示

其中最重要的工程点是“证据打包”：不仅要把 chunks 拼成上下文，还要带上可追溯的索引，让后续绑定层能把每句话关联回 chunkId。

---

## 工程方法：让项目不止能演示，还能持续演进

NotebookLX 不是一次性 demo，它需要可维护、可扩展。我们用三件事保证“能跑”到“能长久跑”：

1) 文档驱动：`DEVELOPMENT_PLAN.md` 提供验收标准与路线图，`TASK_CHECKLIST.md` 跟踪推进。  
2) TDD：先写测试再实现，保证每个验收点都有自动化回归。  
3) 可观测：把耗时、用量、引用链路都结构化出来，前台可看、后台可查。

如果你也在做 RAG/知识库/Agent 相关项目，这三件事往往比“换个更强模型”更能决定项目能不能走到生产。

---

## 谁会特别适合用它（以及你会得到什么）

如果你是技术人员（架构/后端/算法/工程）：

- 你可以把这套“真相边界 + 双层引用 + 透明度 UX”当成一个可复用的产品范式  
- 你可以直接拿走参数表作为系统起步配置，再按你的数据规模迭代  
- 你可以用它做团队内部的“可审计 RAG”对标，复盘召回、引用与成本

如果你不是技术人员（研究/运营/产品/管理/自媒体/学生）：

- 你会得到一个“不会把你带沟里”的 AI：答案不再靠感觉，而是能回到资料里验证  
- 你会更轻松地读完一堆材料：因为可以问、可以追问、可以点引用回到原文  
- 你会把散落的资料沉淀成一个可以持续使用的知识工作台

---

## 路线图（我们接下来最想做的事）

当“可追溯问答”站稳之后，下一步就是把 Notebook 变成真正的学习与研究工作台：

- 自动摘要与主题提取（仍然强绑定 sources）  
- 推荐问题/FAQ/学习指南（可配置、可复盘）  
- 源文档交叉分析（跨 sources 的对比与证据抽取）  
- Reranker 集成与评估流水线（让检索优化更像工程而不是玄学）  
- 权限与协作（让团队共用同一个“证据链”）

---

## 附录：参考资料与原理解释 (References & Rationale)

为了保证系统设计的严谨性，NotebookLX 采纳了以下学术界与工业界的标准实践：

  * **[1] 语义分块（Chunking Size）的甜点区间：**
    行业实践证明，`300-800 tokens` 能在上下文完整性与检索特异性之间取得平衡。

      * **参考:** [Pinecone: Chunking Strategies for LLM Applications](https://www.pinecone.io/learn/chunking-strategies/)
      * **参考:** [OpenAI Cookbook: RAG Quickstart Guide](https://www.google.com/search?q=https://github.com/openai/openai-cookbook/tree/main/examples/chatgpt)

  * **[2] 重叠窗口（Chunk Overlap）的必要性：**
    设定 10%-20% 的重叠是防止长句截断、提升实体召回的标准做法。

      * **参考:** [LangChain Docs: Text Splitters and Overlap](https://www.google.com/search?q=https://python.langchain.com/docs/modules/data_connection/document_transformers/)
      * **参考:** [LlamaIndex: Optimizing Basic RAG Strategies](https://docs.llamaindex.ai/en/stable/optimizing/basic_strategies/basic_strategies/)

  * **[3] HNSW (Hierarchical Navigable Small World) 算法：**
    这是目前工业界最高效的近似最近邻检索算法，支撑了高性能向量数据库的实现。

      * **论文:** [Malkov & Yashunin (2018): Efficient and robust approximate nearest neighbor search using HNSW graphs](https://arxiv.org/abs/1603.09320)
      * **文档:** [pgvector: HNSW Indexing Reference](https://www.google.com/search?q=https://github.com/pgvector/pgvector%23hnsw)

  * **[4] RRF (Reciprocal Rank Fusion) 融合策略：**
    该算法通过倒数排名融合多路检索结果，常数 $k=60$ 是学术界公认的平衡参数。

      * **论文:** [Cormack et al. (2009): Reciprocal Rank Fusion outperforms individual Rank Learning Methods](https://dl.acm.org/doi/10.1145/1571941.1572114)
      * **文档:** [Elasticsearch Guide: Reciprocal Rank Fusion (RRF)](https://www.elastic.co/guide/en/elasticsearch/reference/current/rrf.html)

  * **[5] RAG 的幻觉抑制与真相边界 (Groundedness)：**
    RAG 最初由 Meta AI 提出，旨在将生成式 AI 的知识获取从“记忆”转向“检索”。

      * **论文:** [Lewis et al. (2020): Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://arxiv.org/abs/2005.11401)
      * **综述:** [Gao et al. (2023): Retrieval-Augmented Generation for Large Language Models: A Survey](https://arxiv.org/abs/2312.10997)

  * **[6] 归因与引用评价标准 (ALCE)：**
    评估 AI 答案是否“每句都有出处”的权威基准测试。

      * **论文:** [Gao et al. (2023): ALCE: A Benchmark for Evaluating Grounded Text Generation](https://arxiv.org/abs/2305.14627)
      * **项目:** [Princeton-NLP: ALCE Evaluation Framework](https://github.com/princeton-nlp/ALCE)


---

最后：为什么我愿意把它写成一篇长文

因为我们正处在一个“AI 很强但很难信”的时代。真正能落地的 AI 产品，靠的不是更会说，而是更能把“说的依据”交到你手上。

NotebookLX 想做的是一种更长期主义的体验：当你学习、研究、做决定时，你能更安心、更确定、更少被幻觉浪费时间。它也希望给做技术的同学一个可复用的答案：如何把 RAG 做成产品，而不是做成 demo。
