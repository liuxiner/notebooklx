"""
Shared OpenAI-compatible AI client helpers.

BigModel/ZhipuAI can be used through the OpenAI SDK by pointing the client at
the BigModel base URL, so chat and embeddings should resolve configuration from
one place.
"""
from __future__ import annotations

import os
import time
import logging
from dataclasses import dataclass
from typing import Any

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - exercised in environments without deps
    OpenAI = None

logger = logging.getLogger(__name__)


DEFAULT_BIGMODEL_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"
DEFAULT_BIGMODEL_CHAT_MODEL = "glm-4"
DEFAULT_BIGMODEL_EMBEDDING_MODEL = "embedding-2"


def _is_retryable_stream_error(exc: Exception) -> bool:
    """Detect connection/setup failures that can fall back to non-streaming chat."""
    type_name = type(exc).__name__.lower()
    message = str(exc).strip().lower()
    retryable_type_markers = (
        "apiconnectionerror",
        "apitimeouterror",
        "connecterror",
        "connectionerror",
        "timeouterror",
    )
    retryable_message_markers = (
        "connection error",
        "timed out",
        "timeout",
        "ssl",
        "unexpected eof",
        "temporarily unavailable",
        "eof occurred",
    )
    return any(marker in type_name for marker in retryable_type_markers) or any(
        marker in message for marker in retryable_message_markers
    )


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
        timeout=120.0,  # 120 seconds timeout for long-running requests
    )


def _extract_text_content(content: Any) -> str:
    """Normalize OpenAI-compatible content payloads into plain text."""
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text" and isinstance(part.get("text"), str):
                    text_parts.append(part["text"])
                continue

            if getattr(part, "type", None) != "text":
                continue

            text = getattr(part, "text", None)
            if isinstance(text, str):
                text_parts.append(text)
                continue

            value = getattr(text, "value", None)
            if isinstance(value, str):
                text_parts.append(value)

        return "".join(text_parts)

    return ""


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
        start_time = time.monotonic()
        logger.info(f"[CHAT] Calling LLM with {len(messages)} messages, model: {self._model}")

        try:
            response = self._get_client().chat.completions.create(
                model=self._model,
                messages=messages,
                **kwargs,
            )
            duration = time.monotonic() - start_time
            logger.info(f"[CHAT] LLM call completed in {duration:.2f}s")

            message = response.choices[0].message
            content = getattr(message, "content", "")
            result = _extract_text_content(content)
            if result:
                logger.debug(f"[CHAT] LLM returned {len(result)} characters")
                return result

            logger.warning(f"[CHAT] LLM returned unexpected content type: {type(content)}")
            return ""
        except Exception as e:
            duration = time.monotonic() - start_time
            logger.error(f"[CHAT] LLM call failed after {duration:.2f}s: {e}")
            raise

    def chat_stream(self, messages: list[dict[str, Any]], **kwargs: Any):
        """Create a streaming chat completion and yield text deltas."""
        start_time = time.monotonic()
        logger.info(f"[CHAT] Starting streaming LLM call with {len(messages)} messages, model: {self._model}")
        yielded_text = False

        try:
            stream = self._get_client().chat.completions.create(
                model=self._model,
                messages=messages,
                stream=True,
                **kwargs,
            )

            for chunk in stream:
                choices = getattr(chunk, "choices", None) or []
                if not choices:
                    continue

                delta = getattr(choices[0], "delta", None)
                if delta is None:
                    continue

                text = _extract_text_content(getattr(delta, "content", None))
                if text:
                    yielded_text = True
                    yield text
        except Exception as e:
            if not yielded_text and _is_retryable_stream_error(e):
                duration = time.monotonic() - start_time
                logger.warning(
                    "[CHAT] Streaming LLM call failed after %.2fs before first delta; "
                    "falling back to non-streaming chat: %s",
                    duration,
                    e,
                )
                fallback_text = self.chat(messages, **kwargs)
                if fallback_text:
                    yield fallback_text
                    return

            duration = time.monotonic() - start_time
            logger.error(f"[CHAT] Streaming LLM call failed after {duration:.2f}s: {e}")
            raise
        else:
            duration = time.monotonic() - start_time
            logger.info(f"[CHAT] Streaming LLM call completed in {duration:.2f}s")
