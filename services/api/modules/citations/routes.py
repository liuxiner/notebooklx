"""
API routes for citation persistence and retrieval.

Feature 3.4: Two-Layer Citation System
Acceptance Criteria: Create citation API endpoint for fetching citations by message
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from services.api.core.database import get_db
from services.api.modules.citations.models import Citation
from services.api.modules.citations.schemas import CitationsListResponse, CitationResponse
from services.api.modules.chat.models import Message


router = APIRouter(prefix="/api/messages", tags=["citations"])


def build_error(status_code: int, error: str, message: str) -> HTTPException:
    """Create a consistent HTTPException payload."""
    return HTTPException(
        status_code=status_code,
        detail={"error": error, "message": message},
    )


@router.get("/{message_id}/citations", response_model=CitationsListResponse)
def get_citations_by_message(
    message_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Fetch all citations for a specific message.

    AC: Can fetch all citations for a message via API
    AC: Returns empty list when message has no citations
    AC: Returns 404 when message does not exist
    AC: Citations include relevant chunk metadata

    Args:
        message_id: UUID of the message to fetch citations for
        db: Database session

    Returns:
        CitationsListResponse with all citations for the message, ordered by citation_index
    """
    # Verify message exists
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise build_error(
            status.HTTP_404_NOT_FOUND,
            "not_found",
            f"Message {message_id} not found",
        )

    # Fetch citations, ordered by citation_index
    citations = (
        db.query(Citation)
        .filter(Citation.message_id == message_id)
        .order_by(Citation.citation_index)
        .all()
    )

    # Convert to response schema
    citation_responses = [CitationResponse.model_validate(c) for c in citations]

    return CitationsListResponse(citations=citation_responses)
