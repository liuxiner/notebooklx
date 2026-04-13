"""
Tests for shared OpenAI-compatible AI client helpers.

Slice: BigModel-backed client configuration for chat and embeddings
"""
from unittest.mock import MagicMock, call, patch

import pytest


class TestAIClientSettings:
    """Test environment-driven client settings resolution."""

    def test_settings_require_api_key(self, monkeypatch):
        """Settings resolution should fail without any API key."""
        from services.api.core.ai import get_ai_client_settings

        for key in (
            "ZAI_API_KEY",
            "ZHIPUAI_API_KEY",
            "OPENAI_API_KEY",
        ):
            monkeypatch.delenv(key, raising=False)

        with pytest.raises(ValueError, match="API key is required"):
            get_ai_client_settings()

    def test_settings_prefer_bigmodel_env_vars(self, monkeypatch):
        """ZAI-specific variables should be used before generic OpenAI ones."""
        from services.api.core.ai import get_ai_client_settings

        monkeypatch.setenv("ZAI_API_KEY", "zai-key")
        monkeypatch.setenv("ZAI_API_BASE_URL", "https://bigmodel.example/v4/")
        monkeypatch.setenv("ZAI_API_MODEL_ID", "glm-4")
        monkeypatch.setenv("ZAI_API_EMBEDDING_MODEL_ID", "embedding-3")
        monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
        monkeypatch.setenv("OPENAI_BASE_URL", "https://openai.example/v1/")
        monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
        monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

        settings = get_ai_client_settings()

        assert settings.api_key == "zai-key"
        assert settings.base_url == "https://bigmodel.example/v4/"
        assert settings.chat_model == "glm-4"
        assert settings.embedding_model == "embedding-3"

    def test_settings_fall_back_to_generic_openai_compatible_env_vars(self, monkeypatch):
        """Generic OpenAI-compatible variables should work for BigModel too."""
        from services.api.core.ai import get_ai_client_settings

        monkeypatch.delenv("ZAI_API_KEY", raising=False)
        monkeypatch.delenv("ZAI_API_BASE_URL", raising=False)
        monkeypatch.delenv("ZAI_API_CHAT_MODEL_ID", raising=False)
        monkeypatch.delenv("ZAI_API_MODEL_ID", raising=False)
        monkeypatch.delenv("ZAI_API_EMBEDDING_MODEL_ID", raising=False)
        monkeypatch.delenv("ZHIPUAI_API_KEY", raising=False)
        monkeypatch.delenv("ZHIPUAI_API_BASE_URL", raising=False)
        monkeypatch.delenv("ZHIPUAI_API_MODEL_ID", raising=False)
        monkeypatch.delenv("ZHIPUAI_API_EMBEDDING_MODEL_ID", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "compat-key")
        monkeypatch.setenv("OPENAI_BASE_URL", "https://compat.example/v1/")
        monkeypatch.setenv("OPENAI_MODEL", "compat-chat")
        monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "compat-embedding")

        settings = get_ai_client_settings()

        assert settings.api_key == "compat-key"
        assert settings.base_url == "https://compat.example/v1/"
        assert settings.chat_model == "compat-chat"
        assert settings.embedding_model == "compat-embedding"

    def test_settings_use_bigmodel_defaults(self, monkeypatch):
        """Reasonable BigModel defaults should be applied when models are omitted."""
        from services.api.core.ai import (
            DEFAULT_BIGMODEL_BASE_URL,
            DEFAULT_BIGMODEL_CHAT_MODEL,
            DEFAULT_BIGMODEL_EMBEDDING_MODEL,
            get_ai_client_settings,
        )

        monkeypatch.setenv("ZAI_API_KEY", "zai-key")
        monkeypatch.delenv("ZAI_API_BASE_URL", raising=False)
        monkeypatch.delenv("ZAI_API_CHAT_MODEL_ID", raising=False)
        monkeypatch.delenv("ZAI_API_MODEL_ID", raising=False)
        monkeypatch.delenv("ZAI_API_EMBEDDING_MODEL_ID", raising=False)
        monkeypatch.delenv("ZHIPUAI_API_KEY", raising=False)
        monkeypatch.delenv("ZHIPUAI_API_BASE_URL", raising=False)
        monkeypatch.delenv("ZHIPUAI_API_MODEL_ID", raising=False)
        monkeypatch.delenv("ZHIPUAI_API_EMBEDDING_MODEL_ID", raising=False)
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        monkeypatch.delenv("OPENAI_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_EMBEDDING_MODEL", raising=False)

        settings = get_ai_client_settings()

        assert settings.base_url == DEFAULT_BIGMODEL_BASE_URL
        assert settings.chat_model == DEFAULT_BIGMODEL_CHAT_MODEL
        assert settings.embedding_model == DEFAULT_BIGMODEL_EMBEDDING_MODEL


class TestOpenAICompatibleClientFactory:
    """Test client construction against the OpenAI-compatible SDK."""

    def test_build_openai_compatible_client_uses_api_key_and_base_url(self):
        """OpenAI client should receive the resolved compatibility settings."""
        from services.api.core.ai import AIClientSettings, build_openai_compatible_client

        settings = AIClientSettings(
            api_key="test-key",
            base_url="https://bigmodel.example/v4/",
            chat_model="glm-4",
            embedding_model="embedding-2",
        )

        with patch("services.api.core.ai.OpenAI") as mock_openai:
            build_openai_compatible_client(settings)

        mock_openai.assert_called_once_with(
            api_key="test-key",
            base_url="https://bigmodel.example/v4/",
            timeout=120.0,
        )


