"""
Embedding providers.

Feature 2.3: Embedding Generation

Supports:
- MockEmbeddingProvider: For testing with deterministic embeddings
- BigModelEmbeddingProvider: ZhipuAI/BigModel with OpenAI-compatible API
"""
import hashlib
import time
import logging
from abc import ABC, abstractmethod
from typing import List, Optional

from services.api.core.ai import (
    ModelInputLimitError,
    build_openai_compatible_client,
    get_ai_client_settings,
    get_model_input_budget_settings,
)
from services.api.modules.chunking import count_tokens
from services.api.modules.embeddings.utils import normalize_embedding

logger = logging.getLogger(__name__)


DEFAULT_EMBEDDING_MAX_RETRIES = 3
DEFAULT_EMBEDDING_RETRY_BASE_SECONDS = 1.0
DEFAULT_EMBEDDING_REQUESTS_PER_MINUTE = 120


def _env_int(*names: str, default: Optional[int]) -> Optional[int]:
    """Return the first configured integer environment value."""
    import os

    for name in names:
        value = os.getenv(name)
        if value is None or value == "":
            continue
        return int(value)

    return default


def _env_float(*names: str, default: float) -> float:
    """Return the first configured float environment value."""
    import os

    for name in names:
        value = os.getenv(name)
        if value is None or value == "":
            continue
        return float(value)

    return default


def _is_retryable_embedding_error(error: Exception) -> bool:
    """Return whether an embedding API error should be retried."""
    status_code = getattr(error, "status_code", None)

    if status_code is not None:
        try:
            status_code = int(status_code)
        except (TypeError, ValueError):
            status_code = None

    if status_code in {408, 409, 425, 429}:
        return True

    if status_code is not None and status_code >= 500:
        return True

    return error.__class__.__name__ in {
        "APIConnectionError",
        "APITimeoutError",
        "InternalServerError",
        "RateLimitError",
    }


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding dimension."""
        pass

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        pass

    @abstractmethod
    def embed_many(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        pass


class MockEmbeddingProvider(EmbeddingProvider):
    """
    Mock embedding provider for testing.

    Generates deterministic embeddings based on text hash.
    All embeddings are normalized to unit L2 norm.
    """

    def __init__(self, dimension: int = 1536):
        """
        Initialize mock provider.

        Args:
            dimension: Embedding dimension (default: 1536 for text-embedding-3-small)
        """
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, text: str) -> List[float]:
        """
        Generate deterministic embedding from text hash.

        Args:
            text: Input text

        Returns:
            Normalized embedding vector
        """
        # Create deterministic hash-based embedding
        text_hash = hashlib.sha256(text.encode()).hexdigest()

        # Generate raw embedding values from hash
        raw_embedding = []
        for i in range(self._dimension):
            # Use different parts of hash for different dimensions
            chunk_index = i % 32  # SHA256 produces 64 hex chars = 32 bytes
            hex_pair = text_hash[chunk_index * 2: chunk_index * 2 + 2]
            value = int(hex_pair, 16) / 255.0 - 0.5  # Map to [-0.5, 0.5]

            # Add variation based on position to avoid repetition
            position_factor = ((i // 32) + 1) * 0.1
            raw_embedding.append(value * position_factor)

        # Normalize to unit L2 norm for cosine similarity
        return normalize_embedding(raw_embedding)

    def embed_many(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of input texts

        Returns:
            List of normalized embedding vectors
        """
        return [self.embed(text) for text in texts]


