"""
Tests for hybrid retrieval (BM25 + Vector + RRF).

Feature 3.1: Hybrid Retrieval
"""
import time
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4
from sqlalchemy.orm import Session

from services.api.modules.chunking.models import SourceChunk
from services.api.modules.notebooks.models import Notebook
from services.api.modules.sources.models import Source
from services.api.modules.retrieval.service import SearchResult
from services.api.modules.retrieval.hybrid import (
    BM25SearchService,
    HybridSearchService,
    HybridSearchResult,
    reciprocal_rank_fusion,
)


# ============================================================================
# BM25SearchService Tests
# ============================================================================

class TestBM25Tokenizer:
    """Test BM25 tokenization."""

    def test_tokenize_basic_text(self):
        """Tokenize simple text into lowercase tokens."""
        db = MagicMock()
        service = BM25SearchService(db)

        tokens = service._tokenize("Hello World Test")

        assert tokens == ["hello", "world", "test"]

    def test_tokenize_removes_punctuation(self):
        """Punctuation should be removed during tokenization."""
        db = MagicMock()
        service = BM25SearchService(db)

        tokens = service._tokenize("Hello, World! How are you?")

        assert tokens == ["hello", "world", "how", "are", "you"]

    def test_tokenize_filters_short_tokens(self):
        """Single character tokens should be filtered out."""
        db = MagicMock()
        service = BM25SearchService(db)

        tokens = service._tokenize("I am a test")

        # 'I', 'a' should be filtered (length <= 1)
        assert tokens == ["am", "test"]

    def test_tokenize_empty_string(self):
        """Empty string returns empty token list."""
        db = MagicMock()
        service = BM25SearchService(db)

        tokens = service._tokenize("")

        assert tokens == []


class TestBM25IndexBuilding:
    """Test BM25 index construction."""

    def test_build_index_with_chunks(self):
        """Build index from database chunks."""
        db = MagicMock()
        service = BM25SearchService(db)

        # Mock database response
        mock_rows = [
            MagicMock(
                id=uuid4(),
                source_id=uuid4(),
                notebook_id=uuid4(),
                content="Machine learning algorithms",
                chunk_metadata={"page": 1},
                chunk_index=0,
                source_title="ML Guide",
            ),
            MagicMock(
                id=uuid4(),
                source_id=uuid4(),
                notebook_id=uuid4(),
                content="Deep learning neural networks",
                chunk_metadata={"page": 2},
                chunk_index=1,
                source_title="ML Guide",
            ),
        ]
        db.execute.return_value.all.return_value = mock_rows

        notebook_id = str(uuid4())
        bm25, chunk_data = service._build_index(notebook_id)

        assert len(chunk_data) == 2
        assert chunk_data[0]["content"] == "Machine learning algorithms"
        assert chunk_data[1]["source_title"] == "ML Guide"

    def test_build_index_empty_notebook(self):
        """Empty notebook returns empty index."""
        db = MagicMock()
        service = BM25SearchService(db)

        db.execute.return_value.all.return_value = []

        notebook_id = str(uuid4())
        bm25, chunk_data = service._build_index(notebook_id)

        assert len(chunk_data) == 0

    def test_build_index_accepts_string_notebook_id_on_sqlite(
        self,
        db: Session,
        sample_notebook: Notebook,
        sample_source: Source,
    ):
        """SQLite-backed BM25 queries should accept dashed string notebook ids."""
        db.add(
            SourceChunk(
                source_id=sample_source.id,
                chunk_index=0,
                content="Tuya platform overview",
                token_count=3,
                char_start=0,
                char_end=22,
                chunk_metadata={"page": 1},
            )
        )
        db.commit()

        service = BM25SearchService(db)
        bm25, chunk_data = service._build_index(str(sample_notebook.id))

        assert bm25 is not None
        assert len(chunk_data) == 1
        assert chunk_data[0]["source_id"] == str(sample_source.id)


