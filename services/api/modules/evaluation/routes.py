"""
API routes for evaluation and metrics.

Feature 6.3: Evaluation Dashboard
"""
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from services.api.core.database import get_db
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
from services.api.modules.evaluation.service import EvaluationService
from services.api.modules.notebooks.models import Notebook
from services.api.modules.notebooks.routes import get_current_user_id


router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])


def build_error(status_code: int, error: str, message: str) -> HTTPException:
    """Create a consistent HTTPException payload."""
    return HTTPException(
        status_code=status_code,
        detail={"error": error, "message": message},
    )


def _get_notebook_for_user(
    notebook_id: uuid.UUID,
    db: Session,
    user_id: uuid.UUID,
) -> Notebook:
    """Get notebook for user with ownership check."""
    notebook = (
        db.query(Notebook)
        .filter(
            Notebook.id == notebook_id,
            Notebook.user_id == user_id,
            Notebook.deleted_at.is_(None),
        )
        .first()
    )

    if not notebook:
        raise build_error(
            status.HTTP_404_NOT_FOUND,
            "not_found",
            f"Notebook {notebook_id} not found",
        )

    return notebook


@router.post(
    "/runs",
    response_model=EvaluationRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_evaluation(
    data: EvaluationCreate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """
    Create a new evaluation run.

    AC: Create evaluation dataset
    AC: Track retrieval metrics: recall@5, recall@10, MRR
    AC: Track citation metrics: support rate, wrong citation rate
    AC: Track answer quality: groundedness, completeness, faithfulness
    """
    # Verify notebook ownership
    _get_notebook_for_user(data.notebook_id, db, user_id)

    # Create evaluation run
    evaluation_run = EvaluationRun(
        notebook_id=data.notebook_id,
        query=data.query,
        ground_truth_chunk_ids=[str(chunk_id) for chunk_id in data.ground_truth_chunk_ids]
        if data.ground_truth_chunk_ids
        else None,
        status=EvaluationStatus.PENDING,
    )
    db.add(evaluation_run)
    db.commit()
    db.refresh(evaluation_run)

    # TODO: Actually run the evaluation (this would be async in production)
    # For now, return the created evaluation run

    return evaluation_run


@router.post("/runs/{run_id}/start", response_model=EvaluationRunResponse)
def start_evaluation(
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """
    Start an evaluation run.

    AC: Track retrieval metrics: recall@5, recall@10, MRR
    AC: Track citation metrics: support rate, wrong citation rate
    AC: Track answer quality: groundedness, completeness, faithfulness
    """
    from services.api.modules.evaluation.models import EvaluationRun

    evaluation_run = (
        db.query(EvaluationRun)
        .filter(EvaluationRun.id == run_id)
        .first()
    )

    if not evaluation_run:
        raise build_error(
            status.HTTP_404_NOT_FOUND,
            "not_found",
            f"Evaluation run {run_id} not found",
        )

    # Verify notebook ownership
    _get_notebook_for_user(evaluation_run.notebook_id, db, user_id)

    # Update status to running
    evaluation_run.status = EvaluationStatus.RUNNING
    evaluation_run.started_at = datetime.utcnow()
    db.commit()
    db.refresh(evaluation_run)

    try:
        evaluation_service = EvaluationService(db)
        ground_truth_chunk_ids = [
            uuid.UUID(str(chunk_id))
            for chunk_id in (evaluation_run.ground_truth_chunk_ids or [])
        ]
        retrieved_chunk_ids, retrieved_chunks = evaluation_service.retrieve_chunks_for_query(
            notebook_id=evaluation_run.notebook_id,
            query=evaluation_run.query,
            top_k=10,
        )
        computed_metrics = evaluation_service.run_evaluation(
            evaluation_run=evaluation_run,
            retrieved_chunk_ids_list=[retrieved_chunk_ids] if ground_truth_chunk_ids else [],
            ground_truth_chunk_ids_list=[ground_truth_chunk_ids] if ground_truth_chunk_ids else [],
            answers=[],
            questions=[],
            retrieved_chunks_list=[retrieved_chunks] if retrieved_chunks else [],
        )

        (
            db.query(EvaluationMetric)
            .filter(EvaluationMetric.evaluation_run_id == evaluation_run.id)
            .delete(synchronize_session=False)
        )

        for metric_type, metric_payload in computed_metrics.items():
            metric = EvaluationMetric(
                evaluation_run_id=evaluation_run.id,
                metric_type=MetricType(metric_type),
                metric_value=metric_payload["value"],
                metric_metadata=json.dumps(metric_payload["metadata"])
                if metric_payload.get("metadata") is not None
                else None,
            )
            db.add(metric)

        evaluation_run.status = EvaluationStatus.COMPLETED
        evaluation_run.completed_at = datetime.utcnow()
        evaluation_run.error_message = None
        db.commit()
        db.refresh(evaluation_run)
    except Exception as exc:
        db.rollback()
        evaluation_run = (
            db.query(EvaluationRun)
            .filter(EvaluationRun.id == run_id)
            .first()
        )
        if not evaluation_run:
            raise

        evaluation_run.status = EvaluationStatus.FAILED
        evaluation_run.error_message = str(exc)
        evaluation_run.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(evaluation_run)

    return evaluation_run


@router.get("/runs/{run_id}", response_model=EvaluationDetailResponse)
def get_evaluation(
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """
    Get a single evaluation run by ID with metrics.

    AC: Get single evaluation by ID with all metadata
    """
    from services.api.modules.evaluation.models import EvaluationRun

    evaluation_run = (
        db.query(EvaluationRun)
        .filter(EvaluationRun.id == run_id)
        .first()
    )

    if not evaluation_run:
        raise build_error(
            status.HTTP_404_NOT_FOUND,
            "not_found",
            f"Evaluation run {run_id} not found",
        )

    # Verify notebook ownership
    _get_notebook_for_user(evaluation_run.notebook_id, db, user_id)

    # Get associated metrics
    metrics = (
        db.query(EvaluationMetric)
        .filter(EvaluationMetric.evaluation_run_id == run_id)
        .all()
    )

    metric_values = [
        MetricValue(
            metric_type=metric.metric_type,
            metric_value=metric.metric_value,
            metadata=_parse_metadata(metric.metric_metadata) if metric.metric_metadata else None,
        )
        for metric in metrics
    ]

    return EvaluationDetailResponse(
        id=evaluation_run.id,
        notebook_id=evaluation_run.notebook_id,
        query=evaluation_run.query,
        status=evaluation_run.status,
        error_message=evaluation_run.error_message,
        created_at=evaluation_run.created_at,
        started_at=evaluation_run.started_at,
        completed_at=evaluation_run.completed_at,
        metrics=metric_values,
    )


@router.get("/runs", response_model=MetricsListResponse)
def list_evaluations(
    notebook_id: uuid.UUID | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    metric_types: List[MetricType] | None = None,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """
    List evaluation runs with optional filtering.

    AC: Dashboard shows trends over time
    AC: Filterable by notebook, time range
    """
    from services.api.modules.evaluation.models import EvaluationRun, EvaluationMetric

    # Build base query
    query = db.query(EvaluationRun)

    # Join with metrics if metric_types filter is provided
    if metric_types:
        query = (
            query.join(EvaluationMetric, EvaluationRun.id == EvaluationMetric.evaluation_run_id)
            .filter(EvaluationMetric.metric_type.in_(metric_types))
        )

    # Filter by notebook ownership
    query = query.join(Notebook, EvaluationRun.notebook_id == Notebook.id).filter(
        Notebook.user_id == user_id
    )

    # Apply filters
    if notebook_id is not None:
        query = query.filter(EvaluationRun.notebook_id == notebook_id)

    if start_date is not None:
        query = query.filter(EvaluationRun.created_at >= start_date)

    if end_date is not None:
        query = query.filter(EvaluationRun.created_at <= end_date)

    # Order by created_at descending
    query = query.order_by(EvaluationRun.created_at.desc())

    evaluation_runs = query.all()

    # Fetch metrics for each evaluation run
    runs_with_metrics = []
    summary_metrics: Dict[str, List[float]] = {
        metric_type.value: [] for metric_type in MetricType
    }

    for run in evaluation_runs:
        metrics = (
            db.query(EvaluationMetric)
            .filter(EvaluationMetric.evaluation_run_id == run.id)
            .all()
        )

        metric_values = [
            MetricValue(
                metric_type=metric.metric_type,
                metric_value=metric.metric_value,
                metadata=_parse_metadata(metric.metric_metadata) if metric.metric_metadata else None,
            )
            for metric in metrics
        ]

        # Collect for summary
        for metric in metrics:
            summary_metrics[metric.metric_type.value].append(metric.metric_value)

        runs_with_metrics.append(
            EvaluationDetailResponse(
                id=run.id,
                notebook_id=run.notebook_id,
                query=run.query,
                status=run.status,
                error_message=run.error_message,
                created_at=run.created_at,
                started_at=run.started_at,
                completed_at=run.completed_at,
                metrics=metric_values,
            )
        )

    # Calculate summary statistics
    summary: Dict[str, float] = {}
    for metric_type, values in summary_metrics.items():
        if values:
            summary[metric_type] = sum(values) / len(values)

    return MetricsListResponse(
        evaluation_runs=runs_with_metrics,
        summary=summary,
    )


@router.get("/metrics/export")
def export_metrics_csv(
    notebook_id: uuid.UUID | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    metric_types: List[MetricType] | None = None,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """
    Export evaluation metrics as CSV.

    AC: Export metrics as CSV
    """
    from services.api.modules.evaluation.models import EvaluationRun, EvaluationMetric

    # Get filtered evaluation runs (same logic as list_evaluations)
    query = db.query(EvaluationRun)

    if metric_types:
        query = (
            query.join(EvaluationMetric, EvaluationRun.id == EvaluationMetric.evaluation_run_id)
            .filter(EvaluationMetric.metric_type.in_(metric_types))
        )

    query = query.join(Notebook, EvaluationRun.notebook_id == Notebook.id).filter(
        Notebook.user_id == user_id
    )

    if notebook_id is not None:
        query = query.filter(EvaluationRun.notebook_id == notebook_id)

    if start_date is not None:
        query = query.filter(EvaluationRun.created_at >= start_date)

    if end_date is not None:
        query = query.filter(EvaluationRun.created_at <= end_date)

    query = query.order_by(EvaluationRun.created_at.desc())

    evaluation_runs = query.all()

    # Get all metrics
    all_metrics = []
    for run in evaluation_runs:
        metrics = (
            db.query(EvaluationMetric)
            .filter(EvaluationMetric.evaluation_run_id == run.id)
            .all()
        )

        for metric in metrics:
            all_metrics.append(
                {
                    "run_id": str(run.id),
                    "notebook_id": str(run.notebook_id),
                    "query": run.query,
                    "status": run.status.value,
                    "metric_type": metric.metric_type.value,
                    "metric_value": metric.metric_value,
                    "created_at": run.created_at.isoformat(),
                    "completed_at": run.completed_at.isoformat() if run.completed_at else "",
                    "metadata": metric.metric_metadata if metric.metric_metadata else "",
                }
            )

    # Generate CSV
    import csv
    import io

    output = io.StringIO()
    if all_metrics:
        writer = csv.DictWriter(output, fieldnames=[
            "run_id",
            "notebook_id",
            "query",
            "status",
            "metric_type",
            "metric_value",
            "created_at",
            "completed_at",
            "metadata",
        ])
        writer.writeheader()
        writer.writerows(all_metrics)

    from fastapi.responses import Response

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=evaluation_metrics.csv",
        },
    )


def _parse_metadata(metadata: str | None) -> Dict[str, Any] | None:
    """Parse JSON metadata from string."""
    if not metadata:
        return None
    try:
        import json
        return json.loads(metadata)
    except (json.JSONDecodeError, TypeError):
        return None
