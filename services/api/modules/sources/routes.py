"""
API routes for Source operations.
"""
from pathlib import Path
import logging
import re
from typing import Any, List, TypedDict, cast
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from services.api.core.database import get_db
from services.api.modules.notebooks.models import Notebook
from services.api.modules.notebooks.routes import get_current_user_id
from services.api.modules.sources.cleanup import delete_source_artifacts
from services.api.modules.sources.models import Source, SourceStatus, SourceType
from services.api.modules.sources.schemas import (
    SourceListResponse,
    SourceSnapshotSummaryResponse,
    SourceResponse,
    SourceTextCreate,
    SourceURLCreate,
)
from services.api.modules.sources.storage import StorageError, get_object_storage


router = APIRouter(prefix="/api/notebooks", tags=["sources"])
logger = logging.getLogger(__name__)

TEXT_SOURCE_MAX_BYTES = 10 * 1024 * 1024
MAX_BATCH_UPLOAD_FILES = 50
UPLOAD_RULES = {
    "application/pdf": {
        "source_type": SourceType.PDF,
        "max_size": 50 * 1024 * 1024,
        "default_filename": "upload.pdf",
    },
    "text/plain": {
        "source_type": SourceType.TEXT,
        "max_size": TEXT_SOURCE_MAX_BYTES,
        "default_filename": "upload.txt",
    },
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {
        "source_type": SourceType.TEXT,
        "max_size": TEXT_SOURCE_MAX_BYTES,
        "default_filename": "upload.docx",
    },
}
FILENAME_SANITIZE_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")
FILENAME_CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x1f\x7f]+")


class UploadRule(TypedDict):
    """Validation and storage rules for a supported upload content type."""

    source_type: SourceType
    max_size: int
    default_filename: str


class ValidatedUpload(TypedDict):
    """Validated upload data ready to be persisted as a source."""

    source_type: SourceType
    content: bytes
    content_type: str
    filename: str
    title: str


def get_notebook_or_404(
    notebook_id: uuid.UUID,
    user_id: uuid.UUID,
    db: Session
) -> Notebook:
    """
    Get a notebook by ID or raise 404 if not found or deleted.
    """
    notebook = db.query(Notebook).filter(
        Notebook.id == notebook_id,
        Notebook.user_id == user_id,
        Notebook.deleted_at.is_(None)
    ).first()

    if not notebook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": f"Notebook {notebook_id} not found"}
        )
    return notebook


def get_source_or_404(
    notebook_id: uuid.UUID,
    source_id: uuid.UUID,
    db: Session,
) -> Source:
    """Get a source by notebook/source id or raise 404."""
    source = db.query(Source).filter(
        Source.id == source_id,
        Source.notebook_id == notebook_id,
    ).first()

    if not source:
        raise build_error(
            status.HTTP_404_NOT_FOUND,
            "not_found",
            f"Source {source_id} not found",
        )

    return source


def build_error(status_code: int, error: str, message: str) -> HTTPException:
    """Create a consistent HTTPException payload."""
    return HTTPException(
        status_code=status_code,
        detail={"error": error, "message": message},
    )


def _normalize_string_list(values: Any, *, limit: int) -> list[str]:
    """Convert a raw list payload into a deduplicated list of strings."""
    if not isinstance(values, list):
        return []

    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue

        stripped = value.strip()
        if not stripped or stripped in normalized:
            continue

        normalized.append(stripped)
        if len(normalized) >= limit:
            break

    return normalized


