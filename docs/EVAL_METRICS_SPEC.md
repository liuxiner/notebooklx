# NotebookLX Evaluation Metrics Spec

> Source of truth: `docs/EVALUATION_PRD.md`
> This document operationalizes the scoring, compare, and gate rules from the PRD into implementation-level contracts.

---

# 1. 目标与范围

本文件定义 Evaluation 平台中的评分、聚合、版本对比、回归预算与发布门禁规则，目标是让研发可以直接实现：

- 单 case 评分
- run 级聚合指标
- compare 统计结论
- gate verdict 产出
- Gate Report / Compare Report 数据结构

本文件不定义 adapter 侧 trace 采集细节；该部分由 `docs/EVAL_AGENT_ADAPTER_SPEC.md` 负责。

---

# 2. 术语与口径

## 2.1 核心术语

| 术语 | 定义 |
|------|------|
| planned case | 数据集版本中的全部 case，总分母 |
| completed case | 成功执行并产出可评分结果的 case |
| executable case | 仅用于诊断，不再作为通过率分母口径 |
| run item status | `completed / error / timeout` |
| anchor resolution status | `resolved / anchor_invalid / not_applicable` |
| effective score | 参与 gate 和 compare 的最终分数；若有最终人工裁决则以裁决为准，否则使用自动评分 |
| score profile | 决定某类 case 参与哪些维度计分的配置，取值 `rag_answer / scope_only / custom_agent` |

## 2.2 分母规则

统一规则：

- `pass_rate = pass_case_count / total_planned_case_count`
- `execution_success_rate = completed_case_count / total_planned_case_count`
- `high_risk_pass_rate = high_risk_pass_case_count / total_high_risk_case_count`

禁止使用“剔除无效样本后的剩余样本”作为默认分母来抬高指标。

---

# 3. Score Profile 规则

## 3.1 Profile 定义

| profile | 适用场景 | 参与维度 | 权重 |
|---------|---------|---------|------|
| `rag_answer` | NotebookLX RAG 主链路，有证据、有回答、有 citation | retrieval / citation / answer / scope / system | 25 / 20 / 25 / 15 / 15 |
| `scope_only` | out-of-scope、正确拒答、仅判断是否该答 | scope / system | 70 / 30 |
| `custom_agent` | tool-use / workflow / 非 RAG agent | system + custom dimensions | 由 Adapter Registry 注册 |

## 3.2 Profile 约束

- `rag_answer` 必须满足：
  - `evidence_anchors` 存在且非空
  - 允许输出 citation 或应输出 citation
- `scope_only` 必须满足：
  - `scope_label = out-of-scope` 或该 case 的目标仅为 scope 判定/拒答
  - `evidence_anchors` 可为空
- `custom_agent` 必须满足：
  - object 已在 Adapter Registry 中注册
  - 注册了 custom dimensions、权重、gate eligibility 和 custom scorer hook
- `N/A` 维度不得记 0 分，也不得在运行时静默忽略；必须通过 `score_profile` 预先声明。

## 3.3 Profile 到数据集字段

每个 `evaluation_case` 必须持久化：

- `task_type`
- `score_profile`
- `risk_level`
- `scope_label`

每个 `evaluation_run_item` 必须持久化：

- `score_profile`
- `status`
- `anchor_resolution_status`

---

# 4. 单 Case 评分

## 4.1 评分总则

- 所有最终维度分统一使用 `0-5` 量纲。
- case 级总分统一命名为 `case_total_score`。
- 若存在人工最终裁决 `final_score`，则对应维度的 `effective score = final_score`。
- 若无最终裁决，则 `effective score = auto_score`。

## 4.2 Retrieval Score

适用 profile：`rag_answer`

### 输入

- `retrieved_chunks`
- `resolved_evidence_anchors`
- `first_relevant_rank`

### 原子指标

```text
hit_at_5_case = 1 if any resolved relevant evidence in top-5 else 0
recall_at_10_case = resolved_relevant_evidence_in_top10 / total_resolved_relevant_evidence
mrr_case = 1 / rank_first_relevant_evidence, else 0
```

