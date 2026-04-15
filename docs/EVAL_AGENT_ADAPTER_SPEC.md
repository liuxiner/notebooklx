# NotebookLX Evaluation Agent Adapter Spec

> Source of truth: `docs/EVALUATION_PRD.md`
> This document defines the adapter, trace, registry, and custom scorer contracts used by the Evaluation platform.

---

# 1. 目标与范围

本文件定义：

- Adapter Registry 契约
- Runner 与 adapter 的输入输出接口
- trace step 结构
- `score_profile` 绑定方式
- custom scorer hook
- 正式 gate eligibility 规则
- 表结构落点与实现清单

本文件不重复评分公式；评分与门禁公式以 `docs/EVAL_METRICS_SPEC.md` 为准。

---

# 2. 对象类型与阶段范围

## 2.1 一期支持

| object_type | 场景 | 默认 score_profile | gate eligibility |
|------------|------|-------------------|-----------------|
| `notebooklx_rag` | NotebookLX 检索 + 引用 + 回答主链路 | `rag_answer` | `true` |
| `notebooklx_scope` | 仅 scope 判定 / 正确拒答 | `scope_only` | `true` |

## 2.2 二期扩展

| object_type | 场景 | 默认 score_profile | gate eligibility |
|------------|------|-------------------|-----------------|
| `tool_use_agent` | 带工具调用的 agent | `custom_agent` | 注册后决定 |
| `workflow_agent` | 多步骤 workflow | `custom_agent` | 注册后决定 |

---

# 3. Adapter Registry

## 3.1 Registry 作用

Registry 是平台判断“这个对象如何跑、如何记 trace、如何计分、能否参与 gate”的唯一入口。

## 3.2 Registry Schema

```json
{
  "object_type": "notebooklx_rag",
  "adapter_type": "python_callable",
  "adapter_version": "v1",
  "default_score_profile": "rag_answer",
  "trace_schema_version": "trace.v1",
  "gate_eligible": true,
  "custom_dimensions": [],
  "custom_dimension_weights": {},
  "required_capabilities": [
    "trace_steps",
    "latency_metrics",
    "failure_tags"
  ]
}
```

## 3.3 字段定义

| 字段 | 必填 | 说明 |
|------|------|------|
| `object_type` | 是 | 被评测对象类型 |
| `adapter_type` | 是 | adapter 执行方式，如 `python_callable / http_adapter` |
| `adapter_version` | 是 | adapter 自身版本 |
| `default_score_profile` | 是 | 默认 profile |
| `trace_schema_version` | 是 | trace step 协议版本 |
| `gate_eligible` | 是 | 是否允许进入正式 release gate |
| `custom_dimensions` | `custom_agent` 必填 | 自定义维度名列表 |
| `custom_dimension_weights` | `custom_agent` 必填 | 维度权重，和为 100% |
| `required_capabilities` | 是 | runner 校验所需能力 |

## 3.4 Registry 校验规则

- `custom_agent` 必须注册 `custom_dimensions`
- `custom_dimension_weights` 总和必须为 `100%`
- `system` 权重不得低于 `10%`
- `gate_eligible = false` 的对象只能参与实验和 compare，不能参与正式 Release Holdout gate

---

# 4. Adapter 输入契约

## 4.1 Runner -> Adapter 请求体

```json
{
  "run_id": "run_xxx",
  "run_item_id": "run_item_xxx",
  "object_type": "notebooklx_rag",
  "dataset_case_id": "case_xxx",
  "score_profile": "rag_answer",
  "user_input": "方案 A 和方案 B 的总预算差多少？",
  "context": [],
  "notebook_id": "nb_xxx",
  "config_snapshot_id": "config_xxx",
  "corpus_snapshot_id": "corp_xxx",
  "expected_capabilities": [
    "trace_steps",
    "latency_metrics",
    "failure_tags"
  ]
}
```

## 4.2 必填字段

| 字段 | 说明 |
|------|------|
| `run_id` | 运行主键 |
| `run_item_id` | 单 case 主键 |
| `object_type` | 用于路由 registry |
| `dataset_case_id` | 回写结果用 |
| `score_profile` | 评分 profile |
| `user_input` | 用户输入 |
| `context` | 上下文 |
| `config_snapshot_id` | 配置快照 |
| `corpus_snapshot_id` | corpus/source/parser/chunker 冻结快照 |

---

# 5. Adapter 输出契约

## 5.1 Adapter -> Runner 响应体

