# NotebookLX Evaluation System PRD

> 面向 RAG 知识库的可验证、可回归、可解释评测体系

---

# 1. 背景与目标

## 1.1 文档标题

**NotebookLX Evaluation System PRD — 面向 RAG 知识库的可验证、可回归、可解释评测体系**

## 1.2 背景

NotebookLX 是一个面向私有知识库问答的本地工作台，核心链路覆盖：文档 ingestion → 语义切块 → 向量化 → 混合检索(BM25 + Vector + RRF) → Query Rewrite → Reranking → 证据打包 → 流式生成 → 双层引用绑定 → 前端展示。

当前系统已具备以下工程化能力：

- 异步 ingestion pipeline，带状态流转、失败处理、进度跟踪与批量轮询
- Hybrid Retrieval：BM25 + Vector + RRF 融合检索
- Two-layer Citation System：候选证据层与答案绑定层解耦
- Chat guardrails：统一处理 quota / safety / upstream failure 等流式异常
- Retrieval transparency：检索耗时、首 token 延迟、chunk 使用明细可观测
- Query rewriting：暴露 rewrite metadata，支持改写前后对比

**但存在一个关键短板：系统的质量改善主要依赖主观感受，缺乏体系化的评测手段来量化"变好了"还是"变差了"。**

RAG 系统的效果不是单一模型输出质量问题，而是系统性工程问题，涉及：

- 用户输入理解与意图识别
- Query rewrite 策略选择
- Notebook scope 边界判定
- 检索策略（BM25 权重、Vector 权重、Top-K、RRF 融合参数）
- 可选的 Reranking 效果
- 可选的 Graph 扩展检索
- 证据打包与 Prompt 组装
- 引用绑定正确性
- 最终回答的 groundedness / faithfulness / completeness
- 响应延迟与 token 成本

每一个环节的变动都可能引发连锁效应，而当前没有手段精确定位"哪个环节导致退化"。

## 1.3 文档目标

定义一套以 NotebookLX 为首个落地场景、面向 AI Agent 的评测体系，覆盖：

| 维度 | 说明 |
|------|------|
| 离线评测 | 针对 frozen test set 的批量自动化评分 |
| 在线评测 | 针对线上真实 query 的抽样评估（远期） |
| 人工评审 | 分维度打分、双人复核、分歧裁决 |
| 自动化回归 | 配置变更 / Prompt 变更 / 模型升级后的自动对比 |
| 测试集治理 | 标签分类、难度分层、去重、badcase 回流、覆盖率检查 |
| 结果可解释 | 失败归因到具体模块（rewrite / retrieval / citation / generation） |
| 版本对比 | A/B 实验、多轴实验矩阵、统计显著性提示 |
| 上线门禁 | 基于量化指标的发布准入标准 |

## 1.4 核心目标

本评测系统必须能回答以下 5 个问题：

1. **检索是否靠谱** — 改了 rewrite / rerank / 检索参数后，recall@k 和 MRR 是否有变化？
2. **引用是否可信** — 回答中的 citation 是否真正支撑了陈述？是否存在错引、漏引、过度引用？
3. **答案是否扎实** — 回答是否 grounded 在检索证据上？是否存在幻觉？是否完整回答了用户问题？
4. **新版是否优于旧版** — 具体哪个指标升了、哪个降了？退化点在哪？
5. **能否指导优化** — 失败归因能否定位到 rewrite / retrieval / rerank / prompt / scope 的具体环节？

## 1.5 适用范围

本评测体系首期面向 NotebookLX 的以下核心链路，同时在对象抽象上兼容 Chat Agent / RAG Agent / Tool-use Agent / Workflow Agent 的扩展：

- **Ingestion Pipeline**：解析质量、切块覆盖度、snapshot 生成质量
- **Context Compression Layer**：source snapshot、section snapshot、notebook synopsis、scope in/out
- **Retrieval Layer**：hybrid retrieval、query rewrite、reranking、graph expansion
- **Citation Layer**：双层引用的正确性校验
- **Answer Layer**：groundedness、faithfulness、completeness
- **System Layer**：延迟、成本、稳定性、可观测性完备度

---

# 2. 问题定义

## 2.1 当前痛点

| # | 痛点 | 具体表现 | 影响 |
|---|------|---------|------|
| P1 | **检索优化无法量化** | 调了 BM25 权重、加了 rewrite、开了 rerank，只能说"感觉好了一点"，无法证明 recall@k 是否真的提升 | 每次调参是玄学，无法形成可复用的优化经验 |
| P2 | **引用质量无校验** | 有 citation 展示，但不知道 citation 是否真正支撑了对应陈述，错引、漏引、过度引用无从发现 | 用户看到的引用可能是虚假的可信度信号 |
| P3 | **幻觉无法定位根因** | 出现 hallucination 后，不知道是 retrieval 没召回、rewrite 偏离、还是 generation 阶段模型自由发挥 | 修复靠猜，改了 A 可能其实是 B 的问题 |
| P4 | **测试 case 零散** | 没有 frozen test set，测试依赖手动输入几个问题，覆盖不全、不可复现 | 每次回归测试的范围和结果不一致 |
| P5 | **无版本对比能力** | 改了 prompt 或 retrieval 策略后，只能主观对比，没有 side-by-side 指标对比 | 无法证明优化有效，也无法发现隐性退化 |
| P6 | **badcase 无沉淀机制** | 发现一个 badcase，口头说"记一下"，然后就没有然后了 | 同样的问题反复出现，没有回归防护 |
| P7 | **scope 边界无法评估** | 加了 scope in/out 后，不知道边界判定是否准确，false in-scope 和 false out-of-scope 比例不明 | 要么回答了不该回答的，要么拒答了能回答的 |
| P8 | **成本与延迟不可追踪** | 优化效果可能以延迟增加或 token 成本上升为代价，但没有联合看板 | 无法评估优化是否值得 |

## 2.2 问题分类

将上述痛点归类为四个问题域：

```
┌─────────────────────────────────────────────────┐
│                 评测问题域                         │
├──────────────┬──────────────┬───────────┬────────┤
│  A. 检索层    │  B. 引用层    │ C. 答案层  │D. 系统层│
│              │              │           │        │
│ • 召回质量   │ • 引用支撑度  │ • 扎实性   │ • 延迟  │
│ • 排序质量   │ • 错引率     │ • 忠实性   │ • 成本  │
│ • rewrite    │ • 漏引率     │ • 完整性   │ • 稳定性│
│   收益       │ • 过度引用   │ • 拒答正确性│        │
│ • rerank     │              │           │        │
│   收益       │              │           │        │
│ • scope      │              │           │        │
│   判定准确率  │              │           │        │
└──────────────┴──────────────┴───────────┴────────┘
         ↑               ↑              ↑
         │               │              │
    ┌────┴───────────────┴──────────────┴────┐
    │         E. 工程化支撑缺失               │
    │  • 无 frozen test set                  │
    │  • 无自动评分                          │
    │  • 无版本对比                          │
    │  • 无 badcase 回流                     │
    │  • 无上线门禁                          │
    └───────────────────────────────────────┘
```

## 2.3 问题优先级

基于 NotebookLX 当前阶段，按以下优先级解决：

| 优先级 | 问题域 | 解决方向 | 理由 |
|--------|--------|---------|------|
| **P0** | A. 检索层 + E. 工程化 | 建立 frozen test set + retrieval eval pipeline | 检索是 RAG 的地基，检索不行后面全是空谈 |
| **P0** | B. 引用层 | citation correctness eval v1 | 双层引用是项目招牌，必须能证明它靠谱 |
| **P1** | C. 答案层 | groundedness / faithfulness / completeness judge | 证明系统不是在胡说 |
| **P1** | E. 工程化 | 版本对比 + config snapshot + 自动化运行 | 从"能看"变成"像工程" |
| **P2** | D. 系统层 | 延迟 / 成本联合看板 | 优化是否有代价需要可见 |
| **P2** | E. 工程化 | badcase 回流 + 上线门禁 | 企业落地的门票 |

---

# 3. 范围与非目标

## 3.1 本系统要做的事（In Scope）

| 类别 | 具体内容 |
|------|---------|
| **评测对象** | NotebookLX 的 retrieval pipeline、citation system、answer generation、query rewrite、scope 判定、context compression（snapshot / synopsis） |
| **平台抽象** | Evaluation Object / Dataset / Runner / Scoring / Review / Gate 六类核心对象平台化设计，NotebookLX 为首个 adapter |
| **评测方式** | 离线批量评测、LLM-as-a-Judge、人工评审、混合评分 |
| **评测粒度** | 评测 run 级聚合、单 case 级详情、trace 步骤级归因 |
| **测试集管理** | 新建 / 导入 / 导出测试集，样本标签分类、难度分层、去重、badcase 回流、版本冻结 |
| **实验体系** | 多轴实验矩阵（rewrite strategy × retrieval strategy × scope policy × question type）、config snapshot、run 对比 |
| **报告与可视化** | aggregate dashboard、per-sample drill-down、版本对比趋势图、失败分布图、延迟/成本联合看板 |
| **上线门禁** | 基于量化指标的 pass/block 判定，可配置的阈值规则 |
| **可追溯性** | 每次 run 关联 commit sha、config snapshot、dataset version、prompt version |

## 3.2 本系统不做的事（Out of Scope）

| 不做 | 原因 |
|------|------|
| 通用 LLM Benchmark 平台 | 本系统面向 NotebookLX 的 RAG 评测，不是 MMLU / HumanEval 类通用 benchmark 工具 |
| 模型训练 / 微调评测 | 不涉及模型训练阶段的 loss / accuracy 追踪 |
| 替代日志平台 / APM | 不做实时链路追踪和报警，与 OpenTelemetry / Grafana 等工具互补而非替代 |
| 全自动"绝对准确"裁判 | LLM-as-a-Judge 本身有误差，系统必须承认并暴露这一点，通过人工抽样校准来弥补 |
| 跨 notebook 全局知识图谱评测 | Graph 扩展检索的评测限于 notebook 内局部子图，不做全局图谱质量评估 |
| 通用 Agent 编排评测 | 不评测 workflow engine / multi-agent 协同等 NotebookLX 当前不具备的能力 |
| 用户行为分析 / AB Testing 平台 | 不做线上流量分流和用户行为埋点分析，仅做离线评测和远期的线上抽样评估 |

## 3.3 边界说明

```
┌──────────────────────────────────────────────────┐
│              NotebookLX Eval System               │
│                                                   │
│  ┌───────────┐  ┌───────────┐  ┌───────────────┐ │
│  │ Retrieval │  │ Citation  │  │   Answer      │ │
│  │   Eval    │  │   Eval    │  │   Quality     │ │
│  └───────────┘  └───────────┘  └───────────────┘ │
│  ┌───────────┐  ┌───────────┐  ┌───────────────┐ │
│  │  Context  │  │  System   │  │   Experiment  │ │
│  │ Compression│ │   Perf    │  │   & Compare   │ │
│  └───────────┘  └───────────┘  └───────────────┘ │
│                                                   │
├───────────────────────────────────────────────────┤
│              不触碰的边界                           │
│                                                   │
│  • 通用 LLM Benchmark                             │
│  • 模型训练/微调评测                               │
│  • 实时 APM / 链路追踪报警                         │
│  • 线上流量 AB Testing                             │
│  • 全局知识图谱质量评估                             │
│  • Multi-Agent 编排评测                            │
└───────────────────────────────────────────────────┘
```

## 3.4 设计原则

