"""
SQLAlchemy models for source snapshots.
"""
from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String

from services.api.core.database import Base
from services.api.modules.notebooks.models import UUID


class SourceSnapshot(Base):
    """
    Persist the latest structured snapshot for a source.

    The JSON payload separates deterministic measurements from semantic fields
    so downstream consumers can distinguish measured facts from model output.
    """

    __tablename__ = "source_snapshots"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    source_id = Column(
        UUID,
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    notebook_id = Column(
        UUID,
        ForeignKey("notebooks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    schema_version = Column(String(32), nullable=False)
    source_content_hash = Column(String(64), nullable=False)
    generation_method = Column(String(32), nullable=False)
    model_name = Column(String(128), nullable=True)
    snapshot_data = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
