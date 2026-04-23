"""
Arq worker bootstrap for the async ingestion pipeline.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable
import uuid

from arq.worker import Worker, func
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from services.api.core.database import SessionLocal
from services.api.modules.ingestion.models import IngestionJob, IngestionJobStatus
from services.api.modules.ingestion.queue import (
    INGESTION_TASK_NAME,
    get_ingestion_queue_settings,
    redis_settings_from_url,
)
from services.api.modules.notebooks.models import Notebook
from services.api.modules.sources.storage import get_object_storage
from services.api.modules.sources.models import Source, SourceStatus


logger = logging.getLogger(__name__)


DEFAULT_PROGRESS = {"step": "completed", "percentage": 100}
WORKER_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
WORKER_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
# Keep runtime ingestion concurrency conservative by default so large bulk queues
# do not overwhelm snapshot/embedding providers.
DEFAULT_MAX_JOBS = max(1, int(os.getenv("INGESTION_MAX_JOBS", "4")))
SQLITE_COMMIT_RETRY_ATTEMPTS = max(1, int(os.getenv("SQLITE_COMMIT_RETRY_ATTEMPTS", "6")))
SQLITE_COMMIT_RETRY_BASE_SECONDS = max(
    0.05,
    float(os.getenv("SQLITE_COMMIT_RETRY_BASE_SECONDS", "0.2")),
)


def configure_worker_logging() -> None:
    """Ensure worker-side ingestion monitor logs are visible at INFO level."""
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format=WORKER_LOG_FORMAT,
            datefmt=WORKER_LOG_DATE_FORMAT,
        )
    else:
        root_logger.setLevel(logging.INFO)

    logging.getLogger("services").setLevel(logging.INFO)


def ensure_main_thread_event_loop() -> None:
    """Install a default event loop for Python 3.14+ CLI startup."""
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())


ensure_main_thread_event_loop()
configure_worker_logging()


def utcnow() -> datetime:
    """Return a naive UTC timestamp without using deprecated utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _is_sqlite_locked_error(exc: Exception) -> bool:
    """Return True when the exception indicates SQLite lock contention."""
    return "database is locked" in str(exc).lower()


def _fallback_ingestion_error_message(exc: Exception) -> str:
    """Return a best-effort message when step-aware summarization is unavailable."""
    message = str(exc).strip()
    return message or "Ingestion failed."


async def _commit_with_retry(db: Session, *, operation: str) -> None:
    """Commit a session with bounded retries for transient SQLite write locks."""
    for attempt in range(1, SQLITE_COMMIT_RETRY_ATTEMPTS + 1):
        try:
            db.commit()
            return
        except OperationalError as exc:
            if not _is_sqlite_locked_error(exc) or attempt >= SQLITE_COMMIT_RETRY_ATTEMPTS:
                raise

            db.rollback()
            delay = SQLITE_COMMIT_RETRY_BASE_SECONDS * (2 ** (attempt - 1))
            logger.warning(
                "SQLite lock contention during %s (attempt %s/%s); retrying in %.2fs",
                operation,
                attempt,
                SQLITE_COMMIT_RETRY_ATTEMPTS,
                delay,
            )
            await asyncio.sleep(delay)


def build_user_facing_ingestion_error_message(exc: Exception) -> str:
    """Translate internal ingestion exceptions into user-facing status text."""
    fallback_message = _fallback_ingestion_error_message(exc)

    try:
        from services.api.modules.ingestion.orchestrator import summarize_ingestion_error
    except Exception:
        logger.exception("Failed to import ingestion error summarizer")
        return fallback_message

    try:
        user_facing_message = summarize_ingestion_error(exc)
    except Exception:
        logger.exception("Failed to summarize ingestion error")
        return fallback_message

    if user_facing_message == "Ingestion failed.":
        return fallback_message

    return user_facing_message


def load_active_source_and_job(
    *,
    db: Session,
    source_id: uuid.UUID,
    job_id: uuid.UUID,
) -> tuple[Source | None, IngestionJob | None]:
    """Return the source/job pair only while its parent notebook is active."""
    result = (
        db.query(Source, IngestionJob)
        .join(IngestionJob, IngestionJob.source_id == Source.id)
        .join(Notebook, Notebook.id == Source.notebook_id)
        .filter(
            Source.id == source_id,
            IngestionJob.id == job_id,
            Notebook.deleted_at.is_(None),
        )
        .first()
    )
    if result is None:
        return None, None

    return result


def assert_ingestion_not_cancelled(
    *,
    db: Session,
    source_id: uuid.UUID,
    job_id: uuid.UUID,
) -> None:
    """Abort a worker run when the source/job pair was deleted mid-flight."""
    from services.api.modules.ingestion.orchestrator import IngestionError

    source, job = load_active_source_and_job(db=db, source_id=source_id, job_id=job_id)
    if source is None or job is None:
        raise IngestionError("cancelled", "Source, notebook, or job was deleted")