### 维度分

```text
retrieval_score_case =
5 * (
  0.50 * hit_at_5_case +
  0.30 * recall_at_10_case +
  0.20 * mrr_case
)
```

### 特殊规则

- 若 `anchor_resolution_status = anchor_invalid`，不计算 `retrieval_score_case`，该 case 失去正式 gate 资格。

## 4.3 Citation Score

适用 profile：`rag_answer`

### 输入

- `answer_blocks`
- `citation_chunk_ids`
- judge 输出的 citation support 判定

### Case 级原子统计

| 指标 | 计算方式 |
|------|---------|
| `citation_support_rate_case` | `supported_citation_count / max(1, total_citation_count)` |
| `wrong_citation_rate_case` | `wrong_citation_count / max(1, total_citation_count)` |
| `missing_citation_rate_case` | `missing_required_statement_count / max(1, required_statement_count)` |
| `over_citation_rate_case` | `over_citation_count / max(1, total_citation_count)` |

### 维度分

```text
citation_score_case =
5 * (
  0.50 * citation_support_rate_case +
  0.20 * (1 - wrong_citation_rate_case) +
  0.20 * (1 - missing_citation_rate_case) +
  0.10 * (1 - over_citation_rate_case)
)
```

### 特殊规则

- 若 `required_statement_count > 0` 且 `total_citation_count = 0`：
  - `citation_support_rate_case = 0`
  - `wrong_citation_rate_case = 0`
  - `missing_citation_rate_case = 1`
  - `over_citation_rate_case = 0`

## 4.4 Answer Score

适用 profile：`rag_answer`

### 输入

- `groundedness`
- `faithfulness`
- `completeness`

### 维度分

```text
answer_score_case =
0.40 * groundedness +
0.35 * faithfulness +
0.25 * completeness
```

## 4.5 Scope Score

适用 profile：`rag_answer / scope_only`

| 场景 | 分值 |
|------|------|
| 判定正确，且回答 / 拒答行为符合预期 | 5.0 |
| `borderline`，给出保守且带边界提示的回答 | 4.0 |
| `false_out_of_scope`，应答却拒答 | 2.0 |
| `false_in_scope` 或 `wrong_answer`，不应答却答了 | 0.0 |

## 4.6 System Score

适用 profile：全部

### 输入

- `total_latency_ms`
- `first_token_latency_ms`
- `estimated_cost`
- `success_flag`
- 系统预算：`latency_budget_ms / first_token_budget_ms / cost_budget_per_case`

### 维度分

```text
system_score_case =
5 * (
  0.50 * min(1, latency_budget_ms / total_latency_ms) +
  0.20 * min(1, first_token_budget_ms / first_token_latency_ms) +
  0.20 * success_flag +
  0.10 * min(1, cost_budget_per_case / estimated_cost)
)
```

### 特殊规则

- `error` 或 `timeout` 的 case：
  - `success_flag = 0`
  - `case_total_score = 0`
  - `pass = fail`

## 4.7 Custom Agent Score

适用 profile：`custom_agent`

要求：

- 由 adapter 注册自定义维度集合，维度名唯一。
- 每个维度分必须为 `0-5`。
- 权重总和必须为 `100%`。
- `system` 维度权重不得低于 `10%`。
- custom scorer 必须返回：
  - `score_json`
  - `confidence`
  - `rationale`
  - `failure_tags`

## 4.8 Case Total Score

### `rag_answer`

```text
case_total_score =
0.25 * retrieval_score_case +
0.20 * citation_score_case +
0.25 * answer_score_case +
0.15 * scope_score_case +
0.15 * system_score_case
```

### `scope_only`

```text
case_total_score =
0.70 * scope_score_case +
0.30 * system_score_case
```

### `custom_agent`

```text
case_total_score =
Σ(profile_weight_i * dimension_score_i)
```

## 4.9 单 Case 通过规则

- 默认 `case_total_score >= 4.0` 记为 `pass`
- 任一高风险标签命中以下之一，强制 `fail`
  - `hallucination`
  - `wrong_citation`
  - `wrong_answer`
