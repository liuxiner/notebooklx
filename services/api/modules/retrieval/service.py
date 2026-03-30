"""
Vector similarity search service using pgvector.

Feature 2.4: Vector Indexing with pgvector

Provides:
- Vector similarity search with cosine similarity
- Notebook-scoped search (filter by notebook_id)
- Top-K retrieval with relevance scores
"""
from dataclasses import dataclass
from typing import List, Optional
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session

from services.api.core.database import Base
from services.api.modules.chunking.models import SourceChunk
from services.api.modules.sources.models import Source
from services.api.modules.notebooks.models import Notebook


@dataclass
class SearchResult:
    """A single search result with relevance score and metadata."""
    chunk_id: str
    source_id: str
    notebook_id: str
    content: str
    score: float  # Similarity score (higher is better)
    metadata: dict  # Page, heading, char positions, etc.
    source_title: str
    chunk_index: int

    def __repr__(self) -> str:
        return f"<SearchResult(score={self.score:.4f}, content={self.content[:50]}...)>"


class VectorSearchService:
    """
    Service for performing vector similarity search using pgvector.

    Uses cosine similarity with normalized embeddings for efficient
    semantic search. Always filters by notebook_id for scoped search.
    """

    def __init__(self, db: Session):
        self.db = db

    def search(
        self,
        query_embedding: List[float],
        notebook_id: str,
        top_k: int = 10,
        min_score: float = 0.0,
    ) -> List[SearchResult]:
        """
        Perform vector similarity search within a notebook.

        Args:
            query_embedding: Query vector (must be same dimension as chunk embeddings)
            notebook_id: Scope search to this notebook only
            top_k: Maximum number of results to return
            min_score: Minimum similarity score threshold (0-1)

        Returns:
            List of SearchResult objects sorted by relevance (highest first)

        Raises:
            ValueError: If query_embedding is empty or invalid
        """
        if not query_embedding:
            raise ValueError("query_embedding cannot be empty")

        # Normalize query embedding for cosine similarity
        from services.api.modules.embeddings import normalize_embedding
        normalized_query = normalize_embedding(query_embedding)

        # Build the query with pgvector cosine similarity
        # On PostgreSQL with pgvector, use the <=> operator (cosine distance)
        # On SQLite, fall back to manual calculation

        # First check if we're using PostgreSQL
        is_postgres = self.db.bind.dialect.name == "postgresql"

        if is_postgres:
            # Use pgvector's cosine distance operator
            # Score = 1 - cosine_distance (so higher is better)
            results = self._search_with_pgvector(
                normalized_query, notebook_id, top_k, min_score
            )
        else:
            # Fallback for SQLite: use manual cosine similarity
            results = self._search_fallback(
                normalized_query, notebook_id, top_k, min_score
            )

        return results

    def _search_with_pgvector(
        self,
        query_embedding: List[float],
        notebook_id: str,
        top_k: int,
        min_score: float,
    ) -> List[SearchResult]:
        """Search using pgvector's cosine distance operator."""
        from sqlalchemy import cast

        # Import the vector type
        from services.api.core.vector import EmbeddingVector

        # Convert embedding to pgvector string format
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        # Query with cosine distance and notebook filter
        # cosine_distance = embedding <=> query
        # similarity = 1 - cosine_distance
        query = (
            select(
                SourceChunk.id,
                SourceChunk.source_id,
                SourceChunk.content,
                SourceChunk.chunk_metadata,
                SourceChunk.chunk_index,
                Source.title.label("source_title"),
                Source.notebook_id,
                text("1 - (embedding <=> :query)::float").label("score"),
            )
            .join(Source, SourceChunk.source_id == Source.id)
            .where(Source.notebook_id == notebook_id)
            .where(SourceChunk.embedding.isnot(None))
            .order_by(text("score DESC"))
            .limit(top_k)
        )

        result = self.db.execute(query, {"query": embedding_str})
        rows = result.all()

        # Convert to SearchResult objects
        results = []
        for row in rows:
            score = float(row.score)
            if score >= min_score:
                results.append(
                    SearchResult(
                        chunk_id=str(row.id),
                        source_id=str(row.source_id),
                        notebook_id=str(row.notebook_id),
                        content=row.content,
                        score=score,
                        metadata=row.chunk_metadata or {},
                        source_title=row.source_title,
                        chunk_index=row.chunk_index,
                    )
                )

        return results

    def _search_fallback(
        self,
        query_embedding: List[float],
        notebook_id: str,
        top_k: int,
        min_score: float,
    ) -> List[SearchResult]:
        """
        Fallback search for SQLite (manual cosine similarity).

        This is slower and should only be used for local development/testing.
        """
        import json
        import numpy as np
        import uuid

        # Convert notebook_id to UUID hex format (without dashes) for SQLite compatibility
        if isinstance(notebook_id, str):
            notebook_uuid = uuid.UUID(notebook_id)
            notebook_id_str = notebook_uuid.hex
        else:
            notebook_id_str = notebook_id.hex

        # Fetch all chunks for the notebook with embeddings
        # Use raw SQL to properly filter JSON null values
        raw_query = text("""
            SELECT
                source_chunks.id,
                source_chunks.source_id,
                source_chunks.content,
                source_chunks.chunk_metadata,
                source_chunks.chunk_index,
                sources.title AS source_title,
                sources.notebook_id,
                source_chunks.embedding
            FROM source_chunks
            JOIN sources ON source_chunks.source_id = sources.id
            WHERE sources.notebook_id = :notebook_id
            AND source_chunks.embedding IS NOT NULL
            AND source_chunks.embedding != 'null'
            AND source_chunks.embedding != '[]'
        """)

        result = self.db.execute(raw_query, {"notebook_id": notebook_id_str})
        rows = result.fetchall()

        # Calculate cosine similarity manually
        results = []
        query_array = np.array(query_embedding)

        for row in rows:
            chunk_embedding = row.embedding
            if chunk_embedding:
                # Parse JSON string if needed (SQLite stores JSON columns as strings)
                if isinstance(chunk_embedding, str):
                    try:
                        chunk_embedding = json.loads(chunk_embedding)
                    except json.JSONDecodeError:
                        continue

                if not chunk_embedding or not isinstance(chunk_embedding, (list, tuple)):
                    continue

                chunk_array = np.array(chunk_embedding, dtype=float)
                # Cosine similarity
                norm_query = np.linalg.norm(query_array)
                norm_chunk = np.linalg.norm(chunk_array)
                if norm_query == 0 or norm_chunk == 0:
                    continue

                similarity = np.dot(query_array, chunk_array) / (norm_query * norm_chunk)

                if similarity >= min_score:
                    # Parse chunk_metadata if it's a string
                    metadata = row.chunk_metadata
                    if isinstance(metadata, str):
                        try:
                            metadata = json.loads(metadata)
                        except json.JSONDecodeError:
                            metadata = {}

                    # Convert UUID hex format back to standard UUID format with dashes
                    notebook_id_value = row.notebook_id
                    if isinstance(notebook_id_value, str) and len(notebook_id_value) == 32:
                        # It's a hex string without dashes, convert to standard UUID format
                        notebook_id_value = str(uuid.UUID(notebook_id_value))

                    results.append(
                        SearchResult(
                            chunk_id=str(row.id),
                            source_id=str(row.source_id),
                            notebook_id=notebook_id_value,
                            content=row.content,
                            score=float(similarity),
                            metadata=metadata or {},
                            source_title=row.source_title,
                            chunk_index=row.chunk_index,
                        )
                    )

        # Sort by score and limit to top_k
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def count_chunks_with_embeddings(self, notebook_id: str) -> int:
        """
        Count chunks in a notebook that have embeddings.

        Useful for monitoring ingestion progress.
        """
        is_postgres = self.db.bind.dialect.name == "postgresql"

        if is_postgres:
            # PostgreSQL with pgvector: use isnot(None)
            query = (
                select(func.count(SourceChunk.id))
                .join(Source, SourceChunk.source_id == Source.id)
                .where(Source.notebook_id == notebook_id)
                .where(SourceChunk.embedding.isnot(None))
            )
            result = self.db.execute(query).scalar()
        else:
            # SQLite: JSON null is stored as string 'null', use raw SQL
            # Convert notebook_id to UUID hex format (without dashes) for SQLite compatibility
            import uuid
            if isinstance(notebook_id, str):
                notebook_uuid = uuid.UUID(notebook_id)
                notebook_id_str = notebook_uuid.hex
            else:
                notebook_id_str = notebook_id.hex

            query = text("""
                SELECT COUNT(*) FROM source_chunks
                JOIN sources ON source_chunks.source_id = sources.id
                WHERE sources.notebook_id = :notebook_id
                AND source_chunks.embedding IS NOT NULL
                AND source_chunks.embedding != 'null'
                AND source_chunks.embedding != '[]'
            """)
            result = self.db.execute(query, {"notebook_id": notebook_id_str}).scalar()

        return result or 0

    def get_stats(self) -> dict:
        """Get statistics about indexed chunks."""
        is_postgres = self.db.bind.dialect.name == "postgresql"

        total_chunks = self.db.execute(
            select(func.count(SourceChunk.id))
        ).scalar() or 0

        if is_postgres:
            chunks_with_embeddings = self.db.execute(
                select(func.count(SourceChunk.id)).where(SourceChunk.embedding.isnot(None))
            ).scalar() or 0
        else:
            # SQLite: JSON null is stored as string 'null', use raw SQL
            chunks_with_embeddings = self.db.execute(
                text("""
                    SELECT COUNT(*) FROM source_chunks
                    WHERE embedding IS NOT NULL
                    AND embedding != 'null'
                    AND embedding != '[]'
                """)
            ).scalar() or 0

        return {
            "total_chunks": total_chunks,
            "chunks_with_embeddings": chunks_with_embeddings,
            "coverage_percent": (
                (chunks_with_embeddings / total_chunks * 100) if total_chunks > 0 else 0
            ),
        }
