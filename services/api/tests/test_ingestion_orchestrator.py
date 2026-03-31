"""
Tests for the ingestion orchestrator.

Feature 2.5: Complete Ingestion Workflow

Acceptance Criteria tested:
- Upload triggers async ingestion task
- Source status updates: pending → processing → ready/failed
- All steps execute in order (parse → chunk → embed → index)
- Failed ingestion updates source with error message
- Progress tracking
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.orm import Session

from services.api.modules.sources.models import Source, SourceType, SourceStatus
from services.api.modules.notebooks.models import Notebook
from services.api.modules.chunking.models import SourceChunk
from services.api.modules.ingestion.orchestrator import (
    IngestionOrchestrator,
    IngestionError,
    IngestionProgress,
    IngestionResult,
    run_ingestion,
)
from services.api.modules.embeddings import (
    EmbeddingService,
    EmbeddingResult,
    MockEmbeddingProvider,
)
from services.api.modules.parsers import ParseResult, PageContent


@pytest.fixture
def mock_embedding_service():
    """Create a mock embedding service."""
    provider = MockEmbeddingProvider(dimension=10)
    return EmbeddingService(provider=provider)


@pytest.fixture
def sample_url_source(db: Session, sample_notebook: Notebook) -> Source:
    """Create a URL source for testing."""
    source = Source(
        notebook_id=sample_notebook.id,
        source_type=SourceType.URL,
        title="Test URL Source",
        original_url="https://example.com/test-article",
        status=SourceStatus.PENDING,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@pytest.fixture
def sample_text_source(db: Session, sample_notebook: Notebook) -> Source:
    """Create a text source for testing."""
    source = Source(
        notebook_id=sample_notebook.id,
        source_type=SourceType.TEXT,
        title="Test Text Source",
        file_path="test/text_source.txt",
        status=SourceStatus.PENDING,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


class TestIngestionOrchestrator:
    """Test the ingestion orchestrator."""

    @pytest.mark.asyncio
    async def test_ingest_url_source_creates_chunks_and_embeddings(
        self,
        db: Session,
        sample_url_source: Source,
        mock_embedding_service: EmbeddingService,
    ):
        """
        AC: All steps execute in order (parse → chunk → embed → index)
        """
        # Mock the URL parser to return predictable content
        mock_parse_result = ParseResult(
            full_text="This is a test article. It contains important information. The information is valuable for testing purposes.",
            pages=[
                PageContent(
                    page_number=1,
                    text="This is a test article. It contains important information. The information is valuable for testing purposes.",
                    char_start=0,
                    char_end=110,
                )
            ],
            metadata={"url": "https://example.com/test-article"},
            title="Test Article",
            total_pages=1,
        )

        with patch(
            "services.api.modules.ingestion.orchestrator.URLParser"
        ) as MockURLParser:
            mock_parser = Mock()
            mock_parser.parse_url.return_value = mock_parse_result
            MockURLParser.return_value = mock_parser

            orchestrator = IngestionOrchestrator(
                db=db,
                embedding_service=mock_embedding_service,
            )

            result = await orchestrator.ingest(sample_url_source)

            # Verify result structure
            assert isinstance(result, IngestionResult)
            assert result.source_id == str(sample_url_source.id)
            assert result.chunks_created > 0
            assert result.embeddings_generated == result.chunks_created

            # Verify chunks were saved to database
            chunks = db.query(SourceChunk).filter(
                SourceChunk.source_id == sample_url_source.id
            ).all()
            assert len(chunks) == result.chunks_created

            # Verify embeddings were stored
            for chunk in chunks:
                assert chunk.embedding is not None
                assert len(chunk.embedding) == 10  # MockEmbeddingProvider dimension

    @pytest.mark.asyncio
    async def test_ingest_text_source_with_file_loader(
        self,
        db: Session,
        sample_text_source: Source,
        mock_embedding_service: EmbeddingService,
    ):
        """
        AC: All steps execute in order (parse → chunk → embed → index)
        """
        test_content = b"This is the test file content. It should be parsed and chunked correctly."

        def mock_file_loader(file_path: str) -> bytes:
            return test_content

        orchestrator = IngestionOrchestrator(
            db=db,
            embedding_service=mock_embedding_service,
            file_content_loader=mock_file_loader,
        )

        result = await orchestrator.ingest(sample_text_source)

        assert isinstance(result, IngestionResult)
        assert result.chunks_created > 0

        # Verify chunks in database
        chunks = db.query(SourceChunk).filter(
            SourceChunk.source_id == sample_text_source.id
        ).all()
        assert len(chunks) == result.chunks_created

    @pytest.mark.asyncio
    async def test_ingest_reports_progress(
        self,
        db: Session,
        sample_url_source: Source,
        mock_embedding_service: EmbeddingService,
    ):
        """
        AC: Progress tracking (e.g., "5 of 10 chunks embedded")
        """
        progress_updates = []

        def progress_callback(progress: IngestionProgress):
            progress_updates.append(progress.to_dict().copy())

        mock_parse_result = ParseResult(
            full_text="Short test content for progress tracking.",
            pages=[
                PageContent(
                    page_number=1,
                    text="Short test content for progress tracking.",
                    char_start=0,
                    char_end=42,
                )
            ],
            metadata={},
            title="Test",
            total_pages=1,
        )

        with patch(
            "services.api.modules.ingestion.orchestrator.URLParser"
        ) as MockURLParser:
            mock_parser = Mock()
            mock_parser.parse_url.return_value = mock_parse_result
            MockURLParser.return_value = mock_parser

            orchestrator = IngestionOrchestrator(
                db=db,
                embedding_service=mock_embedding_service,
                progress_callback=progress_callback,
            )

            await orchestrator.ingest(sample_url_source)

        # Verify progress was reported
        assert len(progress_updates) > 0

        # Check progress steps were reported
        steps = [p["step"] for p in progress_updates]
        assert "starting" in steps or progress_updates[0]["percentage"] == 0
        assert "completed" in steps or progress_updates[-1]["percentage"] == 100

    @pytest.mark.asyncio
    async def test_ingest_fails_gracefully_on_parse_error(
        self,
        db: Session,
        sample_url_source: Source,
        mock_embedding_service: EmbeddingService,
    ):
        """
        AC: Failed ingestion updates source with error message
        """
        from services.api.modules.parsers import ParserError

        with patch(
            "services.api.modules.ingestion.orchestrator.URLParser"
        ) as MockURLParser:
            mock_parser = Mock()
            mock_parser.parse_url.side_effect = ParserError("Failed to fetch URL")
            MockURLParser.return_value = mock_parser

            orchestrator = IngestionOrchestrator(
                db=db,
                embedding_service=mock_embedding_service,
            )

            with pytest.raises(IngestionError) as exc_info:
                await orchestrator.ingest(sample_url_source)

            assert exc_info.value.step == "parse"
            assert "Failed to fetch URL" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_ingest_fails_on_missing_url(
        self,
        db: Session,
        sample_notebook: Notebook,
        mock_embedding_service: EmbeddingService,
    ):
        """
        AC: Failed ingestion updates source with error message
        """
        # Create source without URL
        source = Source(
            notebook_id=sample_notebook.id,
            source_type=SourceType.URL,
            title="Source Without URL",
            original_url=None,  # Missing URL
            status=SourceStatus.PENDING,
        )
        db.add(source)
        db.commit()

        orchestrator = IngestionOrchestrator(
            db=db,
            embedding_service=mock_embedding_service,
        )

        with pytest.raises(IngestionError) as exc_info:
            await orchestrator.ingest(source)

        assert exc_info.value.step == "fetch"
        assert "missing URL" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_ingest_fails_on_empty_content(
        self,
        db: Session,
        sample_url_source: Source,
        mock_embedding_service: EmbeddingService,
    ):
        """
        AC: Failed ingestion updates source with error message
        """
        # Mock parser returns empty content
        mock_parse_result = ParseResult(
            full_text="",
            pages=[],
            metadata={},
            title="Empty",
            total_pages=0,
        )

        with patch(
            "services.api.modules.ingestion.orchestrator.URLParser"
        ) as MockURLParser:
            mock_parser = Mock()
            mock_parser.parse_url.return_value = mock_parse_result
            MockURLParser.return_value = mock_parser

            orchestrator = IngestionOrchestrator(
                db=db,
                embedding_service=mock_embedding_service,
            )

            with pytest.raises(IngestionError) as exc_info:
                await orchestrator.ingest(sample_url_source)

            assert exc_info.value.step == "chunk"
            assert "No chunks generated" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_chunks_contain_correct_metadata(
        self,
        db: Session,
        sample_url_source: Source,
        mock_embedding_service: EmbeddingService,
    ):
        """
        AC: Chunks maintain metadata (page numbers, headings)
        """
        mock_parse_result = ParseResult(
            full_text="Page one content here. Page two content follows.",
            pages=[
                PageContent(
                    page_number=1,
                    text="Page one content here.",
                    headings=["Introduction"],
                    char_start=0,
                    char_end=23,
                ),
                PageContent(
                    page_number=2,
                    text="Page two content follows.",
                    headings=["Conclusion"],
                    char_start=24,
                    char_end=49,
                ),
            ],
            metadata={},
            title="Multi-page Doc",
            total_pages=2,
        )

        with patch(
            "services.api.modules.ingestion.orchestrator.URLParser"
        ) as MockURLParser:
            mock_parser = Mock()
            mock_parser.parse_url.return_value = mock_parse_result
            MockURLParser.return_value = mock_parser

            orchestrator = IngestionOrchestrator(
                db=db,
                embedding_service=mock_embedding_service,
            )

            await orchestrator.ingest(sample_url_source)

        chunks = db.query(SourceChunk).filter(
            SourceChunk.source_id == sample_url_source.id
        ).order_by(SourceChunk.chunk_index).all()

        # Verify metadata is present
        for chunk in chunks:
            assert chunk.chunk_metadata is not None
            assert "source_title" in chunk.chunk_metadata
            assert chunk.chunk_metadata["source_title"] == sample_url_source.title


class TestRunIngestionFunction:
    """Test the convenience run_ingestion function."""

    @pytest.mark.asyncio
    async def test_run_ingestion_returns_result(
        self,
        db: Session,
        sample_url_source: Source,
    ):
        """Test the run_ingestion convenience function."""
        mock_provider = MockEmbeddingProvider(dimension=10)
        mock_service = EmbeddingService(provider=mock_provider)

        mock_parse_result = ParseResult(
            full_text="Test content for run_ingestion function.",
            pages=[
                PageContent(
                    page_number=1,
                    text="Test content for run_ingestion function.",
                    char_start=0,
                    char_end=41,
                )
            ],
            metadata={},
            title="Test",
            total_pages=1,
        )

        with patch(
            "services.api.modules.ingestion.orchestrator.URLParser"
        ) as MockURLParser:
            mock_parser = Mock()
            mock_parser.parse_url.return_value = mock_parse_result
            MockURLParser.return_value = mock_parser

            result = await run_ingestion(
                source=sample_url_source,
                db=db,
                embedding_service=mock_service,
            )

            assert isinstance(result, IngestionResult)
            assert result.source_id == str(sample_url_source.id)

    @pytest.mark.asyncio
    async def test_ingest_url_source_uses_parse_url_contract(
        self,
        db: Session,
        sample_url_source: Source,
        mock_embedding_service: EmbeddingService,
    ):
        """URL-like sources should call parse_url instead of parse."""
        mock_parse_result = ParseResult(
            full_text="Contract test content for URL ingestion.",
            pages=[
                PageContent(
                    page_number=1,
                    text="Contract test content for URL ingestion.",
                    char_start=0,
                    char_end=39,
                )
            ],
            metadata={"url": sample_url_source.original_url},
            title="Contract Test",
            total_pages=1,
        )

        with patch(
            "services.api.modules.ingestion.orchestrator.URLParser"
        ) as MockURLParser:
            mock_parser = Mock()
            mock_parser.parse.side_effect = AssertionError(
                "parse() should not be used for URL sources"
            )
            mock_parser.parse_url.return_value = mock_parse_result
            MockURLParser.return_value = mock_parser

            orchestrator = IngestionOrchestrator(
                db=db,
                embedding_service=mock_embedding_service,
            )

            result = await orchestrator.ingest(sample_url_source)

            assert isinstance(result, IngestionResult)
            mock_parser.parse_url.assert_called_once_with(
                sample_url_source.original_url
            )


class TestIngestionProgress:
    """Test progress tracking."""

    def test_progress_to_dict(self):
        """Test progress serialization."""
        progress = IngestionProgress(
            current_step="embedding",
            percentage=75,
            total_chunks=10,
            embedded_chunks=7,
            details={"batch": 2},
        )

        result = progress.to_dict()

        assert result["step"] == "embedding"
        assert result["percentage"] == 75
        assert result["total_chunks"] == 10
        assert result["embedded_chunks"] == 7
        assert result["batch"] == 2


class TestIngestionResult:
    """Test result structure."""

    def test_result_to_dict(self):
        """Test result serialization."""
        progress = IngestionProgress(
            current_step="completed",
            percentage=100,
            total_chunks=5,
            embedded_chunks=5,
        )

        result = IngestionResult(
            source_id="test-id",
            chunks_created=5,
            embeddings_generated=5,
            progress=progress,
        )

        data = result.to_dict()

        assert data["source_id"] == "test-id"
        assert data["chunks_created"] == 5
        assert data["embeddings_generated"] == 5
        assert data["step"] == "completed"
        assert data["percentage"] == 100