async def run_ingestion_pipeline(
    source: Source,
    job: IngestionJob,
    db: Session,
    file_content_loader: Callable[[str], bytes] | None = None,
) -> dict[str, Any]:
    """
    Run the full ingestion pipeline: parse → chunk → embed → save.

    This orchestrates all ingestion steps for a source.
    """
    from services.api.modules.ingestion.orchestrator import (
        run_ingestion,
        IngestionProgress,
    )

    def update_job_progress(progress: IngestionProgress) -> None:
        """Persist job progress with short commits to avoid long SQLite write locks."""
        job.progress = progress.to_dict()
        try:
            db.commit()
        except OperationalError as exc:
            db.rollback()
            if _is_sqlite_locked_error(exc):
                logger.warning(
                    "Skipping progress persistence due to SQLite lock for source=%s job=%s",
                    source.id,
                    job.id,
                )
                return
            raise

    try:
        result = await run_ingestion(
            source=source,
            db=db,
            file_content_loader=file_content_loader,
            progress_callback=update_job_progress,
            cancellation_check=lambda: assert_ingestion_not_cancelled(
                db=db,
                source_id=source.id,
                job_id=job.id,
            ),
        )
        return result.to_dict()
    except Exception:
        logger.exception(
            "Ingestion pipeline failed for source %s job %s",
            source.id,
            job.id,
        )
        raise


async def on_worker_startup(ctx: dict[str, Any]) -> None:
    """Inject dependencies needed by worker jobs."""
    ctx.setdefault("session_factory", SessionLocal)


async def on_worker_shutdown(_: dict[str, Any]) -> None:
    """Arq startup/shutdown hook placeholder."""


def _get_file_content_loader(ctx: dict[str, Any]) -> Callable[[str], bytes] | None:
    """
    Get a file content loader from context or default to the configured storage backend.

    File paths are in format: {notebook_id}/{source_id}/{filename}
    """
    if "file_content_loader" in ctx:
        return ctx["file_content_loader"]

    storage = get_object_storage()

    def load_from_storage(file_path: str) -> bytes:
        return storage.load_bytes(file_path)

    return load_from_storage


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
        source, job = load_active_source_and_job(
            db=db,
            source_id=source_uuid,
            job_id=job_uuid,
        )
        if job is None or source is None:
            logger.info(
                "Skipping ingestion for deleted or missing source=%s job=%s",
                source_uuid,
                job_uuid,
            )
            return {"step": "cancelled", "percentage": 100}

        logger.info("Starting ingestion job source=%s job=%s", source.id, job.id)
        job.status = IngestionJobStatus.RUNNING
        job.started_at = utcnow()
        job.error_message = None
        source.status = SourceStatus.PROCESSING
        source.error_message = None
        await _commit_with_retry(db, operation="mark job running")

        # Get file content loader
        file_content_loader = _get_file_content_loader(ctx)

        # Run the full ingestion pipeline
        progress = await run_ingestion_pipeline(
            source, job, db,
            file_content_loader=file_content_loader,
        ) or DEFAULT_PROGRESS.copy()

        job.status = IngestionJobStatus.COMPLETED
        job.progress = progress
        job.completed_at = utcnow()
        job.error_message = None
        source.status = SourceStatus.READY
        source.error_message = None
        logger.info(
            "Completed ingestion job source=%s job=%s step=%s chunks=%s embeddings=%s",
            source.id,
            job.id,
            progress.get("step"),
            progress.get("chunks_created"),
            progress.get("embeddings_generated"),
        )
        await _commit_with_retry(db, operation="mark job completed")
        return progress
    except Exception as exc:
        db.rollback()
        source, job = load_active_source_and_job(
            db=db,
            source_id=source_uuid,
            job_id=job_uuid,
        )
        try:
            user_facing_error = build_user_facing_ingestion_error_message(exc)
        except Exception:
            logger.exception(
                "Failed to derive user-facing ingestion error source=%s job=%s",
                source_uuid,
                job_uuid,
            )
            user_facing_error = _fallback_ingestion_error_message(exc)

        if user_facing_error == "Ingestion was cancelled." and source is None and job is None:
            logger.info(
                "Cancelled ingestion for deleted source=%s job=%s",
                source_uuid,
                job_uuid,
            )
            return {"step": "cancelled", "percentage": 100}

        logger.exception("Ingestion job failed source=%s job=%s", source_uuid, job_uuid)

        if job is not None:
            job.status = IngestionJobStatus.FAILED
            job.error_message = user_facing_error
            job.completed_at = utcnow()

        if source is not None:
            source.status = SourceStatus.FAILED
            source.error_message = user_facing_error

        await _commit_with_retry(db, operation="mark job failed")
        raise
    finally:
        db.close()


def build_worker(
    *,
    redis_url: str | None = None,
    queue_name: str | None = None,
    session_factory: sessionmaker | None = None,
    burst: bool = False,
    max_jobs: int = DEFAULT_MAX_JOBS,
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
    max_jobs = DEFAULT_MAX_JOBS
    poll_delay = 0.1
    retry_jobs = False
    health_check_interval = 30
    keep_result = 3600
