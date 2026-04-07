---
name: rag-batch-test
description: Batch RAG testing via chat API - runs multiple test cases, records responses and retrieved chunks. Use after generating test dataset with rag-dataset-gen. Trigger phrases: "批量测试 RAG", "batch test", "运行测试集", "rag batch test". Automatically calls chat streaming API for each question, monitors chunk retrieval, captures citation data, and saves results for evaluation with rag-debug skill.
---

# RAG Batch Tester

## Overview

This skill runs batch tests on the RAG system by:
1. Loading test dataset from `test_dataset.json`
2. Calling chat streaming API for each question
3. Recording responses and retrieved chunks
4. Saving results for evaluation

## Quick Start

When triggered, this skill will:
1. Load the test dataset
2. Configure API connection
3. Run all test cases sequentially
4. Save results to JSON file
5. Display summary statistics

## Workflow

### Step 1: Load Dataset

Locate and load the test dataset:
```
请提供测试数据集路径 (test_dataset.json):
例如: data/test_dataset.json
```

Validate dataset structure:
- Check for `test_cases` array
- Verify `notebook_id` is set
- Confirm questions exist

### Step 2: Configure API

Ask for API configuration:
- **API Base URL**: Default `http://localhost:8000`
- **User ID**: Optional (auto-generated if not provided)
- **Top-K**: Default 5 (number of chunks to retrieve)

### Step 3: Run Tests

Execute each test case:
```python
for test_case in dataset["test_cases"]:
    # Call chat streaming API
    # Record SSE events: citations, answer, done/error
    # Store retrieved chunks with IDs and scores
    # Capture timing metrics
```

Monitor progress:
- Show current test number
- Display question preview
- Report success/failure
- Show timing and chunk count

### Step 4: Save Results

Save to `rag-test-results-{TIMESTAMP}.json`:
```json
{
  "timestamp": "2026-04-04T10:00:00Z",
  "total_tests": 25,
  "successful": 23,
  "failed": 2,
  "results": [
    {
      "test_id": "test-001",
      "question": "...",
      "success": true,
      "answer": "...",
      "retrieved_chunks": [
        {
          "chunk_id": "uuid",
          "source_id": "uuid",
          "content": "...",
          "score": 0.95,
          "page": 10
        }
      ],
      "citation_indices": [1, 2, 3],
      "total_time": 3.2,
      "timestamp": "2026-04-04T10:01:00Z"
    }
  ]
}
```

### Step 5: Display Summary

Show aggregate statistics:
- Total tests run
- Success rate
- Average response time
- Average chunks retrieved
- Failure details

## Resources

### scripts/batch_test.py

Main batch testing script.

Usage:
```python
from scripts.batch_test import batch_test_dataset

results = batch_test_dataset(
    dataset_path="data/test_dataset.json",
    notebook_id="uuid",
    api_base_url="http://localhost:8000",
    output_path="results.json",
    top_k=5
)
```

**Key classes:**
- `RAGBatchTester`: Main tester class
- `TestResult`: Dataclass for test results

**Methods:**
- `load_dataset(path)` - Load test dataset
- `run_single_test()` - Execute one test case
- `run_batch_test()` - Run all test cases
- `save_results(path)` - Save to JSON
- `generate_summary()` - Calculate statistics

## API Endpoints Used

- `POST /api/notebooks/{notebook_id}/chat/stream` - Streaming chat with citations

**SSE Events:**
- `event: status` - Status updates
- `event: citations` - Retrieved chunks with citation indices
- `event: answer` - Generated answer text
- `event: done` - Completion signal
- `event: error` - Error details

## Result Schema

Each test result contains:

| Field | Type | Description |
|-------|------|-------------|
| `test_id` | string | Test case identifier |
| `question` | string | Original question |
| `success` | boolean | Whether test completed |
| `answer` | string | Generated answer (if success) |
| `raw_answer` | string | Answer without citation markers |
| `retrieved_chunks` | array | Retrieved chunk details |
| `citation_indices` | array | Citation marker positions |
| `missing_citation_indices` | array | Failed citation links |
| `total_time` | float | Response time in seconds |
| `error_message` | string | Error details (if failed) |
| `timestamp` | string | ISO timestamp of test |

## Integration with rag-debug

After batch testing completes, use rag-debug skill to:

1. **Load results**: Parse `rag-test-results-*.json`
2. **Calculate metrics**:
   - Recall@K: % of expected chunks found
   - MRR: Mean reciprocal rank
   - Citation accuracy: % correct citations
3. **Generate report**: Create markdown evaluation report

## Error Handling

Tests fail when:
- API connection fails
- Request timeout (default 300s)
- SSE stream breaks
- Server returns error event

Failed tests are logged with:
- Error message
- Partial results (if any)
- Original question for retesting

## User Interaction Guidelines

- **Show progress**: Display test number and status
- **Early abort**: Allow Ctrl+C to stop testing
- **Partial results**: Save results even if some tests fail
- **Verbose mode**: Show chunk details on demand

## Notes

- Tests run sequentially (not parallel)
- Each test creates a new chat session
- Retrieved chunks include scores for ranking
- Citation markers indicate answer-chunk links
- Results file includes timestamps for audit trail
