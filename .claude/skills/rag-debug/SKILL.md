---
name: rag-debug
description: RAG (Retrieval-Augmented Generation) debugging session recorder and analyzer. Use this when user wants to record test results from RAG system debugging, compare different model configurations, or track performance improvements over time. Trigger phrases: "帮我记录 RAG 测试", "rag debug", "记录 RAG 调试", "RAG 性能测试记录". Captures performance metrics (total time, embedding time, vector search time, LLM time), quality assessments (chunk relevance, answer quality, citation accuracy), and generates comparison reports between different model configurations.
---

# RAG Debug Session Recorder

## Overview

This skill helps you systematically record and analyze RAG system debugging sessions. It captures performance metrics, quality assessments, and supports comparison between different model configurations (e.g., GLM-4.6 vs GLM-4.7-flashx).

## Quick Start

When triggered, this skill will guide you through a structured session:

1. **Session Setup** - Test configuration (model, question, notebook)
2. **Performance Recording** - Time breakdown and metrics
3. **Quality Assessment** - Answer and retrieval quality ratings
4. **Comparison Mode** - Optional comparison with previous tests
5. **Report Generation** - Create markdown report using template

## Session Workflow

### Step 1: Session Setup

Collect the following information:

| Field | Description | Example |
|-------|-------------|---------|
| Date | Test date (auto-filled with today) | 2026-04-01 |
| Session ID | Unique identifier for this session | debug-001 |
| LLM Model | Model being tested | glm-4.7-flashx |
| Embedding Model | Embedding model used | text-embedding-3-small |
| Test Question | The question asked to the RAG system | "刺头定义和管理..." |
| Notebook ID | Target notebook UUID | 63d8f8f4-646e-497a-9ac7-fd49488172b9 |

**Important:** Use conversation tone. Example: "请提供测试日期（默认今天），会话 ID，LLM 模型名称，测试问题，和 Notebook ID"

### Step 2: Performance Recording

Collect time breakdown from logs or user input:

| Metric | Description |
|--------|-------------|
| Total Time | End-to-end latency |
| Embedding Time | Time to generate query embedding |
| Vector Search Time | Time to retrieve chunks |
| LLM Time | Time for LLM generation |
| Chunk Count | Number of chunks retrieved |

**Calculate percentages:**
- Embedding % = (Embedding Time / Total Time) × 100
- Vector Search % = (Vector Search Time / Total Time) × 100
- LLM % = (LLM Time / Total Time) × 100

**Log pattern example:**
```
INFO:services.api.modules.chat.service:[CHAT] Total answer_question took 125.25s
INFO:services.api.modules.chat.service:[CHAT] Embedding generation took 4.23s
INFO:services.api.modules.chat.service:[CHAT] Vector search took 0.06s, found 5 results
INFO:services.api.core.ai:[CHAT] LLM call completed in 120.95s
```

### Step 3: Quality Assessment

Ask user to rate the following dimensions (1-5 scale):

**Retrieval Quality:**
- Chunk Relevance (1-5): How relevant are the retrieved chunks?
- Chunk Count Adequacy (1-5): Were enough chunks retrieved?
- Coverage (1-5): Did chunks cover the question scope?

**Answer Quality:**
- Relevance (1-5): Does the answer address the question?
- Accuracy (1-5): Is the answer factually correct?
- Completeness (1-5): Does it fully answer the question?
- Conciseness (1-5): Is the answer appropriately detailed?

**Citation Quality:**
- Citation Count: Number of citations
- Citation Accuracy %: Percentage of correct citations
- False Citations: Any incorrect or hallucinated citations

**Allow user to paste the generated answer** for reference in the report.

### Step 4: Comparison Mode (Optional)

If user wants to compare with a previous test:

1. Use `find_history_reports()` from `scripts/find_reports.py` to locate previous reports
2. Ask user which report to compare against
3. Load the previous report data
4. Generate side-by-side comparison table:
   - Model comparison
   - Time differences with % improvement
   - Quality score differences

**Comparison calculation:**
- Time Improvement = ((Old Time - New Time) / Old Time) × 100%
- Quality Delta = New Score - Old Score

### Step 5: Report Generation

1. Read the template from `/rag-debug-template.md` (project root)
2. Replace all placeholders with collected data:
   - `{{DATE}}` → Test date
   - `{{MODEL_NAME}}` → LLM model
   - `{{TOTAL_TIME}}` → Total time (e.g., "42.18s")
   - `{{LLM_TIME}}` → LLM time
   - And all other placeholders...
3. Save the report as `rag-debug-{YYYY-MM-DD}-{MODEL_NAME}.md` in project root
4. Show summary with key metrics after saving

**Summary format:**
```
✅ RAG Debug Report Saved

📄 File: rag-debug-2026-04-01-glm-4.7-flashx.md

📊 Key Metrics:
   • Total Time: 42.18s
   • LLM Time: 40.93s (97%)
   • Answer Quality: 4.2/5
   • Chunk Relevance: 4.5/5

💡 Main Observations:
   • LLM is the primary bottleneck (97% of total time)
   • Answer quality is good (4.2/5)
   • Consider optimizing prompt size or using faster model
```

## Resources

### scripts/find_reports.py

Python script to find and list historical RAG debug reports in the project root. Returns a list of report files with metadata (date, model) for comparison selection.

Usage:
```python
from scripts.find_reports import find_history_reports, load_report_data

reports = find_history_reports()  # Returns list of report files
data = load_report_data('rag-debug-2026-04-01-glm-4.6.md')  # Load specific report
```

This script is used in Step 4 (Comparison Mode) to discover previous test sessions.

## User Interaction Guidelines

- **Be conversational and friendly**: Use natural language, not robotic questions
- **Allow skipping**: If user doesn't have certain data, allow them to skip with "N/A" or "跳过"
- **Progressive disclosure**: Ask questions one section at a time, not all at once
- **Chinese language support**: Skill should support both English and Chinese
- **Show intermediate results**: After each section, briefly confirm what was recorded

## Example Output

After completing all steps, the user will have:
1. A detailed markdown report in the project root
2. A summary of key metrics and observations
3. (Optional) A comparison with previous tests showing improvements

## Notes

- All reports are saved in project root as `rag-debug-{DATE}-{MODEL}.md`
- The template file should exist at `/rag-debug-template.md` before using this skill
- Historical reports are automatically discovered for comparison mode