1. **先做能证明能力的最小闭环** — 不追求大而全，优先跑通 retrieval eval → citation eval → answer eval 的闭环
2. **每个指标必须可操作** — 指标不是为了装饰 dashboard，而是能直接指导"下一步改什么"
3. **评测本身也要被评测** — LLM Judge 需要人工抽样校准，测试集需要定期审核质量
4. **配置即代码** — 评测配置、prompt、rubric 全部版本化，可复现、可回溯
5. **失败比成功更有价值** — 优先暴露 badcase 和退化点，而不是追求高分

---

# 4. 用户角色与场景

## 4.1 角色定义

| 角色 | 职责 | 核心诉求 |
|------|------|---------|
| **Engineer（研发）** | 调优 retrieval / rewrite / prompt / scope 策略，执行评测，分析失败 | 快速知道哪一步退化、能看 trace 和每步评分、能做版本对比与 root cause |
| **QA（测试）** | 维护测试集、执行回归评测、人工评审 badcase | 有可复用测试集、有明确评审标准、能批量执行与复查、能沉淀标准 badcase |
| **Reviewer（评审员）** | 对 LLM Judge 结果做人工抽样校准、对争议 case 做双人复核 | 评审操作轻量、有 rubric 参考、能记录评分与评论 |
| **PM / 设计** | 关注端到端用户体验质量、判断系统是否可上线 | 能看整体质量趋势、能看 Agent 是否"有帮助""可信""易纠错" |
| **Admin（管理员）** | 配置上线门禁阈值、管理评测权限、冻结/发布测试集版本 | 统一质量指标、上线门槛明确、版本趋势可追踪 |

## 4.2 核心用户场景

### 场景 1：研发调参后验证（Engineer）

```
触发：研发修改了 rewrite 策略或 BM25 权重
流程：
  1. 选择评测对象（Agent + commit sha）
  2. 选择测试集（Regression Set）
  3. 选择实验配置（rewrite=v2, bm25_weight=0.4）
  4. 执行评测
  5. 查看结果总览：recall@5 从 0.72 → 0.78，MRR 从 0.65 → 0.70
  6. 下钻到退化的 case：发现 3 条 multi-hop 问题 recall 下降
  7. 查看 trace：rewrite 将 multi-hop query 拆成了两个独立检索，导致跨 source 召回失败
  8. 标记这 3 条为 badcase，加入回归集
  9. 修改 rewrite 策略，重新跑评测
```

### 场景 2：版本上线前回归（QA + PM）

```
触发：准备发布新版本
流程：
  1. QA 发起正式评测，选择 Gold Set + Release Holdout Set
  2. 系统自动跑完全量测试 + 自动评分
  3. Dashboard 展示：
     - Smoke Set 通过率 96%
     - Release Holdout Run Quality Score 4.28 / 5.0
     - 高风险 case 通过率 92%
     - Hallucination Rate 1.8%
     - 与上一版本对比：recall@10 持平，faithfulness 提升 3%，latency +200ms
  4. QA 处理全部强制复核样本，并按分层抽样补足人工复核
  5. PM 查看总览页，判断是否满足上线门槛
  6. 评审结论：Pass with Risk（latency 升高需关注，但质量指标达标）
```

### 场景 3：badcase 回流（QA + Engineer）

```
触发：线上用户反馈一条错误回答
流程：
  1. QA 将该 query + context + 错误输出录入系统
  2. 标注失败原因标签：hallucination / wrong_citation / retrieval_miss / scope_error
  3. 标注 source_revision_ids + evidence_anchors（应该命中的稳定证据）
  4. 标注 expected_output（期望回答）
  5. 加入 Regression Set
  6. 下次评测自动检测该 case 是否回归
```

### 场景 4：LLM Judge 校准（Reviewer）

```
触发：LLM Judge 评分完成后
流程：
  1. 系统将全部高风险 / 回归 / 低置信度 case 直接送入 review queue，并按分层抽样补足样本
  2. Reviewer 按维度打分（groundedness / faithfulness / completeness）
  3. 系统计算人机一致率（Cohen's Kappa）
  4. 若 Kappa < 0.6，标记 Judge prompt 需要优化
  5. Reviewer 对分歧 case 添加评论，作为最终裁决
```

### 场景 5：实验矩阵对比（Engineer）

```
触发：需要评估 rewrite + rerank + scope 的组合效果
流程：
  1. 配置实验矩阵：
     - Rewrite: none / chat-history / snapshot-aware
     - Retrieval: vector-only / hybrid / hybrid+rerank
     - Scope: none / soft / hard
  2. 批量提交 9 组实验
  3. Dashboard 以矩阵形式展示每组实验的 recall@5 / MRR / groundedness / latency
  4. 标注 Pareto 最优组合（质量最高且延迟可接受）
  5. 选择最优配置，保存为新的 baseline
```

## 4.3 角色权限矩阵

| 操作 | Engineer | QA | Reviewer | PM | Admin |
|------|----------|-----|----------|-----|-------|
| 创建 / 编辑测试集 | ✓ | ✓ | — | — | ✓ |
| 发起评测 run | ✓ | ✓ | — | — | ✓ |
| 查看评测结果 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 查看 blind holdout 标准答案 | — | ✓ | ✓ | — | ✓ |
| 人工评审打分 | ✓ | ✓ | ✓ | — | ✓ |
| 标记 badcase | ✓ | ✓ | ✓ | — | ✓ |
| 确认评审结论 | — | ✓ | — | ✓ | ✓ |
| 修改评分 rubric | — | — | — | — | ✓ |
| 配置上线门禁 | — | — | — | — | ✓ |
| 冻结 / 发布测试集版本 | — | ✓ | — | — | ✓ |
| 导出摘要报告 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 导出 full trace / source 报告 | — | — | — | — | ✓ |

---

# 5. 核心概念

## 5.1 Eval Run（评测运行）

一次完整的评测任务。

| 属性 | 说明 |
|------|------|
| eval_run_id | 唯一标识 |
| agent_version | 被评测的 Agent 版本（关联 commit sha） |
| dataset_id + dataset_version | 使用的测试集及其版本 |
| corpus_snapshot_id | 本次 run 绑定的 notebook/source/parser/chunker 冻结快照 |
| config_snapshot | 本次 run 的完整配置快照（retrieval 策略、rewrite 策略、prompt version、scope policy 等） |
| status | pending → running → completed / failed |
| aggregate_metrics | 聚合指标（详见下方） |
| created_at / finished_at | 时间戳 |

### aggregate_metrics 详细定义

每次 Eval Run 完成后，系统自动计算以下聚合指标，覆盖评测体系的全部五个层级：

#### Summary. 总览聚合指标（Summary Metrics）

| 指标 | 计算方式 | 含义 |
|------|---------|------|
| `run_quality_score` | 按 9.3 的风险加权公式聚合所有 case_total_score | 统一用于 dashboard、compare 和 gate 的 run 级主分数 |
| `pass_rate` | pass case / total planned case | 整体通过率，不允许通过缩小分母抬高结果 |
| `high_risk_pass_rate` | 高风险 case 中 pass 的占比 | 高风险样本的通过情况 |
| `execution_success_rate` | completed case / total planned case | 实际执行成功率，用于暴露 `error/timeout` |
| `anchor_invalid_count` | 解析失败的 anchor case 数量 | 用于识别数据集失效和 gate 阻断 |
| `error_count` | 运行状态为 `error` 的 case 数量 | 用于观察执行稳定性 |
| `timeout_count` | 运行状态为 `timeout` 的 case 数量 | 用于观察长尾失败和资源问题 |

#### A. 检索层聚合指标（Retrieval Metrics）

| 指标 | 计算方式 | 含义 |
|------|---------|------|
| `recall@5` | 所有 case 中 evidence_anchors 解析到的相关 chunk 出现在 top-5 检索结果的比例均值 | 衡量检索系统在前 5 条结果中找到相关证据的能力 |
| `recall@10` | 所有 case 中 evidence_anchors 解析到的相关 chunk 出现在 top-10 检索结果的比例均值 | 衡量检索系统在前 10 条结果中找到相关证据的能力 |
| `mrr` | 每条 case 中第一个相关 evidence anchor 对应 chunk 在检索结果中的排名倒数均值 | 衡量相关证据在排序中的位置靠前程度 |
| `ndcg@10` | 基于 evidence_anchors 在 top-10 中的位置和相关性计算 discounted cumulative gain 的归一化均值 | 衡量检索排序的整体质量，考虑位置权重 |
| `hit_rate@k` | 至少有一个相关 evidence anchor 对应 chunk 出现在 top-K 中的 case 占比 | 衡量检索的最低保障能力（至少能命中一条） |
| `rewrite_uplift` | 开启 rewrite 前后 recall@5 的差值 | 量化 query rewrite 对检索质量的提升幅度 |
| `rerank_uplift` | 开启 rerank 前后 MRR 的差值 | 量化 reranking 对排序质量的提升幅度 |

#### B. 引用层聚合指标（Citation Metrics）

| 指标 | 计算方式 | 含义 |
|------|---------|------|
| `citation_support_rate` | 所有 citation 中被判定为"支撑对应陈述"的比例 | 衡量引用是否真正为答案提供证据支持 |
| `wrong_citation_rate` | 所有 citation 中被判定为"不支撑陈述"的比例 | 衡量错误引用的占比 |
| `missing_citation_rate` | 需要引用但未引用的陈述占所有需要引用的陈述的比例 | 衡量应该引用却遗漏的情况 |
| `over_citation_rate` | 引用了无关 chunk 的 citation 占总 citation 的比例 | 衡量过度引用的噪声程度 |
| `citation_coverage` | 回答中带有 citation 的陈述占总陈述数的比例 | 衡量整体引用覆盖程度 |

#### C. 答案层聚合指标（Answer Quality Metrics）

| 指标 | 计算方式 | 含义 |
|------|---------|------|
| `groundedness_avg` | 所有 case 的 groundedness 评分均值（1-5） | 衡量回答内容是否有检索证据支撑 |
| `faithfulness_avg` | 所有 case 的 faithfulness 评分均值（1-5） | 衡量回答是否忠实于证据，未引入幻觉 |
| `completeness_avg` | 所有 case 的 completeness 评分均值（1-5） | 衡量回答是否完整覆盖了问题的核心要点 |
| `hallucination_rate` | groundedness 评分 ≤ 2 的 case 占比 | 衡量严重幻觉的发生比例 |
| `abstain_correctness` | out-of-scope 问题中正确拒答的比例 | 衡量系统在信息不足时的诚实度 |

#### D. Scope 判定聚合指标（Scope Metrics）

| 指标 | 计算方式 | 含义 |
|------|---------|------|
| `scope_classification_accuracy` | scope 判定与 `scope_label` 一致的 case 占比 | 衡量 scope in/out/borderline 判定的整体准确性 |
| `false_in_scope_rate` | 实际 out-of-scope 但被判定为 in-scope 的比例 | 衡量错误回答不该回答的问题的频率 |
| `false_out_of_scope_rate` | 实际 in-scope 但被判定为 out-of-scope 的比例 | 衡量错误拒答能回答的问题的频率 |
| `scope_safe_answer_rate` | in-scope 正确回答 且 out-of-scope 正确拒答的综合比例 | 衡量 scope 边界控制的整体安全度 |

#### E. 系统层聚合指标（System Performance Metrics）

| 指标 | 计算方式 | 含义 |
|------|---------|------|
| `p50_latency_ms` | 所有 case 端到端延迟的中位数 | 衡量典型响应速度 |
| `p95_latency_ms` | 所有 case 端到端延迟的 P95 | 衡量长尾延迟 |
| `first_token_latency_ms` | 所有 case 首 token 延迟的均值 | 衡量用户感知到的首字响应速度 |
| `total_token_count` | 所有 case 的 input + output token 总量 | 衡量 token 消耗 |
| `cost_per_case_avg` | 所有 case 的平均成本（基于 token 用量和模型单价估算） | 衡量单次问答的平均成本 |
| `pass_rate` | 所有 case 中 pass 的占比（分母为 total planned case） | 衡量整体通过率 |
| `badcase_count` | 所有 case 中 fail 的数量 | 衡量失败样本的绝对数量 |

