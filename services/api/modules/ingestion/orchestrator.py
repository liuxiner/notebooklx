"""
Ingestion orchestrator for the complete document processing pipeline.

Feature 2.5: Complete Ingestion Workflow

This module chains all ingestion steps:
1. Fetch file/URL from storage
2. Parse document based on source type
3. Chunk text semantically
4. Generate source snapshot
5. Generate embeddings
6. Save chunks and embeddings to database
6. Update source status
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from sqlalchemy.orm import Session

from services.api.modules.chunking import Chunker, ChunkResult, SourceChunk
from services.api.modules.embeddings import (
    EmbeddingService,
    EmbeddingResult,
    BigModelEmbeddingProvider,
    normalize_embedding,
)
from services.api.modules.parsers import (
    ParseResult,
    ParserError,
    PDFParser,
    URLParser,
    TextParser,
    YouTubeParser,
    GoogleDocsParser,
)
from services.api.modules.snapshots import (
    PreparedSourceChunk,
    SnapshotGenerationError,
    SourceSnapshotService,
    prepare_source_chunks,
)
from services.api.modules.sources.models import Source, SourceType


logger = logging.getLogger(__name__)

USER_FACING_INGESTION_MESSAGES = {
    "fetch": "Ingestion failed while loading the source.",
    "parse": "Ingestion failed while parsing the source.",
    "chunk": "Ingestion failed while preparing chunks.",
    "snapshot": "Ingestion failed during snapshot generation.",
    "embed": "Ingestion failed while generating embeddings.",
    "save": "Ingestion failed while saving processed chunks.",
    "unknown": "Ingestion failed.",
}


def _build_runtime_embedding_service() -> EmbeddingService:
    """
    Build the default runtime embedding service.

    In production flows, ingestion should use the same OpenAI-compatible
    provider as chat and retrieval. Tests and offline environments still fall
    back to the mock provider when AI configuration is unavailable.
    """
    try:
        provider = BigModelEmbeddingProvider()
    except (ImportError, ValueError):
        return EmbeddingService()

    return EmbeddingService(
        provider=provider,
        model_name=provider.model,
        dimension=provider.dimension,
    )


def _build_runtime_snapshot_service(db: Session) -> SourceSnapshotService:
    """Build the default runtime source snapshot service."""
    return SourceSnapshotService(db=db)


class IngestionError(Exception):
    """Raised when ingestion fails at any step."""

    def __init__(self, step: str, message: str, cause: Exception | None = None):
        super().__init__(f"[{step}] {message}")
        self.step = step
        self.cause = cause

    def to_user_message(self) -> str:
        """Return a user-facing summary that omits provider internals."""
        return USER_FACING_INGESTION_MESSAGES.get(self.step, "Ingestion failed.")


def summarize_ingestion_error(exc: Exception) -> str:
    """Convert internal ingestion exceptions into safe user-facing status text."""
    if isinstance(exc, IngestionError):
        return exc.to_user_message()
    return "Ingestion failed."


@dataclass
class IngestionProgress:
    """Tracks progress through the ingestion pipeline."""

    current_step: str = "pending"
    percentage: int = 0
    total_chunks: int = 0
    embedded_chunks: int = 0
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.current_step,
            "percentage": self.percentage,
            "total_chunks": self.total_chunks,
            "embedded_chunks": self.embedded_chunks,
            **self.details,
        }


@dataclass
class IngestionResult:
    """Result of a successful ingestion."""

    source_id: str
    chunks_created: int
    embeddings_generated: int
    progress: IngestionProgress

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "chunks_created": self.chunks_created,
            "embeddings_generated": self.embeddings_generated,
            **self.progress.to_dict(),
        }


class IngestionOrchestrator:
    """
    Orchestrates the complete ingestion pipeline for a source.

    Steps:
    1. Fetch content (from storage or URL)
    2. Parse (extract text with metadata)
    3. Chunk (semantic segmentation)
    4. Snapshot (persist structured source metadata)
    5. Embed (generate vector embeddings)
    6. Save (persist chunks to database)
    """

    def __init__(
        self,
        db: Session,
        embedding_service: EmbeddingService | None = None,
        snapshot_service: SourceSnapshotService | None = None,
        chunker: Chunker | None = None,
        progress_callback: Callable[[IngestionProgress], None] | None = None,
        file_content_loader: Callable[[str], bytes] | None = None,
    ):
        """
        Initialize the orchestrator.

        Args:
            db: SQLAlchemy session for database operations
            embedding_service: Service for generating embeddings (uses default if None)
            chunker: Text chunker (uses default if None)
            progress_callback: Optional callback for progress updates
            file_content_loader: Optional function to load file content from storage path
        """
        self.db = db
        self.embedding_service = embedding_service or _build_runtime_embedding_service()
        self.snapshot_service = snapshot_service or _build_runtime_snapshot_service(db)
        self.chunker = chunker or Chunker()
        self.progress_callback = progress_callback
        self.file_content_loader = file_content_loader
        self.progress = IngestionProgress()
        self._active_source_id: str | None = None

    def _update_progress(
        self,
        step: str,
        percentage: int,
        **kwargs: Any,
    ) -> None:
        """Update and report progress."""
        self.progress.current_step = step
        self.progress.percentage = percentage
        self.progress.details.update(kwargs)

        if self._active_source_id is not None:
            detail_items = [
                f"{key}={value}"
                for key, value in sorted(kwargs.items())
                if value is not None
            ]
            detail_suffix = f" details={', '.join(detail_items)}" if detail_items else ""
            logger.info(
                "Ingestion progress source=%s step=%s percentage=%s total_chunks=%s "
                "embedded_chunks=%s%s",
                self._active_source_id,
                step,
                percentage,
                self.progress.total_chunks,
                self.progress.embedded_chunks,
                detail_suffix,
            )

        if self.progress_callback:
            try:
                self.progress_callback(self.progress)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")

    def _get_parser(self, source: Source):
        """Get the appropriate parser for the source type."""
        parser_map = {
            SourceType.PDF: PDFParser,
            SourceType.URL: URLParser,
            SourceType.TEXT: TextParser,
            SourceType.YOUTUBE: YouTubeParser,
            SourceType.GDOCS: GoogleDocsParser,
        }

        parser_class = parser_map.get(source.source_type)
        if parser_class is None:
            raise IngestionError(
                "parse",
                f"Unsupported source type: {source.source_type}",
            )

        return parser_class()

    def _fetch_content(self, source: Source) -> str | bytes:
        """
        Fetch content based on source type.

        For file-based sources (PDF, uploaded text), loads from storage.
        For URL-based sources, returns the URL for the parser to fetch.
        """
        self._update_progress("fetching", 5)

        if source.source_type == SourceType.PDF:
            if not source.file_path:
                raise IngestionError("fetch", "PDF source missing file_path")
            if self.file_content_loader:
                return self.file_content_loader(source.file_path)
            raise IngestionError("fetch", "No file content loader configured for PDF")

        elif source.source_type == SourceType.TEXT:
            # For text sources, the content is stored directly or via file_path
            if source.file_path and self.file_content_loader:
                content = self.file_content_loader(source.file_path)
                return content.decode("utf-8")
            raise IngestionError("fetch", "Text source missing content")

        elif source.source_type in (SourceType.URL, SourceType.YOUTUBE, SourceType.GDOCS):
            if not source.original_url:
                raise IngestionError("fetch", f"{source.source_type} source missing URL")
            # URL-based parsers handle fetching themselves
            return source.original_url

        else:
            raise IngestionError("fetch", f"Unsupported source type: {source.source_type}")

    def _parse_content(self, source: Source, content: str | bytes) -> ParseResult:
        """Parse content into structured text with metadata."""
        self._update_progress("parsing", 15)

        parser = self._get_parser(source)

        try:
            if source.source_type == SourceType.PDF:
                # PDF parser expects bytes via parse_bytes
                if isinstance(content, str):
                    content = content.encode("utf-8")
                result = parser.parse_bytes(content, filename=source.title)
            elif source.source_type == SourceType.TEXT:
                # Text parser expects bytes via parse_bytes
                if isinstance(content, str):
                    content = content.encode("utf-8")
                result = parser.parse_bytes(content, filename=source.title)
            elif source.source_type in (SourceType.URL, SourceType.YOUTUBE, SourceType.GDOCS):
                if isinstance(content, bytes):
                    content = content.decode("utf-8")

                parse_url = getattr(parser, "parse_url", None)
                if callable(parse_url):
                    result = parse_url(str(content))
                else:
                    result = parser.parse(str(content))
            else:
                # Fallback for unknown types
                if isinstance(content, bytes):
                    content = content.decode("utf-8")
                result = parser.parse(content)

            logger.info(
                f"Parsed source {source.id}: {len(result.pages)} pages, "
                f"{sum(len(p.text) for p in result.pages)} chars"
            )
            return result

        except ParserError as e:
            raise IngestionError("parse", str(e), cause=e)
        except Exception as e:
            raise IngestionError("parse", f"Unexpected parsing error: {e}", cause=e)

    def _chunk_content(self, source: Source, parse_result: ParseResult) -> list[ChunkResult]:
        """Chunk parsed content into semantic segments."""
        self._update_progress("chunking", 30)

        # Combine all pages into full text
        full_text = parse_result.full_text

        try:
            chunks = self.chunker.chunk_text(
                text=full_text,
                source_title=source.title,
                pages=parse_result.pages,
            )

            self.progress.total_chunks = len(chunks)
            logger.info(f"Created {len(chunks)} chunks for source {source.id}")
            return chunks

        except Exception as e:
            raise IngestionError("chunk", f"Chunking failed: {e}", cause=e)

    def _generate_snapshot(
        self,
        source: Source,
        parse_result: ParseResult,
        prepared_chunks: list[PreparedSourceChunk],
    ) -> None:
        """Build and persist a source snapshot before embeddings start."""
        self._update_progress("snapshot", 45)
        logger.info(
            "Generating snapshot for source %s with %s prepared chunks",
            source.id,
            len(prepared_chunks),
        )

        try:
            self.snapshot_service.build_and_persist_snapshot(
                source=source,
                parse_result=parse_result,
                prepared_chunks=prepared_chunks,
            )
            logger.info("Generated snapshot for source %s", source.id)
        except SnapshotGenerationError as exc:
            raise IngestionError("snapshot", f"Snapshot generation failed: {exc}", cause=exc)
        except Exception as exc:
            raise IngestionError("snapshot", f"Snapshot generation failed: {exc}", cause=exc)

    async def _generate_embeddings(
        self,
        prepared_chunks: list[PreparedSourceChunk],
    ) -> list[EmbeddingResult]:
        """Generate embeddings for all chunks."""
        self._update_progress("embedding", 50)

        try:
            texts = [chunk.content for chunk in prepared_chunks]
            results = await self.embedding_service.embed_batch(texts)

            self.progress.embedded_chunks = len(results)

            # Update progress after embeddings complete
            self._update_progress("embedding", 80)

            logger.info(f"Generated {len(results)} embeddings")
            return results

        except Exception as e:
            raise IngestionError("embed", f"Embedding generation failed: {e}", cause=e)

    def _save_chunks(
        self,
        source: Source,
        prepared_chunks: list[PreparedSourceChunk],
        embeddings: list[EmbeddingResult],
    ) -> list[SourceChunk]:
        """Save chunks with embeddings to the database."""
        self._update_progress("saving", 85)

        try:
            self.db.query(SourceChunk).filter(
                SourceChunk.source_id == source.id
            ).delete(synchronize_session=False)

            saved_chunks = []
            for prepared_chunk, embedding_result in zip(prepared_chunks, embeddings):
                # Normalize embedding for cosine similarity
                normalized_embedding = normalize_embedding(embedding_result.embedding)

                source_chunk = SourceChunk(
                    id=prepared_chunk.chunk_id,
                    source_id=source.id,
                    chunk_index=prepared_chunk.chunk_index,
                    content=prepared_chunk.content,
                    token_count=prepared_chunk.token_count,
                    char_start=prepared_chunk.char_start,
                    char_end=prepared_chunk.char_end,
                    chunk_metadata={
                        "page": prepared_chunk.page_number,
                        "pages": prepared_chunk.page_numbers,
                        "headings": prepared_chunk.heading_context,
                        "source_title": prepared_chunk.source_title,
                    },
                    embedding=normalized_embedding,
                )
                self.db.add(source_chunk)
                saved_chunks.append(source_chunk)

            self.db.flush()
            logger.info(f"Saved {len(saved_chunks)} chunks for source {source.id}")
            return saved_chunks

        except Exception as e:
            raise IngestionError("save", f"Failed to save chunks: {e}", cause=e)

    async def ingest(self, source: Source) -> IngestionResult:
        """
        Run the complete ingestion pipeline for a source.

        Args:
            source: The Source model instance to ingest

        Returns:
            IngestionResult with chunk and embedding counts

        Raises:
            IngestionError: If any step fails
        """
        self._active_source_id = str(source.id)
        logger.info(f"Starting ingestion for source {source.id} ({source.source_type})")
        self._update_progress("starting", 0)

        try:
            # Step 1: Fetch content
            content = self._fetch_content(source)

            # Step 2: Parse
            parse_result = self._parse_content(source, content)

            # Step 3: Chunk
            chunks = self._chunk_content(source, parse_result)

            if not chunks:
                raise IngestionError("chunk", "No chunks generated from content")

            prepared_chunks = prepare_source_chunks(source, chunks)

            # Step 4: Snapshot
            self._generate_snapshot(source, parse_result, prepared_chunks)

            # Step 5: Generate embeddings (async)
            embeddings = await self._generate_embeddings(prepared_chunks)

            # Step 6: Save to database
            saved_chunks = self._save_chunks(source, prepared_chunks, embeddings)

            # Finalize
            self._update_progress("completed", 100)

            result = IngestionResult(
                source_id=str(source.id),
                chunks_created=len(saved_chunks),
                embeddings_generated=len(embeddings),
                progress=self.progress,
            )

            logger.info(
                f"Completed ingestion for source {source.id}: "
                f"{result.chunks_created} chunks, {result.embeddings_generated} embeddings"
            )

            return result

        except IngestionError:
            raise
        except Exception as e:
            raise IngestionError("unknown", f"Unexpected error: {e}", cause=e)
        finally:
            self._active_source_id = None


async def run_ingestion(
    source: Source,
    db: Session,
    embedding_service: EmbeddingService | None = None,
    file_content_loader: Callable[[str], bytes] | None = None,
    progress_callback: Callable[[IngestionProgress], None] | None = None,
) -> IngestionResult:
    """
    Convenience function to run ingestion for a source.

    This is the main entry point for the worker to call.
    """
    orchestrator = IngestionOrchestrator(
        db=db,
        embedding_service=embedding_service,
        file_content_loader=file_content_loader,
        progress_callback=progress_callback,
    )
    return await orchestrator.ingest(source)
