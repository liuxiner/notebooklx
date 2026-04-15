# EVALUATION_PRD Review Record

> Review target: `docs/EVALUATION_PRD.md`
> Review date: `2026-04-14`
> Review mode: `pm-review-board`
> Follow-up: `docs/EVALUATION_PRD.md` has been revised after this review; this file preserves the original findings and remains the basis for re-review.

---

# 1. 总体结论

**结论：不通过**

当前 PRD 的结构、覆盖面和工程意识已经达到正式评审文档水平，但仍有 3 个阻断项会直接影响评分可执行性、回归可复现性和发布门禁可信度，不建议按当前版本直接进入开发。

---

# 2. 阻断项

| # | 问题 | 提出角色 | 风险 | 修改方向 |
|---|------|---------|------|---------|
| 1 | 评分体系未闭合，`case / run / gate` 三层判定口径不统一，文档同时出现 `0/1`、`1-5`、`87`、`4.2/5.0` 等多种分值表达 | 产品、研发、测试 | 无法直接实现统一评分与门禁逻辑 | 补齐统一计分公式、归一化规则、case 通过条件、run 质量分、gate 判定关系 |
| 2 | Ground truth 强绑定 `gold_chunk_ids`，当 parser / chunking / source 变更后历史 case 易失效，无法稳定跨版本回归 | 研发、测试 | frozen dataset 无法真正复跑，回归可信度不足 | 升级为稳定证据锚点模型，冻结 corpus/source 版本，并在运行时做 anchor-to-chunk 映射 |
| 3 | 发布门禁缺少 blind holdout / release holdout 机制，Gold Set 容易被工程团队反向优化 | 产品、测试、运营 | 门禁分数逐渐失真，存在“刷题式优化”风险 | 增加对工程侧默认隐藏的 Release Holdout Set，并定义解盲、轮换、泄漏失效机制 |

---

# 3. 重要项

| # | 问题 | 提出角色 | 风险 | 修改方向 |
|---|------|---------|------|---------|
| 1 | 执行策略写死“串行执行”，无法支撑回归集、多实验矩阵和版本 compare 的实际规模 | 研发、运营 | 评测时长和成本失控 | 改为有界并发、断点续跑、按切片局部重跑 |
| 2 | PRD 承诺“统计显著性提示”，但没有 baseline 选择、配对比较、最小样本量和波动处理规则 | 产品、研发、测试 | compare 结论不可用 | 补齐 compare 统计规则、CI/显著性定义、baseline 选择逻辑 |
| 3 | 人工复核规则不一致，一处写随机抽样，一处写高风险必须复核，但没有定义 review queue 组成 | 测试、运营 | review 流程不可执行 | 定义强制复核、低置信度、分层抽样和退出条件 |
| 4 | 敏感数据治理不足，仅提到真实 query 脱敏，未覆盖 source chunk、trace、导出和租户边界 | 法务/合规、运营、研发 | 数据合规和访问控制风险 | 增加 RBAC、tenant scope、导出脱敏、敏感 trace 遮罩和审计规则 |

---

# 4. 建议项

| # | 问题 | 提出角色 | 修改方向 |
|---|------|---------|---------|
| 1 | 术语和状态机不完全统一，如 `question_type` / `task_type` 混用，`Dataset Version` 状态定义前后不一致 | 产品、研发、测试 | 统一命名字典、状态机和字段口径 |
| 2 | UI 页面定义了主页面，但缺少运行中、部分失败、无 baseline、空列表、权限受限等关键状态 | 设计、测试 | 补充状态页、空态、权限态和 reviewer 去偏展示要求 |

---

# 5. 通过条件

满足以下全部条件后，可进入复评：

1. 补齐统一计分公式、归一化规则和 Gate 逻辑。
2. 将 `gold_chunk_ids` 升级为稳定证据锚点，并冻结 corpus/source 版本。
3. 增加 blind holdout / release holdout 机制，避免 visible gold 被长期过拟合。
4. 明确 compare 统计方法、review queue 规则、并发执行策略和敏感数据治理。

---

# 6. 复评清单

| # | 修改项 | 对应问题 | 责任角色 | 复评标准 | 状态 |
|---|--------|---------|---------|---------|------|
| 1 | 统一评分与门禁公式 | 阻断项 #1 | 产品、研发、测试 | 文档可直接指导实现 `case / run / gate` 三层评分 | ⬜ 待修改 |
| 2 | 稳定证据锚点与 corpus 版本冻结 | 阻断项 #2 | 研发、测试 | parser / chunking 变更后，历史 frozen case 仍可复跑或明确失效 | ⬜ 待修改 |
| 3 | Release Holdout Set 机制 | 阻断项 #3 | 产品、测试、运营 | 发布门禁不再依赖工程侧完全可见的数据集 | ⬜ 待修改 |
| 4 | Compare / Review / Runner 规则补齐 | 重要项 #1-#3 | 研发、测试 | compare 可解释、review 可执行、运行时长可控 | ⬜ 待修改 |
| 5 | 敏感数据与权限治理补齐 | 重要项 #4 | 法务、研发、运营 | trace、导出、租户边界满足最小权限和审计要求 | ⬜ 待修改 |

---

# 7. 备注

- 本次评审认为 `docs/EVALUATION_PRD.md` 的问题不在“内容太少”，而在若干关键定义没有闭环。
- 修改建议应优先落在 PRD 主文档中，其次再拆分到配套 spec 文档。