def build_snapshot_summary_response(snapshot_data: Any) -> SourceSnapshotSummaryResponse | None:
    """Extract the UI-facing snapshot summary fields from stored snapshot data."""
    if not isinstance(snapshot_data, dict):
        return None

    semantic = snapshot_data.get("semantic")
    if not isinstance(semantic, dict):
        return None

    content_digest = semantic.get("content_digest")
    keywords = semantic.get("keywords")

    overview = ""
    covered_themes: list[str] = []
    top_keywords: list[str] = []

    if isinstance(content_digest, dict):
        raw_overview = content_digest.get("overview")
        if isinstance(raw_overview, str):
            overview = raw_overview.strip()

        covered_themes = _normalize_string_list(
            content_digest.get("covered_themes"),
            limit=8,
        )

        if not overview:
            key_assertions = _normalize_string_list(
                content_digest.get("key_assertions"),
                limit=2,
            )
            if key_assertions:
                overview = " ".join(key_assertions).strip()

        if not overview:
            representative_passages = content_digest.get("representative_passages")
            if isinstance(representative_passages, list):
                for passage in representative_passages:
                    if not isinstance(passage, dict):
                        continue
                    passage_text = passage.get("text")
                    if isinstance(passage_text, str) and passage_text.strip():
                        overview = passage_text.strip()
                        break

    if isinstance(keywords, list):
        for keyword in keywords:
            term = keyword.get("term") if isinstance(keyword, dict) else keyword
            if not isinstance(term, str):
                continue

            stripped = term.strip()
            if not stripped or stripped in top_keywords:
                continue

            top_keywords.append(stripped)
            if len(top_keywords) >= 10:
                break

    if not overview and not covered_themes and not top_keywords:
        return None

    return SourceSnapshotSummaryResponse(
        overview=overview,
        covered_themes=covered_themes,
        top_keywords=top_keywords,
    )


def slugify_text_filename(title: str | None) -> str:
    """Generate a predictable `.txt` filename for raw text sources."""
    stem = (title or "").strip().lower()
    stem = re.sub(r"\s+", "-", stem)
    stem = FILENAME_SANITIZE_PATTERN.sub("-", stem).strip("-.")
    if not stem:
        stem = "source"
    return f"{stem}.txt"


def split_filename_extension(filename: str) -> tuple[str, str]:
    """Split a filename into stem + last extension while preserving leading dots."""
    if "." not in filename or filename.startswith(".") and filename.count(".") == 1:
        return filename, ""
    stem, extension = filename.rsplit(".", 1)
    return stem, f".{extension}"


def derive_source_title_from_filename(filename: str, fallback: str) -> str:
    """Use the original filename stem as the default source title."""
    stem, _extension = split_filename_extension(filename)
    normalized_stem = stem.strip()
    return normalized_stem or fallback


def sanitize_filename(filename: str | None, fallback: str) -> str:
    """Strip paths and control characters while preserving visible filename text."""
    raw_name = (filename or "").replace("\\", "/").split("/")[-1].strip()
    candidate = raw_name or fallback
    sanitized = FILENAME_CONTROL_CHARS_PATTERN.sub("", candidate).strip()
    if sanitized in {"", ".", ".."}:
        return fallback
    return sanitized


def build_object_path(
    notebook_id: uuid.UUID,
    source_id: uuid.UUID,
    filename: str,
) -> str:
    """Build the logical storage key for an uploaded source."""
    return f"{notebook_id}/{source_id}/{filename}"


def validate_upload_file(file: UploadFile) -> ValidatedUpload:
    """Read and validate one uploaded file against the supported rules."""
    content_type = (file.content_type or "").strip().lower()
    rule = cast(UploadRule | None, UPLOAD_RULES.get(content_type))

    if rule is None:
        raise build_error(
            status.HTTP_400_BAD_REQUEST,
            "validation_error",
            f"Unsupported content type: {file.content_type or 'unknown'}",
        )

    file_bytes = file.file.read()
    if len(file_bytes) > rule["max_size"]:
        max_mb = rule["max_size"] // (1024 * 1024)
        raise build_error(
            status.HTTP_400_BAD_REQUEST,
            "validation_error",
            f"Uploaded file exceeds the {max_mb}MB limit for {content_type}",
        )

    filename = sanitize_filename(file.filename, rule["default_filename"])
    return {
        "source_type": rule["source_type"],
        "content": file_bytes,
        "content_type": content_type,
        "filename": filename,
        "title": derive_source_title_from_filename(
            filename,
            Path(rule["default_filename"]).stem,
        ),
    }


