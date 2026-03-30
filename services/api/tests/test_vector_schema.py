"""
Tests for pgvector-ready vector schema support.

Feature 2.4: Vector Indexing with pgvector
Slice: pgvector extension migration + cross-dialect embedding column

Acceptance Criteria tested:
- pgvector extension installed in PostgreSQL
"""
import importlib

import pytest
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql, sqlite


class TestEmbeddingVectorType:
    """Test the cross-dialect vector column type."""

    def test_embedding_vector_uses_vector_type_on_postgresql(self):
        """PostgreSQL should compile the embedding type to VECTOR."""
        from services.api.core.vector import EmbeddingVector

        embedding_type = EmbeddingVector()
        impl = embedding_type.load_dialect_impl(postgresql.dialect())

        assert impl.get_col_spec() == "VECTOR"

    def test_embedding_vector_can_optionally_pin_dimension(self):
        """The vector type should support an optional fixed dimension."""
        from services.api.core.vector import EmbeddingVector

        embedding_type = EmbeddingVector(dimension=8)
        impl = embedding_type.load_dialect_impl(postgresql.dialect())

        assert impl.get_col_spec() == "VECTOR(8)"

    def test_embedding_vector_uses_json_on_sqlite(self):
        """SQLite should keep using JSON for local development and tests."""
        from services.api.core.vector import EmbeddingVector

        embedding_type = EmbeddingVector()
        impl = embedding_type.load_dialect_impl(sqlite.dialect())

        assert impl.__visit_name__ == "JSON"

    def test_embedding_vector_postgresql_processors_round_trip(self):
        """PostgreSQL processors should serialize vectors to pgvector text format."""
        from services.api.core.vector import EmbeddingVector

        dialect = postgresql.dialect()
        impl = EmbeddingVector().load_dialect_impl(dialect)

        bind_processor = impl.bind_processor(dialect)
        result_processor = impl.result_processor(dialect, None)

        assert bind_processor([0.1, -0.2, 0.3]) == "[0.1,-0.2,0.3]"
        assert result_processor("[0.1,-0.2,0.3]") == pytest.approx([0.1, -0.2, 0.3])


class TestSourceChunkEmbeddingColumn:
    """Test SourceChunk uses the vector-ready column type."""

    def test_source_chunk_uses_embedding_vector_type(self):
        """SourceChunk.embedding should use the shared cross-dialect type."""
        from services.api.core.vector import EmbeddingVector
        from services.api.modules.chunking.models import SourceChunk

        mapper = inspect(SourceChunk)
        embedding_column = mapper.columns["embedding"]

        assert isinstance(embedding_column.type, EmbeddingVector)

    def test_source_chunk_embedding_round_trips_on_sqlite(
        self,
        db,
        sample_source,
    ):
        """SQLite should still persist embeddings for local development."""
        from services.api.modules.chunking.models import SourceChunk

        chunk = SourceChunk(
            source_id=sample_source.id,
            chunk_index=0,
            content="Chunk with stored embedding",
            token_count=4,
            char_start=0,
            char_end=27,
            embedding=[0.1, 0.2, 0.3],
        )
        db.add(chunk)
        db.commit()
        db.refresh(chunk)

        assert chunk.embedding == pytest.approx([0.1, 0.2, 0.3])


class TestPgvectorMigration:
    """Test pgvector installation migration behavior."""

    def test_upgrade_installs_pgvector_extension_on_postgresql(self):
        """Upgrade should install pgvector and alter the embedding column on PostgreSQL."""
        migration = importlib.import_module(
            "services.api.alembic.versions.a7c9d2e1f4b6_enable_pgvector_for_source_chunks"
        )

        class FakeBind:
            class dialect:
                name = "postgresql"

        execute_calls = []
        alter_calls = []

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(migration.op, "get_bind", lambda: FakeBind())
        monkeypatch.setattr(
            migration.op,
            "execute",
            lambda *args, **kwargs: execute_calls.append((args, kwargs)),
        )
        monkeypatch.setattr(
            migration.op,
            "alter_column",
            lambda *args, **kwargs: alter_calls.append((args, kwargs)),
        )

        try:
            migration.upgrade()
        finally:
            monkeypatch.undo()

        # Should have 2 execute calls: pgvector extension + HNSW index
        assert len(execute_calls) == 2
        assert execute_calls[0] == (("CREATE EXTENSION IF NOT EXISTS vector",), {})
        # Second call creates the HNSW index
        hnsw_sql = execute_calls[1][0][0]
        assert "CREATE INDEX IF NOT EXISTS idx_source_chunks_embedding_hnsw" in hnsw_sql
        assert "USING hnsw" in hnsw_sql
        assert "vector_cosine_ops" in hnsw_sql

        assert len(alter_calls) == 1
        assert alter_calls[0][0] == ("source_chunks", "embedding")
        assert alter_calls[0][1]["postgresql_using"] == "embedding::text::vector"

    def test_upgrade_is_noop_on_sqlite(self):
        """Upgrade should skip pgvector work when running against SQLite."""
        migration = importlib.import_module(
            "services.api.alembic.versions.a7c9d2e1f4b6_enable_pgvector_for_source_chunks"
        )

        class FakeBind:
            class dialect:
                name = "sqlite"

        execute_calls = []
        alter_calls = []

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(migration.op, "get_bind", lambda: FakeBind())
        monkeypatch.setattr(migration.op, "execute", lambda *args, **kwargs: execute_calls.append((args, kwargs)))
        monkeypatch.setattr(
            migration.op,
            "alter_column",
            lambda *args, **kwargs: alter_calls.append((args, kwargs)),
        )

        try:
            migration.upgrade()
        finally:
            monkeypatch.undo()

        assert execute_calls == []
        assert alter_calls == []
