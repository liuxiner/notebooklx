"""
Ingestion orchestrator for the complete document processing pipeline.

Feature 2.5: Complete Ingestion Workflow

This module chains all ingestion steps:
1. Fetch file/URL from storage
2. Parse document based on source type
3. Chunk text semantically
4. Generate embeddings
5. Save chunks and embeddings to database
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
from services.api.modules.sources.models import Source, SourceType


logger = logging.getLogger(__name__)


class IngestionError(Exception):
    """Raised when ingestion fails at any step."""

    def __init__(self, step: str, message: str, cause: Exception | None = None):
        super().__init__(f"[{step}] {message}")
        self.step = step
        self.cause = cause


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
    4. Embed (generate vector embeddings)
    5. Save (persist chunks to database)
    """

    def __init__(
        self,
        db: Session,
        embedding_service: EmbeddingService | None = None,
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
        self.embedding_service = embedding_service or EmbeddingService()
        self.chunker = chunker or Chunker()
        self.progress_callback = progress_callback
        self.file_content_loader = file_content_loader
        self.progress = IngestionProgress()

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
                # URL-based parsers expect the URL string
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

    async def _generate_embeddings(
        self,
        chunks: list[ChunkResult],
    ) -> list[EmbeddingResult]:
        """Generate embeddings for all chunks."""
        self._update_progress("embedding", 50)

        try:
            texts = [chunk.content for chunk in chunks]
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
        chunks: list[ChunkResult],
        embeddings: list[EmbeddingResult],
    ) -> list[SourceChunk]:
        """Save chunks with embeddings to the database."""
        self._update_progress("saving", 85)

        try:
            saved_chunks = []
            for i, (chunk, embedding_result) in enumerate(zip(chunks, embeddings)):
                # Normalize embedding for cosine similarity
                normalized_embedding = normalize_embedding(embedding_result.embedding)

                source_chunk = SourceChunk(
                    source_id=source.id,
                    chunk_index=i,
                    content=chunk.content,
                    token_count=chunk.token_count,
                    char_start=chunk.char_start,
                    char_end=chunk.char_end,
                    chunk_metadata={
                        "page": chunk.page_number,
                        "pages": chunk.page_numbers,
                        "headings": chunk.heading_context,
                        "source_title": chunk.source_title,
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

            # Step 4: Generate embeddings (async)
            embeddings = await self._generate_embeddings(chunks)

            # Step 5: Save to database
            saved_chunks = self._save_chunks(source, chunks, embeddings)

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
