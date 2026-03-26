我需要coding一个知识库，目标产品是google 的 notebooklm， show me step by step

## 先看清 NotebookLM 到底是什么

**NotebookLM 的核心不是“大而全知识库”，而是“以 notebook 为单位、被 source 约束的 AI 研究工作台”。**
它现在支持把 PDFs、网页、YouTube、音频、Google Docs、Google Slides 等作为 source 导入，然后基于这些 source 做带引用的对话；同时还能生成 Mind Maps、Audio Overviews、Flashcards/Quizzes、Infographics、Slide Decks 这类衍生产物。企业版还已经把 notebook 和 source 管理做成了 API。([Google Help][1])

所以你要抄的不是“一个 RAG”，而是这 4 个产品原则：

1. **Notebook 是一等公民**
2. **Source 是真相边界**
3. **回答必须尽量可追溯**
4. **衍生内容建立在 source-grounded 之上**

下面我按**真正能 coding 的顺序**给你拆。

---

# Step 1: 先砍 scope，别一上来做“Google 全家桶”

## 你的 v1 只做这 5 个能力

1. 创建 notebook
2. 往 notebook 里加 sources
3. 自动解析和切片
4. 基于 notebook 聊天问答
5. 每个回答附 citation

**不要先做：**

* 多人协作
* 权限系统细粒度
* Audio Overview
* Mind Map
* Flashcards
* 多模态复杂理解
* 企业审计日志

这些都很诱人，像人类购物车里的垃圾一样闪闪发亮，但对 v1 没用。

## v1 的产品定义

你的产品先叫它：

**“Source-grounded notebook knowledge workspace”**

不是“企业知识库平台”，不是“全局智能问答中台”。

---

# Step 2: 定义核心数据模型

你先把数据库模型定对，不然后面全崩。

## 最小对象模型

### 1. Notebook

```ts
type Notebook = {
  id: string
  title: string
  description?: string
  ownerId: string
  createdAt: string
  updatedAt: string
}
```

### 2. Source

```ts
type Source = {
  id: string
  notebookId: string
  type: 'pdf' | 'url' | 'text' | 'youtube' | 'audio' | 'gdoc' | 'gslide'
  title: string
  status: 'pending' | 'processing' | 'ready' | 'failed'
  originalUri?: string
  metadataJson?: Record<string, unknown>
  createdAt: string
}
```

### 3. SourceChunk

```ts
type SourceChunk = {
  id: string
  sourceId: string
  notebookId: string
  chunkIndex: number
  content: string
  tokenCount: number
  embedding?: number[]
  page?: number
  sectionTitle?: string
  charStart?: number
  charEnd?: number
}
```

### 4. Note

```ts
type Note = {
  id: string
  notebookId: string
  title?: string
  content: string
  pinned: boolean
  createdAt: string
}
```

### 5. Conversation / Message

```ts
type Message = {
  id: string
  notebookId: string
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  createdAt: string
}
```

### 6. Citation

```ts
type Citation = {
  sourceId: string
  chunkId: string
  quote?: string
  page?: number
  score?: number
}
```

### 7. GeneratedAsset

```ts
type GeneratedAsset = {
  id: string
  notebookId: string
  type: 'summary' | 'faq' | 'study_guide' | 'timeline' | 'mind_map' | 'flashcards' | 'audio_script'
  contentJson: Record<string, unknown>
  createdAt: string
}
```

---


# Step 3: 技术栈别整花活，先选能跑通的

按你现在的目标和资源条件，我建议技术栈优先遵循一个原则：

**先保证本地能稳定开发、线上能低成本部署，再考虑复杂扩展。**

## 前端

* **Next.js**
* React
* Tailwind CSS
* shadcn/ui
* SSE / Streaming UI

前端这块没必要折腾，目标就是把上传、检索、问答、引用、任务状态这些核心体验先做顺。

## 后端

* **Python + FastAPI**
* **Arq 优先** 做异步 ingestion

  * 如果后面任务编排更复杂，再考虑 Dramatiq 或 Celery
* **PostgreSQL**
* **pgvector 优先** 做向量检索

  * 只有在强全文检索、复杂搜索分析场景下，再考虑 Elasticsearch / OpenSearch
* **Redis** 做任务队列和缓存
* **本地用 MinIO，线上用 S3 / OSS** 做原文件存储

这一套更适合你现在的阶段：

