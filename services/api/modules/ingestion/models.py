"""
SQLAlchemy models for ingestion jobs.
"""
from datetime import datetime
import enum
import uuid

from sqlalchemy import Column, DateTime, Enum as SQLEnum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from services.api.core.database import Base
from services.api.modules.notebooks.models import UUID


class IngestionJobStatus(str, enum.Enum):
    """Enumeration of ingestion job states."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class IngestionJob(Base):
    """
    Track async ingestion work for a source.

    Jobs are persisted separately from the queue so status can be queried from
    the API regardless of the worker process lifecycle.
    """

    __tablename__ = "ingestion_jobs"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    source_id = Column(
        UUID,
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(
        SQLEnum(IngestionJobStatus, values_callable=lambda values: [value.value for value in values]),
        nullable=False,
        default=IngestionJobStatus.QUEUED,
    )
    task_id = Column(String(255), nullable=True, index=True)
    progress = Column(JSON, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    source = relationship("Source", backref="ingestion_jobs")