#### 聚合指标存储格式

```json
{
  "summary": {
    "run_quality_score": 4.28,
    "pass_rate": 0.88,
    "high_risk_pass_rate": 0.92,
    "execution_success_rate": 0.99,
    "anchor_invalid_count": 0,
    "error_count": 1,
    "timeout_count": 0
  },
  "retrieval": {
    "recall_at_5": 0.78,
    "recall_at_10": 0.89,
    "mrr": 0.72,
    "ndcg_at_10": 0.75,
    "hit_rate_at_5": 0.85,
    "rewrite_uplift": 0.06,
    "rerank_uplift": 0.04
  },
  "citation": {
    "support_rate": 0.91,
    "wrong_citation_rate": 0.04,
    "missing_citation_rate": 0.08,
    "over_citation_rate": 0.03,
    "citation_coverage": 0.87
  },
  "answer": {
    "groundedness_avg": 4.2,
    "faithfulness_avg": 4.4,
    "completeness_avg": 3.9,
    "hallucination_rate": 0.03,
    "abstain_correctness": 0.85
  },
  "scope": {
    "classification_accuracy": 0.88,
    "false_in_scope_rate": 0.05,
    "false_out_of_scope_rate": 0.07,
    "scope_safe_answer_rate": 0.90
  },
  "system": {
    "p50_latency_ms": 1200,
    "p95_latency_ms": 2800,
    "first_token_latency_ms": 450,
    "total_token_count": 125000,
    "cost_per_case_avg": 0.008,
    "badcase_count": 6
  }
}
```

## 5.2 Test Case（测试样本）

单条测试数据。

| 属性 | 说明 |
|------|------|
| case_id | 唯一标识 |
| notebook_id | 关联的 notebook |
| user_input | 用户问题 |
| context | 对话上下文（可选，用于 follow-up 类问题） |
| task_type | factoid / summarization / comparison / multi-hop / follow-up / tool-use / out-of-scope |
| difficulty | easy / medium / hard |
| score_profile | `rag_answer` / `scope_only` / `custom_agent` |
| source_revision_ids | 该 case 依赖的 source 冻结版本 |
| evidence_anchors | 稳定证据锚点列表，作为 retrieval/citation 的 ground truth source of truth |
| expected_output | 期望回答（参考答案） |
| must_have_points | 回答中必须包含的关键点 |
| must_not_have_points | 回答中不应出现的内容 |
| scope_label | in-scope / borderline / out-of-scope |
| failure_tags | 预期可能触发的失败类型标签 |
| labels | 自定义标签（用于筛选） |
| data_source | 人工构造 / badcase 回流 / 合成数据 |

## 5.3 Eval Run Item（单条评测结果）

一次 Eval Run 中某个 Test Case 的评测输出。

| 属性 | 说明 |
|------|------|
| run_item_id | 唯一标识 |
| eval_run_id | 关联的 Eval Run |
| case_id | 关联的 Test Case |
| pass / fail | 是否通过 |
| score | 总分 |
| dimension_scores | 分维度得分（retrieval_score、citation_score、answer_score） |
| failure_tags | 失败原因标签 |
| trace | 完整执行过程日志 |
| auto_score | 自动评分结果（LLM Judge / 规则） |
| human_score | 人工评审结果（如有） |
| reviewer_comment | 评审员评论 |

## 5.4 Trace（执行过程日志）

记录 Agent 处理单条 Test Case 的完整链路。

```
Trace 结构：
├── query_rewrite_step
│   ├── original_query
│   ├── rewritten_query
│   ├── intent_type
│   ├── scope_decision
│   └── rewrite_latency_ms
├── retrieval_step
│   ├── search_queries[]
│   ├── retrieved_chunks[] (id, score, source_id, content_snippet)
│   ├── retrieval_latency_ms
│   └── retrieval_config (top_k, bm25_weight, vector_weight)
├── rerank_step (可选)
│   ├── reranked_chunks[]
│   ├── rerank_latency_ms
│   └── rerank_model
├── evidence_pack_step
│   ├── selected_chunks[]
│   ├── assembled_prompt
│   └── prompt_version
├── generation_step
│   ├── answer_blocks[] (text, citation_chunk_ids)
│   ├── generation_latency_ms
│   ├── token_count (input / output)
│   └── model_name
└── scope_check_step (可选)
    ├── scope_decision
    ├── scope_in_topics[]
    └── scope_out_topics[]
```

## 5.5 Scoring Rubric（评分规则）

定义每个维度的评分标准和打分依据。

| 维度 | 评分范围 | 评分依据 |
|------|---------|---------|
| retrieval_score | 0-5 | 基于 evidence_anchors 解析后的 recall@k / MRR / hit rate 计算 |
| citation_support | 1-5 | 每个 citation 是否真正支撑对应陈述 |
| citation_correctness | 1-5 | 是否存在错引、漏引、过度引用 |
| groundedness | 1-5 | 答案内容是否可由检索证据支持 |
| faithfulness | 1-5 | 是否引入证据外推断或幻觉 |
| completeness | 1-5 | 是否回答到问题核心点 |
| scope_correctness | 0-5 | scope 判定及回答/拒答行为是否正确 |

## 5.6 Config Snapshot（配置快照）

每次 Eval Run 冻结的完整配置，确保可复现。

```json
{
  "commit_sha": "abc1234",
  "workflow_version": "rag-pipeline.v3",
  "prompt_version": "v2.3",
  "judge_prompt_version": "v1.0",
  "corpus_snapshot_id": "corp_2026_04_14_001",
  "notebook_corpus_digest": "sha256:4c6f...",
  "parser_version": "parser.v2",
  "chunker_version": "chunker.semantic.v3",
  "rewrite_strategy": "snapshot-aware",
  "retrieval_config": {
    "top_k": 20,
    "bm25_weight": 0.4,
    "vector_weight": 0.6,
    "rrf_k": 60
  },
  "rerank_enabled": true,
  "rerank_model": "cross-encoder-v1",
  "scope_policy": "soft",
  "embedding_model": "text-embedding-3-small",
  "chat_model": "gpt-4o-mini"
}
```

## 5.7 Dataset Version（测试集版本）

测试集的版本化管理。

| 属性 | 说明 |
|------|------|
| dataset_id | 测试集标识 |
| version | 版本号（如 v1.0, v1.1） |
| status | draft → active → frozen → archived |
| exposure_mode | visible / blind_holdout |
| case_count | 样本数量 |
| frozen_at | 冻结时间 |
| frozen_by | 冻结操作人 |

**规则：**

- 正式评测只能使用 `frozen` 状态的测试集版本。
- `blind_holdout` 数据集默认只对 QA / Reviewer / Admin 解盲，Engineer 视角下不展示 `expected_output`、`must_have_points` 和最终人工裁决细节。

## 5.8 实体关系总览

```
Dataset 1───* DatasetVersion 1───* TestCase
                                          │
EvalConfig 1───* EvalRun 1───* EvalRunItem ─┘
                     │                │
                     │                ├── Trace
                     │                │    ├── RewriteStep
                     │                │    ├── RetrievalStep
                     │                │    ├── RerankStep
                     │                │    ├── GenerationStep
                     │                │    └── ScopeCheckStep
                     │                │
                     │                ├── AutoScore (LLM Judge / Rule)
                     │                ├── HumanScore (Reviewer)
                     │                └── ReviewerComment
                     │
                     └── ConfigSnapshot
```

---

# 6. 评测流程闭环

## 6.1 端到端流程总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                        评测流程闭环                                   │
│                                                                     │
│  ① 准备阶段        ② 执行阶段         ③ 评审阶段       ④ 收尾阶段   │
│  ┌─────────┐      ┌──────────┐      ┌──────────┐     ┌──────────┐ │
│  │ 冻结    │      │ 批量执行  │      │ 自动评分  │     │ 生成报告  │ │
│  │ 测试集  │ ───→ │ Agent    │ ───→ │          │ ───→ │          │ │
│  │         │      │          │      │ 人工复核  │     │ 标记     │ │
│  │ 配置    │      │ 收集     │      │          │     │ badcase  │ │
│  │ 快照    │      │ trace    │      │ 分歧裁决  │     │ 回流测试集│ │
│  └─────────┘      └──────────┘      └──────────┘     └──────────┘ │
│       ↑                                                │           │
│       │                ⑤ 持续优化                      │           │
│       │    ┌──────────────────────────────────┐        │           │
│       └────│ 优化 retrieval/rewrite/prompt    │ ←──────┘           │
│            │ 重新发起评测                      │                    │
│            └──────────────────────────────────┘                    │
└─────────────────────────────────────────────────────────────────────┘
```

## 6.2 阶段 1：准备

| 步骤 | 操作 | 产出 | 责任人 |
|------|------|------|--------|
| 1.1 | 选择或创建测试集 | dataset_id + version | QA / Engineer |
| 1.2 | 冻结测试集版本（状态改为 frozen） | frozen dataset version | QA / Admin |
| 1.3 | 冻结 corpus snapshot（source revision / parser / chunker / notebook digest） | corpus_snapshot_id | Engineer / System |
| 1.4 | 选择评测对象（Agent 版本 / commit sha） | agent_version | Engineer |
| 1.5 | 配置评测参数（rewrite、retrieval、rerank、scope 策略） | config_snapshot | Engineer |
| 1.6 | 选择 baseline run 与 compare 模式 | baseline_run_id + compare_plan | Engineer / QA |
| 1.7 | 确认评测环境一致（embedding model、LLM model 可用） | 环境就绪确认 | Engineer |
| 1.8 | 创建 Eval Run 记录，关联以上所有信息 | eval_run_id | System |

**前置检查清单：**

- [ ] 测试集版本已冻结
- [ ] corpus snapshot 已冻结并记录 digest
- [ ] 评分 rubric 版本已确认
- [ ] Agent 配置已明确并记录
- [ ] baseline run 已选择或明确无 baseline
- [ ] LLM / Embedding 服务状态可用
- [ ] 日志链路可追踪

## 6.3 阶段 2：执行

| 步骤 | 操作 | 产出 |
|------|------|------|
| 2.1 | 逐条读取 TestCase | user_input + context |
| 2.2 | 执行 query rewrite（按配置决定策略） | rewritten_query + rewrite metadata |
| 2.3 | 执行 retrieval（hybrid BM25 + Vector + RRF） | retrieved_chunks[] + scores |
| 2.4 | 可选执行 reranking | reranked_chunks[] |
| 2.5 | 可选执行 scope check | scope_decision |
| 2.6 | 组装 evidence pack + prompt | assembled_prompt |
| 2.7 | 调用 LLM 生成回答 | answer_blocks[] + citation_chunk_ids |
| 2.8 | 记录完整 trace 到 EvalRunItem | trace (5.4 定义的结构) |
| 2.9 | 重复 2.1-2.8 直到全量 case 执行完毕 | 全部 run_items |
| 2.10 | 计算聚合指标 aggregate_metrics | 5.1 定义的 JSON 结构 |

**执行策略：**

- **有界并发**：默认并发 5-10 个 case，按 notebook / model 配额限流，避免单次 run 拖垮上游依赖。
- **断点续跑**：run_item 级别幂等，失败或中断后支持仅重跑 `error / timeout / selected slice`。
- **失败处理**：单条 case 执行失败不阻塞后续 case，记录失败原因到 run_item，标记为 `error`。
- **超时控制**：单条 case 超时阈值可配置（默认 30s），超时标记为 `timeout`，支持单 case 重试上限。
- **进度追踪**：实时更新 Eval Run 的进度（completed_count / total_count / error_count / retry_count）。
- **正式 run 资格**：`Gold Set / Release Holdout Set` 生成正式 Gate Report 前，必须满足 `anchor_invalid_count = 0`；否则 run 仅可保存为诊断结果，不得作为发布依据。

## 6.4 阶段 3：评审

| 步骤 | 操作 | 产出 | 责任人 |
|------|------|------|--------|
| 3.1 | 规则评分（检索 / scope / system 原子指标） | retrieval_metrics + scope_outcome + system_metrics | System (自动) |
| 3.2 | 评分聚合（Judge + 规则） | citation_score_case + answer_score_case + scope_score_case + case_total_score | System (自动) |
| 3.3 | 计算聚合指标（5.1 定义的完整结构） | aggregate_metrics | System (自动) |
| 3.4 | 系统自动标记失败 case 和退化 case | badcase 列表 | System (自动) |
| 3.5 | 按 review queue 规则聚合强制复核样本与分层抽样样本 | review queue | System (自动) |
| 3.6 | Reviewer 人工打分 + 评论 | human_score + comments | Reviewer |
| 3.7 | 计算 LLM Judge 与人工评分的一致率 (Cohen's Kappa) | judge_calibration_report | System (自动) |
| 3.8 | 对分歧 case 做双人复核 + 最终裁决 | final_score | Reviewer + QA |

## 6.5 阶段 4：收尾

| 步骤 | 操作 | 产出 | 责任人 |
|------|------|------|--------|
| 4.1 | 生成评测报告（含 aggregate_metrics + 失败分布 + 版本对比） | eval_report | System (自动) |
| 4.2 | 标记 badcase 并标注失败原因标签 | badcase_tags | Engineer / QA |
| 4.3 | 将 badcase 加入回归测试集（一键回流） | regression_set 更新 | QA |
| 4.4 | 与上次 baseline 做 diff 对比 | regression_analysis | Engineer |
| 4.5 | 给出评审结论 | Pass / Pass with Risk / Blocked / Need Fix + Re-run | QA + PM |
| 4.6 | 归档 Eval Run | eval_run status → completed | System |

## 6.6 阶段 5：持续优化（闭环）

```
badcase 回流 ───→ 补充测试集 ───→ 重新冻结版本
     ↑                                    │
     │              优化动作               ↓
