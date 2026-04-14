"""
Queue helpers for the async ingestion pipeline.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import dataclass
from urllib.parse import urlparse

from arq import create_pool
from arq.connections import RedisSettings
from arq.worker import async_check_health


DEFAULT_REDIS_URL = "redis://127.0.0.1:6379/0"
DEFAULT_QUEUE_NAME = "notebooklx:ingestion"
INGESTION_TASK_NAME = "ingest_source"


class IngestionQueueError(RuntimeError):
    """Raised when the ingestion queue cannot be reached."""


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    """Read an integer environment variable with a lower bound."""
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default

    try:
        return max(minimum, int(raw_value))
    except ValueError:
        return default


@dataclass(frozen=True)
class IngestionQueueSettings:
    """Environment-derived queue settings."""

    redis_url: str
    queue_name: str = DEFAULT_QUEUE_NAME


def get_ingestion_queue_settings() -> IngestionQueueSettings:
    """Read queue settings from the process environment."""
    return IngestionQueueSettings(
        redis_url=os.getenv("REDIS_URL", DEFAULT_REDIS_URL),
        queue_name=os.getenv("INGESTION_QUEUE_NAME", DEFAULT_QUEUE_NAME),
    )


def redis_settings_from_url(redis_url: str) -> RedisSettings:
    """Convert a Redis URL into Arq RedisSettings."""
    parsed = urlparse(redis_url)
    if parsed.scheme not in {"redis", "rediss"}:
        raise IngestionQueueError(f"Unsupported Redis URL scheme: {parsed.scheme or 'missing'}")

    database = 0
    if parsed.path and parsed.path != "/":
        database = int(parsed.path.strip("/"))

    conn_timeout_seconds = _env_int("REDIS_CONN_TIMEOUT_SECONDS", 5, minimum=1)
    conn_retries = _env_int("REDIS_CONN_RETRIES", 20, minimum=1)
    conn_retry_delay_seconds = _env_int("REDIS_CONN_RETRY_DELAY_SECONDS", 1, minimum=0)
    max_connections = _env_int("REDIS_MAX_CONNECTIONS", 200, minimum=1)
    retry_on_timeout = os.getenv("REDIS_RETRY_ON_TIMEOUT", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }

    return RedisSettings(
        host=parsed.hostname or "127.0.0.1",
        port=parsed.port or 6379,
        database=database,
        username=parsed.username,
        password=parsed.password,
        ssl=parsed.scheme == "rediss",
        conn_timeout=conn_timeout_seconds,
        conn_retries=conn_retries,
        conn_retry_delay=conn_retry_delay_seconds,
        max_connections=max_connections,
        retry_on_timeout=retry_on_timeout,
    )


class ArqIngestionQueue:
    """Sync-friendly wrapper around Arq enqueue and ping operations."""

    def __init__(self, settings: IngestionQueueSettings | None = None) -> None:
        self.settings = settings or get_ingestion_queue_settings()
        self.redis_settings = redis_settings_from_url(self.settings.redis_url)

    async def _enqueue_ingestion_async(
        self, source_id: uuid.UUID, ingestion_job_id: uuid.UUID
    ) -> str:
        redis = await create_pool(
            self.redis_settings,
            default_queue_name=self.settings.queue_name,
        )
        try:
            job = await redis.enqueue_job(
                INGESTION_TASK_NAME,
                str(source_id),
                str(ingestion_job_id),
                _queue_name=self.settings.queue_name,
            )
        finally:
            await redis.aclose(close_connection_pool=True)

        if job is None:
            raise IngestionQueueError("Arq rejected the ingestion job request")

        return job.job_id

    async def _ping_async(self) -> bool:
        redis = await create_pool(
            self.redis_settings,
            default_queue_name=self.settings.queue_name,
        )
        try:
            pong = await redis.ping()
        finally:
            await redis.aclose(close_connection_pool=True)

        return bool(pong)

    async def _worker_ping_async(self) -> bool:
        exit_code = await async_check_health(
            self.redis_settings,
            queue_name=self.settings.queue_name,
        )
        return exit_code == 0

    def enqueue_ingestion(self, *, source_id: uuid.UUID, ingestion_job_id: uuid.UUID) -> str:
        """Enqueue an ingestion task and return the Arq task ID."""
        try:
            return asyncio.run(
                self._enqueue_ingestion_async(
                    source_id=source_id,
                    ingestion_job_id=ingestion_job_id,
                )
            )
        except IngestionQueueError:
            raise
        except Exception as exc:  # pragma: no cover - exercised via HTTP layer
            raise IngestionQueueError(str(exc)) from exc

    def ping(self) -> bool:
        """Check whether the queue backend is reachable."""
        try:
            return asyncio.run(self._ping_async())
        except Exception as exc:  # pragma: no cover - health endpoint handles status mapping
            raise IngestionQueueError(str(exc)) from exc

    def worker_ping(self) -> bool:
        """Check whether an ingestion worker heartbeat is present."""
        try:
            return asyncio.run(self._worker_ping_async())
        except Exception as exc:  # pragma: no cover - health endpoint handles status mapping
            raise IngestionQueueError(str(exc)) from exc


def get_ingestion_queue() -> ArqIngestionQueue:
    """Return the default ingestion queue client."""
    return ArqIngestionQueue()
