"""
Tests for vector similarity search.

Feature 2.4: Vector Indexing with pgvector

Acceptance Criteria tested:
- Vector similarity search returns relevant chunks
- Index supports cosine similarity queries
- Can filter by notebook_id for scoped search
- Query performance < 200ms for typical notebook (< 1000 chunks)
"""
import time
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from services.api.modules.retrieval.service import VectorSearchService, SearchResult
from services.api.modules.chunking.models import SourceChunk
from services.api.modules.sources.models import Source, SourceType, SourceStatus
from services.api.modules.notebooks.models import Notebook
from services.api.modules.embeddings import normalize_embedding


class TestVectorSearchService:
    """Test vector similarity search functionality."""

    def test_search_returns_relevant_chunks(
        self,
        db: Session,
        sample_notebook: Notebook,
        sample_source: Source,
    ):
        """Vector similarity search should return chunks sorted by relevance."""
        # Create chunks with different embeddings
        chunks = []
        for i in range(5):
            # Create embeddings with increasing similarity to query [1, 0, 0, ...]
            embedding = [0.0] * 10
            embedding[0] = 1.0 - (i * 0.1)  # Decreasing similarity
            embedding = normalize_embedding(embedding)

            chunk = SourceChunk(
                source_id=sample_source.id,
                chunk_index=i,
                content=f"Chunk {i} content",
                token_count=4,
                char_start=i * 20,
                char_end=(i + 1) * 20,
                embedding=embedding,
                chunk_metadata={"page": i + 1},
            )
            chunks.append(chunk)
            db.add(chunk)

        db.commit()

        # Search with query similar to first chunk
        query_embedding = normalize_embedding([1.0] + [0.0] * 9)
        service = VectorSearchService(db)
        results = service.search(
            query_embedding=query_embedding,
            notebook_id=sample_notebook.id,
            top_k=3,
        )

        # Should return top 3 results
        assert len(results) <= 3
        assert all(isinstance(r, SearchResult) for r in results)

        # Results should be sorted by score (highest first)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

        # First result should be most similar
        assert results[0].chunk_index == 0

    def test_search_filters_by_notebook_id(
        self,
        db: Session,
        sample_notebook: Notebook,
        sample_source: Source,
    ):
        """Search should only return chunks from the specified notebook."""
        # Create another notebook with chunks
        other_notebook = Notebook(name="Other Notebook", user_id=sample_notebook.user_id)
        db.add(other_notebook)
        db.commit()

        other_source = Source(
            notebook_id=other_notebook.id,
            source_type=SourceType.TEXT,
            title="Other Source",
            status=SourceStatus.READY,
        )
        db.add(other_source)
        db.commit()

        # Add chunk to other notebook
        query_embedding = normalize_embedding([1.0] + [0.0] * 9)
        other_chunk = SourceChunk(
            source_id=other_source.id,
            chunk_index=0,
            content="Other notebook chunk",
            token_count=3,
            char_start=0,
            char_end=20,
            embedding=query_embedding,
        )
        db.add(other_chunk)

        # Add chunk to sample notebook
        sample_chunk = SourceChunk(
            source_id=sample_source.id,
            chunk_index=0,
            content="Sample notebook chunk",
            token_count=3,
            char_start=0,
            char_end=21,
            embedding=query_embedding,
        )
        db.add(sample_chunk)
        db.commit()

        # Search in sample notebook should not return other notebook's chunk
        service = VectorSearchService(db)
        results = service.search(
            query_embedding=query_embedding,
            notebook_id=sample_notebook.id,
            top_k=10,
        )

        assert len(results) == 1
        assert results[0].notebook_id == str(sample_notebook.id)
        assert results[0].content == "Sample notebook chunk"

    def test_search_respects_min_score_threshold(
        self,
        db: Session,
        sample_notebook: Notebook,
        sample_source: Source,
    ):
        """Search should only return results above the minimum score threshold."""
        # Create chunks with varying similarity
        for i in range(5):
            embedding = normalize_embedding([1.0 - (i * 0.3)] + [0.0] * 9)
            chunk = SourceChunk(
                source_id=sample_source.id,
                chunk_index=i,
                content=f"Chunk {i}",
                token_count=2,
                char_start=i * 10,
                char_end=(i + 1) * 10,
                embedding=embedding,
            )
            db.add(chunk)

        db.commit()

        # Search with high min_score
        query_embedding = normalize_embedding([1.0] + [0.0] * 9)
        service = VectorSearchService(db)
        results = service.search(
            query_embedding=query_embedding,
            notebook_id=sample_notebook.id,
            top_k=10,
            min_score=0.8,
        )

        # Should only return very similar chunks
        for result in results:
            assert result.score >= 0.8

    def test_search_returns_empty_when_no_embeddings(
        self,
        db: Session,
        sample_notebook: Notebook,
        sample_source: Source,
    ):
        """Search should return empty results when no chunks have embeddings."""
        # Create chunk without embedding
        chunk = SourceChunk(
            source_id=sample_source.id,
            chunk_index=0,
            content="Chunk without embedding",
            token_count=4,
            char_start=0,
            char_end=26,
            embedding=None,
        )
        db.add(chunk)
        db.commit()

        query_embedding = normalize_embedding([1.0] + [0.0] * 9)
        service = VectorSearchService(db)
        results = service.search(
            query_embedding=query_embedding,
            notebook_id=sample_notebook.id,
            top_k=10,
        )

        assert len(results) == 0

    def test_search_includes_source_metadata(
        self,
        db: Session,
        sample_notebook: Notebook,
        sample_source: Source,
    ):
        """Search results should include source title and chunk metadata."""
        embedding = normalize_embedding([1.0] + [0.0] * 9)
        chunk = SourceChunk(
            source_id=sample_source.id,
            chunk_index=0,
            content="Test content",
            token_count=2,
            char_start=0,
            char_end=12,
            embedding=embedding,
            chunk_metadata={"page": 5, "heading": "Introduction"},
        )
        db.add(chunk)
        db.commit()

        query_embedding = normalize_embedding([1.0] + [0.0] * 9)
        service = VectorSearchService(db)
        results = service.search(
            query_embedding=query_embedding,
            notebook_id=sample_notebook.id,
            top_k=10,
        )

        assert len(results) == 1
        assert results[0].source_title == sample_source.title
        assert results[0].metadata == {"page": 5, "heading": "Introduction"}
        assert results[0].chunk_index == 0

    def test_search_performance_for_typical_notebook(
        self,
        db: Session,
        sample_notebook: Notebook,
        sample_source: Source,
    ):
        """Query performance should be < 200ms for typical notebook (< 1000 chunks)."""
        # Create 500 chunks (moderate size notebook)
        embeddings_list = []
        for i in range(500):
            # Generate varied embeddings
            base = [0.0] * 10
            base[i % 10] = 1.0
            embedding = normalize_embedding(base)
            embeddings_list.append(embedding)

            chunk = SourceChunk(
                source_id=sample_source.id,
                chunk_index=i,
                content=f"Chunk {i} with some content here",
                token_count=7,
                char_start=i * 30,
                char_end=(i + 1) * 30,
                embedding=embedding,
            )
            db.add(chunk)

        db.commit()

        # Measure search performance
        query_embedding = normalize_embedding([1.0] + [0.0] * 9)
        service = VectorSearchService(db)

        start_time = time.time()
        results = service.search(
            query_embedding=query_embedding,
            notebook_id=sample_notebook.id,
            top_k=10,
        )
        elapsed_ms = (time.time() - start_time) * 1000

        # Should return results quickly
        assert len(results) > 0
        # Performance target: < 200ms (may be slower on SQLite, but PostgreSQL should be fast)
        # We allow a higher threshold for SQLite fallback
        is_postgres = db.bind.dialect.name == "postgresql"
        max_ms = 200 if is_postgres else 1000
        assert elapsed_ms < max_ms, f"Search took {elapsed_ms:.2f}ms (max: {max_ms}ms)"

    def test_count_chunks_with_embeddings(
        self,
        db: Session,
        sample_notebook: Notebook,
        sample_source: Source,
    ):
        """count_chunks_with_embeddings should return accurate count."""
        # Debug: check initial state
        initial_count = db.query(SourceChunk).filter(
            SourceChunk.source_id == sample_source.id,
            SourceChunk.embedding.isnot(None)
        ).count()
        print(f"\nDEBUG: Initial chunks with embedding for source {sample_source.id}: {initial_count}")

        # Add chunks with and without embeddings
        chunk_with_embedding = SourceChunk(
            source_id=sample_source.id,
            chunk_index=0,
            content="With embedding",
            token_count=2,
            char_start=0,
            char_end=15,
            embedding=normalize_embedding([1.0] + [0.0] * 9),
        )
        db.add(chunk_with_embedding)

        chunk_without_embedding = SourceChunk(
            source_id=sample_source.id,
            chunk_index=1,
            content="Without embedding",
            token_count=2,
            char_start=15,
            char_end=33,
            embedding=None,
        )
        db.add(chunk_without_embedding)

        db.commit()

        # Debug: check state after adding
        all_chunks = db.query(SourceChunk).filter(SourceChunk.source_id == sample_source.id).all()
        print(f"DEBUG: Total chunks for source after adding: {len(all_chunks)}")
        for c in all_chunks:
            print(f"  - Chunk {c.chunk_index}: embedding={c.embedding}")

        service = VectorSearchService(db)
        count = service.count_chunks_with_embeddings(sample_notebook.id)

        print(f"DEBUG: count_chunks_with_embeddings returned: {count}")
        assert count == 1

    def test_get_stats(
        self,
        db: Session,
        sample_notebook: Notebook,
        sample_source: Source,
    ):
        """get_stats should return aggregate statistics."""
        # Add some chunks
        for i in range(3):
            chunk = SourceChunk(
                source_id=sample_source.id,
                chunk_index=i,
                content=f"Chunk {i}",
                token_count=2,
                char_start=i * 10,
                char_end=(i + 1) * 10,
                embedding=normalize_embedding([1.0] + [0.0] * 9) if i < 2 else None,
            )
            db.add(chunk)

        db.commit()

        service = VectorSearchService(db)
        stats = service.get_stats()

        assert stats["total_chunks"] == 3
        assert stats["chunks_with_embeddings"] == 2
        assert stats["coverage_percent"] == pytest.approx(66.67, rel=1)

    def test_search_raises_error_for_empty_embedding(
        self,
        db: Session,
        sample_notebook: Notebook,
    ):
        """Search should raise ValueError for empty query embedding."""
        service = VectorSearchService(db)

        with pytest.raises(ValueError, match="query_embedding cannot be empty"):
            service.search(
                query_embedding=[],
                notebook_id=sample_notebook.id,
            )

    def test_search_respects_top_k_limit(
        self,
        db: Session,
        sample_notebook: Notebook,
        sample_source: Source,
    ):
        """Search should return at most top_k results."""
        # Create 10 chunks
        for i in range(10):
            embedding = normalize_embedding([1.0 - (i * 0.05)] + [0.0] * 9)
            chunk = SourceChunk(
                source_id=sample_source.id,
                chunk_index=i,
                content=f"Chunk {i}",
                token_count=2,
                char_start=i * 10,
                char_end=(i + 1) * 10,
                embedding=embedding,
            )
            db.add(chunk)

        db.commit()

        query_embedding = normalize_embedding([1.0] + [0.0] * 9)
        service = VectorSearchService(db)

        # Request top 5
        results = service.search(
            query_embedding=query_embedding,
            notebook_id=sample_notebook.id,
            top_k=5,
        )

        assert len(results) <= 5

    def test_search_normalizes_sqlite_uuid_strings(
        self,
        db: Session,
        sample_notebook: Notebook,
        sample_source: Source,
    ):
        """SQLite fallback should return UUIDs in standard dashed format."""
        embedding = normalize_embedding([1.0] + [0.0] * 9)
        chunk = SourceChunk(
            source_id=sample_source.id,
            chunk_index=0,
            content="课程 方法论",
            token_count=2,
            char_start=0,
            char_end=6,
            embedding=embedding,
        )
        db.add(chunk)
        db.commit()

        service = VectorSearchService(db)
        results = service.search(
            query_embedding=embedding,
            notebook_id=str(sample_notebook.id),
            top_k=1,
        )

        assert len(results) == 1
        assert results[0].chunk_id == str(chunk.id)
        assert results[0].source_id == str(sample_source.id)
        assert results[0].notebook_id == str(sample_notebook.id)
