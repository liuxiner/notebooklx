"""
Arq worker bootstrap for the async ingestion pipeline.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from arq.worker import Worker, func
from sqlalchemy.orm import Session, sessionmaker

from services.api.core.database import SessionLocal
from services.api.modules.ingestion.models import IngestionJob, IngestionJobStatus
from services.api.modules.ingestion.queue import (
    INGESTION_TASK_NAME,
    get_ingestion_queue_settings,
    redis_settings_from_url,
)
from services.api.modules.sources.models import Source, SourceStatus


DEFAULT_PROGRESS = {"step": "completed", "percentage": 100}


def utcnow() -> datetime:
    """Return a naive UTC timestamp without using deprecated utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def run_ingestion_pipeline(
    source: Source,
    job: IngestionJob,
    db: Session,
) -> dict[str, Any]:
    """
    Placeholder ingestion implementation for the pipeline skeleton.

    Later feature slices will replace this with parsing, chunking, and
    embedding orchestration. For now it records a successful completion state.
    """
    return DEFAULT_PROGRESS.copy()


async def on_worker_startup(ctx: dict[str, Any]) -> None:
    """Inject dependencies needed by worker jobs."""
    ctx.setdefault("session_factory", SessionLocal)


async def on_worker_shutdown(_: dict[str, Any]) -> None:
    """Arq startup/shutdown hook placeholder."""


async def ingest_source(ctx: dict[str, Any], source_id: str, ingestion_job_id: str) -> dict[str, Any]:
    """
    Execute a single source ingestion job.

    The worker persists job and source state transitions in the database so the
    API can report progress independently of Redis result retention.
    """
    session_factory: sessionmaker = ctx.get("session_factory", SessionLocal)
    db = session_factory()
    source_uuid = uuid.UUID(str(source_id))
    job_uuid = uuid.UUID(str(ingestion_job_id))

    try:
        job = db.query(IngestionJob).filter(IngestionJob.id == job_uuid).first()
        source = db.query(Source).filter(Source.id == source_uuid).first()
        if job is None or source is None:
            raise RuntimeError("Source or ingestion job not found")

        job.status = IngestionJobStatus.RUNNING
        job.started_at = utcnow()
        job.error_message = None
        source.status = SourceStatus.PROCESSING
        source.error_message = None
        db.commit()

        progress = run_ingestion_pipeline(source, job, db) or DEFAULT_PROGRESS.copy()

        job.status = IngestionJobStatus.COMPLETED
        job.progress = progress
        job.completed_at = utcnow()
        job.error_message = None
        source.status = SourceStatus.READY
        source.error_message = None
        db.commit()
        return progress
    except Exception as exc:
        db.rollback()
        job = db.query(IngestionJob).filter(IngestionJob.id == job_uuid).first()
        source = db.query(Source).filter(Source.id == source_uuid).first()

        if job is not None:
            job.status = IngestionJobStatus.FAILED
            job.error_message = str(exc)
            job.completed_at = utcnow()

        if source is not None:
            source.status = SourceStatus.FAILED
            source.error_message = str(exc)

        db.commit()
        raise
    finally:
        db.close()


def build_worker(
    *,
    redis_url: str | None = None,
    queue_name: str | None = None,
    session_factory: sessionmaker | None = None,
    burst: bool = False,
    max_jobs: int = 10,
) -> Worker:
    """Create a configured Arq worker instance."""
    settings = get_ingestion_queue_settings()
    resolved_redis_url = redis_url or settings.redis_url
    resolved_queue_name = queue_name or settings.queue_name

    return Worker(
        functions=[func(ingest_source, name=INGESTION_TASK_NAME, max_tries=1)],
        queue_name=resolved_queue_name,
        redis_settings=redis_settings_from_url(resolved_redis_url),
        on_startup=on_worker_startup,
        on_shutdown=on_worker_shutdown,
        ctx={"session_factory": session_factory or SessionLocal},
        burst=burst,
        max_jobs=max_jobs,
        handle_signals=False,
        poll_delay=0.1,
        retry_jobs=False,
        health_check_interval=30,
        keep_result=3600,
    )


_default_settings = get_ingestion_queue_settings()


class WorkerSettings:
    """Arq CLI settings for `arq services.worker.main.WorkerSettings`."""

    functions = [func(ingest_source, name=INGESTION_TASK_NAME, max_tries=1)]
    queue_name = _default_settings.queue_name
    redis_settings = redis_settings_from_url(_default_settings.redis_url)
    on_startup = on_worker_startup
    on_shutdown = on_worker_shutdown
    ctx = {"session_factory": SessionLocal}
    max_jobs = 10
    poll_delay = 0.1
    retry_jobs = False
    health_check_interval = 30
    keep_result = 3600
