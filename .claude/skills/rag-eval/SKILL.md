---
name: rag-eval
description: RAG Evaluation and Scoring System - Automated RAG quality assessment with scoring based on performance metrics, retrieval quality, answer quality, and citation accuracy. Supports manual answer paste or automated API testing with ground truth datasets. Generates problem analysis, bottleneck optimization suggestions, and fills in rag-debug records. Trigger phrases: "评估 RAG", "RAG 评分", "rag evaluate", "RAG 质量评估", "评估检索质量".
---

# RAG Evaluation and Scoring System

## Overview

This skill provides comprehensive evaluation and scoring for RAG (Retrieval-Augmented Generation) systems. It can work in two modes:

1. **Manual Mode**: User pastes a chat response for evaluation
2. **Auto Mode**: Skill runs API calls against a ground truth dataset

After evaluation, it automatically fills in the RAG debug record with:
- Performance metrics scores
- Retrieval quality scores
- Answer quality scores
- Citation accuracy scores
- Problem analysis
- Bottleneck optimization suggestions
- Next action recommendations

## Quick Start

When triggered, this skill will:

1. **Mode Selection** - Manual paste vs Auto API testing
2. **Data Collection** - Gather answer or run tests
3. **Scoring** - Apply evaluation standards
4. **Analysis** - Generate insights and suggestions
5. **Report Generation** - Fill in rag-debug template

## Evaluation Standards

### 1. RAG Performance Metrics (性能指标评分)

| Metric | Target | Score Calculation (0-100) |
|--------|--------|---------------------------|
| **Ingestion Success Rate** | >95% | (actual_rate / 95) × 100, capped at 100 |
| **Retrieval Latency** | <300ms | 100 - max(0, (actual_ms - 300) / 10) |
| **Chat First Token** | <2s | 100 - max(0, (actual_s - 2) × 20) |
| **API Uptime** | >99.5% | (actual_uptime / 99.5) × 100 |

**Performance Score = Average of all metric scores**

### 2. Retrieval Quality Standards (检索质量评分)

| Metric | Target | Score Calculation (0-5) |
|--------|--------|------------------------|
| **Recall@10** | >90% | (recall / 90) × 5, capped at 5 |
| **MRR** | >0.8 | (mrr / 0.8) × 5, capped at 5 |
| **Chunk Relevance** | 4.5/5 avg | Direct rating 1-5 |
| **Coverage** | >85% scope | (coverage / 85) × 5, capped at 5 |

**Retrieval Score = (Recall@10 + MRR + Relevance + Coverage) / 4**

### 3. Answer Quality Standards (答案质量评分)

| Metric | Target | Score Calculation (0-5) |
|--------|--------|------------------------|
| **Groundedness** | >90% | (grounded / 90) × 5 |
| **Completeness** | >85% | (complete / 85) × 5 |
| **Faithfulness** | >95% | (faithful / 95) × 5 |
| **Conciseness** | Subjective | Direct rating 1-5 |

**Answer Score = (Groundedness + Completeness + Faithfulness + Conciseness) / 4**

### 4. Citation Accuracy Standards (引用准确性评分)

| Metric | Target | Score Calculation (0-5) |
|--------|--------|------------------------|
| **Citation Support Rate** | >95% | (support_rate / 95) × 5 |
| **Wrong Citation Rate** | <5% | 5 - (wrong_rate / 5) × 5 |

**Citation Score = (Support Rate Score + Wrong Citation Score) / 2**

---

## Workflow

### Step 1: Mode Selection

Ask user to choose evaluation mode:

**Option A: Manual Mode (手动模式)**
- User pastes the RAG response
- User provides relevant context (question, retrieved chunks, etc.)
- Skill evaluates based on provided data

**Option B: Auto Mode (自动模式)**
- Skill loads ground truth dataset from `.claude/skills/rag-eval/data/test_dataset.json`
- Skill calls RAG API for each test case
- Skill compares results with expected answers
- Calculates objective scores

```
请选择评估模式:

A. 手动模式 - 粘贴 RAG 回复进行评估
B. 自动模式 - 使用测试集自动评估

选择 A 或 B:
```

