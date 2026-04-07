# RAG Testing Pipeline - Complete Overview

## Pipeline Architecture

The RAG testing pipeline consists of three coordinated skills that work together to automate end-to-end RAG system evaluation:

```
┌─────────────────────┐
│  rag-dataset-gen    │
│  (Generate Tests)   │
└──────────┬──────────┘
           │ test_dataset.json
           ▼
┌─────────────────────┐
│   rag-batch-test    │
│  (Run Tests)        │
└──────────┬──────────┘
           │ rag-test-results-*.json
           ▼
┌─────────────────────┐
│     rag-debug       │
│  (Evaluate & Report)│
└─────────────────────┘
           │
           ▼
┌─────────────────────┐
│  Evaluation Report  │
│  (Markdown + Tables)│
└─────────────────────┘
```

## Skill 1: rag-dataset-gen

**Purpose**: Generate comprehensive test datasets from source documents.

**Two Modes**:

### 1. Document Analysis Mode (Offline)
- Analyze source documents (PDF, TXT, MD)
- Extract structure and key concepts
- Generate diverse questions (factual, conceptual, procedural)
- Simulate RAG chunking for expected chunk mappings
- Output: `test_dataset.json`

**Use when**: You have source documents but no access to the running system.

### 2. API-Based Mode (Online)
- Upload source files to notebook via API
- Trigger real ingestion pipeline
- Retrieve actual chunk IDs from database
- Create test cases with real chunk mappings
- Output: `test_dataset.json` with real chunk IDs

**Use when**: System is running and you want realistic test data.

**Key Scripts**:
- `scripts/generate_dataset.py` - Document analysis and question generation
- `scripts/document_parser.py` - Multi-format document parsing
- `scripts/upload_ingest.py` - API-based upload and ingestion
- `scripts/get_chunks.py` - Database chunk retrieval

**Output Format**:
```json
{
  "metadata": {
    "version": "1.0",
    "created": "2026-04-04",
    "sources": [...]
  },
  "test_cases": [
    {
      "id": "test-001",
      "question": "What is X?",
      "notebook_id": "uuid",
      "expected_chunks": ["chunk_id_1", "chunk_id_2"],
      "expected_keywords": ["keyword1", "keyword2"],
      "category": "factual"
    }
  ]
}
```

## Skill 2: rag-batch-test

**Purpose**: Execute test cases via chat API and record results.

**Workflow**:
1. Load `test_dataset.json`
2. Configure API connection
3. For each test case:
   - Call `/api/notebooks/{id}/chat/stream`
   - Parse SSE events (citations, answer, done/error)
   - Record retrieved chunks with IDs and scores
   - Capture timing metrics
4. Save results to `rag-test-results-*.json`

**Key Scripts**:
- `scripts/batch_test.py` - Main batch testing script

**Output Format**:
```json
{
  "timestamp": "2026-04-04T10:00:00Z",
  "total_tests": 25,
  "successful": 23,
  "failed": 2,
  "results": [
    {
      "test_id": "test-001",
      "question": "What is X?",
      "success": true,
      "answer": "X is...",
      "retrieved_chunks": [
        {
          "chunk_id": "uuid",
          "source_id": "uuid",
          "content": "...",
          "score": 0.95
        }
      ],
      "citation_indices": [1, 2],
      "total_time": 3.2
    }
  ]
}
```

**API Events Handled**:
- `event: status` - Status updates
- `event: citations` - Retrieved chunks with citation indices
- `event: answer` - Generated answer
- `event: done` - Completion
- `event: error` - Error details

## Skill 3: rag-debug

**Purpose**: Evaluate test results and generate comprehensive reports.

**Two Modes**:

### 1. Single-Test Mode (Manual)
- Record individual RAG debugging sessions
- Collect performance metrics and quality assessments
- Generate detailed markdown reports
- Support model comparison

**Use when**: Testing single questions or doing exploratory debugging.

