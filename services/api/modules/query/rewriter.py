"""
Query rewriting for improved retrieval.

Feature 6.2: Query Rewriting
Acceptance Criteria:
- Vague queries expanded with context
- Follow-up questions include chat history
- Improved retrieval recall
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from collections import Counter
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

DEFAULT_HISTORY_LIMIT = 10
MAX_HISTORY_CHARS = 4000
DEFAULT_MAX_HISTORY_TURNS = 4
DEFAULT_SHORT_QUERY_TOKEN_THRESHOLD = 10
DEFAULT_MAX_SEARCH_QUERIES = 3
MAX_MESSAGE_CONTEXT_CHARS = 240
MAX_QUERY_CHARS = 240
MAX_QUERY_WORDS = 32

REWRITE_STRATEGIES = {
    "no_rewrite",
    "reference_resolution",
    "standalone_expansion",
    "keyword_enrichment",
}

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "does",
    "for",
    "from",
    "how",
    "i",
    "in",
    "into",
    "is",
    "it",
    "its",
    "itself",
    "me",
    "of",
    "on",
    "or",
    "please",
    "say",
    "should",
    "show",
    "summarize",
    "tell",
    "that",
    "their",
    "them",
    "the",
    "there",
    "these",
    "this",
    "those",
    "they",
    "to",
    "us",
    "using",
    "what",
    "when",
    "where",
    "which",
    "why",
    "with",
    "work",
}

GENERIC_QUERY_TERMS = {
    "about",
    "difference",
    "differences",
    "discussed",
    "explain",
    "handle",
    "help",
    "limitation",
    "limitations",
    "mention",
    "mentioned",
    "overview",
    "problem",
    "problems",
    "risk",
    "risks",
    "said",
    "summary",
    "tell",
    "why",
}

PRONOUN_PATTERN = re.compile(
    r"\b(it|its|this|that|they|them|their|these|those|he|she|his|her|itself)\b",
    re.IGNORECASE,
)
FOLLOW_UP_PATTERN = re.compile(
    r"\b(what about|how about|why (?:this|that)|why so|how does that work|"
    r"how does this work|where is that mentioned|where is this mentioned|"
    r"does the document mention|is there anything about)\b",
    re.IGNORECASE,
)
SUMMARY_PATTERN = re.compile(
    r"\b(summarize|summary|recap|overview|tl;dr)\b|总结一下|总结|概括一下|概括|这个怎么说|为什么这样",
    re.IGNORECASE,
)
COMPARISON_PATTERN = re.compile(
    r"\b(compare|comparison|difference|differences|versus|vs\.?)\b|区别|对比",
    re.IGNORECASE,
)
EVIDENCE_PATTERN = re.compile(
    r"\b(where|mention|mentioned|evidence|source|sources|quote|quoted|quoted)\b|"
    r"哪里提到|有没有说|文档里有没有|文档中有没有",
    re.IGNORECASE,
)
CODE_OR_ERROR_PATTERN = re.compile(
    r"`[^`]+`|[A-Za-z_][A-Za-z0-9_]*\([^)]*\)|[A-Za-z0-9_./-]+/[A-Za-z0-9_./-]+|"
    r"\b[A-Z][A-Za-z]+Error\b|\b[A-Z][A-Za-z]+Exception\b|::|Traceback|stack trace|"
    r"\bline \d+\b|[A-Za-z0-9_./-]+\.(py|ts|tsx|js|json|md)\b",
    re.IGNORECASE,
)
TOPIC_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_.:/-]{2,}")
WORD_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9-]{2,}")
PREFIX_PATTERN = re.compile(
    r"^(rewritten query|rewrite|query|standalone query|search query)\s*:\s*",
    re.IGNORECASE,
)
EXPLANATION_PREFIX_PATTERN = re.compile(
    r"^(because|reason|explanation|this query|i rewrote|i would rewrite|"
    r"here(?:'s| is) the rewritten query)",
    re.IGNORECASE,
)

QUERY_REWRITE_SYSTEM_PROMPT = """You are a query rewriter for document retrieval in a notebook grounded in source documents.

This is not a QA step. Your output will be used before hybrid retrieval that combines BM25 keyword matching and semantic/vector search.

Goals:
1. Decide whether the user query needs rewriting for retrieval.
2. If rewriting is needed, produce search-friendly phrasing that improves document matching.
3. Resolve follow-up references using recent chat context.
4. Preserve the user's original intent, technical terms, identifiers, filenames, error strings, and acronyms.