修改 rewrite    修改 retrieval    修改 prompt    修改 scope
     │               │                │              │
     └───────────────┴────────────────┴──────────────┘
                          │
                     重新发起 Eval Run
                          │
                     对比前后结果
```

**闭环触发条件：**

| 触发方式 | 说明 | 场景 |
|---------|------|------|
| 手动触发 | 工程师主动发起 | 调参后验证 |
| PR 触发 | main 分支合并后自动运行 nightly eval | 持续回归 |
| 配置变更触发 | rewrite / retrieval / prompt / scope 策略变更后 | 变更验证 |
| 定时触发 | 每日 / 每周定时运行 | 稳定性监控 |

## 6.7 评审结论定义

| 结论 | 含义 | 后续动作 |
|------|------|---------|
| **Pass** | 所有指标达标，无高风险 badcase | 可以上线 |
| **Pass with Risk** | 核心指标达标，但存在非关键退化或延迟升高 | 可以上线，但需记录风险并安排下一轮优化 |
| **Blocked** | 存在高风险 badcase 或核心指标未达标 | 不可以上线，必须修复后重新评测 |
| **Need Fix + Re-run** | 发现评测配置错误或环境问题 | 修复问题后重新发起评测 |

---

# 7. 指标体系

## 7.1 指标分层架构

```
┌───────────────────────────────────────────────┐
│               一级指标（面向管理者/PM）          │
│   Pass Rate · Quality Score · Cost per Task    │
└──────────────────────┬────────────────────────┘
                       │
┌──────────────────────┴────────────────────────┐
│            二级指标（面向工程师归因）             │
│                                                │
│  ┌──────────┐ ┌──────────┐ ┌───────────────┐  │
│  │ 检索质量 │ │ 引用质量 │ │  答案质量     │  │
│  │ Recall@K │ │ Support  │ │ Groundedness  │  │
│  │ MRR      │ │ Wrong    │ │ Faithfulness  │  │
│  │ nDCG     │ │ Missing  │ │ Completeness  │  │
│  └──────────┘ └──────────┘ └───────────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌───────────────┐  │
│  │ Scope    │ │ 系统性能 │ │  优化收益     │  │
│  │ Accuracy │ │ Latency  │ │ Rewrite Δ     │  │
│  │ FPR/FNR  │ │ Cost     │ │ Rerank Δ      │  │
│  └──────────┘ └──────────┘ └───────────────┘  │
└──────────────────────┬────────────────────────┘
                       │
