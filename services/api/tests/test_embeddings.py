"""
Tests for embedding generation module.

Feature 2.3: Embedding Generation
Slice: Embedding service interface + batch generation with mocked embeddings

Acceptance Criteria tested:
- Use consistent embedding model (interface defined)
- Batch processing for efficiency (32-100 chunks per batch)
- Embeddings are normalized for cosine similarity
"""
import pytest
import numpy as np
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch


class TestEmbeddingServiceInterface:
    """Test EmbeddingService class structure and interface."""

    def test_embedding_service_exists(self):
        """EmbeddingService should be importable."""
        from services.api.modules.embeddings import EmbeddingService
        assert EmbeddingService is not None

    def test_embedding_service_has_model_name(self):
        """EmbeddingService should expose model name."""
        from services.api.modules.embeddings import EmbeddingService
        service = EmbeddingService()
        assert hasattr(service, "model_name")
        assert isinstance(service.model_name, str)
        assert len(service.model_name) > 0

    def test_embedding_service_has_embedding_dimension(self):
        """EmbeddingService should expose embedding dimension."""
        from services.api.modules.embeddings import EmbeddingService
        service = EmbeddingService()
        assert hasattr(service, "dimension")
        assert isinstance(service.dimension, int)
        assert service.dimension > 0

    def test_embedding_service_default_model(self):
        """EmbeddingService should use text-embedding-3-small by default."""
        from services.api.modules.embeddings import EmbeddingService
        service = EmbeddingService()
        assert "text-embedding" in service.model_name.lower() or service.model_name == "text-embedding-3-small"

    def test_embedding_service_configurable_model(self):
        """EmbeddingService should allow custom model configuration."""
        from services.api.modules.embeddings import EmbeddingService
        service = EmbeddingService(model_name="custom-model", dimension=768)
        assert service.model_name == "custom-model"
        assert service.dimension == 768

    def test_embedding_service_uses_provider_metadata_when_omitted(self):
        """EmbeddingService should inherit model metadata from its provider."""
        from services.api.modules.embeddings import BigModelEmbeddingProvider, EmbeddingService

        provider = BigModelEmbeddingProvider(api_key="test-key", model="embedding-3")
        service = EmbeddingService(provider=provider)

        assert service.model_name == "embedding-3"
        assert service.dimension == 2048

    def test_embedding_service_has_batch_size(self):
        """EmbeddingService should have configurable batch size."""
        from services.api.modules.embeddings import EmbeddingService
        service = EmbeddingService()
        assert hasattr(service, "batch_size")
        assert isinstance(service.batch_size, int)
        # Should be within 32-100 range as per acceptance criteria
        assert 32 <= service.batch_size <= 100

    def test_embedding_service_custom_batch_size(self):
        """EmbeddingService should allow custom batch size within valid range."""
        from services.api.modules.embeddings import EmbeddingService
        service = EmbeddingService(batch_size=50)
        assert service.batch_size == 50

    def test_embedding_service_invalid_batch_size_too_small(self):
        """EmbeddingService should reject batch size below 1."""
        from services.api.modules.embeddings import EmbeddingService
        with pytest.raises(ValueError):
            EmbeddingService(batch_size=0)

    def test_embedding_service_invalid_batch_size_too_large(self):
        """EmbeddingService should reject batch size above 100."""
        from services.api.modules.embeddings import EmbeddingService
        with pytest.raises(ValueError):
            EmbeddingService(batch_size=150)