def create_uploaded_source(
    notebook_id: uuid.UUID,
    upload: ValidatedUpload,
    db: Session,
    title: str | None = None,
) -> Source:
    """Create and persist a file-backed source from validated upload data."""
    source = Source(
        notebook_id=notebook_id,
        source_type=upload["source_type"],
        title=title.strip() if title and title.strip() else upload["title"],
        status=SourceStatus.PENDING,
    )
    db.add(source)
    db.flush()

    return persist_source_bytes(
        source=source,
        content=upload["content"],
        content_type=upload["content_type"],
        filename=upload["filename"],
        db=db,
    )


def persist_source_bytes(
    source: Source,
    content: bytes,
    content_type: str,
    filename: str,
    db: Session,
) -> Source:
    """Persist source bytes to storage and keep source status in sync."""
    object_path = build_object_path(source.notebook_id, source.id, filename)

    try:
        source.file_path = get_object_storage().store_bytes(content, object_path, content_type)
        source.file_size = len(content)
        source.error_message = None
    except StorageError as exc:
        source.status = SourceStatus.FAILED
        source.error_message = str(exc)
        db.commit()
        raise build_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "upload_failed",
            "Failed to store source content",
        ) from exc

    db.commit()
    db.refresh(source)
    return source


@router.get("/{notebook_id}/sources", response_model=List[SourceListResponse])
def list_sources(
    notebook_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id)
):
    """
    List all sources for a notebook.

    AC: List sources for a notebook
    AC: Proper error handling - 404 for nonexistent notebook
    """
    # Verify notebook exists and belongs to user
    get_notebook_or_404(notebook_id, user_id, db)

    # Get all sources for this notebook
    sources = db.query(Source).filter(
        Source.notebook_id == notebook_id
    ).order_by(Source.created_at.desc()).all()

    return sources


