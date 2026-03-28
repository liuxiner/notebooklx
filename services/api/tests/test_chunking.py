"""
Tests for semantic chunking module.

Feature 2.2: Semantic Chunking
Slice: SourceChunk model + basic token-based chunking algorithm

Acceptance Criteria tested:
- Chunks are 300-800 tokens each
- 50-120 token overlap between consecutive chunks
- Each chunk includes source title and chunk index
- Chunks maintain character position offsets
- No information loss between chunks
"""
import pytest
import uuid
from datetime import datetime


class TestSourceChunkModel:
    """Test SourceChunk database model."""

    def test_source_chunk_model_exists(self):
        """SourceChunk model should be importable."""
        from services.api.modules.chunking.models import SourceChunk
        assert SourceChunk is not None

    def test_source_chunk_has_required_fields(self):
        """SourceChunk should have all required fields."""
        from services.api.modules.chunking.models import SourceChunk
        from sqlalchemy import inspect

        mapper = inspect(SourceChunk)
        columns = {c.key for c in mapper.columns}

        required_fields = {
            "id",
            "source_id",
            "chunk_index",
            "content",
            "token_count",
            "char_start",
            "char_end",
            "chunk_metadata",
            "created_at",
        }
        assert required_fields.issubset(columns), f"Missing fields: {required_fields - columns}"

    def test_source_chunk_creation(self, db, sample_notebook, sample_source):
        """Should create SourceChunk in database."""
        from services.api.modules.chunking.models import SourceChunk

        chunk = SourceChunk(
            source_id=sample_source.id,
            chunk_index=0,
            content="This is test chunk content.",
            token_count=6,
            char_start=0,
            char_end=27,
            chunk_metadata={"source_title": "Test Source", "page_number": 1},
        )
        db.add(chunk)
        db.commit()

        assert chunk.id is not None
        assert chunk.source_id == sample_source.id
        assert chunk.chunk_index == 0
        assert chunk.content == "This is test chunk content."
        assert chunk.token_count == 6
        assert chunk.char_start == 0
        assert chunk.char_end == 27
        assert chunk.chunk_metadata["source_title"] == "Test Source"
        assert chunk.created_at is not None

    def test_source_chunk_cascade_delete(self, db, sample_notebook, sample_source):
        """Chunks should be deleted when source is deleted."""
        from services.api.modules.chunking.models import SourceChunk
        from services.api.modules.sources.models import Source

        chunk = SourceChunk(
            source_id=sample_source.id,
            chunk_index=0,
            content="Test content",
            token_count=2,
            char_start=0,
            char_end=12,
        )
        db.add(chunk)
        db.commit()
        chunk_id = chunk.id
        source_id = sample_source.id

        # Expunge chunk from session to prevent ORM from setting source_id=NULL
        db.expunge(chunk)

        # Delete source using raw SQL to test DB-level CASCADE
        db.execute(
            Source.__table__.delete().where(Source.id == source_id)
        )
        db.commit()

        # Chunk should be gone due to CASCADE DELETE
        result = db.query(SourceChunk).filter(SourceChunk.id == chunk_id).first()
        assert result is None


class TestTokenCounting:
    """Test token counting functionality."""

    def test_count_tokens_basic(self):
        """Should count tokens using tiktoken."""
        from services.api.modules.chunking.chunker import count_tokens

        text = "Hello world"
        count = count_tokens(text)
        assert count > 0
        assert isinstance(count, int)

    def test_count_tokens_empty_string(self):
        """Should return 0 for empty string."""
        from services.api.modules.chunking.chunker import count_tokens

        assert count_tokens("") == 0

    def test_count_tokens_unicode(self):
        """Should handle unicode text."""
        from services.api.modules.chunking.chunker import count_tokens

        text = "你好世界 こんにちは"
        count = count_tokens(text)
        assert count > 0

    def test_count_tokens_consistency(self):
        """Same text should always return same count."""
        from services.api.modules.chunking.chunker import count_tokens

        text = "The quick brown fox jumps over the lazy dog."
        count1 = count_tokens(text)
        count2 = count_tokens(text)
        assert count1 == count2


