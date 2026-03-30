"""
SQLAlchemy models for semantic chunking.
"""
from sqlalchemy import Column, Text, DateTime, ForeignKey, Integer, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from services.api.core.database import Base
from services.api.core.vector import EmbeddingVector
from services.api.modules.notebooks.models import UUID


class SourceChunk(Base):
    """
    SourceChunk model - semantically meaningful segments of source content.

    Each chunk belongs to a source and contains a portion of the source's text
    with metadata including character positions, page numbers, and heading context.
    """
    __tablename__ = "source_chunks"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    source_id = Column(
        UUID,
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    chunk_index = Column(Integer, nullable=False)  # Position in sequence
    content = Column(Text, nullable=False)  # The chunk text
    token_count = Column(Integer, nullable=False)  # Number of tokens
    char_start = Column(Integer, nullable=False)  # Start position in source text
    char_end = Column(Integer, nullable=False)  # End position in source text
    chunk_metadata = Column(JSON, nullable=True, default=dict)  # Additional metadata (page, heading, etc.)
    embedding = Column(EmbeddingVector(), nullable=True)  # JSON on SQLite, pgvector on PostgreSQL

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    source = relationship("Source", backref="chunks")

    def __repr__(self) -> str:
        return f"<SourceChunk(id={self.id}, source_id={self.source_id}, index={self.chunk_index})>"