class TestEmbeddingResult:
    """Test EmbeddingResult dataclass."""

    def test_embedding_result_exists(self):
        """EmbeddingResult should be importable."""
        from services.api.modules.embeddings import EmbeddingResult
        assert EmbeddingResult is not None

    def test_embedding_result_creation(self):
        """EmbeddingResult should be creatable with required fields."""
        from services.api.modules.embeddings import EmbeddingResult
        embedding = [0.1] * 1536
        result = EmbeddingResult(
            text="Test text",
            embedding=embedding,
            token_count=2,
        )
        assert result.text == "Test text"
        assert result.embedding == embedding
        assert result.token_count == 2

    def test_embedding_result_with_index(self):
        """EmbeddingResult should support optional index field."""
        from services.api.modules.embeddings import EmbeddingResult
        result = EmbeddingResult(
            text="Test",
            embedding=[0.1] * 1536,
            token_count=1,
            index=5,
        )
        assert result.index == 5

    def test_embedding_result_with_estimated_cost(self):
        """EmbeddingResult should track estimated embedding cost in USD."""
        from services.api.modules.embeddings import EmbeddingResult

        result = EmbeddingResult(
            text="Test",
            embedding=[0.1] * 1536,
            token_count=1,
            estimated_cost_usd=0.00002,
        )

        assert result.estimated_cost_usd == pytest.approx(0.00002)


class TestEmbeddingCostTracking:
    """Test embedding cost estimation and batch summaries."""

    def test_embedding_service_exposes_cost_configuration(self):
        """EmbeddingService should expose the configured cost rate."""
        from services.api.modules.embeddings import EmbeddingService

        service = EmbeddingService(cost_per_1k_tokens=0.13)

        assert service.cost_per_1k_tokens == pytest.approx(0.13)

    @pytest.mark.asyncio
    async def test_embed_batch_tracks_estimated_cost_per_result(self):
        """Each embedding result should include its estimated cost."""
        from services.api.modules.embeddings import EmbeddingService, MockEmbeddingProvider

        service = EmbeddingService(
            provider=MockEmbeddingProvider(dimension=8),
            cost_per_1k_tokens=0.2,
        )

        results = await service.embed_batch(["hello world"])

        expected_cost = (results[0].token_count / 1000) * 0.2
        assert results[0].estimated_cost_usd == pytest.approx(expected_cost)

    @pytest.mark.asyncio
    async def test_embed_batch_tracks_latest_cost_summary(self):
        """EmbeddingService should keep a summary of the latest batch costs."""
        from services.api.modules.embeddings import EmbeddingService, MockEmbeddingProvider

        service = EmbeddingService(
            provider=MockEmbeddingProvider(dimension=8),
            cost_per_1k_tokens=0.15,
        )

        results = await service.embed_batch(["short text", "a much longer second text for tokens"])
        summary = service.last_cost_summary

        assert summary is not None
        assert summary.total_texts == 2
        assert summary.total_tokens == sum(result.token_count for result in results)
        assert summary.cost_per_1k_tokens == pytest.approx(0.15)
        assert summary.estimated_cost_usd == pytest.approx(
            sum(result.estimated_cost_usd for result in results)
        )

    def test_embedding_service_reads_cost_from_environment(self, monkeypatch):
        """Embedding cost rate should be configurable through env vars."""
        from services.api.modules.embeddings import EmbeddingService

        monkeypatch.setenv("ZHIPUAI_API_EMBEDDING_COST_PER_1K_TOKENS", "0.42")

        service = EmbeddingService()

        assert service.cost_per_1k_tokens == pytest.approx(0.42)

    def test_embedding_service_prefers_model_specific_cost_from_environment(self, monkeypatch):
        """Model-specific embedding rates should override the generic fallback."""
        from services.api.modules.embeddings import EmbeddingService

        monkeypatch.setenv("ZHIPUAI_API_EMBEDDING_COST_PER_1K_TOKENS", "0.42")
        monkeypatch.setenv("ZHIPUAI_API_EMBEDDING_EMBEDDING_3_COST_PER_1K_TOKENS", "0.73")

        service = EmbeddingService(model_name="embedding-3")

        assert service.cost_per_1k_tokens == pytest.approx(0.73)

    def test_estimate_embedding_cost_uses_model_specific_env_rate(self, monkeypatch):
        """Embedding cost helpers should support model-aware rate lookup."""
        from services.api.modules.embeddings.service import estimate_embedding_cost_usd

        monkeypatch.setenv("ZHIPUAI_API_EMBEDDING_EMBEDDING_2_COST_PER_1K_TOKENS", "0.50")

        assert estimate_embedding_cost_usd(24, model_name="embedding-2") == pytest.approx(
            (24 / 1000.0) * 0.50
        )


