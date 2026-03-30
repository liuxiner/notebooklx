"""
Retrieval module for vector and hybrid search.

Feature 2.4: Vector Indexing with pgvector
Feature 3.1: Hybrid Retrieval (BM25 + Vector)

This module provides:
- Vector similarity search with pgvector
- BM25 keyword search
- Hybrid search with RRF fusion
- Cosine similarity queries with notebook filtering
- HNSW indexing for performance
"""
from services.api.modules.retrieval.service import VectorSearchService, SearchResult
from services.api.modules.retrieval.hybrid import (
    BM25SearchService,
    HybridSearchService,
    HybridSearchResult,
    reciprocal_rank_fusion,
)

__all__ = [
    "VectorSearchService",
    "SearchResult",
    "BM25SearchService",
    "HybridSearchService",
    "HybridSearchResult",
    "reciprocal_rank_fusion",
]
