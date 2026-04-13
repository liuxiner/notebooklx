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

from services.api.modules.chunking import count_tokens

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - exercised in environments without deps
    OpenAI = None

logger = logging.getLogger(__name__)


DEFAULT_BIGMODEL_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"
DEFAULT_BIGMODEL_CHAT_MODEL = "glm-4"
DEFAULT_BIGMODEL_EMBEDDING_MODEL = "embedding-2"


@dataclass(frozen=True)
class ChatUsage:
    """Provider-reported or locally estimated token usage for a chat request."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cached_tokens: int | None = None
    usage_source: str = "provider"
    estimated_cost_usd: float | None = None


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


def _coerce_int(value: Any) -> int | None:
    """Convert usage values from SDK objects or dict payloads to ints."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            return int(stripped)
    return None


def _read_attr_or_key(value: Any, name: str) -> Any:
    """Read a field from either an SDK object or a dict."""
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _extract_cached_tokens(usage: Any) -> int | None:
    """Read cached token counts from common OpenAI-compatible usage shapes."""
    direct_value = _coerce_int(_read_attr_or_key(usage, "cached_tokens"))
    if direct_value is not None:
        return direct_value

    for details_name in ("prompt_tokens_details", "input_tokens_details"):
        details = _read_attr_or_key(usage, details_name)
        cached_value = _coerce_int(_read_attr_or_key(details, "cached_tokens"))
        if cached_value is not None:
            return cached_value

    return None


def extract_chat_usage(value: Any) -> ChatUsage | None:
    """Normalize OpenAI-compatible usage payloads into a stable structure."""
    usage = _read_attr_or_key(value, "usage")
    if usage is None:
        usage = value

    prompt_tokens = _coerce_int(_read_attr_or_key(usage, "prompt_tokens"))
    completion_tokens = _coerce_int(_read_attr_or_key(usage, "completion_tokens"))
    total_tokens = _coerce_int(_read_attr_or_key(usage, "total_tokens"))

    if prompt_tokens is None and completion_tokens is None and total_tokens is None:
        return None

    prompt_tokens = prompt_tokens or 0
    completion_tokens = completion_tokens or 0
    total_tokens = total_tokens or (prompt_tokens + completion_tokens)
    return ChatUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cached_tokens=_extract_cached_tokens(usage),
        usage_source="provider",
    )


def _resolve_float_env(*names: str) -> float | None:
    for name in names:
        raw_value = os.getenv(name)
        if raw_value is None or raw_value == "":
            continue
        return float(raw_value)
    return None


def estimate_chat_cost_usd(
    *,
    prompt_tokens: int,
    completion_tokens: int,
) -> float | None:
    """Estimate chat cost in USD when token rates are configured via env vars."""
    input_rate = _resolve_float_env(
        "ZAI_API_CHAT_INPUT_COST_PER_1K_TOKENS",
        "ZHIPUAI_API_CHAT_INPUT_COST_PER_1K_TOKENS",
        "OPENAI_CHAT_INPUT_COST_PER_1K_TOKENS",
        "ZAI_API_CHAT_COST_PER_1K_TOKENS",
        "ZHIPUAI_API_CHAT_COST_PER_1K_TOKENS",
        "OPENAI_CHAT_COST_PER_1K_TOKENS",
    )
    output_rate = _resolve_float_env(
        "ZAI_API_CHAT_OUTPUT_COST_PER_1K_TOKENS",
        "ZHIPUAI_API_CHAT_OUTPUT_COST_PER_1K_TOKENS",
        "OPENAI_CHAT_OUTPUT_COST_PER_1K_TOKENS",
        "ZAI_API_CHAT_COST_PER_1K_TOKENS",
        "ZHIPUAI_API_CHAT_COST_PER_1K_TOKENS",
        "OPENAI_CHAT_COST_PER_1K_TOKENS",
    )

    if input_rate is None and output_rate is None:
        return None

    if input_rate is None:
        input_rate = output_rate
    if output_rate is None:
        output_rate = input_rate

    if input_rate is None or output_rate is None:
        return None

    return (
        (prompt_tokens / 1000.0) * input_rate
        + (completion_tokens / 1000.0) * output_rate
    )