class TestMockEmbeddingProvider:
    """Test MockEmbeddingProvider for testing purposes."""

    def test_mock_provider_exists(self):
        """MockEmbeddingProvider should be importable."""
        from services.api.modules.embeddings import MockEmbeddingProvider
        assert MockEmbeddingProvider is not None

    def test_mock_provider_generates_embeddings(self):
        """MockEmbeddingProvider should generate deterministic embeddings."""
        from services.api.modules.embeddings import MockEmbeddingProvider
        provider = MockEmbeddingProvider(dimension=1536)
        embedding = provider.embed("test text")
        assert len(embedding) == 1536
        assert all(isinstance(x, float) for x in embedding)

    def test_mock_provider_deterministic(self):
        """Same text should produce same embedding."""
        from services.api.modules.embeddings import MockEmbeddingProvider
        provider = MockEmbeddingProvider(dimension=1536)
        embedding1 = provider.embed("hello world")
        embedding2 = provider.embed("hello world")
        assert embedding1 == embedding2

    def test_mock_provider_different_texts_different_embeddings(self):
        """Different texts should produce different embeddings."""
        from services.api.modules.embeddings import MockEmbeddingProvider
        provider = MockEmbeddingProvider(dimension=1536)
        embedding1 = provider.embed("hello world")
        embedding2 = provider.embed("goodbye world")
        assert embedding1 != embedding2

    def test_mock_provider_normalized_embeddings(self):
        """MockEmbeddingProvider should produce normalized embeddings."""
        from services.api.modules.embeddings import MockEmbeddingProvider
        provider = MockEmbeddingProvider(dimension=1536)
        embedding = provider.embed("test text")
        # Check L2 norm is approximately 1.0
        norm = np.sqrt(sum(x**2 for x in embedding))
        assert abs(norm - 1.0) < 1e-6, f"Embedding norm is {norm}, expected 1.0"


class TestBatchEmbedding:
    """Test batch embedding generation."""

    def test_embed_batch_method_exists(self):
        """EmbeddingService should have embed_batch method."""
        from services.api.modules.embeddings import EmbeddingService
        service = EmbeddingService()
        assert hasattr(service, "embed_batch")
        assert callable(service.embed_batch)

    @pytest.mark.asyncio
    async def test_embed_batch_single_text(self):
        """embed_batch should handle single text."""
        from services.api.modules.embeddings import EmbeddingService, MockEmbeddingProvider
        provider = MockEmbeddingProvider(dimension=1536)
        service = EmbeddingService(provider=provider)

        results = await service.embed_batch(["Hello world"])

        assert len(results) == 1
        assert results[0].text == "Hello world"
        assert len(results[0].embedding) == 1536

    @pytest.mark.asyncio
    async def test_embed_batch_multiple_texts(self):
        """embed_batch should handle multiple texts."""
        from services.api.modules.embeddings import EmbeddingService, MockEmbeddingProvider
        provider = MockEmbeddingProvider(dimension=1536)
        service = EmbeddingService(provider=provider)

        texts = ["Text one", "Text two", "Text three"]
        results = await service.embed_batch(texts)

        assert len(results) == 3
        for i, result in enumerate(results):
            assert result.text == texts[i]
            assert result.index == i

    @pytest.mark.asyncio
    async def test_embed_batch_empty_list(self):
        """embed_batch should handle empty list."""
        from services.api.modules.embeddings import EmbeddingService, MockEmbeddingProvider
        provider = MockEmbeddingProvider(dimension=1536)
        service = EmbeddingService(provider=provider)

        results = await service.embed_batch([])
        assert results == []

    @pytest.mark.asyncio
    async def test_embed_batch_respects_batch_size(self):
        """embed_batch should process in batches of configured size."""
        from services.api.modules.embeddings import EmbeddingService, MockEmbeddingProvider
        provider = MockEmbeddingProvider(dimension=1536)
        service = EmbeddingService(provider=provider, batch_size=32)

        # Create 100 texts to ensure multiple batches
        texts = [f"Text number {i}" for i in range(100)]
        results = await service.embed_batch(texts)

        assert len(results) == 100
        # All should be processed correctly
        for i, result in enumerate(results):
            assert result.text == texts[i]
            assert result.index == i

    @pytest.mark.asyncio
    async def test_embed_batch_large_batch(self):
        """embed_batch should handle large batches efficiently."""
        from services.api.modules.embeddings import EmbeddingService, MockEmbeddingProvider
        provider = MockEmbeddingProvider(dimension=1536)
        service = EmbeddingService(provider=provider, batch_size=50)

        # 200 texts should be processed in 4 batches
        texts = [f"Document content {i}" for i in range(200)]
        results = await service.embed_batch(texts)

        assert len(results) == 200


