# EVALUATION_PRD Review Record - Round 2

> Review target: `docs/EVALUATION_PRD.md`
> Review date: `2026-04-14`
> Review mode: `pm-review-board`
> Follow-up: `docs/EVALUATION_PRD.md` has been revised after this review; this file preserves the round-2 findings for traceability and re-review.

---

# 1. 总体结论

**结论：不通过**

相较第一轮，统一评分、稳定证据锚点、`Release Holdout` 三个核心问题已基本补齐，但 PRD 仍有 2 个会直接导致实现歧义的阻断项：`N/A` 维度计分规则未闭合，`regression budget / 回归阈值` 仍未参数化。

---

# 2. 阻断项

| # | 问题 | 提出角色 | 风险 | 修改方向 |
|---|------|---------|------|---------|
| 1 | 评分体系仍未覆盖 `out-of-scope / abstain / tool-use` 等非适用维度 case，缺少 `N/A` 规则和权重归一化 | 产品、研发、测试 | 同一份 PRD 仍无法唯一推导全部 case 的 `case_total_score / run_quality_score` | 引入 `score_profile` 或 `applicable_dimensions`，明确定义 `rag_answer / scope_only / custom_agent` 等配置及权重规则 |
| 2 | `regression budget / 回归 case 超阈值` 仍是原则表述，没有默认值、风险分层和 override 关闭条件 | 产品、研发、测试、运营 | compare 与 gate 仍需要临场解释，无法直接编码实现 | 补齐 overall/high-risk/safety slice 的默认 budget、delta budget、override 审批和关闭条件 |

---

# 3. 重要项

| # | 问题 | 提出角色 | 风险 | 修改方向 |
|---|------|---------|------|---------|
| 1 | `anchor_invalid` 已定义，但官方 run 中的处理规则未闭合，存在通过排除无效样本抬高结果的空间 | 研发、测试、运营 | Gold / Holdout 的门禁可信度不足 | 明确 `pass_rate` 分母、`anchor_invalid_count` 指标、官方 run 的阻塞逻辑 |
| 2 | “面向 AI Agent 平台”的抽象仍偏声明式，非 RAG agent 没有最小 adapter / trace / scorer contract | 产品、研发 | 平台抽象无法真正指导后续扩展 | 增加 Adapter Registry、最小契约和 `custom_agent` scorer hook |
| 3 | 执行流程和评分规则仍残留旧口径，如 `retrieval_score (0/1)`、`Scope Score 0/1` 等 | 研发、测试 | 文档前后口径不一，容易造成实现分叉 | 全文统一为“原子指标 -> case score -> run score”的三层模型 |

---

# 4. 建议项

| # | 问题 | 提出角色 | 修改方向 |
|---|------|---------|---------|
| 1 | `wrong_citation / citation_wrong`、`scope_label / gold_scope_label` 等命名仍有少量残留不一致 | 产品、测试 | 统一 failure tag 和 gold field 命名 |
| 2 | blind holdout 字段级可见性建议单独成表，减少设计和实现阶段歧义 | 设计、法务 | 明确不同角色对 `expected_output / must_have_points / comments` 的可见范围 |

---

# 5. 通过条件

满足以下全部条件后，可进入复评：

1. 补齐 `N/A` 维度的评分配置，并对不同 case 类型形成唯一计分路径。
2. 将 `regression budget` 写成默认可执行规则，覆盖 overall、high-risk、safety slice 和 override。
3. 明确 `anchor_invalid / error / timeout` 在正式 gate 中的处理逻辑。
4. 为非 RAG agent 补齐最小 adapter / scorer contract。
5. 清理全文旧口径和命名残留。

---

# 6. 复评清单

| # | 修改项 | 对应问题 | 责任角色 | 复评标准 | 状态 |
|---|--------|---------|---------|---------|------|
| 1 | `N/A` 计分与 `score_profile` 规则 | 阻断项 #1 | 产品、研发、测试 | 任一 `out-of-scope / abstain / tool-use` case 都能唯一算出总分 | ⬜ 待修改 |
| 2 | `regression budget` 默认门禁规则 | 阻断项 #2 | 产品、研发、运营 | compare / gate 可直接编码实现，无空白阈值 | ⬜ 待修改 |
| 3 | 官方 run 的 `anchor_invalid / error / timeout` 规则 | 重要项 #1 | 研发、测试 | Gold / Holdout 出现失效样本时有确定 verdict | ⬜ 待修改 |
| 4 | AI Agent 平台最小契约 | 重要项 #2 | 产品、研发 | 非 RAG adapter 至少有 input、trace、scorer hook 标准接口 | ⬜ 待修改 |
| 5 | 清理旧口径与命名残留 | 重要项 #3、建议项 #1 | 产品、研发、测试 | 全文评分口径和术语一致 | ⬜ 待修改 |

---

# 7. 备注

- 本轮评审的核心变化是：大问题已基本收敛，剩下的是“规则收口”和“平台契约”。
- 修改优先级建议：先收口评分和门禁，再补平台契约，最后清理术语与 UI 权限细则。