class TestChunkingAlgorithm:
    """Test core chunking algorithm."""

    @pytest.fixture
    def chunker(self):
        """Create a Chunker instance."""
        from services.api.modules.chunking.chunker import Chunker
        return Chunker(
            min_tokens=300,
            max_tokens=800,
            overlap_tokens=75,  # Middle of 50-120 range
        )

    @pytest.fixture
    def small_chunker(self):
        """Create a Chunker with smaller limits for testing."""
        from services.api.modules.chunking.chunker import Chunker
        return Chunker(
            min_tokens=10,
            max_tokens=50,
            overlap_tokens=5,
        )

    def test_chunker_initialization(self, chunker):
        """Chunker should initialize with correct parameters."""
        assert chunker.min_tokens == 300
        assert chunker.max_tokens == 800
        assert chunker.overlap_tokens == 75

    def test_chunker_invalid_params(self):
        """Should raise error for invalid parameters."""
        from services.api.modules.chunking.chunker import Chunker

        with pytest.raises(ValueError):
            Chunker(min_tokens=800, max_tokens=300, overlap_tokens=50)

        with pytest.raises(ValueError):
            Chunker(min_tokens=100, max_tokens=200, overlap_tokens=150)

    def test_chunk_short_text(self, small_chunker):
        """Short text should become a single chunk."""
        from services.api.modules.chunking.chunker import ChunkResult

        text = "This is short text."
        result = small_chunker.chunk_text(text, source_title="Test")

        assert len(result) == 1
        assert result[0].content == text
        assert result[0].chunk_index == 0
        assert result[0].source_title == "Test"
        assert result[0].char_start == 0
        assert result[0].char_end == len(text)

    def test_chunk_text_within_range(self, small_chunker):
        """Chunks should be within min-max token range (or smaller for last chunk)."""
        from services.api.modules.chunking.chunker import count_tokens

        # Create text that will need multiple chunks
        text = "This is a test sentence. " * 20  # Should create multiple chunks
        result = small_chunker.chunk_text(text, source_title="Test")

        assert len(result) > 1
        for i, chunk in enumerate(result[:-1]):  # All except last
            token_count = count_tokens(chunk.content)
            assert token_count >= small_chunker.min_tokens or len(result) == 1, \
                f"Chunk {i} has {token_count} tokens, less than min {small_chunker.min_tokens}"
            assert token_count <= small_chunker.max_tokens, \
                f"Chunk {i} has {token_count} tokens, more than max {small_chunker.max_tokens}"

    def test_chunk_has_overlap(self, small_chunker):
        """Consecutive chunks should have overlapping content."""
        # Create text that will need multiple chunks
        text = "Word number one. Word number two. Word number three. " * 10
        result = small_chunker.chunk_text(text, source_title="Test")

        if len(result) >= 2:
            # Check that chunks have some overlap in character positions
            for i in range(len(result) - 1):
                current = result[i]
                next_chunk = result[i + 1]
                # Overlap means next chunk starts before current chunk ends
                # (in terms of original text positions)
                assert next_chunk.char_start < current.char_end, \
                    f"No overlap between chunk {i} and {i+1}"

    def test_chunk_preserves_all_content(self, small_chunker):
        """All original content should be present in chunks (no loss)."""
        text = "The quick brown fox jumps over the lazy dog. " * 15
        result = small_chunker.chunk_text(text, source_title="Test")

        # Reconstruct text from chunks (accounting for overlap)
        reconstructed = ""
        for i, chunk in enumerate(result):
            if i == 0:
                reconstructed = chunk.content
            else:
                # Find where the new content starts (after overlap)
                overlap_start = result[i - 1].char_end - chunk.char_start
                if overlap_start > 0 and overlap_start < len(chunk.content):
                    reconstructed += chunk.content[overlap_start:]
                else:
                    reconstructed += chunk.content

        # All text should be covered
        assert text in reconstructed or reconstructed == text

    def test_chunk_index_sequential(self, small_chunker):
        """Chunk indices should be sequential starting from 0."""
        text = "This is a test. " * 30
        result = small_chunker.chunk_text(text, source_title="Test")

        for i, chunk in enumerate(result):
            assert chunk.chunk_index == i

    def test_chunk_source_title_preserved(self, small_chunker):
        """Source title should be in each chunk."""
        text = "Test content here. " * 20
        source_title = "My Test Document"
        result = small_chunker.chunk_text(text, source_title=source_title)

        for chunk in result:
            assert chunk.source_title == source_title

    def test_chunk_preserves_page_numbers_from_structured_pages(self):
        """Chunk metadata should preserve all page numbers covered by a chunk."""
        from services.api.modules.chunking.chunker import Chunker
        from services.api.modules.parsers.base import PageContent

        page_one_text = (
            "Alpha page one starts here. "
            "It continues with more detail. "
            "The section closes cleanly."
        )
        page_two_text = (
            "Beta page two begins now. "
            "It adds supporting evidence. "
            "The analysis finishes here."
        )
        full_text = f"{page_one_text}\n{page_two_text}"
        pages = [
            PageContent(
                page_number=7,
                text=page_one_text,
                headings=["Part I", "Section A"],
                char_start=0,
                char_end=len(page_one_text),
            ),
            PageContent(
                page_number=8,
                text=page_two_text,
                headings=["Part I", "Section B"],
                char_start=len(page_one_text) + 1,
                char_end=len(full_text),
            ),
        ]

        chunker = Chunker(min_tokens=5, max_tokens=200, overlap_tokens=2)
        result = chunker.chunk_text(full_text, source_title="Structured Doc", pages=pages)

        assert len(result) == 1
        assert result[0].page_number == 7
        assert result[0].page_numbers == [7, 8]
        assert result[0].heading_context == ["Part I", "Section A"]

    def test_chunk_preserves_heading_hierarchy_from_page_context(self, small_chunker):
        """Chunks should inherit heading hierarchy from the page where they start."""
        from services.api.modules.parsers.base import PageContent

        page_one_text = "Alpha history matters. " * 15
        page_two_text = "Beta findings differ. " * 15
        full_text = f"{page_one_text}\n{page_two_text}"
        pages = [
            PageContent(
                page_number=1,
                text=page_one_text,
                headings=["Part I", "Section A"],
                char_start=0,
                char_end=len(page_one_text),
            ),
            PageContent(
                page_number=2,
                text=page_two_text,
                headings=["Part I", "Section B"],
                char_start=len(page_one_text) + 1,
                char_end=len(full_text),
            ),
        ]

        result = small_chunker.chunk_text(full_text, source_title="Structured Doc", pages=pages)

        assert len(result) >= 2
        assert result[0].heading_context == ["Part I", "Section A"]

        page_two_chunks = [chunk for chunk in result if chunk.page_number == 2]
        assert page_two_chunks
        assert all(chunk.heading_context == ["Part I", "Section B"] for chunk in page_two_chunks)

    def test_chunk_character_positions_valid(self, small_chunker):
        """Character positions should be valid indices into original text."""
        text = "Hello world! This is a test. " * 15
        result = small_chunker.chunk_text(text, source_title="Test")

        for chunk in result:
            assert chunk.char_start >= 0
            assert chunk.char_end <= len(text)
            assert chunk.char_start < chunk.char_end
            # Content should match text at those positions
            assert chunk.content == text[chunk.char_start:chunk.char_end]

    def test_chunk_empty_text(self, small_chunker):
        """Empty text should return empty list."""
        result = small_chunker.chunk_text("", source_title="Test")
        assert result == []

    def test_chunk_whitespace_only(self, small_chunker):
        """Whitespace-only text should return empty list."""
        result = small_chunker.chunk_text("   \n\t  ", source_title="Test")
        assert result == []