class TestEmbeddingNormalization:
    """Test embedding normalization for cosine similarity."""

    def test_normalize_embedding_function_exists(self):
        """normalize_embedding function should be importable."""
        from services.api.modules.embeddings import normalize_embedding
        assert normalize_embedding is not None

    def test_normalize_embedding_unit_norm(self):
        """Normalized embedding should have unit L2 norm."""
        from services.api.modules.embeddings import normalize_embedding

        embedding = [1.0, 2.0, 3.0, 4.0]
        normalized = normalize_embedding(embedding)

        norm = np.sqrt(sum(x**2 for x in normalized))
        assert abs(norm - 1.0) < 1e-6

    def test_normalize_embedding_preserves_direction(self):
        """Normalization should preserve relative proportions."""
        from services.api.modules.embeddings import normalize_embedding

        embedding = [2.0, 4.0, 6.0]
        normalized = normalize_embedding(embedding)

        # Ratios should be preserved
        assert abs(normalized[1] / normalized[0] - 2.0) < 1e-6
        assert abs(normalized[2] / normalized[0] - 3.0) < 1e-6

    def test_normalize_embedding_already_normalized(self):
        """Already normalized embedding should remain unchanged."""
        from services.api.modules.embeddings import normalize_embedding

        # Create a unit vector
        original = [1.0, 0.0, 0.0]
        normalized = normalize_embedding(original)

        assert normalized == pytest.approx(original)

    def test_normalize_zero_vector(self):
        """Zero vector should return zero vector (or handle gracefully)."""
        from services.api.modules.embeddings import normalize_embedding

        zero_vec = [0.0, 0.0, 0.0]
        result = normalize_embedding(zero_vec)
        # Should not crash and return zero vector
        assert result == zero_vec

    def test_normalize_embedding_negative_values(self):
        """Normalization should handle negative values."""
        from services.api.modules.embeddings import normalize_embedding

        embedding = [-1.0, 2.0, -3.0]
        normalized = normalize_embedding(embedding)

        norm = np.sqrt(sum(x**2 for x in normalized))
        assert abs(norm - 1.0) < 1e-6

    @pytest.mark.asyncio
    async def test_embed_batch_returns_normalized(self):
        """embed_batch should return normalized embeddings."""
        from services.api.modules.embeddings import EmbeddingService, MockEmbeddingProvider
        provider = MockEmbeddingProvider(dimension=1536)
        service = EmbeddingService(provider=provider)

        results = await service.embed_batch(["Test text"])
        embedding = results[0].embedding

        norm = np.sqrt(sum(x**2 for x in embedding))
        assert abs(norm - 1.0) < 1e-6


class TestEmbeddingModuleExports:
    """Test that embedding module exports correctly."""

    def test_module_imports(self):
        """Embedding module should export main classes."""
        from services.api.modules.embeddings import (
            EmbeddingService,
            EmbeddingResult,
            MockEmbeddingProvider,
            BigModelEmbeddingProvider,
            normalize_embedding,
        )

        assert EmbeddingService is not None
        assert EmbeddingResult is not None
        assert MockEmbeddingProvider is not None
        assert BigModelEmbeddingProvider is not None
        assert normalize_embedding is not None


