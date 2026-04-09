"""
Evaluation module for metrics and evaluation dashboard.

Feature 6.3: Evaluation Dashboard

Acceptance Criteria:
- Track retrieval metrics: recall@5, recall@10, MRR
- Track citation metrics: support rate, wrong citation rate
- Track answer quality: groundedness, completeness, faithfulness
- Dashboard shows trends over time
- Filterable by notebook, time range
- Export metrics as CSV
"""
from services.api.modules.evaluation.models import (
    EvaluationRun,
    EvaluationMetric,
    EvaluationStatus,
    MetricType,
)
from services.api.modules.evaluation.schemas import (
    EvaluationCreate,
    EvaluationRunResponse,
    EvaluationDetailResponse,
    MetricValue,
    MetricsQuery,
    MetricsListResponse,
    EvaluationDatasetCreate,
)
from services.api.modules.evaluation.service import (
    RetrievalEvaluator,
    CitationEvaluator,
    AnswerQualityEvaluator,
    EvaluationService,
)

__all__ = [
    "EvaluationRun",
    "EvaluationMetric",
    "EvaluationStatus",
    "MetricType",
    "EvaluationCreate",
    "EvaluationRunResponse",
    "EvaluationDetailResponse",
    "MetricValue",
    "MetricsQuery",
    "MetricsListResponse",
    "EvaluationDatasetCreate",
    "RetrievalEvaluator",
    "CitationEvaluator",
    "AnswerQualityEvaluator",
    "EvaluationService",
]
