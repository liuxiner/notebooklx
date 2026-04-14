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
import logging
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

    def test_default_embedding_service_prefers_bigmodel_provider_when_configured(
        self,
        db: Session,
    ):
        """Runtime ingestion should align with the chat embedding backend."""
        mock_provider = Mock()
        mock_provider.dimension = 2048
        mock_provider.model = "embedding-3"

        with patch(
            "services.api.modules.ingestion.orchestrator.BigModelEmbeddingProvider",
            return_value=mock_provider,
        ):
            orchestrator = IngestionOrchestrator(db=db)

        assert orchestrator.embedding_service.dimension == 2048
        assert orchestrator.embedding_service.model_name == "embedding-3"
        assert orchestrator.embedding_service._provider is mock_provider

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
        assert "snapshot" in steps
        assert steps.index("snapshot") < steps.index("embedding")
        assert "completed" in steps or progress_updates[-1]["percentage"] == 100

    @pytest.mark.asyncio
    async def test_ingest_logs_step_monitor_events(
        self,
        db: Session,
        sample_url_source: Source,
        mock_embedding_service: EmbeddingService,
        caplog: pytest.LogCaptureFixture,
    ):
        """
        Repro: Live worker logs do not expose a reliable step-by-step ingestion trail.
        AC: Ingestion emits monitor logs for each major pipeline step.
        """
        mock_parse_result = ParseResult(
            full_text="Short test content for ingestion monitor logs.",
            pages=[
                PageContent(
                    page_number=1,
                    text="Short test content for ingestion monitor logs.",
                    char_start=0,
                    char_end=45,
                )
            ],
            metadata={},
            title="Monitor Logs Test",
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

            with caplog.at_level(
                logging.INFO,
                logger="services.api.modules.ingestion.orchestrator",
            ):
                await orchestrator.ingest(sample_url_source)

        progress_messages = [
            record.getMessage()
            for record in caplog.records
            if record.name == "services.api.modules.ingestion.orchestrator"
            and "Ingestion progress" in record.getMessage()
        ]

        expected_steps = [
            "starting",
            "fetching",
            "parsing",
            "chunking",
            "snapshot",
            "embedding",
            "saving",
            "completed",
        ]
        step_positions = [
            next(
                index
                for index, message in enumerate(progress_messages)
                if f"step={step}" in message
            )
            for step in expected_steps
        ]

        assert step_positions == sorted(step_positions)
        assert any(str(sample_url_source.id) in message for message in progress_messages)

    @pytest.mark.asyncio
    async def test_ingest_persists_structured_source_snapshot(
        self,
        db: Session,
        sample_url_source: Source,
        mock_embedding_service: EmbeddingService,
    ):
        """
        AC: Each ready source stores a structured snapshot grounded in its chunks.
        AC: Snapshot metrics include deterministic measurements and traceable refs.
        """
        from services.api.modules.snapshots.models import SourceSnapshot

        page_text = (
            "Source snapshot generation explains the ingestion pipeline, semantic chunking, "
            "traceability requirements, notebook scope routing, and keyword extraction."
        )
        mock_parse_result = ParseResult(
            full_text=page_text,
            pages=[
                PageContent(
                    page_number=1,
                    text=page_text,
                    headings=["Architecture", "Pipeline"],
                    char_start=0,
                    char_end=len(page_text),
                )
            ],
            metadata={"parser_version": "test-parser-v1"},
            title="Snapshot Test Source",
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

        snapshot = (
            db.query(SourceSnapshot)
            .filter(SourceSnapshot.source_id == sample_url_source.id)
            .one()
        )

        payload = snapshot.snapshot_data
        assert payload["source_identity"]["source_id"] == str(sample_url_source.id)
        assert payload["source_identity"]["title"] == sample_url_source.title
        assert payload["deterministic"]["content_metrics"]["char_length"] == len(page_text)
        assert (
            payload["deterministic"]["content_metrics"]["chunk_count"]
            == result.chunks_created
        )
        assert payload["deterministic"]["content_metrics"]["estimated_token_count"] > 0
        assert payload["deterministic"]["content_metrics"]["section_count"] >= 2
        assert payload["deterministic"]["content_metrics"]["heading_depth_max"] >= 2
        assert 1 <= payload["deterministic"]["content_metrics"]["keyword_count"] <= 15
        assert payload["deterministic"]["structure_outline"]
        first_node = payload["deterministic"]["structure_outline"][0]
        assert first_node["node_id"]
        assert "chunk_refs" in first_node
        assert payload["semantic"]["content_digest"]["overview"]
        assert payload["semantic"]["keywords"]
        representative_ref = payload["deterministic"]["traceability"][
            "representative_chunk_refs"
        ][0]
        assert representative_ref["chunk_id"]
        assert representative_ref["page_numbers"] == [1]
        assert representative_ref["headings"] == ["Architecture", "Pipeline"]

    @pytest.mark.asyncio
    async def test_ingest_accepts_markdown_wrapped_snapshot_json(
        self,
        db: Session,
        sample_url_source: Source,
        mock_embedding_service: EmbeddingService,
    ):
        """
        Repro: Snapshot LLM output may be wrapped in markdown fences or short preambles.
        AC: Snapshot stage should persist valid structured output when the JSON is recoverable.
        """
        from services.api.modules.snapshots.models import SourceSnapshot
        from services.api.modules.snapshots.service import (
            LLMSourceSnapshotSemanticProvider,
            SourceSnapshotService,
        )

        mock_parse_result = ParseResult(
            full_text=(
                "Notebook ingestion relies on source-grounded snapshots, semantic chunking, "
                "and traceable metadata for downstream retrieval."
            ),
            pages=[
                PageContent(
                    page_number=1,
                    text=(
                        "Notebook ingestion relies on source-grounded snapshots, semantic "
                        "chunking, and traceable metadata for downstream retrieval."
                    ),
                    headings=["Overview"],
                    char_start=0,
                    char_end=123,
                )
            ],
            metadata={"parser_version": "test-parser-v1"},
            title="Wrapped Snapshot Output",
            total_pages=1,
        )

        mock_chat_provider = Mock()
        mock_chat_provider.model = "glm-4"
        mock_chat_provider.chat.return_value = """
Here is the snapshot payload:
```json
{
  "overview": "Notebook ingestion uses source-grounded snapshots.",
  "covered_themes": ["Snapshots", "Traceability"],
  "key_assertions": ["Snapshots are grounded in chunks."],
  "representative_passages": [],
  "unresolved_gaps": [],
  "keywords": []
}
```
"""

        snapshot_service = SourceSnapshotService(
            db=db,
            semantic_provider=LLMSourceSnapshotSemanticProvider(
                chat_provider=mock_chat_provider
            ),
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
                snapshot_service=snapshot_service,
            )

            result = await orchestrator.ingest(sample_url_source)

        snapshot = (
            db.query(SourceSnapshot)
            .filter(SourceSnapshot.source_id == sample_url_source.id)
            .one()
        )

        assert result.chunks_created > 0
        assert snapshot.generation_method == "llm"
        assert (
            snapshot.snapshot_data["semantic"]["content_digest"]["overview"]
            == "Notebook ingestion uses source-grounded snapshots."
        )

    @pytest.mark.asyncio
    async def test_ingest_prefers_schema_matching_snapshot_object(
        self,
        db: Session,
        sample_url_source: Source,
        mock_embedding_service: EmbeddingService,
    ):
        """
        Repro: The model output can contain chunk-like JSON objects before the real payload.
        AC: Snapshot extraction should choose the object that matches the snapshot schema.
        """
        from services.api.modules.snapshots.models import SourceSnapshot
        from services.api.modules.snapshots.service import (
            LLMSourceSnapshotSemanticProvider,
            SourceSnapshotService,
        )

        page_text = (
            "课程内容围绕冲突识别、代理关系、动机分析和机制匹配展开，"
            "并要求把核心判断映射回原始材料。"
        )
        mock_parse_result = ParseResult(
            full_text=page_text,
            pages=[
                PageContent(
                    page_number=1,
                    text=page_text,
                    headings=["课程概览"],
                    char_start=0,
                    char_end=len(page_text),
                )
            ],
            metadata={"parser_version": "test-parser-v1"},
            title="Schema Matching Snapshot",
            total_pages=1,
        )

        mock_chat_provider = Mock()
        mock_chat_provider.model = "glm-4"
        mock_chat_provider.chat.return_value = """
先看一个片段对象：
{"chunk_id":"461bd6a2-6e7e-4d89-9d48-bfcbb7a4d761","text":"1. 冲突识别; 2. 代理关系; 3. 动机分析; 4. 诱导; 5. 机制匹配"}

最终快照：
{
  "overview": "课程内容聚焦冲突识别、代理关系、动机分析与机制匹配。",
  "covered_themes": ["冲突识别", "代理关系", "机制匹配"],
  "key_assertions": ["所有判断都应回到原始材料。"],
  "representative_passages": [],
  "unresolved_gaps": [],
  "keywords": [{"term": "代理关系", "weight": 1.0, "chunk_ids": []}]
}
"""

        snapshot_service = SourceSnapshotService(
            db=db,
            semantic_provider=LLMSourceSnapshotSemanticProvider(
                chat_provider=mock_chat_provider
            ),
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
                snapshot_service=snapshot_service,
            )

            result = await orchestrator.ingest(sample_url_source)

        snapshot = (
            db.query(SourceSnapshot)
            .filter(SourceSnapshot.source_id == sample_url_source.id)
            .one()
        )

        assert result.chunks_created > 0
        assert snapshot.generation_method == "llm"
        assert (
            snapshot.snapshot_data["semantic"]["content_digest"]["overview"]
            == "课程内容聚焦冲突识别、代理关系、动机分析与机制匹配。"
        )

    @pytest.mark.asyncio
    async def test_ingest_falls_back_to_heuristic_snapshot_on_invalid_llm_payload(
        self,
        db: Session,
        sample_url_source: Source,
        mock_embedding_service: EmbeddingService,
    ):
        """
        Repro: The model may return a chunk-shaped payload with no snapshot fields.
        AC: Ingestion should persist a structured snapshot via heuristic fallback.
        """
        from services.api.modules.snapshots.models import SourceSnapshot
        from services.api.modules.snapshots.service import (
            LLMSourceSnapshotSemanticProvider,
            SourceSnapshotService,
        )

        page_text = (
            "Source-grounded snapshots summarize the source, keep traceable chunk refs, "
            "and preserve keywords for downstream retrieval."
        )
        mock_parse_result = ParseResult(
            full_text=page_text,
            pages=[
                PageContent(
                    page_number=1,
                    text=page_text,
                    headings=["Snapshot"],
                    char_start=0,
                    char_end=len(page_text),
                )
            ],
            metadata={"parser_version": "test-parser-v1"},
            title="Invalid Snapshot Payload",
            total_pages=1,
        )

        mock_chat_provider = Mock()
        mock_chat_provider.model = "glm-4"
        mock_chat_provider.chat.return_value = (
            '{"chunk_id":"461bd6a2-6e7e-4d89-9d48-bfcbb7a4d761","text":"traceable chunk refs"}'
        )

        snapshot_service = SourceSnapshotService(
            db=db,
            semantic_provider=LLMSourceSnapshotSemanticProvider(
                chat_provider=mock_chat_provider
            ),
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
                snapshot_service=snapshot_service,
            )

            result = await orchestrator.ingest(sample_url_source)

        snapshot = (
            db.query(SourceSnapshot)
            .filter(SourceSnapshot.source_id == sample_url_source.id)
            .one()
        )

        assert result.chunks_created > 0
        assert snapshot.generation_method == "heuristic"
        assert snapshot.snapshot_data["semantic"]["content_digest"]["overview"]
        assert snapshot.snapshot_data["semantic"]["keywords"]

    @pytest.mark.asyncio
    async def test_ingest_fails_on_snapshot_error_before_embedding(
        self,
        db: Session,
        sample_url_source: Source,
    ):
        """
        AC: Snapshot failures are visible and do not silently skip the stage.
        """

        class FailingSnapshotService:
            def build_and_persist_snapshot(self, *args, **kwargs):
                raise RuntimeError("snapshot model failed")

        embedding_service = Mock()
        embedding_service.embed_batch = AsyncMock()

        mock_parse_result = ParseResult(
            full_text="Source snapshot failure test content.",
            pages=[
                PageContent(
                    page_number=1,
                    text="Source snapshot failure test content.",
                    char_start=0,
                    char_end=37,
                )
            ],
            metadata={},
            title="Snapshot Failure Test",
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
                embedding_service=embedding_service,
                snapshot_service=FailingSnapshotService(),
            )

            with pytest.raises(IngestionError) as exc_info:
                await orchestrator.ingest(sample_url_source)

        assert exc_info.value.step == "snapshot"
        embedding_service.embed_batch.assert_not_awaited()

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
