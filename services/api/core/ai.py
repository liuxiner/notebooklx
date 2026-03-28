"""
Shared OpenAI-compatible AI client helpers.

BigModel/ZhipuAI can be used through the OpenAI SDK by pointing the client at
the BigModel base URL, so chat and embeddings should resolve configuration from
one place.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - exercised in environments without deps
    OpenAI = None


DEFAULT_BIGMODEL_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"
DEFAULT_BIGMODEL_CHAT_MODEL = "glm-4"
DEFAULT_BIGMODEL_EMBEDDING_MODEL = "embedding-2"


@dataclass(frozen=True)
class AIClientSettings:
    """Resolved settings for an OpenAI-compatible backend."""

    api_key: str
    base_url: str
    chat_model: str
    embedding_model: str


def get_ai_client_settings(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    chat_model: str | None = None,
    embedding_model: str | None = None,
) -> AIClientSettings:
    """Resolve BigModel/OpenAI-compatible settings from env vars."""
    resolved_api_key = (
        api_key
        or os.getenv("ZAI_API_KEY")
        or os.getenv("ZHIPUAI_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    )
    if not resolved_api_key:
        raise ValueError(
            "BigModel API key is required. Set ZAI_API_KEY, ZHIPUAI_API_KEY, "
            "or OPENAI_API_KEY."
        )

    resolved_base_url = (
        base_url
        or os.getenv("ZAI_API_BASE_URL")
        or os.getenv("ZHIPUAI_API_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or DEFAULT_BIGMODEL_BASE_URL
    )
    resolved_chat_model = (
        chat_model
        or os.getenv("ZAI_API_CHAT_MODEL_ID")
        or os.getenv("ZAI_API_MODEL_ID")
        or os.getenv("ZHIPUAI_API_MODEL_ID")
        or os.getenv("OPENAI_MODEL")
        or DEFAULT_BIGMODEL_CHAT_MODEL
    )
    resolved_embedding_model = (
        embedding_model
        or os.getenv("ZAI_API_EMBEDDING_MODEL_ID")
        or os.getenv("ZHIPUAI_API_EMBEDDING_MODEL_ID")
        or os.getenv("OPENAI_EMBEDDING_MODEL")
        or DEFAULT_BIGMODEL_EMBEDDING_MODEL
    )

    return AIClientSettings(
        api_key=resolved_api_key,
        base_url=resolved_base_url,
        chat_model=resolved_chat_model,
        embedding_model=resolved_embedding_model,
    )


def build_openai_compatible_client(settings: AIClientSettings):
    """Build an OpenAI SDK client against a compatible backend like BigModel."""
    if OpenAI is None:
        raise ImportError(
            "openai package is required for OpenAI-compatible client helpers. "
            "Install it with: pip install openai"
        )

    return OpenAI(
        api_key=settings.api_key,
        base_url=settings.base_url,
    )


class BigModelChatProvider:
    """Small chat wrapper around BigModel's OpenAI-compatible API."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self._settings = get_ai_client_settings(
            api_key=api_key,
            base_url=base_url,
            chat_model=model,
        )
        self._model = model or self._settings.chat_model
        self._client = None

    @property
    def model(self) -> str:
        return self._model

    def _get_client(self):
        if self._client is None:
            self._client = build_openai_compatible_client(self._settings)
        return self._client

    def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        """Create a chat completion and return the first text response."""
        response = self._get_client().chat.completions.create(
            model=self._model,
            messages=messages,
            **kwargs,
        )
        message = response.choices[0].message
        content = getattr(message, "content", "")

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            text_parts = [
                part.text
                for part in content
                if getattr(part, "type", None) == "text" and getattr(part, "text", None)
            ]
            return "".join(text_parts)

        return ""