### Step 2: Data Collection

#### For Manual Mode:

Collect the following information:

| Field | Description | Example |
|-------|-------------|---------|
| Test Question | The question asked | "刺头定义和管理..." |
| Retrieved Chunks | Chunks returned by retrieval | List of chunk IDs with content |
| Generated Answer | The RAG system's response | "刺头是指在组织..." |
| Citations | Citation markers and their sources | [1] chunk_123, [2] chunk_456 |
| Performance Data | Optional timing data | total_time: 42.18s |

**Prompt format:**
```
请提供以下信息进行评估:

1. 测试问题:
2. 检索到的 Chunks (可选，粘贴内容):
3. 生成的答案:
4. 引用信息 (格式: [1] chunk_id: quote):
5. 性能数据 (可选):
```

#### For Auto Mode:

Load test dataset from `data/test_dataset.json`:

```json
{
  "test_cases": [
    {
      "id": "test-001",
      "question": "刺头定义和管理...",
      "expected_keywords": ["刺头", "管理", "定义"],
      "expected_chunks": ["chunk_123", "chunk_456"],
      "ground_truth_answer": "刺头是指在组织中...",
      "notebook_id": "63d8f8f4-..."
    }
  ]
}
```

For each test case:
1. Call RAG API with the question
2. Capture response (answer, citations, chunks)
3. Capture timing data
4. Compare with ground truth

### Step 3: Scoring Calculation

#### Automated Scoring (Auto Mode)

Use `scripts/evaluate.py` to calculate scores:

```python
from scripts.evaluate import RAGEvaluator

evaluator = RAGEvaluator(
    rag_api_url="http://localhost:8000/api/chat",
    api_key="your-api-key"
)

results = evaluator.evaluate_all("data/test_dataset.json")

# Scores are calculated automatically:
# - Performance metrics from timing data
# - Recall@10 from retrieved vs expected chunks
# - MRR from chunk ranking positions
# - Answer quality via LLM-as-judge or keyword matching
# - Citation accuracy by verifying citation-chunk links
```

#### Manual Scoring (Manual Mode)

Guide user through rating each dimension:

**Performance Rating (1-100 per metric):**
```
请评分以下性能指标 (1-100):

1. 检索延迟 (目标 <300ms):
2. 首字延迟 (目标 <2s):
3. API 可用性 (目标 >99.5%):
```

**Retrieval Quality Rating (1-5 per metric):**
```
请评分以下检索质量 (1-5):

1. Chunks 相关性: ____/5
   说明: 检索到的 chunks 是否与问题相关

2. 检索数量充足性: ____/5
   说明: 检索到的 chunks 数量是否足够

3. 检索覆盖率: ____/5
   说明: 是否覆盖了问题的各个方面
```

**Answer Quality Rating (1-5 per metric):**
```
请评分以下答案质量 (1-5):

1. 相关性: ____/5
   说明: 答案是否针对问题

2. 准确性: ____/5
   说明: 答案内容是否准确

3. 完整性: ____/5
   说明: 答案是否完整回答了问题

4. 简洁性: ____/5
   说明: 答案是否简洁明了，没有冗余
```

**Citation Accuracy Rating:**
```
请评分以下引用准确性:

1. 引用数量: ____ 个
2. 引用正确率: ____%
3. 虚引/误引数量: ____ 个
4. 引用质量评分: ____/5
```

### Step 4: Problem Analysis

Based on scores, identify problems:

#### Performance Bottlenecks

| Symptom | Possible Cause | Suggested Action |
|---------|---------------|------------------|
| High embedding time | Large query, slow model | Use faster embedding model, cache embeddings |
| High vector search time | Missing index, large data | Create HNSW index, partition data |
| High LLM time | Large context, slow model | Reduce context size, use faster model |
| Low ingestion rate | Parser errors, API limits | Fix parsers, implement retry logic |

#### Retrieval Issues

