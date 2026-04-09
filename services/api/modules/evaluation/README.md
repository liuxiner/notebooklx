# Evaluation Module

NotebookLX evaluation system for tracking retrieval, citation, and answer quality metrics.

## Overview

The evaluation module provides comprehensive metrics to assess the quality of your notebook's retrieval and Q&A system. It tracks how well chunks are retrieved, how accurate citations are, and how grounded and complete answers are.

## Features

### Metrics Tracked

#### Retrieval Metrics
- **Recall@K**: Percentage of relevant chunks found in top K results
  - `recall_at_5`: Relevant chunks in top 5
  - `recall_at_10`: Relevant chunks in top 10
- **MRR (Mean Reciprocal Rank)**: Average of 1/rank_of_first_relevant across queries

#### Citation Metrics
- **Citation Support Rate**: Percentage of citations that actually support the claims they reference
- **Wrong Citation Rate**: Percentage of citations that don't support their claims

#### Answer Quality Metrics
- **Groundedness**: How much of the answer comes from source content (0-1 scale)
- **Completeness**: How fully the answer addresses the question (0-1 scale)
- **Faithfulness**: Whether the answer contradicts source information (0-1 scale)

## API Endpoints

### Create Evaluation Run
```bash
POST /api/evaluation/runs
Content-Type: application/json

{
  "notebook_id": "uuid",
  "query": "What is machine learning?",
  "ground_truth_chunk_ids": ["uuid1", "uuid2"]  # Optional
}
```

### Start Evaluation
```bash
POST /api/evaluation/runs/{run_id}/start
```

### Get Single Evaluation
```bash
GET /api/evaluation/runs/{run_id}
```

### List Evaluations (with filters)
```bash
GET /api/evaluation/runs?notebook_id={uuid}&start_date={iso}&end_date={iso}
```

### Export Metrics as CSV
```bash
GET /api/evaluation/metrics/export?notebook_id={uuid}
```

## Usage Examples

### Python Client

```python
import requests

API_BASE = "http://localhost:8000"

# Create an evaluation run
response = requests.post(f"{API_BASE}/api/evaluation/runs", json={
    "notebook_id": "your-notebook-id",
    "query": "What topics are covered in my sources?",
    "ground_truth_chunk_ids": ["chunk-id-1", "chunk-id-2"]
})
run = response.json()

# Start the evaluation
response = requests.post(f"{API_BASE}/api/evaluation/runs/{run['id']}/start")

# Get results
response = requests.get(f"{API_BASE}/api/evaluation/runs/{run['id']}")
result = response.json()

print(f"Recall@5: {result['summary'].get('recall_at_5', 'N/A')}")
print(f"Citation Support: {result['summary'].get('citation_support_rate', 'N/A')}")
```

### Frontend Dashboard

Access the evaluation dashboard at `/evaluation` to:
- View summary metrics across all evaluations
- Filter by notebook and date range
- See detailed evaluation runs with metrics
- Export metrics as CSV

## Metric Calculations

### Recall@K
```
Recall@K = (relevant chunks in top K) / (total relevant chunks)
```

Higher is better. A value of 1.0 means all relevant chunks were found.

### MRR (Mean Reciprocal Rank)
```
MRR = average(1 / rank_of_first_relevant) for each query
```

Higher is better. A value of 1.0 means the first relevant result was always at rank 1.

### Citation Support Rate
```
Support Rate = (supported citations) / (total citations)
```

A citation is "supported" if the chunk content contains relevant keywords from the answer.

### Groundedness
```
Groundedness = (answer words from sources) / (total answer words)
```

Higher is better. Values closer to 1.0 indicate the answer stays within source content.

### Completeness
```
Completeness = min(1.0, answer_words / (question_words * 2))
```

Measures if the answer is sufficiently detailed relative to the question.

### Faithfulness
```
Faithfulness = 1.0 - (contradictions found) / (total statements)
```

Checks for contradiction keywords and verifies they appear in sources.

## Running Evaluations

Evaluations can be run:
1. **Manually** via API endpoints
2. **Scheduled** via automated evaluation jobs (future feature)
3. **On-demand** after adding new sources to a notebook

## Quality Targets

Based on `DEVELOPMENT_PLAN.md`, the target metrics are:

| Metric | Target |
|--------|--------|
| Recall@10 | > 90% |
| MRR | > 0.8 |
| Citation Support Rate | > 95% |
| Wrong Citation Rate | < 5% |
| Groundedness | > 90% |
| Completeness | > 85% |
| Faithfulness | > 95% |

## Testing

Run the evaluation tests:

```bash
PYTHONPATH=$(pwd) venv/bin/python -m pytest services/api/tests/test_evaluation.py -v
```

All 26 tests cover:
- API endpoint CRUD operations
- Metric calculation logic (recall, MRR, citations, quality)
- CSV export functionality
- Filtering and pagination

## Database Schema

### EvaluationRun Table
- `id`: UUID primary key
- `notebook_id`: Foreign key to notebooks
- `query`: The query being evaluated
- `status`: pending, running, completed, failed
- `error_message`: Error details if failed
- `created_at`, `started_at`, `completed_at`: Timestamps

### EvaluationMetric Table
- `id`: UUID primary key
- `evaluation_run_id`: Foreign key to evaluation_runs
- `metric_type`: Type of metric (recall_at_k, mrr, etc.)
- `metric_value`: Numeric value (0-1 for most metrics)
- `metric_metadata`: JSON metadata for additional context
- `created_at`: Timestamp

## Future Enhancements

Potential improvements for v2:
- **Automated evaluation scheduling**: Run evaluations periodically
- **LLM-based quality assessment**: Use GPT-4 to evaluate answer quality more accurately
- **Comparative evaluations**: Compare different retrieval strategies
- **A/B testing**: Test different chunk sizes or embedding models
- **Visualization**: Charts showing metric trends over time
- **Alerting**: Notify when metrics fall below thresholds

## Troubleshooting

### Low Recall@K
- Check if chunks are being created properly during ingestion
- Verify embeddings are being generated correctly
- Consider adjusting chunk size or overlap

### Low Citation Support Rate
- Review how citations are being generated
- Check if retrieved chunks are actually relevant
- Verify citation alignment logic

### Low Groundedness
- Review LLM prompts to ensure answers stay grounded
- Check if retrieved chunks contain sufficient information
- Consider increasing top_k for retrieval

## Contributing

When adding new metrics:
1. Add metric type to `MetricType` enum in `models.py`
2. Implement calculation logic in appropriate evaluator class
3. Add configuration to `METRIC_CONFIG` in frontend component
4. Write tests for the new metric
5. Update this README with metric details
