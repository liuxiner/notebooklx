"""
Embedding service for generating and managing embeddings.

Feature 2.3: Embedding Generation
"""
import os
import re
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy.orm import Session

from services.api.modules.embeddings.models import EmbeddingCostSummary, EmbeddingResult
from services.api.modules.embeddings.providers import EmbeddingProvider, MockEmbeddingProvider
from services.api.modules.chunking import count_tokens

if TYPE_CHECKING:
    from services.api.modules.chunking import ChunkResult
    from services.api.modules.chunking.models import SourceChunk


class EmbeddingService:
    """
    Service for generating embeddings.

    Supports batch processing with configurable batch size.
    All embeddings are normalized for cosine similarity.
    """

    DEFAULT_COST_PER_1K_TOKENS = 0.0

    def __init__(
        self,
        provider: Optional[EmbeddingProvider] = None,
        model_name: Optional[str] = None,
        dimension: Optional[int] = None,
        batch_size: int = 32,
        cost_per_1k_tokens: Optional[float] = None,
    ):
        """
        Initialize embedding service.

        Args:
            provider: Embedding provider (defaults to MockEmbeddingProvider for testing)
            model_name: Name of the embedding model
            dimension: Embedding dimension
            batch_size: Number of texts to process per batch (1-100)

        Raises:
            ValueError: If batch_size is out of valid range
        """
        if batch_size < 1:
            raise ValueError(f"batch_size must be at least 1, got {batch_size}")
        if batch_size > 100:
            raise ValueError(f"batch_size must be at most 100, got {batch_size}")

        self._provider = provider or MockEmbeddingProvider(dimension=dimension or 1536)
        self._model_name = model_name or getattr(self._provider, "model", "text-embedding-3-small")
        self._dimension = dimension or self._provider.dimension
        self._batch_size = batch_size
        self._cost_per_1k_tokens = self._resolve_cost_per_1k_tokens(cost_per_1k_tokens)
        if self._cost_per_1k_tokens < 0:
            raise ValueError("cost_per_1k_tokens must be at least 0")
        self._last_cost_summary = EmbeddingCostSummary(
            cost_per_1k_tokens=self._cost_per_1k_tokens,
        )

    @property
    def model_name(self) -> str:
        """Return the model name."""
        return self._model_name

    @property
    def dimension(self) -> int:
        """Return the embedding dimension."""
        return self._dimension

    @property
    def batch_size(self) -> int:
        """Return the batch size."""
        return self._batch_size

    @property
    def cost_per_1k_tokens(self) -> float:
        """Return the configured estimated USD cost per 1K tokens."""
        return self._cost_per_1k_tokens

    @property
    def last_cost_summary(self) -> EmbeddingCostSummary:
        """Return the latest batch cost summary."""
        return self._last_cost_summary

    def _resolve_cost_per_1k_tokens(self, explicit_value: Optional[float]) -> float:
        """Resolve the embedding cost rate from args or environment."""
        return resolve_embedding_cost_per_1k_tokens(
            model_name=self._model_name,
            explicit_value=explicit_value,
            default=self.DEFAULT_COST_PER_1K_TOKENS,
        )

    def _estimate_cost_usd(self, token_count: int) -> float:
        """Estimate embedding cost in USD from token count."""
        return (token_count / 1000.0) * self._cost_per_1k_tokens

    async def embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
        """
        Generate embeddings for a batch of texts.

        Processes texts in batches of configured batch_size for efficiency.

        Args:
            texts: List of texts to embed

        Returns:
            List of EmbeddingResult objects with embeddings
        """
        if not texts:
            self._last_cost_summary = EmbeddingCostSummary(
                cost_per_1k_tokens=self._cost_per_1k_tokens,
            )
            return []

        results = []
        total_tokens = 0
        total_cost = 0.0

        # Process in batches
        for batch_start in range(0, len(texts), self._batch_size):
            batch_end = min(batch_start + self._batch_size, len(texts))
            batch_texts = texts[batch_start:batch_end]

            # Generate embeddings for this batch
            embeddings = self._provider.embed_many(batch_texts)

            # Create results with token counts
            for i, (text, embedding) in enumerate(zip(batch_texts, embeddings)):
                token_count = count_tokens(text)
                estimated_cost_usd = self._estimate_cost_usd(token_count)
                result = EmbeddingResult(
                    text=text,
                    embedding=embedding,
                    token_count=token_count,
                    estimated_cost_usd=estimated_cost_usd,
                    index=batch_start + i,
                )
                results.append(result)
                total_tokens += token_count
                total_cost += estimated_cost_usd

        self._last_cost_summary = EmbeddingCostSummary(
            total_texts=len(results),
            total_tokens=total_tokens,
            estimated_cost_usd=total_cost,
            cost_per_1k_tokens=self._cost_per_1k_tokens,
        )

        return results

    async def embed_chunks(self, chunks: List["ChunkResult"]) -> List[EmbeddingResult]:
        """
        Generate embeddings for a list of ChunkResult objects.

        Args:
            chunks: List of ChunkResult objects to embed

        Returns:
            List of EmbeddingResult objects with embeddings
        """
        texts = [chunk.content for chunk in chunks]
        return await self.embed_batch(texts)

    async def embed_and_store_chunks(
        self,
        chunks: List["SourceChunk"],
        db: Session,
        *,
        commit: bool = True,
    ) -> List[EmbeddingResult]:
        """
        Generate embeddings for SourceChunk rows and persist them.

        This keeps embedding generation separate from vector indexing so the
        ingestion pipeline can durably store normalized vectors before the
        pgvector search slice is added.
        """
        if not chunks:
            return []

        results = await self.embed_batch([chunk.content for chunk in chunks])

        for chunk, result in zip(chunks, results):
            db.add(chunk)
            chunk.embedding = result.embedding

        if commit:
            db.commit()
            for chunk in chunks:
                db.refresh(chunk)
        else:
            db.flush()

        return results