class TestBM25Search:
    """Test BM25 search functionality."""

    def test_search_returns_ranked_results(self):
        """Search returns results ranked by BM25 score."""
        db = MagicMock()
        service = BM25SearchService(db)

        # Mock database response with searchable content
        notebook_id = str(uuid4())
        mock_rows = [
            MagicMock(
                id=uuid4(),
                source_id=uuid4(),
                notebook_id=uuid4(),
                content="Python programming language",
                chunk_metadata={},
                chunk_index=0,
                source_title="Python Docs",
            ),
            MagicMock(
                id=uuid4(),
                source_id=uuid4(),
                notebook_id=uuid4(),
                content="Python machine learning with scikit-learn",
                chunk_metadata={},
                chunk_index=1,
                source_title="ML Guide",
            ),
            MagicMock(
                id=uuid4(),
                source_id=uuid4(),
                notebook_id=uuid4(),
                content="Java programming basics",
                chunk_metadata={},
                chunk_index=2,
                source_title="Java Docs",
            ),
        ]
        db.execute.return_value.all.return_value = mock_rows

        results = service.search("Python programming", notebook_id, top_k=10)

        # Should return results containing "python" and "programming"
        assert len(results) >= 1
        # First result should be most relevant (contains both terms)
        assert "Python" in results[0].content or "programming" in results[0].content

    def test_search_empty_query(self):
        """Empty query returns no results."""
        db = MagicMock()
        service = BM25SearchService(db)

        results = service.search("", str(uuid4()))

        assert results == []

    def test_search_whitespace_query(self):
        """Whitespace-only query returns no results."""
        db = MagicMock()
        service = BM25SearchService(db)

        results = service.search("   ", str(uuid4()))

        assert results == []

    def test_search_respects_top_k(self):
        """Search respects top_k limit."""
        db = MagicMock()
        service = BM25SearchService(db)

        # Create many mock rows
        notebook_id = str(uuid4())
        mock_rows = [
            MagicMock(
                id=uuid4(),
                source_id=uuid4(),
                notebook_id=uuid4(),
                content=f"Document about Python topic {i}",
                chunk_metadata={},
                chunk_index=i,
                source_title="Docs",
            )
            for i in range(20)
        ]
        db.execute.return_value.all.return_value = mock_rows

        results = service.search("Python", notebook_id, top_k=5)

        assert len(results) <= 5

    def test_search_min_score_filter(self):
        """Search filters results below min_score."""
        db = MagicMock()
        service = BM25SearchService(db)

        notebook_id = str(uuid4())
        mock_rows = [
            MagicMock(
                id=uuid4(),
                source_id=uuid4(),
                notebook_id=uuid4(),
                content="Completely unrelated content about cooking recipes",
                chunk_metadata={},
                chunk_index=0,
                source_title="Cooking",
            ),
        ]
        db.execute.return_value.all.return_value = mock_rows

        # Search for something not in the content with high min_score
        results = service.search("Python machine learning", notebook_id, min_score=1.0)

        # Should filter out low-scoring results
        assert len(results) == 0


class TestBM25Cache:
    """Test BM25 index caching."""

    def test_cache_reused_on_subsequent_search(self):
        """Index cache is reused for same notebook."""
        db = MagicMock()
        service = BM25SearchService(db)

        notebook_id = str(uuid4())
        mock_rows = [
            MagicMock(
                id=uuid4(),
                source_id=uuid4(),
                notebook_id=uuid4(),
                content="Test content",
                chunk_metadata={},
                chunk_index=0,
                source_title="Test",
            ),
        ]
        db.execute.return_value.all.return_value = mock_rows

        # First search builds index
        service.search("test", notebook_id)
        call_count_after_first = db.execute.call_count

        # Second search should reuse cache
        service.search("content", notebook_id)

        # Should not have made additional DB calls
        assert db.execute.call_count == call_count_after_first

    def test_force_rebuild_ignores_cache(self):
        """force_rebuild_index rebuilds even with cache."""
        db = MagicMock()
        service = BM25SearchService(db)

        notebook_id = str(uuid4())
        mock_rows = [
            MagicMock(
                id=uuid4(),
                source_id=uuid4(),
                notebook_id=uuid4(),
                content="Test content",
                chunk_metadata={},
                chunk_index=0,
                source_title="Test",
            ),
        ]
        db.execute.return_value.all.return_value = mock_rows

        # First search
        service.search("test", notebook_id)
        call_count_after_first = db.execute.call_count

        # Force rebuild
        service.search("test", notebook_id, force_rebuild_index=True)

        # Should have made additional DB call
        assert db.execute.call_count > call_count_after_first

    def test_invalidate_cache(self):
        """invalidate_cache removes cached index."""
        db = MagicMock()
        service = BM25SearchService(db)

        notebook_id = str(uuid4())
        mock_rows = [
            MagicMock(
                id=uuid4(),
                source_id=uuid4(),
                notebook_id=uuid4(),
                content="Test content",
                chunk_metadata={},
                chunk_index=0,
                source_title="Test",
            ),
        ]
        db.execute.return_value.all.return_value = mock_rows

        # Build cache
        service.search("test", notebook_id)

        # Invalidate
        service.invalidate_cache(notebook_id)

        # Cache should be empty for this notebook
        assert notebook_id not in service._index_cache


