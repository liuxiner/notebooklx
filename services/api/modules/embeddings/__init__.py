"""
Embedding generation module.

Feature 2.3: Embedding Generation

Providers:
- MockEmbeddingProvider: For testing with deterministic embeddings
- BigModelEmbeddingProvider: ZhipuAI/BigModel with OpenAI-compatible API
  via ZHIPUAI_* or ZAI_* environment variables
"""
from services.api.modules.embeddings.models import EmbeddingCostSummary, EmbeddingResult
from services.api.modules.embeddings.providers import (
    EmbeddingProvider,
    MockEmbeddingProvider,
    BigModelEmbeddingProvider,
)
from services.api.modules.embeddings.service import EmbeddingService
from services.api.modules.embeddings.utils import normalize_embedding

__all__ = [
    "EmbeddingService",
    "EmbeddingCostSummary",
    "EmbeddingResult",
    "EmbeddingProvider",
    "MockEmbeddingProvider",
    "BigModelEmbeddingProvider",
    "normalize_embedding",
]