```json
{
  "run_item_id": "run_item_xxx",
  "status": "completed",
  "final_output": "方案 A 总预算为 X，方案 B 为 Y，差值为 Z",
  "structured_artifacts": {
    "search_queries": ["方案 A 预算", "方案 B 预算"],
    "retrieved_chunks": [],
    "reranked_chunks": [],
    "answer_blocks": [],
    "citation_chunk_ids": [],
    "scope_decision": "in-scope"
  },
  "failure_tags": [],
  "metrics": {
    "total_latency_ms": 1260,
    "first_token_latency_ms": 410,
    "estimated_cost": 0.012,
    "input_tokens": 2200,
    "output_tokens": 380
  },
  "trace_steps": []
}
```

## 5.2 顶层字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `run_item_id` | 是 | 对应请求 |
| `status` | 是 | `completed / error / timeout` |
| `final_output` | `completed` 时必填 | 最终输出 |
| `structured_artifacts` | 是 | 平台评分所需结构化结果 |
| `failure_tags` | 是 | 失败归因标签 |
| `metrics` | 是 | 延迟、token、成本 |
| `trace_steps` | 是 | 关键步骤时间线 |

## 5.3 NotebookLX RAG 必填 artifacts

| 字段 | 必填 | 用途 |
|------|------|------|
| `search_queries` | 是 | 评估 rewrite 与检索链路 |
| `retrieved_chunks` | 是 | 检索评分 |
| `reranked_chunks` | 启用 rerank 时必填 | rerank uplift |
| `answer_blocks` | 是 | citation judge |
| `citation_chunk_ids` | 是 | citation binding |
| `scope_decision` | 是 | scope 评分 |

## 5.4 Status 规则

| status | 说明 | 平台处理 |
|--------|------|---------|
| `completed` | 成功输出结果 | 进入评分链路 |
| `error` | 执行失败 | case 强制 fail |
| `timeout` | 执行超时 | case 强制 fail |

---

# 6. Trace Step 规范

## 6.1 通用 Trace Schema

```json
{
  "step_id": "step_xxx",
  "step_type": "retrieval",
  "status": "completed",
  "started_at": "2026-04-14T10:00:00Z",
  "ended_at": "2026-04-14T10:00:00.240Z",
  "latency_ms": 240,
  "payload_ref": "blob://trace/run_xxx/step_xxx.json"
}
```

## 6.2 通用字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `step_id` | 是 | step 主键 |
| `step_type` | 是 | 见下文枚举 |
| `status` | 是 | `completed / error / timeout / skipped` |
| `started_at` | 是 | 开始时间 |
| `ended_at` | 是 | 结束时间 |
| `latency_ms` | 是 | step 延迟 |
| `payload_ref` | 是 | 原始 payload 引用，不直接塞大 JSON |

## 6.3 标准 Step Type

| step_type | 适用对象 | 说明 |
|----------|---------|------|
| `rewrite` | RAG | query rewrite |
| `retrieval` | RAG | 检索 |
| `rerank` | RAG | rerank |
| `scope_check` | RAG / scope | scope 判定 |
| `generation` | RAG | 最终生成 |
| `snapshot_build` | RAG | snapshot / synopsis |
| `graph_expand` | RAG | graph expansion |
| `tool_call` | custom_agent | 工具调用 |
| `tool_result` | custom_agent | 工具结果 |
| `custom` | all | adapter 自定义步骤 |

## 6.4 Trace 最低要求

- 所有对象必须至少产出 1 条 trace step
- `gate_eligible=true` 的对象必须能回放关键主步骤
- 缺少 trace 的正式 run 不可进入 gate

---

# 7. Anchor Resolution 契约

## 7.1 适用对象

仅 `rag_answer` profile 需要执行 anchor resolution。

## 7.2 Runner 侧职责

Runner / scoring service 负责：

- 用 `evidence_anchors + corpus_snapshot` 执行 anchor-to-chunk 解析
- 写入 `anchor_resolution_status`
- 在 `evaluation_run_item` 或关联表中保存解析结果

## 7.3 Resolution 输出

```json
{
  "anchor_resolution_status": "resolved",
  "resolved_chunk_ids": ["chunk_1", "chunk_9"],
  "unresolved_anchor_ids": []
}
```

状态：

- `resolved`
- `anchor_invalid`
- `not_applicable`

---

# 8. Score Profile Binding

## 8.1 绑定顺序

