"""
Pydantic schemas for Citation API request/response validation.

Feature 3.4: Two-Layer Citation System
Acceptance Criteria: Create citation API endpoint for fetching citations by message
"""
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional
import uuid


class CitationResponse(BaseModel):
    """Schema for citation response data."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    message_id: uuid.UUID
    chunk_id: uuid.UUID
    citation_index: int = Field(description="Display marker index (e.g., [1], [2])")
    quote: str = Field(description="Exact quoted text from the chunk")
    score: float = Field(description="Relevance score from retrieval", ge=0.0, le=1.0)
    page: Optional[str] = Field(None, description="Page number for PDF sources")
    source_title: str = Field(description="Display name of the source")
    created_at: datetime


class CitationsListResponse(BaseModel):
    """Schema for listing citations for a message."""
    citations: list[CitationResponse]


class ErrorResponse(BaseModel):
    """Standard error response schema."""
    error: str
    message: str
    details: Optional[dict] = None