Rewrite guidance:
- Prefer document-retrieval phrasing over conversational phrasing.
- Expand vague or follow-up questions into standalone questions only when context supports it.
- Clarify entities, time ranges, topics, compared objects, or document targets when context provides them.
- For summary, evidence, location, and comparison requests, phrase the query so it can match source text.
- Do not answer the question.
- Do not invent facts, constraints, or new topics.
- If the original query is already retrieval-friendly, return it unchanged.

Return JSON only in this schema:
{
  "strategy": "no_rewrite" | "reference_resolution" | "standalone_expansion" | "keyword_enrichment",
  "standalone_query": "A standalone version of the user query",
  "search_queries": ["1 to 3 search-friendly queries for retrieval"]
}
"""


@dataclass(frozen=True)
class QueryRewriteResult:
    """Structured retrieval-oriented rewrite result."""

    original_query: str
    standalone_query: str
    search_queries: tuple[str, ...]
    strategy: str
    used_llm: bool

    @property
    def primary_query(self) -> str:
        """Return the primary retrieval query."""
        if self.search_queries:
            return self.search_queries[0]
        return self.standalone_query

    @property
    def rewritten(self) -> bool:
        """Whether the final rewrite differs from the original query."""
        normalized_original = _normalize_whitespace(self.original_query)
        return self.primary_query != normalized_original


class ChatProviderProtocol(Protocol):
    """Protocol for chat providers."""

    def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        """Generate a chat response."""
        ...


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _tokenize_for_gate(query: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_./:-]+", query.lower())


def _extract_meaningful_terms(query: str) -> list[str]:
    terms = []
    for token in _tokenize_for_gate(query):
        if token in STOPWORDS or token in GENERIC_QUERY_TERMS:
            continue
        if len(token) < 3:
            continue
        terms.append(token)
    return terms


def _extract_protected_terms(query: str) -> list[str]:
    normalized = _normalize_whitespace(query)
    protected_terms: list[str] = []

    for match in re.findall(r"`([^`]+)`", normalized):
        protected_terms.append(match)

    for token in TOPIC_TOKEN_PATTERN.findall(normalized):
        lower_token = token.lower()
        if lower_token in STOPWORDS or lower_token in GENERIC_QUERY_TERMS:
            continue
        if (
            any(character in token for character in ("_", "-", ".", "/", ":"))
            or any(character.isdigit() for character in token)
            or token != token.lower()
            or lower_token not in GENERIC_QUERY_TERMS
        ):
            protected_terms.append(token)

    deduped: list[str] = []
    seen: set[str] = set()
    for term in protected_terms:
        key = term.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(term)
    return deduped


def _looks_search_friendly(query: str) -> bool:
    query = _normalize_whitespace(query)
    tokens = _tokenize_for_gate(query)
    meaningful_terms = _extract_meaningful_terms(query)
    protected_terms = _extract_protected_terms(query)

    if not query:
        return False
    if CODE_OR_ERROR_PATTERN.search(query):
        return True
    if PRONOUN_PATTERN.search(query) or FOLLOW_UP_PATTERN.search(query):
        return False
    if SUMMARY_PATTERN.search(query) or COMPARISON_PATTERN.search(query) or EVIDENCE_PATTERN.search(query):
        return False
    if protected_terms and len(tokens) >= 3:
        return True
    return len(meaningful_terms) >= 2 and len(tokens) >= 6


def choose_rewrite_strategy(
    query: str,
    chat_history: list[dict[str, str]] | None = None,
    *,
    short_query_token_threshold: int = DEFAULT_SHORT_QUERY_TOKEN_THRESHOLD,
) -> str:
    """Choose the rewrite strategy or skip rewriting entirely."""
    normalized_query = _normalize_whitespace(query)
    if not normalized_query:
        return "no_rewrite"

    chat_history = chat_history or []
    token_count = len(_tokenize_for_gate(normalized_query))
    has_history = bool(chat_history)

    if CODE_OR_ERROR_PATTERN.search(normalized_query):
        return "no_rewrite"
    if has_history and PRONOUN_PATTERN.search(normalized_query):
        return "reference_resolution"
    if has_history and FOLLOW_UP_PATTERN.search(normalized_query):
        return "standalone_expansion"
    if SUMMARY_PATTERN.search(normalized_query):
        return "standalone_expansion" if has_history else "keyword_enrichment"
    if COMPARISON_PATTERN.search(normalized_query) or EVIDENCE_PATTERN.search(normalized_query):
        return "keyword_enrichment" if _extract_meaningful_terms(normalized_query) else "standalone_expansion"
    if token_count <= short_query_token_threshold and not _looks_search_friendly(normalized_query):
        return "standalone_expansion" if has_history else "keyword_enrichment"
    if has_history and token_count <= max(4, short_query_token_threshold // 2):
        return "standalone_expansion"
    return "no_rewrite"


def _select_recent_history_messages(
    chat_history: list[dict[str, str]],
    max_history_turns: int,
) -> list[dict[str, str]]:
    if max_history_turns <= 0 or not chat_history:
        return []

    selected: list[dict[str, str]] = []
    user_turns = 0

    for message in reversed(chat_history):
        role = message.get("role", "").strip().lower()
        content = _normalize_whitespace(message.get("content", ""))
        if not content:
            continue

        selected.insert(0, {"role": role or "unknown", "content": content})
        if role == "user":
            user_turns += 1
            if user_turns >= max_history_turns:
                break

    return selected


def _trim_context_message(content: str, max_chars: int = MAX_MESSAGE_CONTEXT_CHARS) -> str:
    content = _normalize_whitespace(content)
    if len(content) <= max_chars:
        return content
    return f"...{content[-(max_chars - 3):]}"


def _extract_history_topics(
    chat_history: list[dict[str, str]],
    *,
    max_topics: int = 6,
) -> list[str]:
    if not chat_history:
        return []

    topic_candidates: list[str] = []
    bigrams: Counter[str] = Counter()
    keywords: Counter[str] = Counter()

    for message in chat_history:
        content = _normalize_whitespace(message.get("content", ""))
        for token in TOPIC_TOKEN_PATTERN.findall(content):
            lower_token = token.lower()
            if lower_token in STOPWORDS or lower_token in GENERIC_QUERY_TERMS:
                continue
            if (
                token != token.lower()
                or any(character in token for character in ("_", "-", ".", "/", ":"))
                or any(character.isdigit() for character in token)
            ):
                topic_candidates.append(token)

        words = [
            word.lower()
            for word in WORD_PATTERN.findall(content)
            if word.lower() not in STOPWORDS and word.lower() not in GENERIC_QUERY_TERMS
        ]
        for word in words:
            keywords[word] += 1
        for first, second in zip(words, words[1:]):
            bigrams[f"{first} {second}"] += 1

    ordered_topics: list[str] = []
    seen: set[str] = set()

    for topic in topic_candidates:
        key = topic.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered_topics.append(topic)
        if len(ordered_topics) >= max_topics:
            return ordered_topics

    for phrase, count in bigrams.most_common():
        if count < 1:
            continue
        if phrase in seen:
            continue
        seen.add(phrase)
        ordered_topics.append(phrase)
        if len(ordered_topics) >= max_topics:
            return ordered_topics

    for keyword, _ in keywords.most_common():
        if keyword in seen:
            continue
        seen.add(keyword)
        ordered_topics.append(keyword)
        if len(ordered_topics) >= max_topics:
            return ordered_topics

    return ordered_topics


def _format_chat_history(
    chat_history: list[dict[str, str]],
    max_chars: int,
    *,
    max_history_turns: int = DEFAULT_MAX_HISTORY_TURNS,
) -> str:
    """Format recent history into a compact rewrite context."""
    selected_messages = _select_recent_history_messages(chat_history, max_history_turns)
    if not selected_messages:
        return ""

    sections: list[str] = []
    topics = _extract_history_topics(selected_messages)
    if topics:
        sections.append(f"Recent topics/entities: {', '.join(topics)}")

    turn_lines = [
        f"- {message['role']}: {_trim_context_message(message['content'])}"
        for message in selected_messages
    ]
    sections.append("Recent turns:\n" + "\n".join(turn_lines))

    context = "\n".join(sections)
    if len(context) <= max_chars:
        return context

    trimmed_lines = []
    current_length = 0
    for line in reversed(context.splitlines()):
        line_length = len(line) + 1
        if current_length + line_length > max_chars:
            break
        trimmed_lines.insert(0, line)
        current_length += line_length

    return "\n".join(trimmed_lines)


def build_rewrite_prompt(
    query: str,
    chat_history: list[dict[str, str]] | None = None,
    max_history_chars: int = MAX_HISTORY_CHARS,
    *,
    max_history_turns: int = DEFAULT_MAX_HISTORY_TURNS,
    max_search_queries: int = DEFAULT_MAX_SEARCH_QUERIES,
    strategy_hint: str | None = None,
) -> list[dict[str, str]]:
    """
    Build the prompt messages for query rewriting.

    Args:
        query: The original user query
        chat_history: Optional list of previous messages
        max_history_chars: Maximum characters of history to include
        max_history_turns: Maximum recent user turns to retain
        max_search_queries: Maximum number of retrieval queries to request
        strategy_hint: Optional rewrite strategy hint from heuristics

    Returns:
        List of message dicts for the LLM
    """
    normalized_query = _normalize_whitespace(query)
    chat_history = chat_history or []

    history_text = _format_chat_history(
        chat_history,
        max_history_chars,
        max_history_turns=max_history_turns,
    )

    user_sections = [
        f"Original user query:\n{normalized_query}",
        f"Strategy hint: {strategy_hint or choose_rewrite_strategy(normalized_query, chat_history)}",
        (
            "Return 1 standalone_query and up to "
            f"{max_search_queries} search_queries for document retrieval."
        ),
    ]
    if history_text:
        user_sections.append(f"Relevant recent context:\n{history_text}")

    user_sections.append(
        "If the query is already retrieval-friendly, keep standalone_query unchanged and "
        "return it as the first search query."
    )

    return [
        {"role": "system", "content": QUERY_REWRITE_SYSTEM_PROMPT},
        {"role": "user", "content": "\n\n".join(user_sections)},
    ]


def _sanitize_query_text(value: str) -> str:
    if not value:
        return ""

    lines = [_normalize_whitespace(line) for line in value.splitlines() if _normalize_whitespace(line)]
    if not lines:
        return ""

    candidate = lines[0]
    candidate = PREFIX_PATTERN.sub("", candidate)
    candidate = candidate.strip(" -:*'\"")
    candidate = _normalize_whitespace(candidate)

    if len(candidate) > MAX_QUERY_CHARS:
        candidate = candidate[:MAX_QUERY_CHARS].rsplit(" ", 1)[0].strip()

    return candidate


def _looks_like_query_text(value: str) -> bool:
    if not value:
        return False
    if value.startswith("{") or value.endswith("}"):
        return False
    if EXPLANATION_PREFIX_PATTERN.search(value):
        return False
    if len(value.split()) > MAX_QUERY_WORDS:
        return False
    return bool(re.search(r"[A-Za-z0-9]", value))


def _normalize_search_queries(
    standalone_query: str,
    raw_search_queries: Any,
    *,
    max_search_queries: int,
) -> tuple[str, ...]:
    candidates: list[str] = []

    if isinstance(raw_search_queries, str):
        raw_items = [raw_search_queries]
    elif isinstance(raw_search_queries, list):
        raw_items = raw_search_queries
    else:
        raw_items = []

    for item in raw_items:
        if not isinstance(item, str):
            continue
        candidate = _sanitize_query_text(item)
        if not _looks_like_query_text(candidate):
            continue
        candidates.append(candidate)
        if len(candidates) >= max_search_queries:
            break

    if not candidates and standalone_query:
        candidates.append(standalone_query)

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
        if len(deduped) >= max_search_queries:
            break

    return tuple(deduped)


def _fallback_result(
    query: str,
    *,
    strategy: str = "no_rewrite",
    used_llm: bool = False,
) -> QueryRewriteResult:
    normalized_query = _normalize_whitespace(query)
    return QueryRewriteResult(
        original_query=normalized_query,
        standalone_query=normalized_query,
        search_queries=(normalized_query,) if normalized_query else (),
        strategy=strategy,
        used_llm=used_llm,
    )


def _parse_llm_rewrite_result(
    raw_output: str,
    *,
    original_query: str,
    fallback_strategy: str,
    max_search_queries: int,
) -> QueryRewriteResult | None:
    stripped_output = raw_output.strip()
    payload: dict[str, Any] | None = None

    if stripped_output.startswith("{") and stripped_output.endswith("}"):
        try:
            parsed = json.loads(stripped_output)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            payload = parsed

    if payload is None:
        standalone_query = _sanitize_query_text(stripped_output)
        if not _looks_like_query_text(standalone_query):
            return None
        return QueryRewriteResult(
            original_query=original_query,
            standalone_query=standalone_query,
            search_queries=(standalone_query,),
            strategy=fallback_strategy,
            used_llm=True,
        )

    strategy = str(payload.get("strategy", fallback_strategy)).strip().lower()
    if strategy not in REWRITE_STRATEGIES:
        strategy = fallback_strategy

    standalone_query = _sanitize_query_text(
        str(
            payload.get("standalone_query")
            or payload.get("query")
            or payload.get("rewritten_query")
            or ""
        )
    )
    if not _looks_like_query_text(standalone_query):
        return None

    search_queries = _normalize_search_queries(
        standalone_query,
        payload.get("search_queries"),
        max_search_queries=max_search_queries,
    )
    if not search_queries:
        return None

    return QueryRewriteResult(
        original_query=original_query,
        standalone_query=standalone_query,
        search_queries=search_queries,
        strategy=strategy,
        used_llm=True,
    )


def _preserves_protected_terms(original_query: str, candidates: tuple[str, ...]) -> bool:
    protected_terms = _extract_protected_terms(original_query)
    if not protected_terms:
        return True

    candidate_text = " ".join(candidates).lower()
    for term in protected_terms:
        if term.lower() not in candidate_text:
            return False
    return True


class QueryRewriter:
    """
    Rewrites user queries to improve retrieval quality.

    The rewriter is retrieval-first: it only calls the LLM when lightweight
    heuristics detect that a query is vague, context-dependent, or poorly suited
    for document retrieval.
    """

    def __init__(
        self,
        chat_provider: ChatProviderProtocol,
        max_history_chars: int = MAX_HISTORY_CHARS,
        *,
        max_history_turns: int = DEFAULT_MAX_HISTORY_TURNS,
        short_query_token_threshold: int = DEFAULT_SHORT_QUERY_TOKEN_THRESHOLD,
        max_search_queries: int = DEFAULT_MAX_SEARCH_QUERIES,
    ):
        self.chat_provider = chat_provider
        self.max_history_chars = max_history_chars
        self.max_history_turns = max_history_turns
        self.short_query_token_threshold = short_query_token_threshold
        self.max_search_queries = max_search_queries

    def rewrite_for_retrieval(
        self,
        query: str,
        chat_history: list[dict[str, str]] | None = None,
    ) -> QueryRewriteResult:
        """
        Rewrite a query for retrieval and return a structured result.

        The primary retrieval query is exposed via ``primary_query``. The
        standalone question remains available for future answer-chain use.
        """
        normalized_query = _normalize_whitespace(query)
        chat_history = chat_history or []

        if not normalized_query:
            return _fallback_result("", strategy="no_rewrite", used_llm=False)

        strategy = choose_rewrite_strategy(
            normalized_query,
            chat_history,
            short_query_token_threshold=self.short_query_token_threshold,
        )
        if strategy == "no_rewrite":
            return _fallback_result(normalized_query, strategy=strategy, used_llm=False)

        messages = build_rewrite_prompt(
            normalized_query,
            chat_history=chat_history,
            max_history_chars=self.max_history_chars,
            max_history_turns=self.max_history_turns,
            max_search_queries=self.max_search_queries,
            strategy_hint=strategy,
        )

        try:
            raw_output = self.chat_provider.chat(messages)
        except Exception as exc:
            logger.error("Query rewriting failed: %s. Falling back to original query.", exc)
            return _fallback_result(normalized_query, strategy="no_rewrite", used_llm=True)

        parsed_result = _parse_llm_rewrite_result(
            raw_output,
            original_query=normalized_query,
            fallback_strategy=strategy,
            max_search_queries=self.max_search_queries,
        )
        if parsed_result is None:
            logger.warning("Query rewriter returned unparsable output. Falling back to original query.")
            return _fallback_result(normalized_query, strategy="no_rewrite", used_llm=True)

        if not _preserves_protected_terms(
            normalized_query,
            (parsed_result.standalone_query, *parsed_result.search_queries),
        ):
            logger.warning("Query rewrite dropped protected terms. Falling back to original query.")
            return _fallback_result(normalized_query, strategy="no_rewrite", used_llm=True)

        logger.debug(
            "Query rewritten for retrieval: '%s' -> '%s' (%s)",
            normalized_query,
            parsed_result.primary_query,
            parsed_result.strategy,
        )
        return parsed_result

    def rewrite(
        self,
        query: str,
        chat_history: list[dict[str, str]] | None = None,
    ) -> str:
        """Return the primary retrieval query for downstream search."""
        return self.rewrite_for_retrieval(query, chat_history=chat_history).primary_query


def get_recent_chat_history(
    db: Session,
    notebook_id: str,
    limit: int = DEFAULT_HISTORY_LIMIT,
) -> list[dict[str, str]]:
    """
    Retrieve recent chat history from the database.

    Returns the newest ``limit`` messages in chronological order. Invalid
    notebook IDs are tolerated and logged so the caller can safely fall back
    to rewrite-without-history behavior.
    """
    from services.api.modules.chat.models import Message

    if limit <= 0:
        return []

    try:
        normalized_notebook_id = uuid.UUID(notebook_id)
    except (TypeError, ValueError):
        logger.warning("Invalid notebook_id for query rewrite history lookup: %s", notebook_id)
        return []

    messages = (
        db.query(Message)
        .filter(Message.notebook_id == normalized_notebook_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .all()
    )
    messages.reverse()

    return [{"role": message.role.value, "content": message.content} for message in messages]