1. 优先使用 `evaluation_case.score_profile`
2. 若缺失，回退到 Adapter Registry 的 `default_score_profile`
3. 正式 run 不允许 profile 缺失；若缺失则 run_item 记 `error`

## 8.2 Profile 与 Object Type 兼容矩阵

| object_type | 允许 profile |
|------------|-------------|
| `notebooklx_rag` | `rag_answer`, `scope_only` |
| `notebooklx_scope` | `scope_only` |
| `tool_use_agent` | `custom_agent` |
| `workflow_agent` | `custom_agent` |

---

# 9. Custom Scorer Hook

## 9.1 适用场景

- tool-use agent
- workflow agent
- 非 citation 中心的 agent

## 9.2 Hook 输出

```json
{
  "score_json": {
    "tool_correctness": 4.5,
    "plan_quality": 4.0,
    "system": 4.2
  },
  "confidence": 0.84,
  "rationale": "工具选择正确，但计划步骤仍有冗余。",
  "failure_tags": ["tool_extra_steps"]
}
```

## 9.3 Hook 规则

- 每个维度分范围必须为 `0-5`
- 维度名必须先在 Registry 注册
- `score_json` 中维度集合必须和注册表完全一致
- `confidence` 必须为 `0-1`
- 必须返回 `rationale`

## 9.4 Gate Eligibility

- 未注册 custom scorer 的对象：
  - 可运行
  - 可产出 trace
  - 不可进入正式 Release Holdout gate

---

# 10. Runner 集成流程

## 10.1 生命周期

```text
读取 evaluation_case
    ↓
解析 score_profile
    ↓
读取 Adapter Registry
    ↓
组装 adapter request
    ↓
调用 adapter
    ↓
写入 evaluation_run_item / trace_step / auto_score
    ↓
对 rag_answer 执行 anchor resolution
    ↓
进入 scoring / compare / gate
```

## 10.2 幂等与重试

- `run_item_id` 是 adapter 调用幂等键
- 支持重跑 `error / timeout / selected slice`
- 重跑不得覆盖历史 trace，必须追加新尝试记录或新版本引用

---

# 11. 表结构落点

## 11.1 已有表映射

| 表 | 关键新增/必用字段 |
|----|------------------|
| `evaluation_case` | `task_type`, `score_profile`, `risk_level`, `rubric_ref` |
| `evaluation_run_item` | `score_profile`, `status`, `score`, `pass_fail`, `failure_tags` |
| `evaluation_trace_step` | `step_type`, `payload`, `latency_ms`, `status` |
| `evaluation_auto_score` | `judge_version`, `score_json`, `confidence` |
| `evaluation_compare_report` | `delta_json`, `significance_json` |
| `evaluation_gate_decision` | `verdict`, `reason`, `approved_by` |

## 11.2 建议补充字段

如实现阶段发现现有表不足，优先补以下字段：

- `evaluation_object.gate_eligible`
- `evaluation_run_item.anchor_resolution_status`
- `evaluation_run_item.final_output_ref`
- `evaluation_trace_step.payload_ref`

---

# 12. NotebookLX RAG Adapter 最小实现清单

## 12.1 必须产出

- `search_queries`
- `retrieved_chunks`
- `answer_blocks`
- `citation_chunk_ids`
- `scope_decision`
- `total_latency_ms`
- `first_token_latency_ms`
- `estimated_cost`
- trace steps: `rewrite / retrieval / scope_check / generation`

## 12.2 可选产出

- `reranked_chunks`
- `snapshot_build`
- `graph_expand`

## 12.3 不通过条件

以下任一成立，NotebookLX RAG adapter 不得标记为 gate eligible：

- 缺少 `score_profile`
- 缺少 `retrieved_chunks`
- 缺少 `scope_decision`
- 缺少关键 trace
- 无法关联 `corpus_snapshot_id`

---

# 13. 实现检查清单

## 13.1 Adapter 侧

- Registry 有 `object_type -> score_profile` 映射
- Adapter 输入输出结构固定
- Trace step 遵循统一 schema
- `payload_ref` 使用引用，不直接塞大对象
- `custom_agent` 有注册与校验

## 13.2 Platform 侧

- Runner 能按 registry 路由 adapter
- `score_profile` 进入持久化链路
- `gate_eligible` 生效
- 正式 gate 前完成 anchor resolution 和 trace completeness 检查

## 13.3 不可妥协项

- 不允许未注册的 `custom_agent` 直接接入正式 gate
- 不允许缺 trace 的对象进入 gate
- 不允许 adapter 自己决定是否跳过某个评分维度