# ============================================================================
# RRF Fusion Tests
# ============================================================================

class TestReciprocalRankFusion:
    """Test RRF algorithm."""

    def test_rrf_combines_two_lists(self):
        """RRF combines results from two ranked lists."""
        chunk_id_1 = str(uuid4())
        chunk_id_2 = str(uuid4())
        chunk_id_3 = str(uuid4())

        # List 1: chunk_1 is rank 1, chunk_2 is rank 2
        list1 = [
            SearchResult(
                chunk_id=chunk_id_1,
                source_id=str(uuid4()),
                notebook_id=str(uuid4()),
                content="Content 1",
                score=0.9,
                metadata={},
                source_title="Source 1",
                chunk_index=0,
            ),
            SearchResult(
                chunk_id=chunk_id_2,
                source_id=str(uuid4()),
                notebook_id=str(uuid4()),
                content="Content 2",
                score=0.8,
                metadata={},
                source_title="Source 2",
                chunk_index=1,
            ),
        ]

        # List 2: chunk_2 is rank 1, chunk_3 is rank 2
        list2 = [
            SearchResult(
                chunk_id=chunk_id_2,
                source_id=str(uuid4()),
                notebook_id=str(uuid4()),
                content="Content 2",
                score=5.0,
                metadata={},
                source_title="Source 2",
                chunk_index=1,
            ),
            SearchResult(
                chunk_id=chunk_id_3,
                source_id=str(uuid4()),
                notebook_id=str(uuid4()),
                content="Content 3",
                score=4.0,
                metadata={},
                source_title="Source 3",
                chunk_index=2,
            ),
        ]

        results = reciprocal_rank_fusion([list1, list2], k=60)

        # chunk_2 should be highest (appears in both lists)
        assert len(results) == 3
        assert results[0].chunk_id == chunk_id_2

        # Check that ranks are tracked
        assert results[0].vector_rank == 2  # list_0 rank
        assert results[0].bm25_rank == 1    # list_1 rank

    def test_rrf_with_empty_list(self):
        """RRF handles empty result lists."""
        chunk_id = str(uuid4())

        list1 = [
            SearchResult(
                chunk_id=chunk_id,
                source_id=str(uuid4()),
                notebook_id=str(uuid4()),
                content="Content",
                score=0.9,
                metadata={},
                source_title="Source",
                chunk_index=0,
            ),
        ]

        results = reciprocal_rank_fusion([list1, []], k=60)

        assert len(results) == 1
        assert results[0].chunk_id == chunk_id

    def test_rrf_k_parameter_affects_scores(self):
        """Different k values produce different score magnitudes."""
        chunk_id = str(uuid4())

        result_list = [
            SearchResult(
                chunk_id=chunk_id,
                source_id=str(uuid4()),
                notebook_id=str(uuid4()),
                content="Content",
                score=0.9,
                metadata={},
                source_title="Source",
                chunk_index=0,
            ),
        ]

        results_k60 = reciprocal_rank_fusion([result_list], k=60)
        results_k1 = reciprocal_rank_fusion([result_list], k=1)

        # With k=60: score = 1/(60+1) ≈ 0.0164
        # With k=1: score = 1/(1+1) = 0.5
        assert results_k1[0].score > results_k60[0].score

    def test_rrf_preserves_metadata(self):
        """RRF preserves chunk metadata from first occurrence."""
        chunk_id = str(uuid4())
        source_id = str(uuid4())
        notebook_id = str(uuid4())

        result_list = [
            SearchResult(
                chunk_id=chunk_id,
                source_id=source_id,
                notebook_id=notebook_id,
                content="Original content",
                score=0.9,
                metadata={"page": 5},
                source_title="Important Source",
                chunk_index=42,
            ),
        ]

        results = reciprocal_rank_fusion([result_list], k=60)

        assert results[0].source_id == source_id
        assert results[0].notebook_id == notebook_id
        assert results[0].content == "Original content"
        assert results[0].metadata == {"page": 5}
        assert results[0].source_title == "Important Source"
        assert results[0].chunk_index == 42