| Symptom | Possible Cause | Suggested Action |
|---------|---------------|------------------|
| Low recall@10 | Poor chunking, wrong embeddings | Re-evaluate chunking strategy, test different embedding models |
| Low MRR | Poor ranking, no reranking | Implement reranking, tune BM25 weights |
| Low relevance | Query mismatch | Implement query rewriting/expansion |
| Low coverage | Insufficient chunks | Increase top_k, add more sources |

#### Answer Issues

| Symptom | Possible Cause | Suggested Action |
|---------|---------------|------------------|
| Low groundedness | LLM hallucination | Improve prompts, add constraints |
| Low completeness | Missing context | Increase retrieved chunks |
| Low faithfulness | Contradictory sources | Deduplicate sources, improve chunking |
| Poor conciseness | No length constraint | Add token limit to prompt |

#### Citation Issues

| Symptom | Possible Cause | Suggested Action |
|---------|---------------|------------------|
| Low support rate | Wrong citation binding | Fix citation alignment logic |
| High wrong citation rate | Hallucinated citations | Validate citation exists before output |

### Step 5: Report Generation

1. Calculate overall scores and ratings
2. Identify problems based on score thresholds
3. Generate optimization suggestions
4. Fill in rag-debug template
5. Save as `rag-eval-{YYYY-MM-DD}-{MODEL}.md`

**Score Thresholds for Problem Detection:**
- Performance < 70/100 → Performance issue
- Retrieval < 3.5/5 → Retrieval issue
- Answer < 3.5/5 → Answer issue
- Citation < 3.5/5 → Citation issue

### Step 6: Fill RAG Debug Record

Use the evaluation results to fill in `/rag-debug-template.md`:

```python
from scripts.fill_debug_report import fill_rag_debug_template

fill_rag_debug_template(
    evaluation_results=results,
    output_file="rag-eval-2026-04-01-glm-4.7-flashx.md"
)
```

## Resources

### scripts/evaluate.py

Main evaluation script that:
- Loads test dataset
- Calls RAG API for each test case
- Calculates scores automatically
- Generates evaluation report

Usage:
```bash
python .claude/skills/rag-eval/scripts/evaluate.py
```

### scripts/fill_debug_report.py

Helper script that:
- Takes evaluation results
- Fills in rag-debug template
- Saves formatted report

### data/test_dataset.json

Ground truth dataset for automated evaluation.

Format:
```json
{
  "test_cases": [
    {
      "id": "test-001",
      "question": "问题文本",
      "notebook_id": "uuid",
      "expected_chunks": ["chunk_id1", "chunk_id2"],
      "expected_keywords": ["关键词1", "关键词2"],
      "ground_truth_answer": "标准答案",
      "min_recall": 0.9,
      "min_mrr": 0.8
    }
  ]
}
```

## Example Output

After evaluation, user gets:

```
✅ RAG 评估完成

📊 评估报告: rag-eval-2026-04-01-glm-4.7-flashx.md

📈 综合评分:
   • 性能指标: 72/100
   • 检索质量: 3.8/5
   • 答案质量: 4.2/5
   • 引用准确性: 4.5/5

⚠️  发现的问题:
   • 检索延迟超标 (450ms > 300ms目标)
   • Recall@10 偏低 (85% < 90%目标)

💡 优化建议:
   1. 创建 HNSW 索引以加速向量搜索
   2. 调整 chunking 策略提高召回率
   3. 考虑使用更快的 embedding 模型

📋 下一步行动:
   - [ ] 创建 HNSW 索引
   - [ ] 重新评估 chunking 参数
   - [ ] 测试 text-embedding-3-small 模型
```

## User Interaction Guidelines

- **Bilingual support**: Support both Chinese and English
- **Flexible input**: Allow skipping optional fields
- **Explain scores**: Show what each score means
- **Actionable suggestions**: Provide specific next steps
- **Progress tracking**: Show evaluation progress for auto mode

## Notes

- All evaluation reports are saved as `rag-eval-{DATE}-{MODEL}.md`
- RAG debug records are filled using existing template
- Test dataset should be maintained and updated regularly
- Scores follow the standards defined in CLAUDE.md
