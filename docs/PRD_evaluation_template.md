# AI Agent Evaluation PRD 大纲与要求

## 1. 文档基础信息
### 1.1 文档标题

**AI Agent Evaluation System PRD**

### 1.2 文档目标

定义一套用于评估 AI Agent 能力的产品与工程体系，覆盖：

* 离线评测
* 在线评测
* 人工评审
* 自动化回归
* 测试集管理
* UI/UX 评审体验
* 结果可解释与可追踪
* 支持工程上线、质量门禁、版本对比与持续优化

### 1.3 适用范围

适用于以下 Agent 类型：

* Chat Agent
* RAG Agent
* Tool-use Agent
* Workflow Agent
* Multi-step / Multi-agent Agent

### 1.4 核心目标

系统必须支持：

1. **评价 Agent 是否“好用”**
2. **评价 Agent 是否“可上线”**
3. **评价 Agent 哪一步出了问题**
4. **评价新版本是否优于旧版本**
5. **评价结果是否能反向指导 Prompt / Workflow / RAG / Tool 调优**

---

# 2. 背景与问题定义

## 2.1 背景

AI Agent 的效果不是单一模型输出质量问题，而是一个系统性问题，涉及：

* 用户输入理解
* 意图识别
* 规划与决策
* 工具调用
* 外部知识检索
* 结果整合
* 最终输出表达
* 交互体验与纠错能力

传统模型评测方法无法完整反映 Agent 的真实表现。

## 2.2 当前痛点

常见问题包括：

* 只有主观“感觉不错”，没有标准
* 测试 case 零散，缺乏结构化分类
* 评测只看最终答案，不看中间过程
* 没有失败归因，无法定位是 Prompt、Tool、RAG 还是 Workflow 问题
* UI 只展示一个分数，无法支撑分析
* 没有版本对比，优化效果无法证明
* 测试集质量低，覆盖不全，重复严重
* 线上 badcase 无法快速沉淀成回归集

---

# 3. 产品目标

## 3.1 业务目标

建立统一 AI Agent 评估平台，支持：

* 新版本上线前质量验收
* 回归测试与持续评估
* 研发/测试/产品共同对齐质量标准
* 将 badcase 快速转为标准测试样本
* 给招聘/项目展示提供体系化亮点

## 3.2 用户目标

### 面向研发

* 快速知道哪个模块退化
* 能看 trace 和每一步评分
* 能做版本对比与 root cause 分析

### 面向测试

* 有可复用测试集
* 有明确评审标准
* 能批量执行与复查
* 能沉淀标准 badcase

### 面向产品/设计

* 能看最终用户体验质量
* 能看 Agent 是否“有帮助”“可信”“易纠错”
* 能看交互是否自然、是否解释清楚

### 面向管理者

* 有统一质量指标
* 有上线门槛
* 有版本趋势图
* 有问题分布与风险面板

---

# 4. 非目标

明确不做这些，省得人类又开始无限膨胀需求：

* 不做通用模型训练平台
* 不做底层 LLM Benchmark 全替代
* 不直接替代日志平台/APM
* 不做全自动“绝对准确”裁判系统
* 不承诺所有任务都能用单一指标衡量

---

# 5. 关键概念定义

## 5.1 Evaluation Object

被评估对象，可以是：

* 某个 Agent
* 某个 Workflow
* 某个版本
* 某个 Prompt 策略
* 某个 RAG 配置
* 某个 Tool 组合

## 5.2 Eval Run

一次完整评测任务，包含：

* 评测目标对象
* 测试集
* 评测配置
* 评分方式
* 输出结果与报告

## 5.3 Test Case

单条测试样本，包含：

* 输入
* 上下文
* 预期
* 标签
* 难度
* 类型
* 评分标准
* Ground truth / Reference / Rubric

## 5.4 Rubric

评分规则。用于人工或 LLM-as-a-Judge 按维度打分。

## 5.5 Trace

Agent 执行过程日志，如：

* query rewrite
* retrieval
* rerank
* tool call
* planner step
* final answer

---

# 6. 核心能力范围

## 6.1 评测任务管理

系统需支持：

* 新建评测任务
* 选择 Agent / 版本
* 选择测试集
* 选择指标与评分策略
* 执行评测
* 查看结果
* 导出报告

## 6.2 测试集管理

