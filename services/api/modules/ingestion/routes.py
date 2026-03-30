"""
API routes for ingestion queue operations and task status.
"""
from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from services.api.core.database import get_db
from services.api.modules.ingestion.models import IngestionJob, IngestionJobStatus
from services.api.modules.ingestion.queue import IngestionQueueError, get_ingestion_queue
from services.api.modules.ingestion.schemas import (
    IngestionHealthResponse,
    IngestionJobResponse,
    IngestionQueueStatusResponse,
)
from services.api.modules.notebooks.models import Notebook
from services.api.modules.notebooks.routes import get_current_user_id
from services.api.modules.sources.models import Source, SourceStatus


router = APIRouter(prefix="/api", tags=["ingestion"])


def utcnow() -> datetime:
    """Return a naive UTC timestamp without using deprecated utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def build_error(status_code: int, error: str, message: str) -> HTTPException:
    """Create a consistent HTTPException payload."""
    return HTTPException(
        status_code=status_code,
        detail={"error": error, "message": message},
    )


def get_source_for_user(
    source_id: uuid.UUID,
    user_id: uuid.UUID,
    db: Session,
) -> Source:
    """Load a source that belongs to one of the current user's live notebooks."""
    source = (
        db.query(Source)
        .join(Notebook, Notebook.id == Source.notebook_id)
        .filter(
            Source.id == source_id,
            Notebook.user_id == user_id,
            Notebook.deleted_at.is_(None),
        )
        .first()
    )

    if not source:
        raise build_error(
            status.HTTP_404_NOT_FOUND,
            "not_found",
            f"Source {source_id} not found",
        )

    return source


def build_status_response(source: Source, job: IngestionJob | None) -> IngestionJobResponse:
    """Create the API response shape for source/job status queries."""
    return IngestionJobResponse(
        source_id=source.id,
        status=source.status,
        job_id=job.id if job else None,
        job_status=job.status if job else None,
        task_id=job.task_id if job else None,
        progress=job.progress if job else None,
        error_message=job.error_message if job else source.error_message,
        started_at=job.started_at if job else None,
        completed_at=job.completed_at if job else None,
    )


@router.post(
    "/sources/{source_id}/ingest",
    response_model=IngestionJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_source_ingestion(
    source_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """
    Enqueue a source for background ingestion.

    AC: Can enqueue ingestion tasks
    AC: Failed tasks are logged with error details
    """
    source = get_source_for_user(source_id, user_id, db)
    source.status = SourceStatus.PENDING
    source.error_message = None

    job = IngestionJob(source_id=source.id, status=IngestionJobStatus.QUEUED)
    db.add(job)
    db.flush()

    try:
        job.task_id = get_ingestion_queue().enqueue_ingestion(
            source_id=source.id,
            ingestion_job_id=job.id,
        )
    except IngestionQueueError as exc:
        source.status = SourceStatus.FAILED
        source.error_message = str(exc)
        job.status = IngestionJobStatus.FAILED
        job.error_message = str(exc)
        job.completed_at = utcnow()
        db.commit()
        raise build_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "ingestion_enqueue_failed",
            "Failed to enqueue ingestion task",
        ) from exc

    db.commit()
    db.refresh(source)
    db.refresh(job)
    return build_status_response(source, job)


@router.get("/sources/{source_id}/status", response_model=IngestionJobResponse)
def get_source_ingestion_status(
    source_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """
    Get the current ingestion status for a source.

    AC: Task status can be queried
    """
    source = get_source_for_user(source_id, user_id, db)
    job = (
        db.query(IngestionJob)
        .filter(IngestionJob.source_id == source.id)
        .order_by(IngestionJob.created_at.desc())
        .first()
    )
    return build_status_response(source, job)


@router.get("/status/ingestion", response_model=IngestionQueueStatusResponse)
def get_ingestion_queue_status(
    db: Session = Depends(get_db),
    _: uuid.UUID = Depends(get_current_user_id),
):
    """Return aggregate ingestion queue counts."""
    counts = {
        row[0]: row[1]
        for row in db.query(IngestionJob.status, func.count(IngestionJob.id))
        .group_by(IngestionJob.status)
        .all()
    }

    return IngestionQueueStatusResponse(
        queued_jobs=counts.get(IngestionJobStatus.QUEUED, 0),
        running_jobs=counts.get(IngestionJobStatus.RUNNING, 0),
        failed_jobs=counts.get(IngestionJobStatus.FAILED, 0),
        completed_jobs=counts.get(IngestionJobStatus.COMPLETED, 0),
    )


@router.get("/status/ingestion/health", response_model=IngestionHealthResponse)
def get_ingestion_health(
    _: uuid.UUID = Depends(get_current_user_id),
):
    """Return ingestion worker backend health information."""
    queue = get_ingestion_queue()

    try:
        redis_connected = queue.ping()
    except IngestionQueueError:
        redis_connected = False
        worker_connected = False
    else:
        try:
            worker_connected = queue.worker_ping()
        except IngestionQueueError:
            worker_connected = False

    return IngestionHealthResponse(
        status="healthy" if redis_connected and worker_connected else "degraded",
        redis="connected" if redis_connected else "disconnected",
        worker="connected" if worker_connected else "disconnected",
    )