┌──────────────────────┴────────────────────────┐
│            三级指标（面向 root cause 定位）      │
│                                                │
│  按问题类型切片：fact / compare / multi-hop     │
│  按难度切片：easy / medium / hard               │
│  按模块切片：rewrite / retrieval / rerank / gen │
│  按 scope 切片：in-scope / out-of-scope         │
└───────────────────────────────────────────────┘
```

## 7.2 一级指标

面向管理者和 PM，回答"系统整体好不好"。

| 指标 | 定义 | 目标值 | 说明 |
|------|------|--------|------|
| **Pass Rate** | 通过 case / 总 case 数 | ≥ 88% | 最直观的整体质量指标 |
| **Run Quality Score** | 按风险权重聚合后的 run 级综合评分 | ≥ 4.0 / 5.0 | 统一主分数，定义见 9.3 |
| **Hallucination Rate** | groundedness ≤ 2 的 case 占比 | ≤ 3% | 最关键的风险指标 |
| **Cost per Task** | 平均每次问答的 token 成本 | — | 需与质量联合看，单独看无意义 |
| **P95 Latency** | 95% 的 case 在该延迟内完成 | ≤ 3s | 用户体验底线 |

## 7.3 二级指标

面向工程师，回答"哪个模块有问题"。

### 7.3.1 检索质量指标

| 指标 | 公式 | 目标值 | 适用场景 |
|------|------|--------|---------|
| Recall@5 | \|gold ∩ top5\| / \|gold\| 的均值 | ≥ 0.75 | 评估 top-5 召回能力 |
| Recall@10 | \|gold ∩ top10\| / \|gold\| 的均值 | ≥ 0.90 | 评估 top-10 召回能力 |
| MRR | Σ(1/rank_first_gold) / N | ≥ 0.80 | 评估首个相关结果的排序位置 |
| nDCG@10 | 归一化 DCG@10 的均值 | ≥ 0.75 | 评估排序整体质量 |
| Hit Rate@5 | 至少命中 1 条 gold 的 case 占比 | ≥ 0.90 | 评估最低召回保障 |

**按切片的二级指标：**

| 切片维度 | 指标 | 用途 |
|---------|------|------|
| 按 task_type | 每种类型的 recall@5 / MRR | 发现哪类问题检索最弱 |
| 按 difficulty | easy / medium / hard 的 recall@5 | 发现难度上升后检索退化程度 |
| 按 source_count | 1 source / 2-5 sources / 5+ 的 recall@5 | 发现多 source 场景的召回瓶颈 |

### 7.3.2 引用质量指标

| 指标 | 公式 | 目标值 | 适用场景 |
|------|------|--------|---------|
| Citation Support Rate | supported citations / total citations | ≥ 0.93 | 引用是否真正支撑陈述 |
| Wrong Citation Rate | unsupported citations / total citations | ≤ 0.05 | 错误引用占比 |
| Missing Citation Rate | uncited claims / total claims needing citation | ≤ 0.10 | 应引用但遗漏的比例 |
| Over-citation Rate | irrelevant citations / total citations | ≤ 0.05 | 过度引用噪声 |
| Citation Coverage | cited statements / total statements | ≥ 0.85 | 整体引用覆盖度 |

### 7.3.3 答案质量指标

| 指标 | 评分方式 | 目标值 | 适用场景 |
|------|---------|--------|---------|
| Groundedness | LLM Judge 1-5 + 人工校准 | ≥ 4.0 | 答案是否有证据支撑 |
| Faithfulness | LLM Judge 1-5 + 人工校准 | ≥ 4.2 | 是否忠实于证据 |
| Completeness | LLM Judge 1-5 + 人工校准 | ≥ 3.8 | 是否完整回答问题 |
| Abstain Correctness | 正确拒答 / out-of-scope 总数 | ≥ 0.85 | 信息不足时是否诚实拒答 |

### 7.3.4 Scope 判定指标

| 指标 | 公式 | 目标值 | 适用场景 |
|------|------|--------|---------|
| Scope Classification Accuracy | 正确判定 / 总判定 | ≥ 0.88 | scope 判定整体准确性 |
| False In-Scope Rate | 错误判定为 in-scope / 实际 out-of-scope | ≤ 0.05 | 不该回答却回答了 |
| False Out-of-Scope Rate | 错误判定为 out-of-scope / 实际 in-scope | ≤ 0.08 | 该回答却拒答了 |
| Scope Safe Answer Rate | 正确处理 / 总数 | ≥ 0.90 | scope 边界整体安全度 |

### 7.3.5 系统性能指标

| 指标 | 公式 | 目标值 | 说明 |
|------|------|--------|------|
| P50 Latency | 中位数端到端延迟 | ≤ 1.5s | 典型响应速度 |
| P95 Latency | 95 分位端到端延迟 | ≤ 3.0s | 长尾延迟 |
| First Token Latency | 首 token 延迟均值 | ≤ 0.8s | 首字响应速度 |
| Token Count per Case | 平均每条 case 的 token 用量 | — | 成本估算基础 |
| Cost per Case | 平均每条 case 的 API 成本 | — | 与质量联合看 |

### 7.3.6 优化收益指标

| 指标 | 计算方式 | 用途 |
|------|---------|------|
| Rewrite Uplift | 开启 rewrite 后 recall@5 - 关闭时 recall@5 | 量化 rewrite 的检索提升 |
| Rerank Uplift | 开启 rerank 后 MRR - 关闭时 MRR | 量化 rerank 的排序提升 |
| Snapshot-aware Rewrite Uplift | snapshot-aware rewrite 后 recall@5 - chat-history rewrite 后 recall@5 | 量化 snapshot 上下文对 rewrite 的增量收益 |
| Graph Expansion Uplift | 开启 graph expansion 后 recall@10 - 关闭时 recall@10 | 量化 graph 扩展的召回增量 |

## 7.4 三级指标

面向 root cause 定位，回答"具体为什么失败"。

### 7.4.1 失败归因标签体系

每条失败的 EvalRunItem 必须打上至少一个失败归因标签：

| 归因域 | 标签 | 含义 | 优化方向 |
|--------|------|------|---------|
| **Rewrite** | `rewrite_too_broad` | 改写后查询过于宽泛，导致无关结果 | 收紧 rewrite prompt |
| | `rewrite_too_narrow` | 改写后查询过于狭窄，遗漏相关 chunk | 放宽 rewrite 策略 |
| | `rewrite_intent_shift` | 改写后意图偏移 | 优化 intent 识别 |
| **Retrieval** | `retrieval_miss` | gold chunk 未出现在 top-K | 调整 top-K / 权重 / embedding |
| | `retrieval_noise` | 大量无关 chunk 混入 top-K | 调整 BM25/Vector 权重比 |
| | `retrieval_scope_error` | 检索结果超出 notebook scope | 检查 scope filter |
| **Rerank** | `rerank_degradation` | rerank 后相关 chunk 排名反而下降 | 检查 rerank 模型 |
| **Citation** | `wrong_citation` | 引用了不支撑陈述的 chunk | 优化 citation binding prompt |
| | `citation_missing` | 应引用但未引用 | 优化 citation prompt |
| | `citation_over` | 引用了无关 chunk | 优化 citation 判定阈值 |
| **Answer** | `hallucination` | 回答包含证据外内容 | 优化 generation prompt + retrieval |
| | `incomplete` | 回答不完整 | 检查 evidence pack + prompt |
| | `unfaithful` | 回答与证据矛盾 | 优化 faithfulness 约束 |
| | `wrong_abstain` | 应回答却拒答 | 检查 scope / evidence 策略 |
| | `wrong_answer` | 应拒答却回答了 | 收紧 scope filter |
| **System** | `timeout` | 执行超时 | 优化延迟 / 增加超时阈值 |
| | `llm_error` | LLM 调用失败 | 检查 API 状态 / 重试 |

### 7.4.2 按切片的归因统计

系统自动按以下维度聚合失败归因标签：

| 切片维度 | 示例问题 |
|---------|---------|
| 按 task_type | "multi-hop 类问题的失败归因中 retrieval_miss 占比最高" |
| 按 difficulty | "hard 难度的失败归因中 rewrite_too_narrow 占比显著高于 easy" |
| 按 source_count_bucket | "多 source 场景的 citation_missing 率显著高于单 source" |
| 按 scope_label | "borderline 问题的 scope 判定错误占 scope 错误的 70%" |

## 7.5 指标设计原则

每个指标必须满足以下条件：

| 原则 | 要求 | 验证方式 |
|------|------|---------|
| **定义清晰** | 任何人看到指标名都知道在衡量什么 | 指标有公式和含义说明 |
| **可计算** | 能通过系统数据自动算出 | 有明确的输入字段和计算逻辑 |
| **可复现** | 同样输入、同样配置下结果一致 | 多次 run 结果在合理误差范围内 |
| **可对比** | 跨版本、跨配置可横向比较 | 指标定义和计算方式在版本间一致 |
| **可归因** | 指标变化能定位到具体模块 | 有失败归因标签体系支撑 |
| **可操作** | 看到指标后知道下一步改什么 | 每个归因标签有对应的优化方向 |

## 7.6 实验矩阵

系统支持按以下实验轴组合评测，产出交叉对比报告：

| 实验轴 | 选项 |
|--------|------|
| Rewrite Strategy | none / chat-history / snapshot-aware |
| Retrieval Strategy | vector-only / hybrid(BM25+Vector) / hybrid+rerank |
| Scope Policy | none / soft-bias / hard-filter |
| Task Type | fact / compare / summarization / multi-hop / follow-up / out-of-scope |

**输出矩阵示例：**

| Rewrite | Retrieval | Scope | Recall@5 | MRR | Groundedness | P95 Latency |
|---------|-----------|-------|----------|-----|-------------|-------------|
| none | vector-only | none | 0.62 | 0.55 | 3.6 | 1.1s |
| chat-history | hybrid | soft | 0.74 | 0.68 | 4.0 | 1.4s |
| snapshot-aware | hybrid+rerank | hard | **0.82** | **0.78** | **4.3** | 2.1s |
| snapshot-aware | hybrid+rerank | soft | 0.81 | 0.77 | 4.2 | 2.0s |

通过矩阵可以判断 Pareto 最优组合（如最后一行的 soft scope 可能是比 hard scope 更好的 trade-off）。

## 7.7 版本对比与统计规则

为避免 compare 结论流于主观，版本对比必须遵循以下规则：

| 规则 | 定义 |
|------|------|
| baseline 选择 | 默认使用“相同 dataset_version + 相同 corpus_snapshot 类型下，最近一次 `Pass/Pass with Risk` 的正式 run”作为 baseline |
| 配对比较 | compare 必须基于同一批 case 的 paired diff，不允许跨不同样本集合直接比较 |
| 分值指标 | `run_quality_score`、`answer_score` 等连续指标使用 paired bootstrap（默认 1000 次）估计 95% CI |
| 比例指标 | `pass_rate`、`hallucination_rate`、`wrong_citation_rate` 等比例指标使用 Wilson CI 或 bootstrap 估计区间 |
| 显著回归判定 | 当 `delta < 0` 且 95% CI 不跨 0，或超过预设 regression budget 时，标记为显著回归 |
| 样本量不足 | 当有效样本 `< 30` 或关键切片样本不足时，仅给出方向性提示，不输出显著性结论 |
| 随机性控制 | 对存在 LLM 随机性的 compare，可配置固定 seed 或重复运行 3 次取均值 |

**默认 regression budget（正式 gate 适用）：**

| 预算项 | 默认值 | 说明 |
|-------|-------|------|
| overall significant regression cases | `<= max(3, ceil(0.03 * N))` | `N` 为本次 compare 的 paired case 数 |
| high-risk significant regression cases | `0` | 高风险样本不允许显著回归 |
| safety_sensitive significant regression cases | `0` | 安全敏感样本不允许显著回归 |
| `run_quality_score` delta budget | `>= -0.05` | 允许轻微波动，但不能出现显著下滑 |
| `hallucination_rate` delta budget | `<= +0.5pp` | 防止质量提升掩盖幻觉增加 |
| `wrong_citation_rate` delta budget | `<= +1.0pp` | 防止引用质量退化 |
| `p95_latency_ms` delta budget | `<= +10%` | 与 12.1 的门禁一致 |

**预算超标后的处理规则：**

- 任一 `high-risk / safety_sensitive` slice 出现显著回归，默认直接 `Blocked`。
- 若仅普通样本超预算，可进入 `Pass with Risk` 或 `Need Fix + Re-run`，但必须记录 `override_reason`、责任人、修复版本和关闭时间。
- 未关闭的风险豁免不得跨两个正式发布版本延续。

**Compare 输出要求：**

- 同时展示 point estimate、delta、95% CI、样本量和是否显著。
- 对 high-risk slice 单独展示 compare 结果，避免整体均值掩盖高风险退化。

---

# 8. 测试集标准

## 8.1 测试集分层体系

| 层级 | 规模建议 | 用途 | 运行频率 | 质量要求 | 变更权限 |
|------|---------|------|---------|---------|---------|
| Smoke Set | 20-50 条 | 核心主链路和关键风险点校验 | 每次提交 / 每次 PR | 覆盖主路径，允许快速迭代 | Engineer / QA |
| Dev Set | 50-150 条 | 日常调参与可见题集优化 | 日常 / 每周 | 可见、可快速补题，但需标注来源 | Engineer / QA |
| Regression Set | 100-500 条 | 版本候选回归、防止老问题复发 | 每次候选版本、重大配置变更后 | 覆盖主要能力模块和常见场景 | QA |
| Gold Set | 50-100 条 | 正式评审、人工校准、质量看板基准 | 每周 / 发布前 | 高质量人工审核、稳定、不轻易改动 | QA / Admin |
| Release Holdout Set | 30-80 条 | 真正的上线门禁与盲测验证 | 发布前 | 默认对 Engineer 不解盲，定期轮换 | Admin |
| Challenge Set | 持续增长 | 边界、对抗、冲突证据、超长上下文 | 按需 / 每周 | 强调极端场景和失败归因 | Engineer / QA |

**两条数据集建设路线：**

- `Public Showcase Set`：对外展示和简历演示，覆盖技术文档、PRD、多来源主题材料，规模 30-50 条。
- `Internal Pilot Set`：面向企业落地验证，覆盖周报、会议纪要、SOP、FAQ 等内部知识库材料。

**门禁原则：**

- `Dev Set` 和 `Gold Set` 可用于调参与分析，但**不能单独作为最终发布门禁**。
- `Release Holdout Set` 必须作为正式发布前的 blind holdout，避免对可见 Gold Set 的长期过拟合。

## 8.2 测试集分类维度

### 8.2.1 按任务类型

| 类型 | 定义 | 示例 | 占比建议 |
|------|------|------|---------|
| factoid | 事实型单点问答 | “NotebookLX 使用什么向量数据库？” | 25%-30% |
| summarization | 总结概括型 | “总结这篇文档的核心观点” | 10%-15% |
| comparison | 对比分析型 | “方案 A 和方案 B 的主要区别是什么？” | 10%-15% |
| multi-hop | 跨文档 / 多步推理 | “结合所有文档，项目总预算是多少？” | 15%-20% |
| follow-up | 基于上下文的追问 | “那它的局限性呢？” | 10%-15% |
| tool-use | 需要工具或结构化动作的场景 | “请找出状态异常的 source 并给出修复建议” | 0%-10%（平台化预留） |
| out-of-scope | 超出知识库范围 | “今天天气怎么样？” | 10% |
| edge-case | 异常 / 冲突 / 不完整输入 | 空 query、歧义 query、矛盾证据 | 5% |

### 8.2.2 按能力模块

| 模块 | 核心检查点 | 典型失败 |
|------|-----------|---------|
| intent | 意图理解、澄清是否必要 | rewrite_intent_shift |
| context_compression | source snapshot、section snapshot、notebook synopsis、scope in/out | snapshot_hallucination |
| retrieval | query rewrite、hybrid retrieval、rerank、graph expansion | retrieval_miss / retrieval_noise |
| citation | 证据支撑度、错引、漏引、过引 | wrong_citation / citation_missing |
| answer | groundedness、faithfulness、completeness、拒答 | hallucination / incomplete |
| system | 延迟、成本、稳定性、trace 完整性 | timeout / llm_error |

### 8.2.3 按难度

| 等级 | 定义 | 特征 | 占比建议 |
|------|------|------|---------|
| easy | 单 source、单 chunk 即可回答 | 直接匹配，无需推理 | 30% |
| medium | 单 source 多 chunk 或简单跨 source | 需要拼接或轻量对比 | 40% |
| hard | 跨 source 多 chunk + 综合推理 | 需要多步推理、证据整合 | 25% |
| extreme | 对抗、冲突、边界条件 | 故意构造的极端场景 | 5% |

### 8.2.4 按风险等级

| 风险等级 | 说明 | 示例 |
|---------|------|------|
| low | 普通事实和总结类问题 | 基础问答 |
| medium | 容易出现遗漏或错引的问题 | 对比、跨段总结 |
| high | 一旦答错会误导用户的场景 | 范围判断、关键结论引用 |
| safety_sensitive | 涉及明显风险或敏感决策 | 需要谨慎拒答或给出边界提示 |

### 8.2.5 按来源

| 来源 | 说明 | 用途 |
|------|------|------|
| manual | 基于真实 notebook 内容手动标注 | 建立高质量 baseline |
| badcase | 线上反馈或评测失败 case 回流 | 回归防护 |
| synthetic | LLM 生成后再人工审核 | 快速扩覆盖面 |
| real_user | 脱敏后的真实 query | 贴近真实分布（远期） |

## 8.3 单条 TestCase Schema

```json
{
  "case_id": "uuid",
  "title": "多文档预算对比",
  "notebook_id": "nb_xxx",
  "dataset_layer": "regression",
  "task_type": "comparison",
  "score_profile": "rag_answer",
  "capability_tags": ["retrieval", "citation", "answer"],
  "user_input": "方案 A 和方案 B 的总预算差多少？",
  "context": [],
  "difficulty": "hard",
  "risk_level": "high",
  "scope_label": "in-scope",
  "gold_topics": ["预算", "方案对比"],
  "source_revision_ids": ["src_1@v7", "src_3@v5"],
  "evidence_anchors": [
    {
      "source_revision_id": "src_1@v7",
      "anchor_type": "page_span",
      "locator": {"page": 12, "start_char": 120, "end_char": 280},
      "text_hash": "sha256:aaa111"
    },
    {
      "source_revision_id": "src_3@v5",
      "anchor_type": "semantic_span",
      "locator": {"section_title": "预算明细", "quote": "总预算为 520 万元"},
      "text_hash": "sha256:bbb222"
    }
  ],
  "expected_abstain": false,
  "expected_behavior": "先对比两份文档的预算项，再给出差值并引用来源",
  "expected_output": "方案 A 总预算为 X，方案 B 为 Y，差值为 Z",
  "must_have_points": ["两个方案预算", "差值", "来源引用"],
  "must_not_have_points": ["编造第三个方案", "无证据结论"],
  "failure_tags": ["retrieval_miss", "citation_missing"],
  "labels": ["budget", "multi-source"],
  "source_count_bucket": "2-5",
  "needs_cross_source_reasoning": true,
  "needs_graph_expansion": false,
  "scoring_rubric_ref": "rubric.answer.v1",
  "data_source": "manual",
  "created_by": "qa_01",
  "reviewed_by": "reviewer_02",
  "version": 1,
  "status": "active"
}
```

**关键字段说明：**

| 字段 | 是否必填 | 用途 |
|------|---------|------|
| `notebook_id` | 是 | 保证评测在正确 scope 内执行 |
| `task_type` | 是 | 用于按问题类型切片统计 |
| `score_profile` | 是 | 明确本 case 使用哪套维度与权重，不允许运行时静默跳过维度 |
| `capability_tags` | 是 | 用于按模块归因和覆盖率检查 |
| `source_revision_ids` | 推荐 | 绑定稳定的 source 版本，避免知识源漂移 |
| `evidence_anchors` | out-of-scope 之外必填 | 检索与引用评测的 ground truth source of truth |
| `gold_topics` | 推荐 | 支撑 snapshot / graph / topic 扩展评测 |
| `scope_label` | 是 | scope 判定的 gold label |
| `expected_abstain` | 是 | 明确是否应该拒答 |
| `scoring_rubric_ref` | 是 | 绑定固定评分规则版本 |
| `needs_graph_expansion` | 推荐 | 标识 graph 扩展是否应该带来收益 |

**稳定性规则：**

- `evidence_anchors` 是测试集中的唯一 ground truth source of truth。
- `gold_chunk_ids` 如需展示，只作为运行时由 `evidence_anchors -> chunk` 解析得到的缓存字段，不允许反向写回测试集作为唯一真值。
- 若 source revision 不存在或 anchor 无法解析，case 必须标记为 `anchor_invalid`，不得静默跳过。
- `Gold Set / Release Holdout Set` 的正式 run 若出现 `anchor_invalid`，必须直接阻塞 gate，并触发数据集修复。

## 8.4 测试集质量标准

| 维度 | 定义 | 检查方式 |
|------|------|---------|
| 代表性 | 覆盖核心真实场景 | task_type、difficulty、risk_level 分布符合目标占比 |
| 多样性 | 避免同义重复样本堆高分数 | embedding 去重 + 人工复核 |
| 可判定性 | 有明确的通过标准和 ground truth | 必须存在可验证的 gold 或 rubric |
| 边界性 | 包含失败、冲突、超界、异常输入 | Challenge Set 维持最低占比 |
| 可维护性 | 样本能持续新增和冻结管理 | 支持导入、回流、版本冻结 |
| 可追溯性 | 能追溯样本来源和修改历史 | 保留 created_by / reviewed_by / version |
| 稳定性 | Gold Set 不随意变化 | 变更需审批并保留历史版本 |

## 8.5 测试集治理流程

### 8.5.1 新建与导入

```text
手动录入 / 批量导入 / badcase 回流
        ↓
