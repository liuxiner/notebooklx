"""
Pydantic schemas for ingestion pipeline endpoints.
"""
from datetime import datetime
from typing import Any
import uuid

from pydantic import BaseModel, ConfigDict, Field

from services.api.modules.ingestion.models import IngestionJobStatus
from services.api.modules.sources.models import SourceStatus


class IngestionJobResponse(BaseModel):
    """Response schema for enqueue and source ingestion status APIs."""

    model_config = ConfigDict(from_attributes=True)

    source_id: uuid.UUID
    status: SourceStatus
    job_id: uuid.UUID | None = None
    job_status: IngestionJobStatus | None = None
    task_id: str | None = None
    progress: dict[str, Any] | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class BulkIngestionRequest(BaseModel):
    """Request schema for enqueuing multiple sources in one call."""

    source_ids: list[uuid.UUID] = Field(..., min_length=1)


class BulkIngestionResponse(BaseModel):
    """Response schema for bulk-ingestion enqueue requests."""

    jobs: list[IngestionJobResponse]


class BulkIngestionStatusRequest(BaseModel):
    """Request schema for loading multiple source statuses in one call."""

    source_ids: list[uuid.UUID] = Field(..., min_length=1)


class BulkIngestionStatusResponse(BaseModel):
    """Response schema for bulk source-status requests."""

    statuses: list[IngestionJobResponse]
    has_pending_sources: bool


class IngestionQueueStatusResponse(BaseModel):
    """Aggregate queue status for the ingestion pipeline."""

    queued_jobs: int
    running_jobs: int
    failed_jobs: int
    completed_jobs: int


class IngestionHealthResponse(BaseModel):
    """Health response for the ingestion worker backend."""

    status: str
    redis: str
    worker: str
