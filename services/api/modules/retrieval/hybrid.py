"""
Hybrid retrieval combining BM25 keyword search and vector similarity.

Feature 3.1: Hybrid Retrieval (BM25 + Vector)

Implements:
- BM25 keyword search for lexical matching
- Vector similarity for semantic matching
- RRF (Reciprocal Rank Fusion) for combining results
"""
from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from sqlalchemy import text, select
from sqlalchemy.orm import Session

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    class BM25Okapi:
        """
        Lightweight BM25 fallback used when the optional dependency is not installed.

        This keeps local tests runnable in stripped-down environments while
        preserving the same get_scores() interface used by the service.
        """

        def __init__(self, corpus: List[List[str]], k1: float = 1.5, b: float = 0.75):
            self.corpus = corpus
            self.k1 = k1
            self.b = b
            self.doc_len = [len(doc) for doc in corpus]
            self.avgdl = sum(self.doc_len) / len(self.doc_len) if self.doc_len else 0.0

            doc_freqs: Dict[str, int] = {}
            for doc in corpus:
                for token in set(doc):
                    doc_freqs[token] = doc_freqs.get(token, 0) + 1

            self.idf: Dict[str, float] = {}
            n_docs = len(corpus)
            for token, df in doc_freqs.items():
                self.idf[token] = math.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))

        def get_scores(self, query_tokens: List[str]) -> List[float]:
            scores: List[float] = []
            if not self.corpus:
                return scores

            query_terms = set(query_tokens)
            for doc in self.corpus:
                score = 0.0
                doc_len = len(doc)
                if not doc_len:
                    scores.append(0.0)
                    continue

                for term in query_terms:
                    tf = doc.count(term)
                    if not tf:
                        continue

                    idf = self.idf.get(term, 0.0)
                    denom = tf + self.k1 * (1.0 - self.b + self.b * doc_len / self.avgdl) if self.avgdl else tf + self.k1
                    score += idf * (tf * (self.k1 + 1.0)) / denom

                scores.append(score)

            return scores

from services.api.modules.chunking.models import SourceChunk
from services.api.modules.sources.models import Source
from services.api.modules.retrieval.service import VectorSearchService, SearchResult

logger = logging.getLogger(__name__)


@dataclass
class HybridSearchResult:
    """Result from hybrid search with combined scoring."""

    chunk_id: str
    source_id: str
    notebook_id: str
    content: str
    score: float  # Combined RRF score
    vector_score: Optional[float] = None
    bm25_score: Optional[float] = None
    vector_rank: Optional[int] = None
    bm25_rank: Optional[int] = None
    metadata: dict = field(default_factory=dict)
    source_title: str = ""
    chunk_index: int = 0

    def __repr__(self) -> str:
        return f"<HybridSearchResult(score={self.score:.4f}, content={self.content[:50]}...)>"