字段完整性校验
        ↓
语义去重检测
        ↓
notebook / source / chunk 关联校验
        ↓
状态 = draft
        ↓
人工审核通过
        ↓
状态 = active
```

### 8.5.2 badcase 回流

```text
发现 badcase（线上反馈 / 评测失败 / reviewer 标记）
        ↓
补充 user_input / wrong_output / failure_tags
        ↓
标注 source_revision_ids / evidence_anchors / expected_behavior / expected_output
        ↓
一键加入 Regression Set
        ↓
下次评测自动检测是否回归
```

### 8.5.3 版本冻结与发布

| 状态 | 含义 | 允许操作 |
|------|------|---------|
| draft | 编辑中 | 可增删改 |
| active | 可被日常评测引用 | 可继续编辑，但需生成新版本 |
| frozen | 正式评测版本 | 不可编辑，只可运行 |
| archived | 历史版本 | 只读，不再参与默认流程 |

**治理规则：**

- 正式评测只能使用 `frozen` 状态的数据集版本。
- Gold Set 的冻结、解冻、删除必须由 Admin 审批。
- Release Holdout Set 默认 `exposure_mode=blind_holdout`，仅 QA / Reviewer / Admin 可解盲。
- 每次冻结都生成新版本号，历史版本永久保留。
- 回流 badcase 默认先进入 Regression Set，再评估是否升级进 Gold Set。
- 已泄漏或被频繁针对性优化的 holdout case 必须轮换或归档，不得长期复用。

## 8.6 覆盖率与健康度检查

| 指标 | 计算方式 | 目标值 |
|------|---------|-------|
| task_type 覆盖率 | 已覆盖类型数 / 总类型数 | 100% |
| capability_tags 覆盖率 | 已覆盖模块数 / 总模块数 | 100% |
| difficulty 覆盖率 | 已覆盖难度数 / 总难度数 | 100% |
| risk_level 覆盖率 | 已覆盖风险等级数 / 总风险等级数 | 100% |
| notebook 覆盖率 | 有样本的 notebook 数 / 目标 notebook 数 | ≥ 3 |
| scope_label 覆盖率 | 已覆盖 scope 类型数 / 总类型数 | 100% |
| 去重健康度 | 去重后样本数 / 原始样本数 | ≥ 90% |
| badcase 回流时效 | badcase 发现到进入回归集的中位时间 | ≤ 2 天 |
| holdout 泄漏率 | 被非授权角色查看 expected_output 的 holdout case / holdout 总 case | 0 |

## 8.7 Snapshot / Scope / Graph 专项样本要求

为支持后续的 context compression 和 graph-backed retrieval，测试集还需额外满足：

- 至少 20% 样本包含 `gold_topics`，用于验证 snapshot 与 topic 聚合质量。
- 至少 10% 样本标记 `needs_graph_expansion=true`，用于验证 graph 扩展收益与噪声。
- 至少 10% 样本为 `scope_label=out-of-scope`，用于验证拒答与 scope-safe answer rate。
- 至少 15% 样本为跨 source 推理，验证 notebook synopsis、section bias、graph relation path 的有效性。

---

# 9. 评分机制与评审体系

## 9.1 评分模式

| 模式 | 适用对象 | 典型指标 |
|------|---------|---------|
| Rule-based Scoring | 检索、scope、系统性能 | recall@k、MRR、scope correctness、latency |
| Match-based Scoring | 结构化输出和 must-have 检查 | JSON 字段完整性、关键点命中 |
| Reference-based Scoring | 有参考答案的问答 | must_have_points、expected_output 对齐 |
| LLM-as-a-Judge | 引用质量、答案质量、snapshot 质量 | groundedness、faithfulness、citation support |
| Human Review | 高风险和争议样本 | 双人复核、最终裁决 |
| Hybrid Scoring | 正式发布决策 | 自动评分 + 人工校准后的综合结论 |

## 9.2 自动评分链路

| 评分阶段 | 输入 | 输出 | 说明 |
|---------|------|------|------|
| Score Profile Router | case metadata + `score_profile` | applicable_dimensions + weight_profile | 决定本 case 哪些维度参与总分 |
| Retrieval Score | retrieved_chunks + evidence_anchors + corpus_snapshot | recall@k、MRR、hit rate | 先做 anchor 解析，再纯规则计算 |
| Scope Score | scope_decision + scope_label | scope_outcome + scope_score_case(0-5) | 纯规则计算 |
| Citation Judge | answer_blocks + citation_chunk_ids + evidence | support / unsupported / partial | LLM Judge + 规则校验 |
| Answer Judge | question + answer + evidence + reference | groundedness / faithfulness / completeness | LLM Judge |
| Snapshot Judge | source snapshot / notebook synopsis + gold_topics | summary coverage / hallucination / token adherence | LLM Judge + 规则 |
| System Score | latency、token、cost、error | system_score_case(0-5) + stability flags | 运行时直接采集 |

## 9.3 综合评分与通过判定

建议一期采用如下加权方式，二期支持按 agent 类型配置：

| 维度 | 权重 | 说明 |
|------|------|------|
| retrieval_score | 25% | RAG 系统地基，优先级最高 |
| citation_score | 20% | NotebookLX 的核心差异化能力 |
| answer_score | 25% | 端到端用户体验的核心体现 |
| scope_score | 15% | 企业知识库落地的关键安全边界 |
| system_score | 15% | 延迟、成本、稳定性三者平衡 |

**统一计分口径：**

0. `score_profile` 与维度适用性

不同类型 case 不允许通过“运行时临时跳过某个维度”来算分，必须在测试集里显式声明 `score_profile`：

| `score_profile` | 适用场景 | 参与维度 | 权重 |
|----------------|---------|---------|------|
| `rag_answer` | NotebookLX 当前主链路，有证据、有回答、有 citation | retrieval / citation / answer / scope / system | 25% / 20% / 25% / 15% / 15% |
| `scope_only` | out-of-scope、正确拒答、仅判断是否该答 | scope / system | 70% / 30% |
| `custom_agent` | 非 RAG Agent 或 tool-use/workflow 评测 | system + adapter 注册的 custom dimensions | 由 Adapter Registry 注册，权重总和必须为 100%，且 `system >= 10%` |

规则：

- `evidence_anchors` 不适用的 case 必须使用 `scope_only` 或 `custom_agent`，不得仍绑定 `rag_answer`。
- `tool-use` / `workflow` 类 case 在一期可进入平台，但只有注册了 `custom_agent` 的 scorer contract 后才能参与正式 gate。
- `N/A` 维度不得记 0 分，也不得在运行时静默忽略；必须通过 `score_profile` 预先声明并使用该 profile 的规范化权重。

1. `retrieval_score_case`

```text
hit_at_5_case = 1 if any resolved relevant evidence in top-5 else 0
recall_at_10_case = resolved_relevant_evidence_in_top10 / total_relevant_evidence
mrr_case = 1 / rank_first_relevant_evidence, else 0

retrieval_score_case =
5 * (0.50 * hit_at_5_case + 0.30 * recall_at_10_case + 0.20 * mrr_case)
```

2. `citation_score_case`

```text
citation_score_case =
5 * (
  0.50 * citation_support_rate_case +
  0.20 * (1 - wrong_citation_rate_case) +
  0.20 * (1 - missing_citation_rate_case) +
  0.10 * (1 - over_citation_rate_case)
)
```

3. `answer_score_case`

```text
answer_score_case =
0.40 * groundedness +
0.35 * faithfulness +
0.25 * completeness
```

4. `scope_score_case`

| 场景 | 分值 |
|------|------|
| 判定正确，且回答 / 拒答行为符合预期 | 5.0 |
| `borderline`，给出保守且带边界提示的回答 | 4.0 |
| `false_out_of_scope`，应答却拒答 | 2.0 |
| `false_in_scope` 或 `wrong_answer`，不应答却答了 | 0.0 |

5. `system_score_case`

```text
system_score_case =
5 * (
  0.50 * min(1, latency_budget_ms / total_latency_ms) +
  0.20 * min(1, first_token_budget_ms / first_token_latency_ms) +
  0.20 * success_flag +
  0.10 * min(1, cost_budget_per_case / estimated_cost)
)
```

6. `case_total_score`

```text
case_total_score =
Σ(profile_weight_i * dimension_score_i)
```

7. `run_quality_score`

```text
risk_weight(low=1.0, medium=1.2, high=1.5, safety_sensitive=2.0)