class TestTokenCounting:
    """Test token counting for embeddings."""

    @pytest.mark.asyncio
    async def test_embed_batch_includes_token_count(self):
        """embed_batch results should include token counts."""
        from services.api.modules.embeddings import EmbeddingService, MockEmbeddingProvider
        provider = MockEmbeddingProvider(dimension=1536)
        service = EmbeddingService(provider=provider)

        results = await service.embed_batch(["Hello world"])

        assert results[0].token_count > 0
        assert isinstance(results[0].token_count, int)

    @pytest.mark.asyncio
    async def test_token_counts_vary_by_text_length(self):
        """Longer texts should have higher token counts."""
        from services.api.modules.embeddings import EmbeddingService, MockEmbeddingProvider
        provider = MockEmbeddingProvider(dimension=1536)
        service = EmbeddingService(provider=provider)

        short_text = "Hi"
        long_text = "This is a much longer piece of text with many more words and tokens."

        results = await service.embed_batch([short_text, long_text])

        assert results[1].token_count > results[0].token_count


class TestEmbeddingServiceWithChunks:
    """Test embedding service integration with ChunkResult."""

    @pytest.mark.asyncio
    async def test_embed_chunks_method_exists(self):
        """EmbeddingService should have embed_chunks method."""
        from services.api.modules.embeddings import EmbeddingService
        service = EmbeddingService()
        assert hasattr(service, "embed_chunks")
        assert callable(service.embed_chunks)

    @pytest.mark.asyncio
    async def test_embed_chunks_with_chunk_results(self):
        """embed_chunks should handle ChunkResult objects."""
        from services.api.modules.embeddings import EmbeddingService, MockEmbeddingProvider
        from services.api.modules.chunking import ChunkResult

        provider = MockEmbeddingProvider(dimension=1536)
        service = EmbeddingService(provider=provider)

        chunks = [
            ChunkResult(
                content="First chunk content",
                chunk_index=0,
                source_title="Test Source",
                token_count=3,
                char_start=0,
                char_end=19,
            ),
            ChunkResult(
                content="Second chunk content",
                chunk_index=1,
                source_title="Test Source",
                token_count=3,
                char_start=20,
                char_end=40,
            ),
        ]

        results = await service.embed_chunks(chunks)

        assert len(results) == 2
        assert results[0].text == "First chunk content"
        assert results[1].text == "Second chunk content"


class TestEmbeddingPersistence:
    """Test persisting generated embeddings on SourceChunk rows."""

    def test_source_chunk_has_embedding_field(self):
        """SourceChunk should expose a nullable embedding column."""
        from sqlalchemy import inspect

        from services.api.modules.chunking.models import SourceChunk

        mapper = inspect(SourceChunk)
        columns = {column.key for column in mapper.columns}

        assert "embedding" in columns

    @pytest.mark.asyncio
    async def test_embed_and_store_chunks_persists_embeddings(
        self,
        db,
        sample_source,
    ):
        """EmbeddingService should generate and persist embeddings for chunk rows."""
        from services.api.modules.chunking.models import SourceChunk
        from services.api.modules.embeddings import EmbeddingService, MockEmbeddingProvider

        chunks = [
            SourceChunk(
                source_id=sample_source.id,
                chunk_index=0,
                content="First persisted chunk.",
                token_count=3,
                char_start=0,
                char_end=22,
            ),
            SourceChunk(
                source_id=sample_source.id,
                chunk_index=1,
                content="Second persisted chunk.",
                token_count=3,
                char_start=23,
                char_end=46,
            ),
        ]
        db.add_all(chunks)
        db.commit()

        provider = MockEmbeddingProvider(dimension=8)
        service = EmbeddingService(provider=provider, batch_size=2)

        results = await service.embed_and_store_chunks(chunks, db)

        db.expire_all()
        stored_chunks = (
            db.query(SourceChunk)
            .filter(SourceChunk.source_id == sample_source.id)
            .order_by(SourceChunk.chunk_index.asc())
            .all()
        )

        assert len(results) == 2
        assert len(stored_chunks) == 2
        assert stored_chunks[0].embedding == pytest.approx(results[0].embedding)
        assert stored_chunks[1].embedding == pytest.approx(results[1].embedding)
        assert len(stored_chunks[0].embedding) == 8
        assert len(stored_chunks[1].embedding) == 8

    @pytest.mark.asyncio
    async def test_embed_and_store_chunks_keeps_embeddings_normalized(
        self,
        db,
        sample_source,
    ):
        """Persisted embeddings should remain normalized for cosine similarity."""
        from services.api.modules.chunking.models import SourceChunk
        from services.api.modules.embeddings import EmbeddingService, MockEmbeddingProvider

        chunk = SourceChunk(
            source_id=sample_source.id,
            chunk_index=0,
            content="Normalized chunk content.",
            token_count=3,
            char_start=0,
            char_end=25,
        )
        db.add(chunk)
        db.commit()

        service = EmbeddingService(provider=MockEmbeddingProvider(dimension=16))

        await service.embed_and_store_chunks([chunk], db)

        db.refresh(chunk)
        norm = np.sqrt(sum(value ** 2 for value in chunk.embedding))
        assert abs(norm - 1.0) < 1e-6