class TestBigModelChatProvider:
    """Test the shared BigModel chat provider wrapper."""

    def test_chat_provider_uses_explicit_model(self):
        """Explicit model argument should override environment defaults."""
        from services.api.core.ai import BigModelChatProvider

        provider = BigModelChatProvider(api_key="test-key", model="glm-4-air")
        assert provider.model == "glm-4-air"

    def test_chat_provider_returns_first_message_text(self):
        """Chat provider should unwrap the first completion choice into text."""
        from services.api.core.ai import BigModelChatProvider

        mock_message = MagicMock()
        mock_message.content = "hello from bigmodel"

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("services.api.core.ai.build_openai_compatible_client", return_value=mock_client):
            provider = BigModelChatProvider(api_key="test-key", model="glm-4")
            result = provider.chat(
                [{"role": "user", "content": "hello"}],
                temperature=0.3,
            )

        assert result == "hello from bigmodel"
        usage = provider.consume_last_usage()
        assert usage is None
        mock_client.chat.completions.create.assert_called_once_with(
            model="glm-4",
            messages=[{"role": "user", "content": "hello"}],
            temperature=0.3,
        )

    def test_chat_provider_captures_provider_usage_from_sync_response(self):
        """Sync chat responses should retain provider token usage."""
        from services.api.core.ai import BigModelChatProvider

        mock_message = MagicMock()
        mock_message.content = "hello from bigmodel"

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 123
        mock_usage.completion_tokens = 45
        mock_usage.total_tokens = 168

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("services.api.core.ai.build_openai_compatible_client", return_value=mock_client):
            provider = BigModelChatProvider(api_key="test-key", model="glm-4")
            result = provider.chat([{"role": "user", "content": "hello"}])

        assert result == "hello from bigmodel"
        usage = provider.consume_last_usage()
        assert usage is not None
        assert usage.prompt_tokens == 123
        assert usage.completion_tokens == 45
        assert usage.total_tokens == 168
        assert usage.usage_source == "provider"
        assert provider.consume_last_usage() is None

    def test_chat_stream_provider_yields_incremental_text(self):
        """Streaming chat should expose text deltas in order."""
        from services.api.core.ai import BigModelChatProvider

        def make_chunk(content):
            delta = MagicMock()
            delta.content = content
            choice = MagicMock()
            choice.delta = delta
            chunk = MagicMock()
            chunk.choices = [choice]
            return chunk

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = [
            make_chunk("Alpha "),
            make_chunk("is supported."),
        ]

        with patch("services.api.core.ai.build_openai_compatible_client", return_value=mock_client):
            provider = BigModelChatProvider(api_key="test-key", model="glm-4")
            result = list(
                provider.chat_stream(
                    [{"role": "user", "content": "hello"}],
                    temperature=0.3,
                )
            )

        assert result == ["Alpha ", "is supported."]
        assert provider.consume_last_usage() is None
        mock_client.chat.completions.create.assert_called_once_with(
            model="glm-4",
            messages=[{"role": "user", "content": "hello"}],
            stream=True,
            temperature=0.3,
        )

    def test_chat_stream_provider_captures_usage_from_final_chunk(self):
        """Streaming chat should retain usage when the provider reports it at the end."""
        from services.api.core.ai import BigModelChatProvider

        def make_chunk(content):
            delta = MagicMock()
            delta.content = content
            choice = MagicMock()
            choice.delta = delta
            chunk = MagicMock()
            chunk.choices = [choice]
            chunk.usage = None
            return chunk

        usage_chunk = MagicMock()
        usage_chunk.choices = []
        usage = MagicMock()
        usage.prompt_tokens = 321
        usage.completion_tokens = 67
        usage.total_tokens = 388
        usage.cached_tokens = 12
        usage_chunk.usage = usage

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = [
            make_chunk("Alpha "),
            make_chunk("is supported."),
            usage_chunk,
        ]

        with patch("services.api.core.ai.build_openai_compatible_client", return_value=mock_client):
            provider = BigModelChatProvider(api_key="test-key", model="glm-4")
            result = list(provider.chat_stream([{"role": "user", "content": "hello"}]))

        assert result == ["Alpha ", "is supported."]
        captured_usage = provider.consume_last_usage()
        assert captured_usage is not None
        assert captured_usage.prompt_tokens == 321
        assert captured_usage.completion_tokens == 67
        assert captured_usage.total_tokens == 388
        assert captured_usage.cached_tokens == 12
        assert captured_usage.usage_source == "provider"

    def test_chat_stream_provider_falls_back_to_non_streaming_on_connection_error(self):
        """If streaming fails before the first delta, fall back to a normal chat call."""
        from services.api.core.ai import BigModelChatProvider

        class FakeAPIConnectionError(Exception):
            pass

        mock_message = MagicMock()
        mock_message.content = "Recovered from non-streaming fallback."

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            FakeAPIConnectionError("Connection error."),
            mock_response,
        ]

        with patch("services.api.core.ai.build_openai_compatible_client", return_value=mock_client):
            provider = BigModelChatProvider(api_key="test-key", model="glm-4")
            result = list(
                provider.chat_stream(
                    [{"role": "user", "content": "hello"}],
                    temperature=0.3,
                )
            )

        assert result == ["Recovered from non-streaming fallback."]
        assert mock_client.chat.completions.create.call_args_list == [
            call(
                model="glm-4",
                messages=[{"role": "user", "content": "hello"}],
                stream=True,
                temperature=0.3,
            ),
            call(
                model="glm-4",
                messages=[{"role": "user", "content": "hello"}],
                temperature=0.3,
            ),
        ]