def _sanitize_model_name_for_env(model_name: str) -> str:
    """Convert a model name into a safe env-var suffix."""
    sanitized = re.sub(r"[^A-Za-z0-9]+", "_", model_name.strip().upper())
    sanitized = re.sub(r"_+", "_", sanitized).strip("_")
    return sanitized


def resolve_embedding_cost_per_1k_tokens_optional(model_name: Optional[str]) -> float | None:
    """Resolve embedding token cost from model-specific or generic environment variables."""
    env_names: list[str] = []

    if model_name and model_name.strip():
        suffix = _sanitize_model_name_for_env(model_name)
        env_names.extend(
            [
                f"ZAI_API_EMBEDDING_{suffix}_COST_PER_1K_TOKENS",
                f"ZHIPUAI_API_EMBEDDING_{suffix}_COST_PER_1K_TOKENS",
                f"OPENAI_EMBEDDING_{suffix}_COST_PER_1K_TOKENS",
            ]
        )

    env_names.extend(
        [
            "ZAI_API_EMBEDDING_COST_PER_1K_TOKENS",
            "ZHIPUAI_API_EMBEDDING_COST_PER_1K_TOKENS",
            "OPENAI_EMBEDDING_COST_PER_1K_TOKENS",
        ]
    )

    for env_name in env_names:
        raw_value = os.getenv(env_name)
        if raw_value is None or raw_value == "":
            continue
        return float(raw_value)

    return None


def resolve_embedding_cost_per_1k_tokens(
    *,
    model_name: Optional[str],
    explicit_value: Optional[float] = None,
    default: float = 0.0,
) -> float:
    """Resolve embedding token cost with explicit value, model-specific envs, then generic envs."""
    if explicit_value is not None:
        return explicit_value

    configured_value = resolve_embedding_cost_per_1k_tokens_optional(model_name)
    if configured_value is not None:
        return configured_value

    return default


def estimate_embedding_cost_usd(
    token_count: int,
    *,
    model_name: Optional[str],
    cost_per_1k_tokens: Optional[float] = None,
) -> float | None:
    """Estimate embedding cost when a model-specific or generic rate is configured."""
    resolved_rate = (
        cost_per_1k_tokens
        if cost_per_1k_tokens is not None
        else resolve_embedding_cost_per_1k_tokens_optional(model_name)
    )
    if resolved_rate is None:
        return None
    return (token_count / 1000.0) * resolved_rate
