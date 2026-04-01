"""
SQLAlchemy models for citation persistence.

Feature 3.4: Two-Layer Citation System
Acceptance Criteria: Citations persist in database for audit
"""
from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from services.api.core.database import Base
from services.api.modules.notebooks.models import UUID


class Citation(Base):
    """
    Persist a citation linking an assistant message to a source chunk.

    This represents the binding layer where LLM output is mapped to specific
    source chunks. Each citation records which chunk was referenced, the
    citation marker index shown to the user (e.g., [1], [2]), and metadata
    like the quoted text and relevance score.
    """

    __tablename__ = "citations"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    message_id = Column(
        UUID,
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_id = Column(
        UUID,
        ForeignKey("source_chunks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    citation_index = Column(Integer, nullable=False)  # Display marker [1], [2], etc.
    quote = Column(Text, nullable=False)  # The quoted text from the chunk
    score = Column(Float, nullable=False)  # Relevance score from retrieval
    page = Column(String(50), nullable=True)  # Page number (for PDFs)
    source_title = Column(String(500), nullable=False)  # Source display name
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    message = relationship("Message", backref="citations")
    chunk = relationship("SourceChunk", backref="citations")

    def __repr__(self) -> str:
        return f"<Citation(id={self.id}, message_id={self.message_id}, chunk_id={self.chunk_id}, index={self.citation_index})>"