* FastAPI 和 async 体系天然契合
* Arq 比 Celery 更轻，更适合个人项目或小团队快速落地
* pgvector 直接挂在 PostgreSQL 上，开发和部署都更省事
* MinIO 适合本地模拟对象存储，线上没必要执着自建，直接接云存储更省心

## LLM / AI 能力

* 一个**主模型**负责问答、总结、生成
* 一个 **embedding 模型**负责向量化和召回
* 一个**可选 reranker 模型**负责重排结果

这里也别一开始堆满：

* **第一阶段**：主模型 + embedding 就够用
* **第二阶段**：当召回结果质量不稳时，再补 reranker
* **第三阶段**：再考虑 query rewrite、multi-hop retrieval、workflow routing 这些增强能力

## 一句话定版

如果你要一个当前最合理的默认组合，可以直接写成：

**Next.js + FastAPI + Arq + PostgreSQL + pgvector + Redis + MinIO（本地）/ S3 或 OSS（线上）**

这套的优点不是“最豪华”，而是：

**本地能跑、成本可控、后续还能扩。**



## 为什么这样拆

因为 NotebookLM 本质上是：

* **web 是 usage layer**
* **python 是 knowledge/ingestion/assembly layer**

这不是玄学，是工程现实。NotebookLM 自己的产品抽象也是 notebook + sources + grounded outputs，不是单纯聊天框。([blog.google][2])

---

# Step 4: 先做 notebook/source CRUD

## 你第一个 Sprint 要交付的 API

```http
POST   /api/notebooks
GET    /api/notebooks
GET    /api/notebooks/:id
PATCH  /api/notebooks/:id
DELETE /api/notebooks/:id

POST   /api/notebooks/:id/sources/upload
POST   /api/notebooks/:id/sources/url
GET    /api/notebooks/:id/sources
GET    /api/sources/:id
DELETE /api/sources/:id
```

## 前端页面

1. notebook 列表页
2. notebook 详情页
3. source 上传区
4. source 状态列表

## 完成标准

* 能创建 notebook
* 能上传 PDF / 贴文本 / 加 URL
* source 状态能从 pending -> processing -> ready

---

# Step 5: 做 ingestion pipeline，这是知识库的心脏

## 统一 ingestion 流程

```txt
上传 source
-> 保存原始文件/链接
-> 抽取文本
-> 清洗归一化
-> 按语义/段落切块
-> 生成 embedding
-> 写入向量索引
-> 生成 source-level summary
-> 标记 ready
```

## 具体做法

### PDF

* 提取 page number
* 尽量保留段落结构和标题层级
* chunk 时保留 `page`

### URL

* 抓正文
* 去掉导航/footer/广告
* 保留标题、h1/h2/h3

### YouTube

* 先用 transcript
* 没 transcript 就失败回退

### Audio

* 先转写
* 再当普通文本 source

NotebookLM 当前支持多种 source 类型，包括 PDF、网页、YouTube、音频、Docs、Slides，这意味着你自己的 schema 一开始就别只写死 PDF。([Google Help][1])

## chunking 建议

不要固定 500 字硬切。

用：

* 标题优先分段
* 段落级 chunk
* 超长段再切
* chunk 大小控制在 **300 到 800 tokens**
* overlap 50 到 120 tokens

同时保存：

* page
* heading path
* source title
* chunk index

这些元数据会直接决定 citation 体验。

---

# Step 6: 做 source-grounded chat，不要先追求“聪明”

NotebookLM 从一开始的差异点就是**source-grounding**，不是自由发挥；Google 也明确把“基于用户选定 sources 的总结、问答、引用回指”当成核心。([blog.google][2])

## 你的问答链路应该是

```txt
用户问题
-> Query rewrite（可选）
-> 在当前 notebook 范围内检索
-> hybrid retrieval（BM25 + vector）
-> rerank
-> 组装 evidence pack
-> LLM 生成回答
-> 插入 citations
-> 返回 answer + citation cards
```

## 为什么必须“当前 notebook 范围内”

因为 NotebookLM 的基本交互就是“跟这个 notebook 聊”，不是全局乱搜。
**notebook boundary 是产品边界，也是 hallucination 边界。**

## API 设计

```http
POST /api/notebooks/:id/chat
```

request:

```json
{
  "message": "总结这几份材料里关于 onboarding 的关键风险",
  "mode": "grounded_qa"
}
```

response:

```json
{
  "answer": "......[1][2]",
  "citations": [
    {
      "index": 1,
      "sourceId": "src_1",
      "sourceTitle": "Employee Handbook",
      "chunkId": "chk_8",
      "quote": "New hires must complete security training within 7 days.",
      "page": 12
    }
  ]
}
```

---

# Step 7: citation 必须设计成产品能力，不是模型顺手吐出来

很多人做 RAG 死在这里。模型嘴里冒出来个 `[1]`，你就信了，属实把系统可靠性献祭给概率。

## 你要做两层 citation

### 第一层：检索证据层

在生成前就确定候选 evidence：

```ts
type EvidenceItem = {
  chunkId: string
  sourceId: string
  sourceTitle: string
  content: string
  page?: number
  score: number
}
```

### 第二层：回答绑定层

生成后把句子和 evidence 对齐：

* 要么模型输出 structured JSON
* 要么后处理用 span alignment

### 推荐输出格式

让模型先输出：

```json
{
  "answer_blocks": [
    {
      "text": "Onboarding 的最大风险是权限开通滞后。",
      "citation_chunk_ids": ["chk_8", "chk_11"]
    }
  ]
}
```

然后后端再映射成 UI 的 `[1][2]`

## 这是为什么

Google 明确把 NotebookLM 的关键价值放在 grounded responses、inline citations、relevant quotes 上。([Google Help][1])

---

# Step 8: 做 notebook 首页，不要只有聊天框

NotebookLM 早期就强调：当你加完 source 后，它会自动生成 summary、key topics、suggested questions，帮助用户先“理解材料”，再进入聊天。([blog.google][2])

所以你的 notebook 详情页应该有：

## 左侧

* source 列表
* source 状态
* source summary

## 中间

* notebook overview
* key topics
* suggested questions
* pinned notes

## 右侧

* chat panel
* citations panel

## 自动生成内容

当 source ready 后自动生成：

1. notebook summary
2. 5-10 个 key topics
3. 5 个 suggested questions
4. source-to-source overlap points

这一步会显著提升“像 NotebookLM”的感觉。

---

# Step 9: v1.5 再做“衍生产物”

NotebookLM 现在已经把很多输出形态做成按钮化能力，包括 Mind Maps、Audio Overview、Flashcards、Quizzes、Infographics、Slide Decks；Google 还强调 study guides、briefing docs、reports 这类二次生成内容。([Google Help][3])

## 你的优先顺序应该是

### 第一批最值钱

1. **Briefing Doc**
2. **FAQ**
3. **Study Guide**
4. **Timeline**
5. **Glossary**

### 第二批再做

6. Mind Map
7. Flashcards
8. Quiz
9. Audio Script
10. Audio TTS

## 为什么先做文档类

因为它们只是：
**同一套检索证据 + 不同的 prompt/template**

成本低，价值高。

## API

```http
POST /api/notebooks/:id/generate
```

request:

```json
{
  "type": "faq"
}
```

---

# Step 10: Audio Overview 别太早碰，但架构上提前预留

NotebookLM 的 Audio Overview 是很强的差异点，但它本质上是**基于 sources 的二次生成内容**，而且 Google 自己都明确说它有延迟、可能不准确、并且只是对 source 的一种反映，不是客观完整视图。([blog.google][4])

## 所以你应该这样做

先把它拆成两步：

### 1. 生成 audio script

```json
{
  "hosts": [
    {"name": "Host A", "lines": [...]},
    {"name": "Host B", "lines": [...]}
  ],
  "citations": [...]
}
```

### 2. 再接 TTS

* Azure TTS / ElevenLabs / 其他
* 合成音频文件
* 回写到 GeneratedAsset

这样你以后可做：

* single host brief
* debate
* critique
* podcast

而不是一上来被语音链路拖死。

---

# Step 11: 先做“单 notebook 检索”，别做“全局知识库”

这个选择非常关键。

## v1 检索边界

只在当前 notebook 里检索。

## v2 才做

* workspace-level search
* cross-notebook retrieval
* shared knowledge base
* org-level memory

## 原因

单 notebook 检索有 4 个好处：

1. 相关性更高
2. prompt 更短
3. citation 更容易对齐
4. 用户心智更清楚

而且这跟 NotebookLM 的产品抽象一致。企业版文档也说明它围绕 notebook 和 notebook sources 进行管理。([Google Cloud Documentation][5])

---

# Step 12: 权限和隐私，第一天就留接口

Google Workspace 对 NotebookLM 的表述里很明确：上传的数据不会被用来训练模型，source 默认私有，除非你主动分享 notebook。([Google Workspace][6])

