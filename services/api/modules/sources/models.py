"""
SQLAlchemy models for sources.
"""
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from services.api.core.database import Base
from services.api.modules.notebooks.models import UUID


class SourceType(str, enum.Enum):
    """Enumeration of supported source types."""
    PDF = "pdf"
    URL = "url"
    TEXT = "text"
    YOUTUBE = "youtube"
    AUDIO = "audio"
    GDOCS = "gdocs"


class SourceStatus(str, enum.Enum):
    """Enumeration of source processing statuses."""
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class Source(Base):
    """
    Source model - files, URLs, or content added to a notebook.

    Each source belongs to a notebook and goes through an ingestion
    pipeline to extract text, create chunks, and generate embeddings.
    """
    __tablename__ = "sources"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    notebook_id = Column(
        UUID,
        ForeignKey("notebooks.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    source_type = Column(
        SQLEnum(SourceType, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    title = Column(String(512), nullable=False)

    # Optional fields for different source types
    original_url = Column(String(2048), nullable=True)  # For URL/YouTube/GDocs sources
    file_path = Column(String(1024), nullable=True)  # Storage path for uploaded files
    file_size = Column(Integer, nullable=True)  # File size in bytes

    # Processing status
    status = Column(
        SQLEnum(SourceStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=SourceStatus.PENDING
    )
    error_message = Column(Text, nullable=True)  # Error details if status is FAILED

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    notebook = relationship("Notebook", backref="sources")