def apply_chat_cost_estimate(usage: ChatUsage) -> ChatUsage:
    """Attach an estimated USD cost when chat pricing env vars are configured."""
    estimated_cost_usd = usage.estimated_cost_usd
    if estimated_cost_usd is None:
        estimated_cost_usd = estimate_chat_cost_usd(
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
        )
    return ChatUsage(
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
        cached_tokens=usage.cached_tokens,
        usage_source=usage.usage_source,
        estimated_cost_usd=estimated_cost_usd,
    )


def estimate_chat_usage(
    messages: list[dict[str, Any]],
    completion_text: str,
) -> ChatUsage:
    """Estimate prompt and completion tokens locally when provider usage is absent."""
    prompt_parts: list[str] = []
    for message in messages:
        role = str(message.get("role", "user")).strip() or "user"
        content = _extract_text_content(message.get("content", ""))
        prompt_parts.append(f"{role}\n{content}".strip())

    prompt_tokens = count_tokens("\n\n".join(part for part in prompt_parts if part))
    completion_tokens = count_tokens(completion_text)
    return apply_chat_cost_estimate(
        ChatUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            usage_source="estimated",
        )
    )


def merge_chat_usage(*usage_items: ChatUsage | None) -> ChatUsage | None:
    """Combine usage across rewrite and answer stages into one request summary."""
    usages = [usage for usage in usage_items if usage is not None]
    if not usages:
        return None

    prompt_tokens = sum(usage.prompt_tokens for usage in usages)
    completion_tokens = sum(usage.completion_tokens for usage in usages)
    total_tokens = sum(usage.total_tokens for usage in usages)

    cached_values = [usage.cached_tokens for usage in usages if usage.cached_tokens is not None]
    cached_tokens = sum(cached_values) if cached_values else None
    cost_values = [
        usage.estimated_cost_usd for usage in usages if usage.estimated_cost_usd is not None
    ]
    estimated_cost_usd = sum(cost_values) if cost_values else None

    source_set = {usage.usage_source for usage in usages if usage.usage_source != "none"}
    if not source_set:
        usage_source = "none"
    elif source_set == {"provider"}:
        usage_source = "provider"
    elif source_set == {"estimated"}:
        usage_source = "estimated"
    else:
        usage_source = "mixed"

    return apply_chat_cost_estimate(
        ChatUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cached_tokens=cached_tokens,
            usage_source=usage_source,
            estimated_cost_usd=estimated_cost_usd,
        )
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
        self._last_usage: ChatUsage | None = None

    @property
    def model(self) -> str:
        return self._model

    def _get_client(self):
        if self._client is None:
            self._client = build_openai_compatible_client(self._settings)
        return self._client

    @property
    def last_usage(self) -> ChatUsage | None:
        return self._last_usage

    def consume_last_usage(self) -> ChatUsage | None:
        usage = self._last_usage
        self._last_usage = None
        return usage

    def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        """Create a chat completion and return the first text response."""
        start_time = time.monotonic()
        logger.info(f"[CHAT] Calling LLM with {len(messages)} messages, model: {self._model}")
        self._last_usage = None

        try:
            response = self._get_client().chat.completions.create(
                model=self._model,
                messages=messages,
                **kwargs,
            )
            duration = time.monotonic() - start_time
            logger.info(f"[CHAT] LLM call completed in {duration:.2f}s")
            provider_usage = extract_chat_usage(response)
            if provider_usage is not None:
                self._last_usage = apply_chat_cost_estimate(provider_usage)

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
        self._last_usage = None

        try:
            stream = self._get_client().chat.completions.create(
                model=self._model,
                messages=messages,
                stream=True,
                **kwargs,
            )

            for chunk in stream:
                provider_usage = extract_chat_usage(chunk)
                if provider_usage is not None:
                    self._last_usage = apply_chat_cost_estimate(provider_usage)

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