系统需支持：

* 新建测试集
* 导入/导出测试集
* 样本标签分类
* 样本去重
* 样本版本管理
* badcase 回流
* 覆盖率检查

## 6.3 评分与评审

系统需支持：

* 自动评分
* 人工评分
* LLM 辅助评分
* 混合评分
* 多维度评分
* 分步评分

## 6.4 分析与报告

系统需支持：

* 总分与分项分
* 成功率/失败率
* 模块级归因
* 版本对比
* case drill-down
* badcase 聚类
* 可导出评审报告

---

# 7. 评测维度设计

这个是核心。别只盯“答得对不对”，Agent 的问题经常死在中间过程。

## 7.1 最终结果维度

### 必须评估

* **任务完成度**
  是否完成用户目标

* **结果正确性**
  输出是否事实正确、逻辑正确

* **结果完整性**
  是否遗漏关键点

* **结果可执行性**
  是否能直接拿去执行，而不是嘴上热闹

* **结果安全性**
  是否存在风险、误导、不当建议

## 7.2 过程质量维度

### 必须评估

* **意图理解准确性**
* **任务拆解合理性**
* **工具选择正确性**
* **工具调用成功率**
* **检索内容相关性**
* **证据引用充分性**
* **中间步骤一致性**
* **是否出现幻觉规划/伪造工具结果**

## 7.3 交互体验维度

### 必须评估

* **表达清晰度**
* **结构化程度**
* **响应礼貌与自然度**
* **纠错能力**
* **澄清提问是否必要且高效**
* **失败时是否给出替代方案**
* **不确定性表达是否诚实**

## 7.4 工程质量维度

### 必须评估

* **响应时延**
* **失败重试表现**
* **稳定性**
* **并发可用性**
* **成本**
* **token 使用量**
* **可观测性完备度**
* **trace 可追踪性**

---

# 8. 指标体系要求

## 8.1 一级指标

建议至少包含：

* Success Rate
* Final Quality Score
* Step Reliability Score
* UX Score
* Latency
* Cost per Task
* Hallucination Rate
* Tool Failure Rate
* Retrieval Relevance Score
* Regression Rate

## 8.2 二级指标示例

### 对 RAG Agent

* Query Rewrite Quality
* TopK Recall
* Evidence Precision
* Citation Faithfulness
* Answer Groundedness

### 对 Tool Agent

* Tool Selection Accuracy
* Tool Param Correctness
* Tool Call Success Rate
* Recovery after Tool Failure

### 对 Workflow Agent

* Plan Coherence
* Step Completion Rate
* State Transition Validity
* Interrupt / Retry Recovery

## 8.3 指标设计原则

每个指标必须满足：

* 定义清晰
* 可计算或可评审
* 可复现
* 可对比版本
* 可反向定位问题
* 能指导优化动作

---

# 9. 测试集标准

这是最容易被做烂的地方。很多团队的测试集就是“随便抄几条用户问题”，那不叫测试集，那叫许愿池。

## 9.1 测试集分类要求

测试集必须按以下维度组织：

### 按任务类型

* 问答类
* 检索类
* 总结类
* 规划类
* 工具调用类
* 多步执行类
* 异常处理类

### 按能力模块

* Intent
* Planning
* RAG
* Tool Use
* Memory
* Final Response

### 按难度

* L1 简单
* L2 中等
* L3 复杂
* L4 极端边界

### 按风险等级

* 低风险
* 中风险
* 高风险
* 安全敏感

### 按来源

* 人工构造
* 线上 badcase 回流
* 历史真实用户数据脱敏
* 合成数据

## 9.2 单条测试样本字段要求

每个 case 建议至少包含：

* case_id
* title
* task_type
* user_input
* context
* expected_behavior
* expected_output / reference_answer
* must_have_points
* must_not_have_points
* labels
* difficulty
* risk_level
* scoring_rubric
* data_source
* created_by
* reviewed_by
* version
* status

## 9.3 测试集质量标准

测试集必须满足：

* **代表性**: 覆盖核心真实场景
* **多样性**: 避免全是一个套路
* **可判定性**: 不是那种谁都能硬掰的题
* **去重性**: 避免语义重复 case 冲高得分
* **边界性**: 包含失败、冲突、不完整输入
* **可维护性**: 能持续加新样本
* **可追溯性**: 样本来源清晰
* **稳定性**: Ground truth 不随意变化

