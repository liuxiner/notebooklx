"""
Pydantic schemas for Notebook API request/response validation.
"""
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional
import uuid


class NotebookCreate(BaseModel):
    """Schema for creating a new notebook."""
    name: str = Field(..., min_length=1, max_length=255, description="Notebook name (required)")
    description: Optional[str] = Field(None, description="Notebook description (optional)")


class NotebookUpdate(BaseModel):
    """Schema for updating an existing notebook."""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Updated notebook name")
    description: Optional[str] = Field(None, description="Updated notebook description")


class NotebookResponse(BaseModel):
    """Schema for notebook response data."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class NotebookListResponse(BaseModel):
    """Schema for listing multiple notebooks."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ErrorResponse(BaseModel):
    """Standard error response schema."""
    error: str
    message: str
    details: Optional[dict] = None
