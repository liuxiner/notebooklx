"""Language preference helpers for chat prompts and fallback copy."""
from __future__ import annotations

import re
from typing import Any


LANGUAGE_CHINESE = "zh"
LANGUAGE_ENGLISH = "en"
LANGUAGE_UNSPECIFIED = "same_as_user"

NOT_ENOUGH_INFORMATION_EN = "I don't have enough information"
NOT_ENOUGH_INFORMATION_ZH = "我没有足够的信息"

_HAN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_LATIN_RE = re.compile(r"[A-Za-z]")


def infer_language(text: str) -> str:
    """Infer whether the user is primarily writing in Chinese or English."""
    normalized = text.strip()
    if not normalized:
        return LANGUAGE_UNSPECIFIED
    if _HAN_RE.search(normalized):
        return LANGUAGE_CHINESE
    if _LATIN_RE.search(normalized):
        return LANGUAGE_ENGLISH
    return LANGUAGE_UNSPECIFIED


def infer_language_from_messages(messages: list[dict[str, Any]]) -> str:
    """Infer the preferred response language from user-authored message content."""
    user_content = []
    for message in messages:
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            user_content.append(content)

    return infer_language("\n".join(user_content))


def build_answer_language_instruction(question: str) -> str:
    """Build a grounded-answer language constraint for the system prompt."""
    language = infer_language(question)
    if language == LANGUAGE_CHINESE:
        return (
            "Respond in Simplified Chinese. Keep citation markers like [1][2], "
            "filenames, identifiers, and quoted source text unchanged when needed."
        )
    if language == LANGUAGE_ENGLISH:
        return (
            "Respond in English. Keep citation markers like [1][2], filenames, "
            "identifiers, and quoted source text unchanged when needed."
        )
    return (
        "Respond in the same language as the user's question. Keep citation markers "
        "like [1][2], filenames, identifiers, and quoted source text unchanged when needed."
    )


def build_query_rewrite_language_instruction(query: str) -> str:
    """Build a rewrite-language constraint for standalone and retrieval queries."""
    language = infer_language(query)
    if language == LANGUAGE_CHINESE:
        return (
            "Return standalone_query and search_queries in Simplified Chinese, in the "
            "same language as the original user query. Preserve identifiers, "
            "filenames, acronyms, and error strings exactly."
        )
    if language == LANGUAGE_ENGLISH:
        return (
            "Return standalone_query and search_queries in English, in the same "
            "language as the original user query. Preserve identifiers, filenames, "
            "acronyms, and error strings exactly."
        )
    return (
        "Return standalone_query and search_queries in the same language as the "
        "original user query. Preserve identifiers, filenames, acronyms, and "
        "error strings exactly."
    )


def get_not_enough_information_message(language: str) -> str:
    """Return the localized insufficient-information fallback copy."""
    if language == LANGUAGE_CHINESE:
        return NOT_ENOUGH_INFORMATION_ZH
    return NOT_ENOUGH_INFORMATION_EN


def is_not_enough_information_message(value: str) -> bool:
    """Check whether an answer is one of the localized insufficient-information fallbacks."""
    normalized = value.strip()
    return normalized in {NOT_ENOUGH_INFORMATION_EN, NOT_ENOUGH_INFORMATION_ZH}