class BM25SearchService:
    """
    BM25 keyword search service.

    Provides lexical search using the BM25 ranking algorithm.
    Results are scoped to a specific notebook.
    """

    def __init__(self, db: Session):
        self.db = db
        self._index_cache: Dict[str, tuple[BM25Okapi, List[Dict[str, Any]]]] = {}

    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize text for BM25 indexing.

        Simple whitespace + punctuation tokenization with lowercasing.
        """
        # Remove punctuation, split on whitespace, lowercase
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        tokens = text.split()
        # Filter very short tokens
        return [t for t in tokens if len(t) > 1]

    def _build_index(
        self,
        notebook_id: str,
    ) -> tuple[BM25Okapi, List[Dict[str, Any]]]:
        """
        Build BM25 index for all chunks in a notebook.

        Returns the BM25 index and a list of chunk metadata for result mapping.
        """
        # Fetch all chunks for the notebook
        query = (
            select(
                SourceChunk.id,
                SourceChunk.source_id,
                SourceChunk.content,
                SourceChunk.chunk_metadata,
                SourceChunk.chunk_index,
                Source.title.label("source_title"),
                Source.notebook_id,
            )
            .join(Source, SourceChunk.source_id == Source.id)
            .where(Source.notebook_id == notebook_id)
        )

        result = self.db.execute(query)
        rows = result.all()

        if not rows:
            return BM25Okapi([[""]]), []

        # Tokenize all documents
        corpus = []
        chunk_data = []

        for row in rows:
            tokens = self._tokenize(row.content)
            corpus.append(tokens)
            chunk_data.append({
                "chunk_id": str(row.id),
                "source_id": str(row.source_id),
                "notebook_id": str(row.notebook_id),
                "content": row.content,
                "metadata": row.chunk_metadata or {},
                "source_title": row.source_title,
                "chunk_index": row.chunk_index,
            })

        # Build BM25 index
        bm25 = BM25Okapi(corpus)
        return bm25, chunk_data

    def _get_or_build_index(
        self,
        notebook_id: str,
        force_rebuild: bool = False,
    ) -> tuple[BM25Okapi, List[Dict[str, Any]]]:
        """Get cached index or build a new one."""
        if force_rebuild or notebook_id not in self._index_cache:
            self._index_cache[notebook_id] = self._build_index(notebook_id)
        return self._index_cache[notebook_id]

    def search(
        self,
        query: str,
        notebook_id: str,
        top_k: int = 10,
        min_score: float = 0.0,
        force_rebuild_index: bool = False,
    ) -> List[SearchResult]:
        """
        Search for chunks using BM25 keyword matching.

        Args:
            query: Search query text
            notebook_id: Scope search to this notebook
            top_k: Maximum number of results
            min_score: Minimum BM25 score threshold
            force_rebuild_index: Force rebuilding the index

        Returns:
            List of SearchResult sorted by BM25 score
        """
        if not query or not query.strip():
            return []

        bm25, chunk_data = self._get_or_build_index(notebook_id, force_rebuild_index)

        if not chunk_data:
            return []

        # Tokenize query
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # Get BM25 scores
        scores = bm25.get_scores(query_tokens)

        # Pair scores with chunk data and sort
        scored_chunks = [
            (score, data) for score, data in zip(scores, chunk_data)
            if score >= min_score
        ]
        scored_chunks.sort(key=lambda x: x[0], reverse=True)

        # Convert to SearchResult objects
        results = []
        for score, data in scored_chunks[:top_k]:
            results.append(
                SearchResult(
                    chunk_id=data["chunk_id"],
                    source_id=data["source_id"],
                    notebook_id=data["notebook_id"],
                    content=data["content"],
                    score=float(score),
                    metadata=data["metadata"],
                    source_title=data["source_title"],
                    chunk_index=data["chunk_index"],
                )
            )

        return results

    def invalidate_cache(self, notebook_id: str) -> None:
        """Invalidate the cached index for a notebook."""
        if notebook_id in self._index_cache:
            del self._index_cache[notebook_id]


def reciprocal_rank_fusion(
    result_lists: List[List[SearchResult]],
    k: int = 60,
) -> List[HybridSearchResult]:
    """
    Combine multiple ranked result lists using Reciprocal Rank Fusion.

    RRF score = sum(1 / (k + rank)) across all lists

    Args:
        result_lists: List of ranked result lists
        k: RRF constant (typically 60)

    Returns:
        Combined results sorted by RRF score
    """
    # Track RRF scores and metadata by chunk_id
    chunk_scores: Dict[str, float] = {}
    chunk_data: Dict[str, Dict[str, Any]] = {}
    chunk_ranks: Dict[str, Dict[str, int]] = {}

    for list_idx, results in enumerate(result_lists):
        list_name = f"list_{list_idx}"
        for rank, result in enumerate(results, start=1):
            chunk_id = result.chunk_id

            # Calculate RRF contribution
            rrf_score = 1.0 / (k + rank)
            chunk_scores[chunk_id] = chunk_scores.get(chunk_id, 0.0) + rrf_score

            # Store metadata (from first occurrence)
            if chunk_id not in chunk_data:
                chunk_data[chunk_id] = {
                    "source_id": result.source_id,
                    "notebook_id": result.notebook_id,
                    "content": result.content,
                    "metadata": result.metadata,
                    "source_title": result.source_title,
                    "chunk_index": result.chunk_index,
                }
                chunk_ranks[chunk_id] = {}

            # Store rank from this list
            chunk_ranks[chunk_id][list_name] = rank

    # Sort by RRF score
    sorted_chunks = sorted(chunk_scores.items(), key=lambda x: x[1], reverse=True)

    # Build hybrid results
    results = []
    for chunk_id, score in sorted_chunks:
        data = chunk_data[chunk_id]
        ranks = chunk_ranks[chunk_id]

        results.append(
            HybridSearchResult(
                chunk_id=chunk_id,
                source_id=data["source_id"],
                notebook_id=data["notebook_id"],
                content=data["content"],
                score=score,
                vector_rank=ranks.get("list_0"),
                bm25_rank=ranks.get("list_1"),
                metadata=data["metadata"],
                source_title=data["source_title"],
                chunk_index=data["chunk_index"],
            )
        )

    return results


class HybridSearchService:
    """
    Hybrid retrieval combining vector similarity and BM25 keyword search.

    Uses RRF (Reciprocal Rank Fusion) to combine results from both methods.
    """

    def __init__(
        self,
        db: Session,
        vector_service: Optional[VectorSearchService] = None,
        bm25_service: Optional[BM25SearchService] = None,
        rrf_k: int = 60,
    ):
        """
        Initialize hybrid search service.

        Args:
            db: SQLAlchemy session
            vector_service: Optional custom vector search service
            bm25_service: Optional custom BM25 search service
            rrf_k: RRF constant (default 60)
        """
        self.db = db
        self.vector_service = vector_service or VectorSearchService(db)
        self.bm25_service = bm25_service or BM25SearchService(db)
        self.rrf_k = rrf_k

    async def search(
        self,
        query: str,
        query_embedding: List[float],
        notebook_id: str,
        top_k: int = 10,
        vector_weight: float = 0.5,
        bm25_weight: float = 0.5,
        vector_top_k: Optional[int] = None,
        bm25_top_k: Optional[int] = None,
    ) -> List[HybridSearchResult]:
        """
        Perform hybrid search using both vector and BM25.

        Args:
            query: Text query for BM25 search
            query_embedding: Query embedding vector for vector search
            notebook_id: Scope search to this notebook
            top_k: Maximum final results to return
            vector_weight: Weight for vector results (not used in RRF, reserved for future)
            bm25_weight: Weight for BM25 results (not used in RRF, reserved for future)
            vector_top_k: Number of candidates from vector search (default: 2*top_k)
            bm25_top_k: Number of candidates from BM25 search (default: 2*top_k)

        Returns:
            List of HybridSearchResult sorted by combined RRF score
        """
        # Set default candidate counts
        vector_top_k = vector_top_k or (top_k * 2)
        bm25_top_k = bm25_top_k or (top_k * 2)

        # Get vector search results
        vector_results = self.vector_service.search(
            query_embedding=query_embedding,
            notebook_id=notebook_id,
            top_k=vector_top_k,
        )

        # Store original vector scores
        for i, r in enumerate(vector_results):
            r._vector_score = r.score  # type: ignore

        # Get BM25 search results
        bm25_results = self.bm25_service.search(
            query=query,
            notebook_id=notebook_id,
            top_k=bm25_top_k,
        )

        # Combine using RRF
        hybrid_results = reciprocal_rank_fusion(
            [vector_results, bm25_results],
            k=self.rrf_k,
        )

        # Add individual scores
        vector_scores = {r.chunk_id: r.score for r in vector_results}
        bm25_scores = {r.chunk_id: r.score for r in bm25_results}

        for result in hybrid_results:
            result.vector_score = vector_scores.get(result.chunk_id)
            result.bm25_score = bm25_scores.get(result.chunk_id)

        return hybrid_results[:top_k]

    def search_sync(
        self,
        query: str,
        query_embedding: List[float],
        notebook_id: str,
        top_k: int = 10,
        **kwargs,
    ) -> List[HybridSearchResult]:
        """
        Synchronous version of hybrid search.

        Use this when not in an async context.
        """
        import asyncio

        # Check if we're already in an event loop
        try:
            loop = asyncio.get_running_loop()
            # We're in an async context, create a new task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    self.search(query, query_embedding, notebook_id, top_k, **kwargs)
                )
                return future.result()
        except RuntimeError:
            # No running loop, safe to use asyncio.run
            return asyncio.run(
                self.search(query, query_embedding, notebook_id, top_k, **kwargs)
            )

    def invalidate_bm25_cache(self, notebook_id: str) -> None:
        """Invalidate the BM25 index cache for a notebook."""
        self.bm25_service.invalidate_cache(notebook_id)
