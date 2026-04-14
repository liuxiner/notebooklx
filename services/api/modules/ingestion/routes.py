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
    BulkIngestionRequest,
    BulkIngestionResponse,
    BulkIngestionStatusRequest,
    BulkIngestionStatusResponse,
    IngestionHealthResponse,
    IngestionJobResponse,
    IngestionQueueStatusResponse,
)
from services.api.modules.notebooks.models import Notebook
from services.api.modules.notebooks.routes import get_current_user_id
from services.api.modules.sources.models import Source, SourceStatus
from services.api.modules.chunking.models import SourceChunk


router = APIRouter(prefix="/api", tags=["ingestion"])
MAX_BULK_INGESTION_SOURCES = 50


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


def get_sources_for_user(
    source_ids: list[uuid.UUID],
    user_id: uuid.UUID,
    db: Session,
) -> list[Source]:
    """Load multiple sources that all belong to the current user's live notebooks."""
    sources = (
        db.query(Source)
        .join(Notebook, Notebook.id == Source.notebook_id)
        .filter(
            Source.id.in_(source_ids),
            Notebook.user_id == user_id,
            Notebook.deleted_at.is_(None),
        )
        .all()
    )
    source_lookup = {source.id: source for source in sources}
    missing_source_id = next(
        (source_id for source_id in source_ids if source_id not in source_lookup),
        None,
    )

    if missing_source_id is not None:
        raise build_error(
            status.HTTP_404_NOT_FOUND,
            "not_found",
            f"Source {missing_source_id} not found",
        )

    return [source_lookup[source_id] for source_id in source_ids]


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


def get_latest_jobs_for_sources(
    source_ids: list[uuid.UUID],
    db: Session,
) -> dict[uuid.UUID, IngestionJob]:
    """Return the latest ingestion job per source for the provided ids."""
    jobs = (
        db.query(IngestionJob)
        .filter(IngestionJob.source_id.in_(source_ids))
        .order_by(IngestionJob.created_at.desc(), IngestionJob.id.desc())
        .all()
    )
    latest_jobs: dict[uuid.UUID, IngestionJob] = {}

    for job in jobs:
        latest_jobs.setdefault(job.source_id, job)

    return latest_jobs


def is_resolved_source_status(status: SourceStatus) -> bool:
    """Return whether a source has reached a terminal ingestion state."""
    return status in {SourceStatus.READY, SourceStatus.FAILED}


def enqueue_ingestion_job_for_source(
    source: Source,
    db: Session,
    queue=None,
) -> tuple[IngestionJob, str | None]:
    """Create and enqueue one ingestion job, returning any enqueue error string."""
    queue_client = queue or get_ingestion_queue()
    source.status = SourceStatus.PENDING
    source.error_message = None

    job = IngestionJob(source_id=source.id, status=IngestionJobStatus.QUEUED)
    db.add(job)
    db.flush()

    try:
        job.task_id = queue_client.enqueue_ingestion(
            source_id=source.id,
            ingestion_job_id=job.id,
        )
    except IngestionQueueError as exc:
        source.status = SourceStatus.FAILED
        source.error_message = str(exc)
        job.status = IngestionJobStatus.FAILED
        job.error_message = str(exc)
        job.completed_at = utcnow()
        return job, str(exc)

    return job, None


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
    job, error_message = enqueue_ingestion_job_for_source(
        source,
        db,
        queue=get_ingestion_queue(),
    )

    if error_message is not None:
        db.commit()
        raise build_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "ingestion_enqueue_failed",
            "Failed to enqueue ingestion task",
        )

    db.commit()
    db.refresh(source)
    db.refresh(job)
    return build_status_response(source, job)


@router.post(
    "/sources/ingest/batch",
    response_model=BulkIngestionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_sources_ingestion_batch(
    payload: BulkIngestionRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """
    Enqueue multiple sources for background ingestion in one request.

    AC: Ingestion API accepts multiple source IDs in one enqueue request
    AC: Bulk ingestion validates ownership/not-found before enqueuing
    """
    if len(payload.source_ids) > MAX_BULK_INGESTION_SOURCES:
        raise build_error(
            status.HTTP_400_BAD_REQUEST,
            "validation_error",
            f"Bulk ingestion supports up to {MAX_BULK_INGESTION_SOURCES} sources per request.",
        )

    sources = get_sources_for_user(payload.source_ids, user_id, db)
    jobs: list[IngestionJobResponse] = []
    queue = get_ingestion_queue()

    for source in sources:
        job, _ = enqueue_ingestion_job_for_source(source, db, queue=queue)
        jobs.append(build_status_response(source, job))

    db.commit()
    return BulkIngestionResponse(jobs=jobs)


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


@router.post("/sources/status/batch", response_model=BulkIngestionStatusResponse)
def get_sources_ingestion_status_batch(
    payload: BulkIngestionStatusRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """
    Get the latest ingestion status for multiple sources in one request.

    AC: Bulk status returns latest payloads in request order
    AC: Bulk status indicates whether any requested source is unresolved
    """
    if len(payload.source_ids) > MAX_BULK_INGESTION_SOURCES:
        raise build_error(
            status.HTTP_400_BAD_REQUEST,
            "validation_error",
            f"Bulk status supports up to {MAX_BULK_INGESTION_SOURCES} sources per request.",
        )

    sources = get_sources_for_user(payload.source_ids, user_id, db)
    latest_jobs = get_latest_jobs_for_sources(payload.source_ids, db)
    statuses = [
      build_status_response(source, latest_jobs.get(source.id))
      for source in sources
    ]

    return BulkIngestionStatusResponse(
        statuses=statuses,
        has_pending_sources=any(
            not is_resolved_source_status(status.status) for status in statuses
        ),
    )


@router.delete(
    "/sources/{source_id}/ingestion",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_source_ingestion_data(
    source_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> None:
    """
    Remove ingestion jobs/chunks for a source and reset its status.

    AC: Ingestion data can be cleared for a source (jobs + chunks).
    """
    source = get_source_for_user(source_id, user_id, db)

    db.query(IngestionJob).filter(IngestionJob.source_id == source.id).delete(
        synchronize_session=False
    )
    db.query(SourceChunk).filter(SourceChunk.source_id == source.id).delete(
        synchronize_session=False
    )
    source.status = SourceStatus.PENDING
    source.error_message = None
    db.commit()
    return None


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