- `error / timeout` 强制 `fail`
- `anchor_invalid` 不进入正式 gate 计分

---

# 5. Run 级聚合指标

## 5.1 Run Quality Score

```text
risk_weight(low=1.0, medium=1.2, high=1.5, safety_sensitive=2.0)

run_quality_score =
Σ(case_total_score * risk_weight) / Σ(risk_weight)
```

## 5.2 必须落库的 Summary 指标

| 指标 | 定义 |
|------|------|
| `run_quality_score` | 主分数 |
| `pass_rate` | `pass / total_planned_case` |
| `high_risk_pass_rate` | `high_risk_pass / total_high_risk_case` |
| `execution_success_rate` | `completed / total_planned_case` |
| `anchor_invalid_count` | anchor 解析失败 case 数 |
| `error_count` | `status=error` 数量 |
| `timeout_count` | `status=timeout` 数量 |

## 5.3 其他聚合指标

按 PRD 保持以下分组：

- retrieval: `recall@5 / recall@10 / mrr / ndcg@10 / hit_rate@k / rewrite_uplift / rerank_uplift`
- citation: `citation_support_rate / wrong_citation_rate / missing_citation_rate / over_citation_rate / citation_coverage`
- answer: `groundedness_avg / faithfulness_avg / completeness_avg / hallucination_rate / abstain_correctness`
- scope: `scope_classification_accuracy / false_in_scope_rate / false_out_of_scope_rate / scope_safe_answer_rate`
- system: `p50_latency_ms / p95_latency_ms / first_token_latency_ms / total_token_count / cost_per_case_avg / badcase_count`

---

# 6. Anchor / Status 处理规则

## 6.1 Anchor Resolution

| 状态 | 含义 | Gate 影响 |
|------|------|---------|
| `resolved` | anchor 成功映射到当前 corpus snapshot | 正常计分 |
| `anchor_invalid` | source revision 不存在或 locator 无法解析 | `Gold / Release Holdout` 正式 run 直接阻塞 |
| `not_applicable` | 当前 profile 不需要 anchor | 不阻塞 |

## 6.2 Run Item Status

| 状态 | 含义 | Gate 影响 |
|------|------|---------|
| `completed` | 执行完成 | 正常计分 |
| `error` | 执行失败 | case 强制 fail |
| `timeout` | 执行超时 | case 强制 fail |

## 6.3 正式 Run 资格

`Gold Set / Release Holdout Set` 生成正式 Gate Report 前必须满足：

- `anchor_invalid_count = 0`
- `execution_success_rate >= 99%`
- 任一高风险样本不得出现 `error / timeout`

否则该 run 仅可保存为诊断结果，不得作为发布依据。

---

# 7. Compare 规则

## 7.1 Baseline 选择

默认使用以下 baseline：

- 相同 `dataset_version`
- 相同 `corpus_snapshot` 类型
- 最近一次 `Pass / Pass with Risk` 的正式 run

## 7.2 配对比较

- compare 必须基于同一批 case 的 paired diff
- 不允许跨不同数据集直接比较
- 样本不足时仅输出方向性提示，不输出显著性结论

## 7.3 统计方法

| 指标类型 | 方法 |
|---------|------|
| 连续指标 | paired bootstrap，默认 1000 次，95% CI |
| 比例指标 | Wilson CI 或 bootstrap |

## 7.4 显著回归判定

以下任一满足则记为显著回归：

- `delta < 0` 且 95% CI 不跨 0
- 超过 regression budget

---

# 8. Regression Budget

## 8.1 默认预算

| 预算项 | 默认值 |
|-------|-------|
| overall significant regression cases | `<= max(3, ceil(0.03 * N))` |
| high-risk significant regression cases | `0` |
| safety_sensitive significant regression cases | `0` |
| `run_quality_score` delta budget | `>= -0.05` |
| `hallucination_rate` delta budget | `<= +0.5pp` |
| `wrong_citation_rate` delta budget | `<= +1.0pp` |
| `p95_latency_ms` delta budget | `<= +10%` |

`N` 为 compare 的 paired case 数。