# ============================================================================
# HybridSearchService Tests
# ============================================================================

class TestHybridSearchService:
    """Test hybrid search combining vector and BM25."""

    @pytest.mark.asyncio
    async def test_hybrid_search_scopes_both_retrievers_to_notebook(self):
        """Hybrid search passes the notebook scope to both retrievers."""
        db = MagicMock()
        notebook_id = str(uuid4())

        vector_service = MagicMock()
        vector_service.search.return_value = []

        bm25_service = MagicMock()
        bm25_service.search.return_value = []

        service = HybridSearchService(
            db=db,
            vector_service=vector_service,
            bm25_service=bm25_service,
        )

        await service.search(
            query="test query",
            query_embedding=[0.1] * 1536,
            notebook_id=notebook_id,
            top_k=7,
        )

        vector_service.search.assert_called_once()
        bm25_service.search.assert_called_once()

        assert vector_service.search.call_args.kwargs["notebook_id"] == notebook_id
        assert bm25_service.search.call_args.kwargs["notebook_id"] == notebook_id

    @pytest.mark.asyncio
    async def test_hybrid_search_handles_empty_results(self):
        """Hybrid search returns an empty list when both retrievers return nothing."""
        db = MagicMock()

        vector_service = MagicMock()
        vector_service.search.return_value = []

        bm25_service = MagicMock()
        bm25_service.search.return_value = []

        service = HybridSearchService(
            db=db,
            vector_service=vector_service,
            bm25_service=bm25_service,
        )

        results = await service.search(
            query="no matches",
            query_embedding=[0.1] * 1536,
            notebook_id=str(uuid4()),
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_hybrid_search_combines_results(self):
        """Hybrid search combines vector and BM25 results."""
        db = MagicMock()

        # Mock vector service
        vector_service = MagicMock()
        chunk_id_1 = str(uuid4())
        chunk_id_2 = str(uuid4())

        vector_service.search.return_value = [
            SearchResult(
                chunk_id=chunk_id_1,
                source_id=str(uuid4()),
                notebook_id=str(uuid4()),
                content="Vector result 1",
                score=0.9,
                metadata={},
                source_title="Source",
                chunk_index=0,
            ),
        ]

        # Mock BM25 service
        bm25_service = MagicMock()
        bm25_service.search.return_value = [
            SearchResult(
                chunk_id=chunk_id_2,
                source_id=str(uuid4()),
                notebook_id=str(uuid4()),
                content="BM25 result",
                score=5.0,
                metadata={},
                source_title="Source",
                chunk_index=1,
            ),
        ]

        service = HybridSearchService(
            db=db,
            vector_service=vector_service,
            bm25_service=bm25_service,
        )

        query = "test query"
        query_embedding = [0.1] * 1536
        notebook_id = str(uuid4())

        results = await service.search(
            query=query,
            query_embedding=query_embedding,
            notebook_id=notebook_id,
            top_k=10,
        )

        # Should have results from both services
        assert len(results) == 2

        # Verify both services were called
        vector_service.search.assert_called_once()
        bm25_service.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_hybrid_search_includes_individual_scores(self):
        """Hybrid results include original vector and BM25 scores."""
        db = MagicMock()

        chunk_id = str(uuid4())

        # Same chunk in both results
        vector_service = MagicMock()
        vector_service.search.return_value = [
            SearchResult(
                chunk_id=chunk_id,
                source_id=str(uuid4()),
                notebook_id=str(uuid4()),
                content="Shared content",
                score=0.85,
                metadata={},
                source_title="Source",
                chunk_index=0,
            ),
        ]

        bm25_service = MagicMock()
        bm25_service.search.return_value = [
            SearchResult(
                chunk_id=chunk_id,
                source_id=str(uuid4()),
                notebook_id=str(uuid4()),
                content="Shared content",
                score=4.5,
                metadata={},
                source_title="Source",
                chunk_index=0,
            ),
        ]

        service = HybridSearchService(
            db=db,
            vector_service=vector_service,
            bm25_service=bm25_service,
        )

        results = await service.search(
            query="test",
            query_embedding=[0.1] * 1536,
            notebook_id=str(uuid4()),
        )

        # Should have individual scores
        assert len(results) == 1
        assert results[0].vector_score == 0.85
        assert results[0].bm25_score == 4.5

    @pytest.mark.asyncio
    async def test_hybrid_search_respects_top_k(self):
        """Hybrid search returns at most top_k results."""
        db = MagicMock()

        # Create many results
        vector_service = MagicMock()
        vector_service.search.return_value = [
            SearchResult(
                chunk_id=str(uuid4()),
                source_id=str(uuid4()),
                notebook_id=str(uuid4()),
                content=f"Vector {i}",
                score=0.9 - i * 0.1,
                metadata={},
                source_title="Source",
                chunk_index=i,
            )
            for i in range(10)
        ]

        bm25_service = MagicMock()
        bm25_service.search.return_value = [
            SearchResult(
                chunk_id=str(uuid4()),
                source_id=str(uuid4()),
                notebook_id=str(uuid4()),
                content=f"BM25 {i}",
                score=5.0 - i * 0.5,
                metadata={},
                source_title="Source",
                chunk_index=i + 10,
            )
            for i in range(10)
        ]

        service = HybridSearchService(
            db=db,
            vector_service=vector_service,
            bm25_service=bm25_service,
        )

        results = await service.search(
            query="test",
            query_embedding=[0.1] * 1536,
            notebook_id=str(uuid4()),
            top_k=5,
        )

        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_hybrid_search_custom_candidate_counts(self):
        """Hybrid search respects custom candidate counts."""
        db = MagicMock()

        vector_service = MagicMock()
        vector_service.search.return_value = []

        bm25_service = MagicMock()
        bm25_service.search.return_value = []

        service = HybridSearchService(
            db=db,
            vector_service=vector_service,
            bm25_service=bm25_service,
        )

        await service.search(
            query="test",
            query_embedding=[0.1] * 1536,
            notebook_id=str(uuid4()),
            top_k=10,
            vector_top_k=50,
            bm25_top_k=30,
        )

        # Check vector service was called with custom top_k
        vector_call_args = vector_service.search.call_args
        assert vector_call_args.kwargs.get("top_k") == 50

        # Check BM25 service was called with custom top_k
        bm25_call_args = bm25_service.search.call_args
        assert bm25_call_args.kwargs.get("top_k") == 30

    def test_hybrid_search_sync_version(self):
        """Synchronous hybrid search wrapper works."""
        db = MagicMock()

        vector_service = MagicMock()
        vector_service.search.return_value = []

        bm25_service = MagicMock()
        bm25_service.search.return_value = []

        service = HybridSearchService(
            db=db,
            vector_service=vector_service,
            bm25_service=bm25_service,
        )

        # This should work synchronously
        results = service.search_sync(
            query="test",
            query_embedding=[0.1] * 1536,
            notebook_id=str(uuid4()),
        )

        assert results == []

    def test_invalidate_bm25_cache(self):
        """Can invalidate BM25 cache through hybrid service."""
        db = MagicMock()

        bm25_service = MagicMock()

        service = HybridSearchService(
            db=db,
            bm25_service=bm25_service,
        )

        notebook_id = str(uuid4())
        service.invalidate_bm25_cache(notebook_id)

        bm25_service.invalidate_cache.assert_called_once_with(notebook_id)


class TestHybridSearchServiceDefaults:
    """Test default service initialization."""

    def test_creates_default_services(self):
        """HybridSearchService creates default vector and BM25 services."""
        db = MagicMock()

        service = HybridSearchService(db=db)

        assert service.vector_service is not None
        assert service.bm25_service is not None
        assert service.rrf_k == 60  # Default RRF constant

    def test_custom_rrf_k(self):
        """Can configure custom RRF k parameter."""
        db = MagicMock()

        service = HybridSearchService(db=db, rrf_k=100)

        assert service.rrf_k == 100


# ============================================================================
# Integration Tests (with real database mocks)
# ============================================================================

class TestHybridSearchIntegration:
    """Integration tests for hybrid search flow."""

    @pytest.mark.asyncio
    async def test_full_hybrid_search_flow(self):
        """Test complete hybrid search with mocked dependencies."""
        db = MagicMock()

        notebook_id = str(uuid4())
        chunk_id_both = str(uuid4())
        chunk_id_vector = str(uuid4())
        chunk_id_bm25 = str(uuid4())

        # Chunk appearing in both (should rank highest)
        vector_service = MagicMock()
        vector_service.search.return_value = [
            SearchResult(
                chunk_id=chunk_id_both,
                source_id=str(uuid4()),
                notebook_id=notebook_id,
                content="Machine learning is powerful",
                score=0.95,
                metadata={"page": 1},
                source_title="ML Guide",
                chunk_index=0,
            ),
            SearchResult(
                chunk_id=chunk_id_vector,
                source_id=str(uuid4()),
                notebook_id=notebook_id,
                content="Neural networks for classification",
                score=0.85,
                metadata={"page": 2},
                source_title="ML Guide",
                chunk_index=1,
            ),
        ]

        bm25_service = MagicMock()
        bm25_service.search.return_value = [
            SearchResult(
                chunk_id=chunk_id_both,
                source_id=str(uuid4()),
                notebook_id=notebook_id,
                content="Machine learning is powerful",
                score=6.5,
                metadata={"page": 1},
                source_title="ML Guide",
                chunk_index=0,
            ),
            SearchResult(
                chunk_id=chunk_id_bm25,
                source_id=str(uuid4()),
                notebook_id=notebook_id,
                content="Python machine learning tutorial",
                score=4.2,
                metadata={"page": 3},
                source_title="Python Guide",
                chunk_index=2,
            ),
        ]

        service = HybridSearchService(
            db=db,
            vector_service=vector_service,
            bm25_service=bm25_service,
        )

        results = await service.search(
            query="machine learning",
            query_embedding=[0.1] * 1536,
            notebook_id=notebook_id,
            top_k=10,
        )

        # Verify results
        assert len(results) == 3

        # Chunk appearing in both should be first (highest RRF score)
        assert results[0].chunk_id == chunk_id_both
        assert results[0].vector_rank == 1
        assert results[0].bm25_rank == 1
        assert results[0].vector_score == 0.95
        assert results[0].bm25_score == 6.5

        # Other chunks should follow
        chunk_ids = [r.chunk_id for r in results]
        assert chunk_id_vector in chunk_ids
        assert chunk_id_bm25 in chunk_ids


class TestHybridSearchPerformance:
    """Performance checks for hybrid retrieval orchestration."""

    @pytest.mark.asyncio
    async def test_hybrid_search_typical_query_runs_fast(self):
        """Typical hybrid query should complete within the target budget."""
        db = MagicMock()
        notebook_id = str(uuid4())

        vector_service = MagicMock()
        vector_service.search.return_value = [
            SearchResult(
                chunk_id=str(uuid4()),
                source_id=str(uuid4()),
                notebook_id=notebook_id,
                content=f"Vector result {i}",
                score=0.95 - (i * 0.001),
                metadata={"page": i + 1},
                source_title="Vector Source",
                chunk_index=i,
            )
            for i in range(100)
        ]

        bm25_service = MagicMock()
        bm25_service.search.return_value = [
            SearchResult(
                chunk_id=str(uuid4()),
                source_id=str(uuid4()),
                notebook_id=notebook_id,
                content=f"BM25 result {i}",
                score=6.0 - (i * 0.01),
                metadata={"page": i + 1},
                source_title="BM25 Source",
                chunk_index=100 + i,
            )
            for i in range(100)
        ]

        service = HybridSearchService(
            db=db,
            vector_service=vector_service,
            bm25_service=bm25_service,
        )

        start = time.perf_counter()
        results = await service.search(
            query="machine learning",
            query_embedding=[0.1] * 1536,
            notebook_id=notebook_id,
            top_k=10,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert len(results) == 10
        assert elapsed_ms < 300, f"Hybrid search took {elapsed_ms:.2f}ms"
