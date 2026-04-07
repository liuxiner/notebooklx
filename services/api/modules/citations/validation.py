"""
Citation validation utilities.

Feature 3.4: Two-Layer Citation System
Task 9: Add citation validation (check chunk IDs exist)
"""
from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from services.api.modules.chunking.models import SourceChunk

if TYPE_CHECKING:
    from services.api.modules.chat.service import EvidenceChunk

logger = logging.getLogger(__name__)


def validate_chunk_ids(
    db: Session,
    chunk_ids: list[str],
) -> tuple[list[str], list[str]]:
    """
    Validate that chunk IDs exist in the database.

    Args:
        db: Database session
        chunk_ids: List of chunk ID strings to validate

    Returns:
        Tuple of (valid_ids, invalid_ids) where each is a list of chunk ID strings.
        Duplicates in the input are deduplicated in the output.
    """
    if not chunk_ids:
        return [], []

    # Deduplicate input IDs
    unique_ids = list(set(chunk_ids))

    # Convert string IDs to UUIDs for database query
    uuid_ids = []
    invalid_format_ids = []
    for chunk_id in unique_ids:
        try:
            uuid_ids.append(uuid.UUID(chunk_id))
        except (ValueError, TypeError):
            invalid_format_ids.append(chunk_id)
            logger.warning(f"Invalid chunk ID format: {chunk_id}")

    # Query database for existing chunks
    existing_chunks = (
        db.query(SourceChunk.id)
        .filter(SourceChunk.id.in_(uuid_ids))
        .all()
    )
    existing_ids = {str(row.id) for row in existing_chunks}

    # Separate valid and invalid IDs
    valid_ids = []
    invalid_ids = list(invalid_format_ids)  # Start with format-invalid IDs

    for chunk_id in unique_ids:
        if chunk_id in invalid_format_ids:
            continue  # Already added to invalid
        if chunk_id in existing_ids:
            valid_ids.append(chunk_id)
        else:
            invalid_ids.append(chunk_id)
            logger.warning(f"Chunk ID not found in database: {chunk_id}")

    return valid_ids, invalid_ids


def filter_citations_by_valid_chunks(
    db: Session,
    citations: list["EvidenceChunk"],
) -> tuple[list["EvidenceChunk"], int]:
    """
    Filter citations to only include those with valid chunk IDs.

    Args:
        db: Database session
        citations: List of EvidenceChunk objects to filter

    Returns:
        Tuple of (valid_citations, filtered_count) where valid_citations
        contains only citations with existing chunk IDs, and filtered_count
        is the number of citations that were removed.
    """
    if not citations:
        return [], 0

    chunk_ids = [c.chunk_id for c in citations]
    valid_ids, invalid_ids = validate_chunk_ids(db, chunk_ids)
    valid_ids_set = set(valid_ids)

    valid_citations = [c for c in citations if c.chunk_id in valid_ids_set]
    filtered_count = len(citations) - len(valid_citations)

    if filtered_count > 0:
        logger.warning(
            f"Filtered {filtered_count} citations with invalid chunk IDs: {invalid_ids}"
        )

    return valid_citations, filtered_count