## 8.2 超预算处理

- 任一 `high-risk / safety_sensitive` slice 出现显著回归：默认 `Blocked`
- 普通样本超预算：
  - 可判 `Pass with Risk`
  - 或 `Need Fix + Re-run`
- 风险豁免必须记录：
  - `override_reason`
  - 责任人
  - 修复版本
  - 关闭时间
- 未关闭的风险豁免不得跨两个正式发布版本延续

---

# 9. Gate 规则

## 9.1 建议门槛

| 指标 | 阈值 |
|------|------|
| `Smoke Set pass_rate` | `>= 95%` |
| `Release Holdout run_quality_score` | `>= 4.2` |
| `Release Holdout high_risk_pass_rate` | `>= 90%` |
| `Release Holdout execution_success_rate` | `>= 99%` |
| `Release Holdout anchor_invalid_count` | `= 0` |
| `hallucination_rate` | `<= 2%` |
| `wrong_citation_rate` | `<= 5%` |
| `scope_safe_answer_rate` | `>= 90%` |
| `p95_latency_ms` relative delta | `<= +10%` |
| significant regression cases | `<= max(3, ceil(0.03 * N))` 且高风险/安全敏感显著回归数为 `0` |

## 9.2 阻塞条件

存在以下任一即 `Blocked`：

- 核心主链路失败
- 高风险 hallucination
- 错引、伪造证据、错误 scope 回答
- trace 缺失导致不可审计
- `Gold / Release Holdout` 中任意 `anchor_invalid`
- `Release Holdout execution_success_rate < 99%`
- 任一高风险样本 `error / timeout`
- `Release Holdout` 未执行或已泄漏
- 显著回归超预算且无豁免

## 9.3 Verdict 决策

| verdict | 条件 |
|--------|------|
| `Pass` | 无阻塞项，全部门槛达标，无未关闭风险豁免 |
| `Pass with Risk` | 无阻塞项，核心门槛达标，但存在已审批的普通风险项 |
| `Need Fix + Re-run` | 无致命阻塞，但普通样本超预算或人工复核未完成 |
| `Blocked` | 任一阻塞条件成立 |

---

# 10. Report 数据结构

## 10.1 Compare Report

最少字段：

```json
{
  "baseline_run_id": "run_baseline_xxx",
  "compare_run_id": "run_candidate_xxx",
  "dataset_version_id": "dataset_v3",
  "paired_case_count": 120,
  "metric_deltas": [
    {
      "metric_name": "run_quality_score",
      "baseline": 4.31,
      "candidate": 4.28,
      "delta": -0.03,
      "ci95": [-0.06, -0.01],
      "significant": true,
      "budget_exceeded": false
    }
  ],
  "slice_regressions": [
    {
      "slice_name": "risk_level=high",
      "significant_regression_cases": 0
    }
  ]
}
```

## 10.2 Gate Report

最少字段：

```json
{
  "run_id": "run_candidate_xxx",
  "verdict": "Pass with Risk",
  "threshold_checks": {
    "run_quality_score": true,
    "high_risk_pass_rate": true,
    "execution_success_rate": true,
    "anchor_invalid_count": true
  },
  "blocking_conditions": [],
  "regression_budget_summary": {
    "overall_budget_exceeded": false,
    "high_risk_budget_exceeded": false
  },
  "override_reason": "p95 latency 上升但仍在预算内，批准带风险放行",
  "approved_by": "admin_01"
}
```

---

# 11. 实现检查清单

## 11.1 必做

- `score_profile` 进入数据集、run_item、report 主链
- `pass_rate` 分母使用 `total_planned_case`
- `anchor_invalid / error / timeout` 进入 Summary 指标
- compare 实现 paired diff + CI + regression budget
- gate 实现 verdict matrix 与 override 审计

## 11.2 不可妥协项

- 不允许在运行时临时跳过某个维度后直接算总分
- 不允许用 `total executable case` 作为默认通过率分母
- 不允许对 `Gold / Release Holdout` 中的 `anchor_invalid` 做静默忽略
- 不允许未注册的 `custom_agent` 进入正式 release gate