run_quality_score =
Σ(case_total_score * risk_weight) / Σ(risk_weight)
```

**通过规则：**

- 单 case 默认 `case_total_score >= 4.0/5.0` 且无高风险标签时记为 `pass`。
- 任一高风险标签命中 `hallucination`、`wrong_citation`、`wrong_answer` 时强制记为 `fail`。
- `error` 或 `timeout` 的 case 记 `case_total_score = 0` 且 `pass = fail`。
- `anchor_invalid` 的 case 不参与正式 gate 计分；若出现在 `Gold Set / Release Holdout Set` 正式 run 中，run 直接失去 gate 资格并标记为 `Blocked`。
- `run_quality_score` 是统一展示在 dashboard、compare、gate report 中的 run 级主分数。
- 发布门禁以 `run_quality_score + 高风险 case 通过率 + 阻塞条件` 共同决定，不以平均分单独决策。

## 9.4 LLM-as-a-Judge 设计要求

| 要求 | 具体规则 |
|------|---------|
| Prompt 固定版本化 | Judge prompt 必须带版本号，绑定到 Eval Run |
| 输出结构化 JSON | 评分、理由、失败标签、置信度必须结构化 |
| 理由可解释 | 至少说明“为什么扣分”，不能只给模糊总分 |
| 允许人工抽样复核 | 默认抽样 30-50 条，计算一致率 |
| 防止漂移 | 同一 Judge prompt 在固定样本上的历史分布要可比 |
| 结果可回放 | 可以从 run_item 还原 judge 输入与输出 |

**Judge 输出示例：**

```json
{
  "citation_support": 4,
  "groundedness": 4,
  "faithfulness": 5,
  "completeness": 3,
  "failure_tags": ["incomplete"],
  "confidence": 0.82,
  "rationale": "答案有证据支撑，但遗漏了方案 B 的一个关键差异点。"
}
```

## 9.5 人工评审机制

| 场景 | 动作 | 规则 |
|------|------|------|
| 高风险样本 | 必须人工复核 | hallucination、wrong_citation、scope 错误 |
| 回归样本 | 必须人工复核 | 相比 baseline 发生显著回归 |
| Judge 低置信度样本 | 进入 review queue | `confidence < 0.7` |
| 自动与人工分歧大 | 双人复核 | 评分差值 ≥ 2 分 |
| 争议 case | 最终裁决 | QA 或 Admin 给出 final_score |

**评审要求：**

- 支持 reviewer 评论、差异标注、最终裁决和历史回溯。
- 人工评审结果不覆盖自动评分原值，而是并存保存。
- 系统持续计算 Judge 与人工的一致率，推荐使用 `Cohen's Kappa`。
- review queue 组成规则：`全部高风险样本 + 全部显著回归样本 + 全部低置信度样本 + 分层抽样补足`。
- 分层抽样目标：`max(30, ceil(0.1 * 有效样本数))`，上限 50，按 `task_type / difficulty / risk_level` 保持分布。
- 复核完成条件：所有强制复核样本完成 + 抽样目标达成，方可生成正式 Gate Report。

## 9.6 Snapshot / Scope / Graph 专项评分

| 专项能力 | 评分项 | 说明 |
|---------|------|------|
| Source Snapshot | coverage、hallucination、token adherence | 是否覆盖核心主题、是否压缩得当 |
| Notebook Synopsis | topic coverage、scope clarity | 是否正确概括 notebook 的主题和边界 |
| Scope Decision | classification accuracy、false in/out rate | 是否做对回答或拒答决策 |
| Graph Expansion | uplift、precision、noise increase rate | 是否带来召回提升且不过度引入噪声 |

---

# 10. 工程落地与系统架构

## 10.1 平台化设计原则

虽然一期以 NotebookLX 为第一落地对象，但底层抽象按平台化设计：

- `Evaluation Object`：被评估对象，可是 Agent、Workflow、Prompt 策略、RAG 配置、Tool 组合。
- `Dataset`：统一定义测试样本、标签、版本和冻结状态。
- `Runner`：按 adapter 调用具体系统执行评测。
- `Scorer`：统一接收 trace、output、reference，产出自动评分。
- `Review`：承载人工评审、分歧裁决和审计记录。
- `Gate`：基于阈值规则和评审结论做发布判定。
- `Score Profile Registry`：统一声明不同对象类型的适用维度、权重和 scorer contract。

## 10.2 核心服务模块

| 模块 | 职责 | 首期状态 |
|------|------|---------|
| Dataset Service | 测试集管理、导入导出、版本冻结、去重 | P0 |
| Eval Config Service | 管理 run 配置、实验矩阵、配置快照 | P0 |
| Runner Service | 批量执行 Agent，采集输出和 trace | P0 |
| Scoring Service | 规则评分、Judge 评分、聚合计算 | P0 |
| Review Service | review queue、双人复核、最终裁决 | P1 |
| Report Service | 汇总报表、版本对比、趋势分析 | P1 |
| Gate Service | 发布门禁、阻塞条件、审批记录 | P1 |
| Adapter Registry | object_type、trace schema、score_profile、custom scorer hook | P1 |
| Adapter Layer | 接入 NotebookLX RAG、后续 Tool/Workflow Agent | P1-P2 |

## 10.2.1 Adapter / Scorer 最小契约

为支撑“首期先服务 NotebookLX，同时兼容 AI Agent 扩展”，所有 adapter 至少需要满足以下最小契约：

| 契约层 | 必须字段 / 能力 | 说明 |
|-------|----------------|------|
| Adapter Input | `object_type`、`user_input`、`context`、`dataset_case_id`、`config_snapshot_id` | 统一 runner 调用入口 |
| Adapter Output | `final_output`、`structured_artifacts`、`status`、`failure_tags` | 统一结果落库结构 |
| Trace Step | `step_id`、`step_type`、`status`、`started_at`、`ended_at`、`payload_ref` | 所有对象类型都必须能回放关键步骤 |
| Score Profile Binding | `score_profile` | 决定使用 `rag_answer`、`scope_only` 或 `custom_agent` |
| Custom Scorer Hook | `score_json`、`confidence`、`rationale` | `custom_agent` 必须返回 0-5 维度分和解释 |

约束：

- `rag_answer` 是 NotebookLX 首期默认 profile。
- `custom_agent` 必须在 Adapter Registry 中预注册维度名、权重和 gate eligibility，未注册对象不可进入正式 Release Holdout 门禁。
- 所有 profile 的维度分统一使用 `0-5` 量纲，避免 compare 时再做二次映射。

## 10.3 执行链路

```text
创建 Eval Run
    ↓
冻结并绑定 dataset_version + corpus_snapshot + config_snapshot
    ↓
Runner 批量执行 NotebookLX adapter
    ↓
采集 trace / output / latency / token / citation
    ↓
Scoring Service 进行规则评分 + Judge 评分
    ↓
生成 aggregate_metrics + regression diff
    ↓
Review Service 处理高风险和争议样本
    ↓
Gate Service 产出发布结论
    ↓
badcase 回流 Regression Set
```

## 10.4 数据存储模型

| 表名 | 作用 | 关键字段 |
|------|------|---------|
| `evaluation_object` | 定义被评测对象 | object_type、adapter_type、owner |
| `evaluation_dataset` | 测试集元信息 | dataset_name、layer、owner |
| `evaluation_dataset_version` | 测试集版本 | version、status、frozen_at |
| `evaluation_case` | 测试样本 | case_id、task_type、score_profile、risk_level、rubric_ref |
| `evaluation_evidence_anchor` | 稳定证据锚点 | source_revision_id、anchor_type、locator_json、text_hash |
| `evaluation_corpus_snapshot` | 冻结知识源与解析配置 | notebook_digest、parser_version、chunker_version |
| `evaluation_run` | 评测运行 | run_id、object_id、dataset_version_id、status |
| `evaluation_config_snapshot` | 运行配置快照 | commit_sha、prompt_version、retrieval_config |
| `evaluation_run_item` | 单 case 结果 | run_item_id、score_profile、status、score、pass_fail、failure_tags |
| `evaluation_trace_step` | 分步骤 trace | step_type、payload、latency_ms |
| `evaluation_metric_aggregate` | 聚合指标 | metric_group、metric_name、metric_value |
| `evaluation_auto_score` | 自动评分明细 | judge_version、score_json、confidence |
| `evaluation_review_record` | 人工评审记录 | reviewer_id、score_json、comment、final_flag |
| `evaluation_compare_report` | 版本对比结果 | baseline_run_id、compare_run_id、delta_json、significance_json |
| `evaluation_gate_decision` | 上线门禁结论 | verdict、reason、approved_by |
| `evaluation_badcase` | badcase 回流记录 | source_run_item_id、regression_dataset_version_id |

**平台化扩展预留：**

- 如 snapshot / graph 评测明细过于复杂，可按需拆出 `evaluation_snapshot_score`、`evaluation_graph_metric`。
- 如果未来引入在线抽样评测，可追加 `evaluation_online_sample` 与 `evaluation_feedback_event`。

## 10.5 版本化与可复现

每次 Eval Run 必须冻结以下版本信息：

- agent version / commit sha
- prompt version
- workflow version
- dataset version
- corpus snapshot / notebook digest
- parser version / chunker version / source revision 集合
- judge prompt version
- eval config version
- embedding model / chat model / rerank model 版本

**原则：**

- 同一 run 的输入、模型、配置、数据集都必须可回放。
- 未记录完整配置的 run 不可作为发布依据。
- 任何门禁结论都必须能追溯到具体的 dataset version 和 config snapshot。

## 10.6 与 NotebookLX 现有系统的集成点

| NotebookLX 模块 | Eval 侧接入点 | 需要采集的信息 |
|----------------|-------------|---------------|
| ingestion | snapshot / section / scope 产物 | parse 状态、chunk 数、snapshot 内容、source revision |
| retrieval | hybrid retrieval、rerank、graph expansion | top-k 结果、score、策略参数 |
| citation | two-layer citation binding | answer block、citation_chunk_ids |
| chat / generation | 最终回答和流式指标 | answer、first token latency、token 用量 |
| observability | 已有 timing / transparency 面板 | step latency、error type、trace id |

---

# 11. UI / UX 设计要求

## 11.1 设计目标

评测 UI 必须做到：

- 一眼看懂整体质量，而不是把用户扔进 JSON 墓地。
- 一步下钻到 badcase 和失败归因。
- 支持版本对比，而不是孤立地看一次 run。
- 让 reviewer 在 3-5 分钟内完成单 case 复核。

## 11.2 核心页面

| 页面 | 关键内容 | 关键动作 |
|------|---------|---------|
| Eval Run List | run 名称、版本、数据集、通过率、状态 | 发起、重跑、进入对比 |
| Overview Dashboard | 总分、各维度趋势、失败分布、成本/延迟 | 筛选、导出、标记回归 |
| Version Compare | A/B 指标差异、回归 case、改善 case、显著性提示 | 选择 baseline、保存新 baseline |
| Case Detail | 输入、输出、reference、自动评分、人工评分、trace | 评审、评论、标记 badcase |
| Dataset Manager | 分层、标签分布、去重结果、冻结版本 | 导入、编辑、冻结、回流 |
| Review Queue | 待复核样本、低置信度样本、争议样本 | 批量评审、双人复核 |
| Gate Report | 发布结论、门禁阈值、阻塞原因 | 审批、记录风险 |
| Run Status / Empty States | 运行中、部分失败、无 baseline、空列表、权限受限 | 重试、补基线、申请权限 |

## 11.3 Case Detail 页必备信息面板

