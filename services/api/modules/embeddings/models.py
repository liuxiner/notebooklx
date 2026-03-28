"""
Embedding result models.

Feature 2.3: Embedding Generation
"""
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class EmbeddingCostSummary:
    """Aggregate cost summary for a batch embedding request."""

    total_texts: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    cost_per_1k_tokens: float = 0.0


@dataclass
class EmbeddingResult:
    """Result of embedding a single text."""

    text: str
    embedding: List[float]
    token_count: int
    estimated_cost_usd: float = 0.0
    index: Optional[int] = None