class TestBigModelEmbeddingProvider:
    """Test BigModelEmbeddingProvider for ZhipuAI/BigModel."""

    def test_bigmodel_provider_exists(self):
        """BigModelEmbeddingProvider should be importable."""
        from services.api.modules.embeddings import BigModelEmbeddingProvider
        assert BigModelEmbeddingProvider is not None

    def test_bigmodel_provider_requires_api_key(self):
        """BigModelEmbeddingProvider should require API key."""
        from services.api.modules.embeddings import BigModelEmbeddingProvider
        import os

        # Clear environment variables temporarily
        old_key = os.environ.pop("ZAI_API_KEY", None)
        old_key2 = os.environ.pop("ZHIPUAI_API_KEY", None)

        try:
            with pytest.raises(ValueError, match="API key is required"):
                BigModelEmbeddingProvider()
        finally:
            # Restore environment variables
            if old_key:
                os.environ["ZAI_API_KEY"] = old_key
            if old_key2:
                os.environ["ZHIPUAI_API_KEY"] = old_key2

    def test_bigmodel_provider_accepts_api_key_param(self):
        """BigModelEmbeddingProvider should accept api_key parameter."""
        from services.api.modules.embeddings import BigModelEmbeddingProvider
        provider = BigModelEmbeddingProvider(api_key="test-key")
        assert provider is not None

    def test_bigmodel_provider_default_model(self):
        """BigModelEmbeddingProvider should default to embedding-2."""
        from services.api.modules.embeddings import BigModelEmbeddingProvider
        provider = BigModelEmbeddingProvider(api_key="test-key")
        assert provider.model == "embedding-2"

    def test_bigmodel_provider_custom_model(self):
        """BigModelEmbeddingProvider should allow custom model."""
        from services.api.modules.embeddings import BigModelEmbeddingProvider
        provider = BigModelEmbeddingProvider(api_key="test-key", model="embedding-3")
        assert provider.model == "embedding-3"

    def test_bigmodel_provider_dimension_embedding2(self):
        """embedding-2 should have dimension 1024."""
        from services.api.modules.embeddings import BigModelEmbeddingProvider
        provider = BigModelEmbeddingProvider(api_key="test-key", model="embedding-2")
        assert provider.dimension == 1024

    def test_bigmodel_provider_dimension_embedding3(self):
        """embedding-3 should have dimension 2048."""
        from services.api.modules.embeddings import BigModelEmbeddingProvider
        provider = BigModelEmbeddingProvider(api_key="test-key", model="embedding-3")
        assert provider.dimension == 2048

    def test_bigmodel_provider_with_mocked_client(self):
        """BigModelEmbeddingProvider should work with mocked OpenAI client."""
        from services.api.modules.embeddings import BigModelEmbeddingProvider
        from unittest.mock import MagicMock, patch

        # Create mock response
        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.1, 0.2, 0.3, 0.4] * 256  # 1024 dimensions

        mock_response = MagicMock()
        mock_response.data = [mock_embedding]

        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_response

        with patch(
            "services.api.modules.embeddings.providers.build_openai_compatible_client",
            return_value=mock_client,
        ):
            provider = BigModelEmbeddingProvider(api_key="test-key")
            result = provider.embed("test text")

            # Should return normalized embedding
            assert len(result) == 1024
            # Check normalization (L2 norm should be ~1.0)
            norm = np.sqrt(sum(x**2 for x in result))
            assert abs(norm - 1.0) < 1e-6

    def test_bigmodel_provider_embed_many_with_mocked_client(self):
        """BigModelEmbeddingProvider.embed_many should handle multiple texts."""
        from services.api.modules.embeddings import BigModelEmbeddingProvider
        from unittest.mock import MagicMock, patch

        # Create mock response with two embeddings
        mock_embedding1 = MagicMock()
        mock_embedding1.embedding = [0.1, 0.2] * 512  # 1024 dimensions

        mock_embedding2 = MagicMock()
        mock_embedding2.embedding = [0.3, 0.4] * 512  # 1024 dimensions

        mock_response = MagicMock()
        mock_response.data = [mock_embedding1, mock_embedding2]

        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_response

        with patch(
            "services.api.modules.embeddings.providers.build_openai_compatible_client",
            return_value=mock_client,
        ):
            provider = BigModelEmbeddingProvider(api_key="test-key")
            results = provider.embed_many(["text one", "text two"])

            assert len(results) == 2
            assert len(results[0]) == 1024
            assert len(results[1]) == 1024

            # Verify API was called with both texts
            mock_client.embeddings.create.assert_called_once_with(
                model="embedding-2",
                input=["text one", "text two"],
            )

    def test_bigmodel_provider_embed_many_empty_list(self):
        """BigModelEmbeddingProvider.embed_many should handle empty list."""
        from services.api.modules.embeddings import BigModelEmbeddingProvider
        provider = BigModelEmbeddingProvider(api_key="test-key")
        results = provider.embed_many([])
        assert results == []

    def test_bigmodel_provider_retries_retryable_errors_with_backoff(self):
        """Retryable API errors should be retried with exponential backoff."""
        from services.api.modules.embeddings import BigModelEmbeddingProvider

        class FakeRateLimitError(Exception):
            status_code = 429

        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.1, 0.2] * 512

        mock_response = MagicMock()
        mock_response.data = [mock_embedding]

        mock_client = MagicMock()
        mock_client.embeddings.create.side_effect = [
            FakeRateLimitError("too many requests"),
            mock_response,
        ]

        with patch(
            "services.api.modules.embeddings.providers.build_openai_compatible_client",
            return_value=mock_client,
        ), patch("services.api.modules.embeddings.providers.time.sleep") as mock_sleep:
            provider = BigModelEmbeddingProvider(
                api_key="test-key",
                max_retries=2,
                base_backoff_seconds=0.5,
                requests_per_minute=0,
            )
            results = provider.embed_many(["retry me"])

        assert len(results) == 1
        assert mock_client.embeddings.create.call_count == 2
        mock_sleep.assert_called_once_with(pytest.approx(0.5))

    def test_bigmodel_provider_stops_after_retry_budget_is_exhausted(self):
        """Retryable errors should eventually surface after max_retries is reached."""
        from services.api.modules.embeddings import BigModelEmbeddingProvider

        class FakeRateLimitError(Exception):
            status_code = 429

        mock_client = MagicMock()
        mock_client.embeddings.create.side_effect = FakeRateLimitError("still limited")

        with patch(
            "services.api.modules.embeddings.providers.build_openai_compatible_client",
            return_value=mock_client,
        ), patch("services.api.modules.embeddings.providers.time.sleep") as mock_sleep:
            provider = BigModelEmbeddingProvider(
                api_key="test-key",
                max_retries=2,
                base_backoff_seconds=0.25,
                requests_per_minute=0,
            )

            with pytest.raises(FakeRateLimitError, match="still limited"):
                provider.embed_many(["keep failing"])

        assert mock_client.embeddings.create.call_count == 3
        assert [call.args[0] for call in mock_sleep.call_args_list] == pytest.approx([0.25, 0.5])

    def test_bigmodel_provider_does_not_retry_non_retryable_errors(self):
        """Client-side errors should fail fast without retry/backoff."""
        from services.api.modules.embeddings import BigModelEmbeddingProvider

        class FakeBadRequestError(Exception):
            status_code = 400

        mock_client = MagicMock()
        mock_client.embeddings.create.side_effect = FakeBadRequestError("bad request")

        with patch(
            "services.api.modules.embeddings.providers.build_openai_compatible_client",
            return_value=mock_client,
        ), patch("services.api.modules.embeddings.providers.time.sleep") as mock_sleep:
            provider = BigModelEmbeddingProvider(
                api_key="test-key",
                max_retries=3,
                base_backoff_seconds=0.25,
                requests_per_minute=0,
            )

            with pytest.raises(FakeBadRequestError, match="bad request"):
                provider.embed_many(["do not retry"])

        assert mock_client.embeddings.create.call_count == 1
        mock_sleep.assert_not_called()

    def test_bigmodel_provider_rate_limits_successive_requests(self):
        """Configured requests_per_minute should throttle back-to-back API calls."""
        from services.api.modules.embeddings import BigModelEmbeddingProvider

        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.1, 0.2] * 512

        mock_response = MagicMock()
        mock_response.data = [mock_embedding]

        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_response

        with patch(
            "services.api.modules.embeddings.providers.build_openai_compatible_client",
            return_value=mock_client,
        ), patch(
            "services.api.modules.embeddings.providers.time.monotonic",
            side_effect=[100.0, 100.1, 101.0],
        ), patch("services.api.modules.embeddings.providers.time.sleep") as mock_sleep:
            provider = BigModelEmbeddingProvider(
                api_key="test-key",
                requests_per_minute=60,
            )

            provider.embed_many(["first"])
            provider.embed_many(["second"])

        assert mock_client.embeddings.create.call_count == 2
        mock_sleep.assert_called_once_with(pytest.approx(0.9))

    def test_bigmodel_provider_rejects_texts_over_model_budget(self, monkeypatch):
        """Embedding calls should fail fast when a text exceeds the model input budget."""
        from services.api.modules.embeddings import BigModelEmbeddingProvider
        from services.api.core.ai import ModelInputLimitError

        monkeypatch.setenv("NOTEBOOKLX_PROMPT_BUDGET_RATIO", "0.8")

        mock_client = MagicMock()

        with patch(
            "services.api.modules.embeddings.providers.build_openai_compatible_client",
            return_value=mock_client,
        ), patch(
            "services.api.modules.embeddings.providers.count_tokens",
            return_value=7000,
        ):
            provider = BigModelEmbeddingProvider(api_key="test-key", model="embedding-2")

            with pytest.raises(ModelInputLimitError, match="embedding-2"):
                provider.embed_many(["too long for embedding budget"])

        mock_client.embeddings.create.assert_not_called()


class TestEmbeddingServiceWithBigModel:
    """Test EmbeddingService integration with BigModelEmbeddingProvider."""

    @pytest.mark.asyncio
    async def test_service_with_bigmodel_provider(self):
        """EmbeddingService should work with BigModelEmbeddingProvider."""
        from services.api.modules.embeddings import EmbeddingService, BigModelEmbeddingProvider
        from unittest.mock import MagicMock, patch

        # Create mock response
        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.1, 0.2, 0.3, 0.4] * 256  # 1024 dimensions

        mock_response = MagicMock()
        mock_response.data = [mock_embedding]

        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_response

        with patch(
            "services.api.modules.embeddings.providers.build_openai_compatible_client",
            return_value=mock_client,
        ):
            provider = BigModelEmbeddingProvider(api_key="test-key")
            service = EmbeddingService(
                provider=provider,
            )

            results = await service.embed_batch(["test text"])

            assert len(results) == 1
            assert results[0].text == "test text"
            assert len(results[0].embedding) == 1024
            assert service.model_name == "embedding-2"
            assert service.dimension == 1024