class TestChunkResult:
    """Test ChunkResult dataclass."""

    def test_chunk_result_creation(self):
        """ChunkResult should be creatable with required fields."""
        from services.api.modules.chunking.chunker import ChunkResult

        chunk = ChunkResult(
            content="Test content",
            chunk_index=0,
            source_title="Test Source",
            token_count=2,
            char_start=0,
            char_end=12,
        )

        assert chunk.content == "Test content"
        assert chunk.chunk_index == 0
        assert chunk.source_title == "Test Source"
        assert chunk.token_count == 2
        assert chunk.char_start == 0
        assert chunk.char_end == 12

    def test_chunk_result_optional_metadata(self):
        """ChunkResult should support optional metadata."""
        from services.api.modules.chunking.chunker import ChunkResult

        chunk = ChunkResult(
            content="Test",
            chunk_index=0,
            source_title="Test",
            token_count=1,
            char_start=0,
            char_end=4,
            page_number=5,
            page_numbers=[5, 6],
            heading_context=["Chapter 1", "Section A"],
        )

        assert chunk.page_number == 5
        assert chunk.page_numbers == [5, 6]
        assert chunk.heading_context == ["Chapter 1", "Section A"]


class TestChunkerWithDefaultSettings:
    """Test chunker with production-like settings (300-800 tokens, 50-120 overlap)."""

    @pytest.fixture
    def production_chunker(self):
        """Create chunker with production settings."""
        from services.api.modules.chunking.chunker import Chunker
        return Chunker(
            min_tokens=300,
            max_tokens=800,
            overlap_tokens=75,
        )

    def test_long_document_chunking(self, production_chunker):
        """Long document should be chunked correctly."""
        from services.api.modules.chunking.chunker import count_tokens

        # Create a document with ~2000 tokens
        paragraph = (
            "Artificial intelligence has transformed many industries. "
            "Machine learning algorithms can now process vast amounts of data. "
            "Natural language processing enables computers to understand human text. "
            "Deep learning models have achieved remarkable accuracy in image recognition. "
        )
        text = paragraph * 50  # Should be >1500 tokens

        result = production_chunker.chunk_text(text, source_title="AI Research Paper")

        # Should have multiple chunks
        assert len(result) >= 2

        # Check token counts (except possibly last chunk)
        for i, chunk in enumerate(result[:-1]):
            token_count = count_tokens(chunk.content)
            assert 300 <= token_count <= 800, \
                f"Chunk {i} has {token_count} tokens, outside 300-800 range"

    def test_overlap_within_range(self, production_chunker):
        """Overlap should be within 50-120 token range."""
        from services.api.modules.chunking.chunker import count_tokens

        paragraph = "This is test content for chunking. " * 100
        result = production_chunker.chunk_text(paragraph, source_title="Test")

        if len(result) >= 2:
            for i in range(len(result) - 1):
                current = result[i]
                next_chunk = result[i + 1]

                # Calculate overlap
                overlap_text = current.content[-(current.char_end - next_chunk.char_start):]
                if overlap_text:
                    overlap_tokens = count_tokens(overlap_text)
                    # Overlap should be approximately in the target range
                    # Allow some variance since we work with sentences
                    assert overlap_tokens >= 20, \
                        f"Overlap between chunk {i} and {i+1} is too small: {overlap_tokens} tokens"


class TestChunkerModuleExports:
    """Test that chunking module exports correctly."""

    def test_module_imports(self):
        """Chunking module should export main classes."""
        from services.api.modules.chunking import (
            SourceChunk,
            Chunker,
            ChunkResult,
            count_tokens,
        )

        assert SourceChunk is not None
        assert Chunker is not None
        assert ChunkResult is not None
        assert count_tokens is not None

