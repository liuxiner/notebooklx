"""
Pydantic schemas for evaluation API request/response validation.

Feature 6.3: Evaluation Dashboard
"""
from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import datetime
from typing import Optional, List, Dict, Any
import uuid

from services.api.modules.evaluation.models import EvaluationStatus, MetricType


class EvaluationCreate(BaseModel):
    """Schema for creating a new evaluation run."""
    notebook_id: uuid.UUID = Field(..., description="Notebook ID to evaluate")
    query: str = Field(..., min_length=1, max_length=1000, description="Query to evaluate")
    ground_truth_chunk_ids: Optional[List[uuid.UUID]] = Field(
        default=None,
        description="List of ground truth chunk IDs for evaluation (for retrieval metrics)"
    )


class EvaluationRunResponse(BaseModel):
    """Schema for evaluation run response data."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    notebook_id: uuid.UUID
    query: str
    status: EvaluationStatus
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class MetricValue(BaseModel):
    """Schema for a single metric value."""
    model_config = ConfigDict(from_attributes=True)

    metric_type: MetricType
    metric_value: float
    metadata: Optional[Dict[str, Any]] = None


class EvaluationDetailResponse(EvaluationRunResponse):
    """Schema for evaluation run with included metrics."""
    model_config = ConfigDict(from_attributes=True)

    metrics: List[MetricValue] = []


class EvaluationMetricCreate(BaseModel):
    """Schema for creating evaluation metrics (internal use)."""
    evaluation_run_id: uuid.UUID
    metric_type: MetricType
    metric_value: float
    metadata: Optional[str] = None


class MetricsQuery(BaseModel):
    """Schema for querying metrics with filters."""
    model_config = ConfigDict(from_attributes=True)

    notebook_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Filter by notebook ID"
    )
    start_date: Optional[datetime] = Field(
        default=None,
        description="Filter by start date"
    )
    end_date: Optional[datetime] = Field(
        default=None,
        description="Filter by end date"
    )
    metric_types: Optional[List[MetricType]] = Field(
        default=None,
        description="Filter by metric types"
    )


class MetricsListResponse(BaseModel):
    """Schema for metrics list response."""
    model_config = ConfigDict(from_attributes=True)

    evaluation_runs: List[EvaluationDetailResponse]
    summary: Dict[str, float]


class EvaluationDatasetItem(BaseModel):
    """Schema for evaluation dataset question-answer pair."""
    model_config = ConfigDict(from_attributes=True)

    question: str
    answer: str
    ground_truth_chunk_ids: List[uuid.UUID]
    notebook_id: uuid.UUID


class EvaluationDatasetCreate(BaseModel):
    """Schema for creating evaluation dataset."""
    model_config = ConfigDict(from_attributes=True)

    items: List[EvaluationDatasetItem]


class RecallAtKMetric(BaseModel):
    """Schema for recall@K metric."""
    model_config = ConfigDict(from_attributes=True)

    k: int = Field(..., ge=1, description="K value for recall@K")
    recall: float = Field(..., ge=0, le=1, description="Recall value (0-1)")
    total_relevant: int = Field(..., ge=0, description="Total relevant chunks")
    retrieved_relevant: int = Field(..., ge=0, description="Relevant chunks found")


class MRRMetric(BaseModel):
    """Schema for Mean Reciprocal Rank metric."""
    model_config = ConfigDict(from_attributes=True)

    mrr: float = Field(..., ge=0, description="MRR value")
    query_count: int = Field(..., ge=0, description="Number of queries evaluated")


class CitationMetric(BaseModel):
    """Schema for citation-related metrics."""
    model_config = ConfigDict(from_attributes=True)

    support_rate: float = Field(..., ge=0, le=1, description="Citation support rate")
    wrong_citation_rate: float = Field(..., ge=0, le=1, description="Wrong citation rate")
    total_citations: int = Field(..., ge=0, description="Total citations evaluated")


class AnswerQualityMetric(BaseModel):
    """Schema for answer quality metrics."""
    model_config = ConfigDict(from_attributes=True)

    groundedness: float = Field(..., ge=0, le=1, description="Groundedness score")
    completeness: float = Field(..., ge=0, le=1, description="Completeness score")
    faithfulness: float = Field(..., ge=0, le=1, description="Faithfulness score")
    total_answers: int = Field(..., ge=0, description="Total answers evaluated")