你不一定第一版就做到企业级，但至少要把模型设计成：

## 访问控制最小单位

* notebook owner
* notebook collaborators
* source visibility 跟 notebook 走

## 需要预留的字段

```ts
type NotebookPermission = {
  notebookId: string
  userId: string
  role: 'owner' | 'editor' | 'viewer'
}
```

## 产品上要写清楚

* source 只用于本次 notebook 检索与生成
* 是否用于模型训练
* 删除后多久真正清除索引

这种东西不写，后面客户会把你按在墙上问。也正常，毕竟大家对“AI 会不会偷我文档”都很敏感。

---

# Step 13: 评测体系要和 coding 同步，不要最后补

你这种产品，没评测就是撞大运。

## 先建 3 套评测

### 1. Retrieval eval

看 top-k 里有没有正确 chunk

* recall@5
* recall@10
* MRR

### 2. Citation eval

回答里的 citation 是否真的支持该句子

* support rate
* wrong citation rate

### 3. Answer eval

* groundedness
* completeness
* conciseness
* faithfulness

## 你要准备的数据

每个 notebook 造 20 到 50 个问题：

```json
{
  "question": "...",
  "gold_chunk_ids": ["chk_1", "chk_7"],
  "gold_answer": "..."
}
```

## 最重要的一条

**先测检索，再测生成。**
80% 的“模型胡说八道”其实是你喂错料了。

---

# Step 14: 直接给你一个实现顺序

## 第 1 周

* Notebook CRUD
* Source 上传
* Source 列表页
* 异步 ingestion pipeline 骨架

## 第 2 周

* PDF / URL / text parser
* chunking
* embedding
* vector index
* source status flow

## 第 3 周

* notebook 范围检索
* basic grounded chat
* citation UI

## 第 4 周

* notebook summary
* key topics
* suggested questions
* pinned notes

## 第 5 周

* generate FAQ / briefing doc / glossary / timeline
* generated asset 页面

## 第 6 周

* rerank
* query rewrite
* eval dashboard
* failure retry
* basic permission

---

# 你最该先写的 repo 结构

```txt
apps/
  web/                    # Next.js 前端

services/
  api/                    # FastAPI 主服务
  worker/                 # ingestion / generation worker

packages/
  shared/                 # schema/types
  prompts/                # system prompts / templates

infra/
  docker/
  sql/
```

## services/api 里分模块

```txt
modules/
  notebooks/
  sources/
  ingestion/
  retrieval/
  chat/
  citations/
  generation/
  auth/
```

---

# 你的 MVP 页面结构

## 1. Notebook List

* 新建 notebook
* 最近使用

## 2. Notebook Detail

* source panel
* notebook overview
* chat panel
* citation drawer

## 3. Source Detail

* source summary
* original text preview
* chunk list

## 4. Generated Assets

* FAQ
* briefing doc
* glossary
* timeline

---

# 最后给你一句非常直白的产品判断

**想做得像 NotebookLM，最重要的不是“接一个大模型”，而是把“notebook boundary + source grounding + citation traceability + derived outputs”这套产品骨架搭出来。**

真正的优先级是：

**Notebook 抽象 > Ingestion 质量 > Retrieval/Citation > Chat > 衍生内容 > 花哨多模态**

别反过来。
反过来做，最后就会得到一个会说话的文件上传器，行业里这种东西已经多得像便利店冰柜里的无糖气泡水了。

如果你要，我下一条可以直接继续给你：
**1) 数据库表设计 SQL**，或者 **2) FastAPI + Next.js 的最小项目骨架**。

[1]: https://support.google.com/notebooklm/answer/16164461?co=GENIE.Platform%3DDesktop&hl=en "Learn about NotebookLM - Computer - NotebookLM Help"
[2]: https://blog.google/innovation-and-ai/technology/ai/notebooklm-google-ai/ "NotebookLM: How to try Google’s experimental AI-first notebook"
[3]: https://support.google.com/notebooklm/?hl=en "NotebookLM Help"
[4]: https://blog.google/innovation-and-ai/products/notebooklm-audio-overviews/ "NotebookLM now lets you listen to a conversation about your sources"
[5]: https://docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/api-notebooks "Create and manage notebooks (API)  |  NotebookLM Enterprise  |  Google Cloud Documentation"
[6]: https://workspace.google.com/products/notebooklm/ "NotebookLM: AI-Powered Research and Learning Assistant Tool | Google Workspace"