## 9.4 测试集分层建议

建议至少拆为三层：

### A. Smoke Set

* 20到50条
* 核心主链路
* 每次提交必跑

### B. Regression Set

* 100到500条
* 覆盖主要能力模块
* 每次版本候选必跑

### C. Gold Set / Release Set

* 高质量人工审核集
* 用于上线门禁
* 稳定、严谨、不能随便改

### D. Challenge Set

* 边界条件
* 对抗输入
* 长上下文
* 模糊指令
* Tool failure
* Retrieval conflict

---

# 10. 评分机制要求

## 10.1 评分模式

系统需支持：

* Rule-based Scoring
* String/Regex/JSON Match
* Reference-based Scoring
* Rubric-based Human Review
* LLM-as-a-Judge
* Hybrid Scoring

## 10.2 评分输出格式

每条 case 输出至少包括：

* 总分
* 分维度得分
* 通过/失败
* 失败原因标签
* 中间步骤评分
* 评审备注
* trace_link

## 10.3 人工评审要求

人工评审必须支持：

* 双人复核
* 分歧标记
* 最终裁决
* 评论记录
* 评分历史

## 10.4 LLM 评分要求

若使用 LLM-as-a-Judge，必须满足：

* Judge Prompt 固定版本化
* 输出结构化 JSON
* 可解释评分理由
* 可抽样人工复核
* 防止 judge 漂移
* 禁止只输出一个模糊总分

---

# 11. 工程落地要求

## 11.1 系统架构要求

至少拆成以下模块：

* Eval Config Service
* Dataset Service
* Runner Service
* Scoring Service
* Trace Collect Service
* Report Service
* Review UI

## 11.2 执行链路要求

一次评测流程应为：

1. 选择评测对象
2. 选择测试集
3. 注入评测配置
4. 批量执行 Agent
5. 收集 trace / output / metrics
6. 自动评分
7. 人工复核
8. 生成报告
9. 标记 badcase
10. 回流测试集

## 11.3 数据存储要求

至少保存：

* eval_run
* eval_case_result
* trace_step
* score_detail
* rubric_result
* reviewer_comment
* dataset_version
* agent_version

## 11.4 版本化要求

必须支持版本化管理：

* Agent version
* Prompt version
* Workflow version
* Dataset version
* Judge prompt version
* Eval config version

否则后面根本没法复盘，大家只能靠记忆争论，像原始部落围着篝火讲故事。

---

# 12. 测试评审流程要求

## 12.1 评审前置要求

评测前必须确认：

* 测试集版本冻结
* 评分规则冻结
* 评测环境一致
* Agent 配置明确
* 工具服务状态可用
* 日志链路可追踪

## 12.2 评审流程

建议流程：

### 阶段 1: 自动评测

* 批量跑全量测试
* 输出初步分数与失败分布

### 阶段 2: 人工 spot check

* 抽样复核高分样本
* 复核争议样本
* 审查严重 badcase

### 阶段 3: 测试评审会

评审会议重点：

* 是否达到上线门槛
* 退化点在哪里
* 是否有高风险 badcase
* 是否需要补测试集
* 是否需要修 rubric

### 阶段 4: 结论

评审结论必须明确：

* Pass
* Pass with Risk
* Blocked
* Need Fix + Re-run

---

# 13. UI / UX 设计要求

这个部分你特别强调了，我就直接按**好用的评测产品**来写。不是给工程师看的 JSON 墓地。

## 13.1 总体设计目标

评测 UI 必须做到：

* 一眼看懂整体质量
* 一步下钻到 badcase
* 一眼看出哪个模块出问题
* 评审操作轻量，不费脑
* 支持对比，而不是孤立看单次分数

## 13.2 核心页面

### 1. Eval Run 列表页

展示：

* Run 名称
* Agent 版本
* 测试集版本
* 时间
* 总体得分
* 通过率
* badcase 数
* 状态
* 对比入口

### 2. Eval Overview 总览页

展示：

* 总分卡片
* 各维度分布图
* 版本对比趋势
* 失败类型分布
* 模块归因图
* Top badcases
* 成本/时延概览

### 3. Case Detail 页面

必须展示：

