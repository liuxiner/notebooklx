"""
Shared cleanup helpers for source-backed resources.
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import delete
from sqlalchemy.orm import Session

from services.api.modules.sources.models import Source
from services.api.modules.sources.storage import StorageError, get_object_storage


logger = logging.getLogger(__name__)


def delete_source_artifacts(
    *,
    db: Session,
    sources: list[Source],
) -> int:
    """
    Delete storage-backed payloads and remove source rows.

    Database cascades handle ingestion jobs, chunks, and other derived records.
    Storage cleanup failures are logged and do not block DB cleanup.
    """
    if not sources:
        return 0

    storage = get_object_storage()

    for source in sources:
        if not source.file_path:
            continue

        try:
            storage.delete_bytes(source.file_path)
        except StorageError as exc:
            logger.warning(
                "Failed to delete storage object %s for source %s: %s",
                source.file_path,
                source.id,
                exc,
            )

    source_ids = [source.id for source in sources]
    db.execute(delete(Source).where(Source.id.in_(source_ids)))
    return len(source_ids)


def delete_notebook_source_artifacts(
    *,
    db: Session,
    notebook_id: uuid.UUID,
) -> int:
    """Delete all sources and derived records for a notebook."""
    sources = db.query(Source).filter(Source.notebook_id == notebook_id).all()
    return delete_source_artifacts(db=db, sources=sources)