### 2. Batch Evaluation Mode (Automated)
- Load `rag-test-results-*.json` and `test_dataset.json`
- Calculate metrics for each test case:
  - Recall@K: % of expected chunks found
  - MRR: Mean reciprocal rank
  - Citation Accuracy: % correct citations
- Generate aggregate statistics
- Create table-based reports
- Provide recommendations

**Use when**: Evaluating system performance on full test suite.

**Key Scripts**:
- `scripts/evaluate_batch.py` - Calculate evaluation metrics
- `scripts/generate_report.py` - Generate markdown reports
- `scripts/find_reports.py` - Find historical reports

**Metrics Calculated**:
| Metric | Formula | Target |
|--------|---------|--------|
| Recall@K | hits / \|relevant\| | ≥0.90 |
| MRR | 1 / rank_of_first_hit | ≥0.80 |
| Citation Accuracy | correct_citations / total_citations | ≥95% |
| Avg Time | sum(time) / count | ≤5s |

**Report Sections**:
1. Summary (test counts, success rate)
2. Aggregate Metrics (with target comparisons)
3. Per-Test Results (full table)
4. Category Breakdown (by question type)
5. Failed Tests (error details)
6. Recommendations (based on metrics)

## Complete Workflow Example

```bash
# Step 1: Generate test dataset (API mode)
python -m scripts.upload_ingest /path/to/document.pdf
python -m scripts.get_chunks --notebook <notebook_id>
python -m scripts.generate_dataset --api-mode

# Step 2: Run batch tests
python -m scripts.batch_test data/test_dataset.json <notebook_id>

# Step 3: Evaluate and generate report
python -m scripts.evaluate_batch rag-test-results-*.json data/test_dataset.json
python -m scripts.generate_report rag-test-results-*.json data/test_dataset.json
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_BASE_URL` | `http://localhost:8000` | API server URL |
| `DATABASE_URL` | `postgresql://localhost/notebooklx` | Database connection |
| `USER_ID` | auto-generated | User UUID for API calls |

## File Locations

```
project/
├── data/
│   └── test_dataset.json           # Generated test cases
├── rag-test-results-*.json         # Batch test results
├── rag-evaluation-report-*.md      # Final evaluation report
└── .claude/skills/
    ├── rag-dataset-gen/            # Test generation
    │   └── scripts/
    │       ├── generate_dataset.py
    │       ├── document_parser.py
    │       ├── upload_ingest.py
    │       └── get_chunks.py
    ├── rag-batch-test/             # Batch testing
    │   └── scripts/
    │       └── batch_test.py
    └── rag-debug/                  # Evaluation & reporting
        └── scripts/
            ├── evaluate_batch.py
            ├── generate_report.py
            └── find_reports.py
```

## Quick Reference

### Trigger Phrases

- **rag-dataset-gen**: "生成测试集", "generate test dataset", "创建 RAG 测试数据"
- **rag-batch-test**: "批量测试", "batch test", "运行测试集"
- **rag-debug**: "记录 RAG 测试", "rag debug", "评估测试结果"

### When to Use Each Skill

1. **Starting fresh**: Use `rag-dataset-gen` (API mode) to upload sources and generate test cases
2. **Have test dataset**: Use `rag-batch-test` to run all tests
3. **Have test results**: Use `rag-debug` (batch mode) to evaluate and report

### Integration Points

- `rag-dataset-gen` → `test_dataset.json` → `rag-batch-test`
- `rag-batch-test` → `rag-test-results-*.json` → `rag-debug`
- `rag-debug` → `rag-evaluation-report-*.md` (final output)

## Tips for Best Results

1. **Dataset Quality**: Review generated questions and expected chunks
2. **Test Diversity**: Include multiple question types and categories
3. **API Stability**: Ensure API server is running before batch tests
4. **Result Analysis**: Check failed tests first for system issues
5. **Iterate**: Use evaluation insights to improve chunking and retrieval