| 面板 | 必须展示的信息 |
|------|---------------|
| Input & Context | user_input、历史上下文、notebook |
| Output & Reference | 最终回答、expected_output、must_have_points；对 Release Holdout 的 Engineer 视角默认遮罩答案锚点和标准答案 |
| Score Summary | 自动评分、人工评分、失败标签、置信度 |
| Trace Timeline | rewrite、retrieval、rerank、scope、generation 的时间线 |
| Evidence Panel | 检索 chunks、引用绑定、support 判定 |
| Scope Panel | scope_decision、scope in/out 依据 |
| Snapshot Panel | source snapshot、section snapshot、notebook synopsis |
| Graph Panel | relation path、是否触发 graph expansion、扩展结果质量 |

## 11.4 关键交互要求

- 支持按 `task_type`、`difficulty`、`risk_level`、`failure_tag`、`dataset_layer` 多维筛选。
- 支持一键加入回归集、一键标记误判、一键复制 trace / case JSON。
- 支持从 compare 页直接跳到回归 case 明细。
- 支持 reviewer 批注和差异高亮，不要求 reviewer 读完整原始 payload 才能判断。
- 对 `blind_holdout` case 支持 reviewer blind mode：先看输入、输出、证据和 rubric，再按权限解盲参考答案。
- 必须覆盖 `运行中 / 部分失败 / 无 baseline / 空列表 / 权限受限` 五类关键状态。

## 11.5 UX 原则

- 默认展示最重要信息，失败 case 优先曝光。
- 复杂 trace 默认折叠，重点步骤高亮。
- 图表必须支撑决策，不做装饰性可视化。
- 术语统一，避免把相同概念在不同页面用不同名字表示。

---

# 12. 上线门禁标准

## 12.1 建议门槛

| 指标 | 门槛 |
|------|------|
| Smoke Set 通过率 | `>= 95%` |
| Release Holdout Run Quality Score | `>= 4.2 / 5.0` |
| Release Holdout 高风险 case 通过率 | `>= 90%` |
| Release Holdout Execution Success Rate | `>= 99%` |
| Release Holdout Anchor Invalid Count | `= 0` |
| Hallucination Rate | `<= 2%` |
| Wrong Citation Rate | `<= 5%` |
| Scope Safe Answer Rate | `>= 90%` |
| P95 Latency 相对上版本涨幅 | `<= 10%` |
| 显著回归 case 数量 | `<= max(3, ceil(0.03 * N))`，且不得包含高风险/安全敏感显著回归 |

## 12.2 阻塞条件

出现以下任一情况必须阻塞上线：

- 核心主链路失败。
- 高风险 hallucination。
- 错引、伪造证据、错误 scope 回答。
- trace 缺失导致结果不可审计。
- `Gold Set / Release Holdout Set` 正式 run 出现任意 `anchor_invalid`。
- `Release Holdout Execution Success Rate < 99%`，或任一高风险样本发生 `error/timeout`。
- Release Holdout 未执行或已泄漏，导致门禁失去盲测意义。
- 回归 case 超阈值，且未有风险豁免记录。

## 12.3 发布决策流程

```text
完成 Gold Set + Release Holdout 评测
      ↓
系统自动生成 Gate Report
      ↓
QA 审核 badcase 与回归 diff
      ↓
PM / Admin 查看风险摘要
      ↓
输出 verdict：Pass / Pass with Risk / Blocked / Need Fix + Re-run
```

**治理要求：**

- `Pass with Risk` 必须附带风险描述、影响范围和计划修复时间。
- 人工 override 门禁结论必须记录审批人和理由。

---

# 13. 数据与埋点要求

## 13.1 必须采集的数据

| 类别 | 字段 |
|------|------|
| 请求标识 | request_id、trace_id、case_id、run_id |
| 版本信息 | agent_version、prompt_version、dataset_version、judge_version、corpus_snapshot_id、score_profile |
| 输入输出 | user_input、context、answer、reference、scope_decision |
| 检索链路 | search_queries、retrieved_chunks、reranked_chunks、scores |
| 引用链路 | answer_blocks、citation_chunk_ids、support_result |
| 性能成本 | latency per step、first_token_latency、token_count、estimated_cost |
| 评分结果 | auto_score、human_score、failure_tags、confidence、run_item_status、anchor_resolution_status |
| 审批审计 | reviewer_actions、gate_decision、override_reason、export_audit |

## 13.2 埋点原则

- 全链路可追踪：任何 aggregate 指标都能 drill down 到 run_item 和 trace。
- 字段语义明确：同一字段名在不同模块中语义一致。
- 敏感数据脱敏：导入真实用户 query 时必须先脱敏，source chunk、assembled prompt、review comment 也纳入脱敏范围。
- 支持离线分析：评测数据可导出为报表或离线查询表，但导出内容必须走权限与脱敏规则。

## 13.3 数据保留与审计

- Gold Set 相关 run 和 gate decision 永久保留。
- Release Holdout 相关 run、gate decision 和 compare report 永久保留。
- 非正式草稿 run 可按周期归档，但保留聚合指标。
- 所有 reviewer 和 gate override 操作必须写审计日志。

## 13.4 租户隔离与导出治理

- 评测数据默认按 notebook / workspace / tenant 做访问隔离，不允许跨租户查看 trace 和证据内容。
- `blind_holdout` 的标准答案、must-have points、人工裁决仅 QA / Reviewer / Admin 可见。
- 导出报告分为 `summary export` 和 `full export` 两级权限；`full export` 需要管理员授权并记录审计。
- 敏感 trace 默认遮罩原文片段，仅在具备源文档访问权限时可查看全文。

---

# 14. 权限与治理

## 14.1 角色治理原则

角色定义与操作权限矩阵以 `4.1` 和 `4.3` 为准，本节补充治理原则：

- Dataset 的冻结 / 解冻由 QA 或 Admin 发起，Gold Set 仅 Admin 可批准。
- Release Holdout Set 的创建、轮换、解盲和归档只允许 Admin 操作。
- Rubric 和 Judge Prompt 属于高风险配置，只允许 Admin 修改并发布版本。
- 发布门禁的最终 override 只能由 Admin 执行。
- Reviewer 可以修改人工评分，但不能修改原始自动评分结果。
- Engineer 可查看可见题集的 expected_output，但默认不能查看 blind holdout 的标准答案与 must-have points。

## 14.2 高风险操作审批

| 操作 | 审批要求 |
|------|---------|
| 冻结 / 解冻 Gold Set | Admin |
| 创建 / 解盲 / 轮换 Release Holdout Set | Admin |
| 修改 judge prompt | Admin + 记录变更说明 |
| 修改 gate 阈值 | Admin |
| Full export 含 trace / source 片段 | Admin + 审计记录 |
| 人工放行被阻塞版本 | Admin + 风险说明 |
| 删除历史评测数据 | 禁止直接删除，只允许归档 |

## 14.3 Blind Holdout 字段级可见性

| 字段 | Engineer | QA | Reviewer | PM | Admin |
|------|----------|----|----------|----|-------|
| `user_input` / `answer` / `trace` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `expected_output` | — | ✓ | 按需解盲 | — | ✓ |
| `must_have_points` | — | ✓ | 按需解盲 | — | ✓ |
| `manual_review_comments` | 摘要 | ✓ | ✓ | 摘要 | ✓ |
| `final_override_reason` | — | ✓ | — | 摘要 | ✓ |

---

# 15. 验收标准

## 15.1 产品验收

- 能完成从建集、跑测、评分、评审、报告、回流到门禁的闭环。
- 支持版本对比、badcase 回流和人工评审。
- 支持至少 1 个 NotebookLX adapter，且扩展点清晰。

## 15.2 工程验收

- Eval Run 可稳定执行，失败可重试。
- 配置、数据集、prompt、judge 全部可版本化追踪。
- corpus snapshot、source revision、parser/chunker 版本全部可追踪。
- 单 case 的 trace 完整，能回放核心步骤。
- 聚合指标和 run_item 之间可以双向追溯。

## 15.3 UX 验收

- reviewer 3 分钟内能定位 badcase 主要问题。
- 5 分钟内能完成单 case 复核并写评论。
- Overview 页能在 1 分钟内判断版本是否值得继续推进。
- blind holdout 在 Engineer 视角下不会泄漏标准答案，在 Reviewer 视角下可控解盲。

## 15.4 指标验收

- Retrieval / Citation / Answer / Scope / System 五类指标全部可计算并落库。
- Judge 与人工评分一致率达到目标线，推荐 `Cohen's Kappa >= 0.6`。
- Gate Report 至少包含门槛命中情况、回归 diff、风险摘要三部分。
- Compare Report 至少包含 baseline、delta、95% CI、样本量和显著性结论。

---

# 16. 分阶段实施计划

| 阶段 | 核心目标 | 交付物 | 退出条件 |
|------|---------|-------|---------|
| Phase 1 / P0 | 跑通最小闭环 | Smoke/Dev/Regression 数据集、Runner、规则评分、Judge v1、Overview 页 | 可完成 retrieval + citation + answer 的端到端评测 |
| Phase 2 / P1 | 形成工程化实验体系 | config snapshot、corpus snapshot、A/B compare、自动运行、review queue、CSV 导出 | 能做版本对比、Judge 校准和 badcase 回流 |
| Phase 3 / P2 | 贴近企业落地 | Release Holdout、scope/snapshot/graph 专项评测、Gate Report、风险治理 | 能支撑正式发布决策和企业知识库试点 |

**优先级建议：**

- 先做 `dataset + retrieval eval + citation eval + answer judge`。
- 再做 `版本对比 + 自动运行 + 人工评审 + corpus snapshot`。
- 最后做 `Release Holdout + snapshot / scope / graph 专项评测 + 发布门禁`。

---

# 17. 风险与缓解

| 风险 | 表现 | 缓解策略 |
|------|------|---------|
| Judge 漂移 | 同样样本不同时间打分波动大 | 固定 judge 版本，做抽样校准 |
| 测试集过拟合 | 指标越来越好但真实体验没提升 | 保持 badcase 回流，引入 Internal Pilot Set |
| Holdout 泄漏 | 工程侧提前看到标准答案或 must-have points | 使用 blind holdout、按权限解盲、定期轮换 |
| Anchor 漂移 | source 更新后 evidence anchor 无法稳定映射 | 冻结 source revision，失效 case 显式标记并修复 |
| Graph 扩展噪声 | recall 提升但 wrong citation 上升 | 同时观察 uplift 和 noise increase rate |
| 成本失控 | 评分过多依赖 LLM Judge | 分层抽样、缓存 judge 结果 |
| 评审成本过高 | reviewer 被大量低价值样本淹没 | 只复核高风险、低置信度和争议 case |
| trace 不完整 | 出现结果无法复盘 | 将 trace completeness 设为硬性门禁 |

---

# 18. 未来扩展方向

- 在线真实会话抽样评测。
- 自动 badcase 聚类与失败模式发现。
- 基于失败归因推荐新增测试样本。
- 不同模型 / Prompt / Workflow 的显著性分析。
- Tool-use Agent、Workflow Agent、多 Agent 协同链路的 adapter 扩展。
- 基于 graph relation path 的解释性可视化增强。

---

# 19. 附录：建议配套文档

为保证本 PRD 能真正指导工程落地，建议继续补齐以下文档：

| 文档 | 内容 |
|------|------|
| `docs/EVAL_METRICS_SPEC.md` | 指标定义、公式、输入输出、边界说明 |
| `docs/EVAL_DATASET_SPEC.md` | case schema、标签体系、去重规则、回流规则 |
| `docs/EVAL_REVIEWER_RUBRIC.md` | 人工评分标准、1/3/5 分定义、误判示例 |
| `docs/EVAL_UI_IA.md` | 页面结构、信息优先级、关键交互、状态流转 |

这些文档不是可选装饰，而是把 PRD 变成工程实施蓝图的必要补充。
