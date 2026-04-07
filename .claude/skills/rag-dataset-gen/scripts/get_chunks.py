#!/usr/bin/env python3
"""
Retrieve chunks from database for a given source.

This script queries the database for all chunks belonging to a source,
returning their IDs, content, and metadata for test case generation.
"""
import uuid
from typing import List, Dict, Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool


def get_source_chunks(
    source_id: str,
    db_url: str = "postgresql://localhost/notebooklx",
) -> List[Dict]:
    """
    Retrieve all chunks for a source from the database.

    Args:
        source_id: Source UUID
        db_url: Database connection URL

    Returns:
        List of chunk dicts with id, content, metadata
    """
    from services.api.modules.chunking.models import SourceChunk

    # Create engine with connection pooling
    engine = create_engine(
        db_url,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
    )

    # Create session
    SessionLocal = sessionmaker(bind=engine)
    db: Session = SessionLocal()

    try:
        # Query chunks for this source, ordered by chunk_index
        chunks = (
            db.query(SourceChunk)
            .filter(SourceChunk.source_id == uuid.UUID(source_id))
            .order_by(SourceChunk.chunk_index)
            .all()
        )

        # Convert to dict format
        result = []
        for chunk in chunks:
            result.append({
                "id": str(chunk.id),
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "token_count": chunk.token_count,
                "char_start": chunk.char_start,
                "char_end": chunk.char_end,
                "metadata": chunk.chunk_metadata or {},
            })

        return result

    finally:
        db.close()
        engine.dispose()


def get_chunks_by_notebook(
    notebook_id: str,
    db_url: str = "postgresql://localhost/notebooklx",
) -> List[Dict]:
    """
    Retrieve all chunks for all sources in a notebook.

    Args:
        notebook_id: Notebook UUID
        db_url: Database connection URL

    Returns:
        List of chunk dicts with source info included
    """
    from services.api.modules.chunking.models import SourceChunk
    from services.api.modules.sources.models import Source

    engine = create_engine(
        db_url,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
    )

    SessionLocal = sessionmaker(bind=engine)
    db: Session = SessionLocal()

    try:
        # Query chunks with source info
        chunks = (
            db.query(SourceChunk, Source)
            .join(Source, Source.id == SourceChunk.source_id)
            .filter(Source.notebook_id == uuid.UUID(notebook_id))
            .order_by(Source.id, SourceChunk.chunk_index)
            .all()
        )

        result = []
        for chunk, source in chunks:
            result.append({
                "id": str(chunk.id),
                "source_id": str(source.id),
                "source_title": source.title,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "token_count": chunk.token_count,
                "metadata": chunk.chunk_metadata or {},
            })

        return result

    finally:
        db.close()
        engine.dispose()


def find_relevant_chunks(
    question: str,
    notebook_id: str,
    top_k: int = 5,
    db_url: str = "postgresql://localhost/notebooklx",
) -> List[Dict]:
    """
    Find relevant chunks for a question using vector similarity.

    This uses pgvector cosine similarity to find the most relevant chunks.

    Args:
        question: Question text
        notebook_id: Notebook UUID
        top_k: Number of chunks to return
        db_url: Database connection URL

    Returns:
        List of chunk dicts with similarity scores
    """
    import numpy as np
    from services.api.modules.chunking.models import SourceChunk
    from services.api.modules.sources.models import Source
    from services.api.modules.embeddings.providers import BigModelEmbeddingProvider

    # Generate question embedding
    provider = BigModelEmbeddingProvider()
    question_embedding = provider.embed_text(question)

    engine = create_engine(db_url, poolclass=QueuePool, pool_size=5)
    SessionLocal = sessionmaker(bind=engine)
    db: Session = SessionLocal()

    try:
        # Use pgvector cosine similarity
        # Note: This requires pgvector extension to be installed
        embedding_array = str(question_embedding).replace("[", "{").replace("]", "}")

        query = (
            db.query(
                SourceChunk.id,
                SourceChunk.content,
                SourceChunk.chunk_index,
                Source.title.label("source_title"),
                SourceChunk.chunk_metadata,
            )
            .join(Source, Source.id == SourceChunk.source_id)
            .filter(Source.notebook_id == uuid.UUID(notebook_id))
            .filter(SourceChunk.embedding.isnot(None))
            .order_by(f"1 - (embedding <=> '{embedding_array}')")
            .limit(top_k)
        )

        results = query.all()

        return [
            {
                "id": str(r.id),
                "content": r.content,
                "chunk_index": r.chunk_index,
                "source_title": r.source_title,
                "metadata": r.chunk_metadata or {},
            }
            for r in results
        ]

    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    import sys
    import os
    from dotenv import load_dotenv

    # Load environment variables
    load_dotenv()

    if len(sys.argv) < 2:
        print("Usage: python get_chunks.py <source_id> [notebook_id]")
        print("   Or: python get_chunks.py --notebook <notebook_id>")
        sys.exit(1)

    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://localhost/notebooklx",
    )

    if sys.argv[1] == "--notebook":
        # Get all chunks for notebook
        notebook_id = sys.argv[2]
        chunks = get_chunks_by_notebook(notebook_id, db_url)
        print(f"Found {len(chunks)} chunks in notebook {notebook_id}")
    else:
        # Get chunks for specific source
        source_id = sys.argv[1]
        chunks = get_source_chunks(source_id, db_url)
        print(f"Found {len(chunks)} chunks for source {source_id}")

    # Print sample chunks
    for i, chunk in enumerate(chunks[:3]):
        print(f"\n--- Chunk {i+1} ---")
        print(f"ID: {chunk['id']}")
        print(f"Content: {chunk['content'][:100]}...")
        print(f"Metadata: {chunk.get('metadata', {})}")
