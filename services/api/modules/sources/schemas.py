"""
Pydantic schemas for Source API request/response validation.
"""
from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from datetime import datetime
from typing import Optional
import uuid

from services.api.modules.sources.models import SourceType, SourceStatus


class SourceURLCreate(BaseModel):
    """Schema for creating a URL-backed source."""

    url: HttpUrl
    title: Optional[str] = None


class SourceTextCreate(BaseModel):
    """Schema for creating a text-backed source."""

    content: str = Field(..., min_length=1, description="Raw text content to ingest")
    title: Optional[str] = Field(None, max_length=512, description="Optional source title")


class SourceResponse(BaseModel):
    """Schema for source response data."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    notebook_id: uuid.UUID
    source_type: SourceType
    title: str
    original_url: Optional[str] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    status: SourceStatus
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SourceListResponse(BaseModel):
    """Schema for listing sources (compact view)."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_type: SourceType
    title: str
    status: SourceStatus
    file_size: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class SourceSnapshotSummaryResponse(BaseModel):
    """Minimal snapshot summary payload for source preview surfaces."""

    overview: str
    covered_themes: list[str] = Field(default_factory=list)
    top_keywords: list[str] = Field(default_factory=list)