class BigModelEmbeddingProvider(EmbeddingProvider):
    """
    ZhipuAI/BigModel embedding provider using OpenAI-compatible API.

    Uses the OpenAI Python client with custom base_url to connect to
    ZhipuAI's embedding API (embedding-2 or embedding-3 models).

    Environment variables:
        ZHIPUAI_API_KEY: ZhipuAI API key
        ZHIPUAI_API_BASE_URL: ZhipuAI API base URL (default: https://open.bigmodel.cn/api/paas/v4/)
        ZHIPUAI_API_EMBEDDING_MODEL_ID: Embedding model ID (default: embedding-2)
        ZAI_API_*: Legacy aliases supported by the shared AI settings helper
    """

    # Model dimensions for ZhipuAI embedding models
    MODEL_DIMENSIONS = {
        "embedding-2": 1024,
        "embedding-3": 2048,
    }
    MODEL_MAX_TOKENS = {
        "embedding-2": 8_000,
        "embedding-3": 8_000,
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        max_retries: Optional[int] = None,
        base_backoff_seconds: Optional[float] = None,
        requests_per_minute: Optional[int] = None,
    ):
        """
        Initialize BigModel embedding provider.

        Args:
            api_key: ZhipuAI API key (defaults to ZHIPUAI_API_KEY/ZAI_API_KEY env var)
            base_url: API base URL (defaults to ZHIPUAI_API_BASE_URL/ZAI_API_BASE_URL env var)
            model: Embedding model ID (defaults to ZHIPUAI_API_EMBEDDING_MODEL_ID/ZAI_API_EMBEDDING_MODEL_ID or embedding-2)

        Raises:
            ValueError: If API key is not provided and not in environment
            ImportError: If openai package is not installed
        """
        self._settings = get_ai_client_settings(
            api_key=api_key,
            base_url=base_url,
            embedding_model=model,
        )
        self._api_key = self._settings.api_key
        self._base_url = self._settings.base_url
        self._model = self._settings.embedding_model
        resolved_max_retries = (
            max_retries
            if max_retries is not None
            else _env_int(
                "ZAI_API_EMBEDDING_MAX_RETRIES",
                "ZHIPUAI_API_EMBEDDING_MAX_RETRIES",
                "OPENAI_EMBEDDING_MAX_RETRIES",
                default=DEFAULT_EMBEDDING_MAX_RETRIES,
            )
        )
        resolved_backoff_seconds = (
            base_backoff_seconds
            if base_backoff_seconds is not None
            else _env_float(
                "ZAI_API_EMBEDDING_RETRY_BASE_SECONDS",
                "ZHIPUAI_API_EMBEDDING_RETRY_BASE_SECONDS",
                "OPENAI_EMBEDDING_RETRY_BASE_SECONDS",
                default=DEFAULT_EMBEDDING_RETRY_BASE_SECONDS,
            )
        )
        resolved_requests_per_minute = (
            requests_per_minute
            if requests_per_minute is not None
            else _env_int(
                "ZAI_API_EMBEDDING_REQUESTS_PER_MINUTE",
                "ZHIPUAI_API_EMBEDDING_REQUESTS_PER_MINUTE",
                "OPENAI_EMBEDDING_REQUESTS_PER_MINUTE",
                default=DEFAULT_EMBEDDING_REQUESTS_PER_MINUTE,
            )
        )

        if resolved_max_retries is None or resolved_max_retries < 0:
            raise ValueError("max_retries must be at least 0")
        if resolved_backoff_seconds <= 0:
            raise ValueError("base_backoff_seconds must be greater than 0")
        if resolved_requests_per_minute is not None and resolved_requests_per_minute < 0:
            raise ValueError("requests_per_minute must be at least 0")

        # Determine dimension from model
        self._dimension = self.MODEL_DIMENSIONS.get(self._model, 1024)
        self._max_input_tokens = get_model_input_budget_settings(
            model_max_tokens=self.MODEL_MAX_TOKENS.get(self._model, 8_000),
        ).max_input_tokens
        self._max_retries = resolved_max_retries
        self._base_backoff_seconds = resolved_backoff_seconds
        self._requests_per_minute = (
            None
            if resolved_requests_per_minute in (None, 0)
            else resolved_requests_per_minute
        )
        self._min_interval_seconds = (
            0.0
            if self._requests_per_minute is None
            else 60.0 / self._requests_per_minute
        )
        self._last_request_started_at: Optional[float] = None

        # Lazy-load the OpenAI client
        self._client = None

    def _get_client(self):
        """Get or create OpenAI client."""
        if self._client is None:
            self._client = build_openai_compatible_client(
                self._settings,
            )
        return self._client

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model(self) -> str:
        return self._model

    def _apply_rate_limit(self) -> None:
        """Sleep when needed to stay inside the configured request budget."""
        if self._min_interval_seconds <= 0 or self._last_request_started_at is None:
            return

        elapsed = time.monotonic() - self._last_request_started_at
        remaining = self._min_interval_seconds - elapsed
        if remaining > 0:
            logger.debug(f"[EMBEDDING] Rate limiting: sleeping {remaining:.2f}s")
            time.sleep(remaining)

    def _sleep_for_backoff(self, attempt: int) -> None:
        """Sleep using exponential backoff before the next retry."""
        delay = self._base_backoff_seconds * (2 ** attempt)
        time.sleep(delay)

    def _create_embedding_response(self, texts: List[str]):
        """
        Call the embeddings API with retry/backoff and client-side throttling.
        """
        for text in texts:
            token_count = count_tokens(text)
            if token_count > self._max_input_tokens:
                raise ModelInputLimitError(
                    f"Input for {self._model} exceeds the configured input budget: "
                    f"{token_count} tokens > {self._max_input_tokens}."
                )

        client = self._get_client()

        for attempt in range(self._max_retries + 1):
            self._apply_rate_limit()
            self._last_request_started_at = time.monotonic()

            try:
                logger.debug(f"[EMBEDDING] Calling API for {len(texts)} texts (attempt {attempt + 1}/{self._max_retries + 1})")
                return client.embeddings.create(
                    model=self._model,
                    input=texts,
                )
            except Exception as error:
                if attempt >= self._max_retries or not _is_retryable_embedding_error(error):
                    logger.error(f"[EMBEDDING] API error on attempt {attempt + 1}: {error}")
                    raise

                delay = self._base_backoff_seconds * (2 ** attempt)
                logger.warning(f"[EMBEDDING] Retryable error on attempt {attempt + 1}, retrying in {delay:.2f}s: {error}")
                self._sleep_for_backoff(attempt)

        raise RuntimeError("embedding request exhausted retry attempts")

    def embed(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Input text

        Returns:
            Normalized embedding vector
        """
        return self.embed_many([text])[0]

    def embed_many(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts using BigModel API.

        Args:
            texts: List of input texts

        Returns:
            List of normalized embedding vectors
        """
        if not texts:
            return []

        response = self._create_embedding_response(texts)

        # Extract embeddings and normalize
        embeddings = []
        for item in response.data:
            # ZhipuAI embeddings may already be normalized, but we ensure it
            normalized = normalize_embedding(item.embedding)
            embeddings.append(normalized)

        return embeddings