@router.post(
    "/{notebook_id}/sources/url",
    response_model=SourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_url_source(
    notebook_id: uuid.UUID,
    source_data: SourceURLCreate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """
    Create a URL source for a notebook.

    AC: Add URL source (validate URL format)
    AC: Return source ID and initial status (pending)
    """
    notebook = get_notebook_or_404(notebook_id, user_id, db)
    normalized_url = str(source_data.url)

    source = Source(
        notebook_id=notebook.id,
        source_type=SourceType.URL,
        title=source_data.title.strip() if source_data.title and source_data.title.strip() else normalized_url,
        original_url=normalized_url,
        status=SourceStatus.PENDING,
    )

    db.add(source)
    db.commit()
    db.refresh(source)

    return source


@router.post(
    "/{notebook_id}/sources/text",
    response_model=SourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_text_source(
    notebook_id: uuid.UUID,
    source_data: SourceTextCreate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """
    Create a text source for a notebook.

    AC: Upload plain text content
    AC: Return source ID and initial status (pending)
    """
    notebook = get_notebook_or_404(notebook_id, user_id, db)
    content_bytes = source_data.content.encode("utf-8")

    if len(content_bytes) > TEXT_SOURCE_MAX_BYTES:
        raise build_error(
            status.HTTP_400_BAD_REQUEST,
            "validation_error",
            "Text source content exceeds the 10MB limit",
        )

    title = source_data.title.strip() if source_data.title and source_data.title.strip() else "Text Source"
    source = Source(
        notebook_id=notebook.id,
        source_type=SourceType.TEXT,
        title=title,
        status=SourceStatus.PENDING,
    )
    db.add(source)
    db.flush()

    return persist_source_bytes(
        source=source,
        content=content_bytes,
        content_type="text/plain; charset=utf-8",
        filename=slugify_text_filename(source_data.title),
        db=db,
    )


@router.post(
    "/{notebook_id}/sources/upload",
    response_model=SourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_source_file(
    notebook_id: uuid.UUID,
    file: UploadFile = File(...),
    title: str | None = Form(None),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """
    Upload a file-backed source for a notebook.

    AC: Upload PDF file (max 50MB)
    AC: Store original file in MinIO/S3
    AC: Support multiple file types (PDF, TXT, DOCX)
    AC: Proper MIME type validation
    AC: File size limits enforced
    AC: Error handling for failed uploads
    """
    notebook = get_notebook_or_404(notebook_id, user_id, db)
    upload = validate_upload_file(file)

    return create_uploaded_source(
        notebook_id=notebook.id,
        upload=upload,
        db=db,
        title=title,
    )


@router.post(
    "/{notebook_id}/sources/upload/batch",
    response_model=List[SourceResponse],
    status_code=status.HTTP_201_CREATED,
)
def upload_source_files_batch(
    notebook_id: uuid.UUID,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """
    Upload multiple file-backed sources for a notebook in one request.

    AC: Notebook source upload accepts multiple selected PDF and TXT files
    AC: Sources API creates one source record per uploaded file
    AC: Bulk upload rejects unsupported file types
    """
    notebook = get_notebook_or_404(notebook_id, user_id, db)
    if len(files) == 0:
        raise build_error(
            status.HTTP_400_BAD_REQUEST,
            "validation_error",
            "At least one file is required for batch upload.",
        )

    if len(files) > MAX_BATCH_UPLOAD_FILES:
        raise build_error(
            status.HTTP_400_BAD_REQUEST,
            "validation_error",
            f"Batch upload supports up to {MAX_BATCH_UPLOAD_FILES} files per request.",
        )

    validated_uploads = [validate_upload_file(file) for file in files]

    return [
        create_uploaded_source(notebook_id=notebook.id, upload=upload, db=db)
        for upload in validated_uploads
    ]


@router.get(
    "/{notebook_id}/sources/{source_id}/snapshot",
    response_model=SourceSnapshotSummaryResponse,
)
def get_source_snapshot_summary(
    notebook_id: uuid.UUID,
    source_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Return a compact snapshot summary for a single source."""
    from services.api.modules.snapshots.models import SourceSnapshot

    get_notebook_or_404(notebook_id, user_id, db)
    source = get_source_or_404(notebook_id, source_id, db)

    snapshot = (
        db.query(SourceSnapshot)
        .filter(SourceSnapshot.source_id == source.id)
        .first()
    )
    if snapshot is None:
        raise build_error(
            status.HTTP_404_NOT_FOUND,
            "not_found",
            "Snapshot preview is not available for this source",
        )

    summary = build_snapshot_summary_response(snapshot.snapshot_data)
    if summary is None:
        logger.warning(
            "Snapshot summary unavailable for source=%s notebook=%s; semantic payload keys=%s",
            source.id,
            notebook_id,
            list(snapshot.snapshot_data.keys()) if isinstance(snapshot.snapshot_data, dict) else [],
        )
        raise build_error(
            status.HTTP_404_NOT_FOUND,
            "not_found",
            "Snapshot preview is not available for this source",
        )

    if not summary.overview:
        logger.warning(
            "Snapshot summary overview still empty after fallback source=%s notebook=%s",
            source.id,
            notebook_id,
        )

    return summary


@router.delete(
    "/{notebook_id}/sources/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_source(
    notebook_id: uuid.UUID,
    source_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """
    Delete a source from a notebook.

    Deletes the source row and relies on database cascades to remove derived
    source records such as chunks and ingestion jobs.
    """
    get_notebook_or_404(notebook_id, user_id, db)
    source = get_source_or_404(notebook_id, source_id, db)

    delete_source_artifacts(db=db, sources=[source])
    db.commit()

    return None