* 用户输入
* Agent 输出
* 参考答案 / 评审标准
* 自动评分结果
* 人工评分结果
* trace 时间线
* 每一步输入输出
* tool call 详情
* retrieval 证据
* 失败原因
* reviewer comment

### 4. Dataset 管理页

展示：

* 测试集分层
* 标签分布
* 样本数
* 难度分布
* 来源分布
* 去重状态
* 最近新增 badcases

### 5. Version Compare 页

展示：

* A/B 版本总体分数
* 每个维度增减
* 回归 case 列表
* 改善 case 列表
* 新增失败类型
* 统计显著性提示

## 13.3 交互要求

UI 必须支持：

* 标签筛选
* 多维排序
* 快速搜索
* badcase 收藏
* 一键加入回归集
* 一键标记误判
* 一键复制 trace / case JSON
* 支持 reviewer 批注

## 13.4 UX 原则

必须遵循：

* 默认展示最重要信息
* 失败 case 优先曝光
* 减少页面跳转
* 术语统一
* 支持展开收起复杂 trace
* 避免信息噪音过多
* 图表要能支撑判断，不是装饰

---

# 14. 上线门禁标准

## 14.1 必须具备的发布门槛

示例：

* Smoke Set 通过率 ≥ 95%
* Gold Set 总分 ≥ 85
* 高风险 case 通过率 ≥ 90%
* Hallucination Rate ≤ 2%
* Tool Failure Rate ≤ 3%
* P95 Latency 不高于上版本 10%
* 回归 case 数量不超过阈值

## 14.2 阻塞条件

出现以下任一项应阻塞上线：

* 核心主链路失败
* 高风险错误输出
* 引用失真/编造证据
* 工具结果伪造
* 关键能力退化明显
* trace 缺失导致不可审计

---

# 15. 数据与埋点要求

## 15.1 必须采集的数据

* request_id / trace_id
* case_id
* agent_version
* prompt_version
* dataset_version
* input
* output
* step logs
* tool call params/result
* retrieval candidates
* latency per step
* token cost
* score detail
* reviewer actions

## 15.2 埋点原则

* 全链路可追踪
* 字段语义明确
* 敏感数据脱敏
* 支持离线分析
* 支持版本对比

---

# 16. 权限与角色

建议角色：

* Admin
* Engineer
* QA
* PM
* Reviewer
* Viewer

权限差异包括：

* 是否可编辑测试集
* 是否可修改 rubric
* 是否可发起正式评测
* 是否可确认评审结论
* 是否可上线放行

---

# 17. 验收标准

## 17.1 产品验收

* 能完成从建集到评测到评审到报告输出的闭环
* 能支持版本对比
* 能支持 badcase 回流
* 能支持人工评审

## 17.2 工程验收

* 评测任务可稳定执行
* trace 完整
* 数据可追溯
* 配置可版本化
* 失败可重试
* 报告可导出

## 17.3 UX 验收

* 评审员 3 分钟内可定位 badcase
* 5 分钟内可完成单 case 评审
* 总览页可快速判断是否可上线
* 页面信息层次清晰，无明显认知负担

---

# 18. 未来扩展方向

后续可以扩展：

* 线上真实用户会话自动抽样评估
* 自动 badcase 聚类
* 自动推荐补充测试集
* 不同模型/Prompt/Workflow A/B 对比
* 统计显著性分析
* 基于失败归因的优化建议生成
* 多 Agent 协同链路评测
* 人工评分一致性分析

---

# 19. 附录：建议你在 PRD 后面直接补的几个产物

为了让这份 PRD 真能指导落地，建议你紧跟着补 4 个文档，不然 PRD 很容易沦为体面废纸。

## A. Eval Metrics Spec

内容包括：

* 指标定义
* 计算公式
* 输入输出
* 指标边界
* 适用场景
* 不适用场景

## B. Dataset Spec

内容包括：

* case schema
* 标签体系
* 难度定义
* 采样规则
* 去重规则
* badcase 回流规则

## C. Reviewer Rubric

内容包括：

* 每个维度如何打分
* 什么叫 1 分/3 分/5 分
* 常见误判示例
* reviewer 注意事项

## D. Eval UI Information Architecture

内容包括：

* 页面结构
* 信息优先级
* 用户路径
* 状态流转
* 筛选与对比设计
