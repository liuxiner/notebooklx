"""
Grounded Q&A orchestration helpers.

Feature 3.2: Grounded Q&A with Citations
"""
from __future__ import annotations

import json
import re
import time
import logging
from dataclasses import dataclass, field
from typing import Any, Iterator, Protocol

from services.api.modules.query.rewriter import QueryRewriteResult
from services.api.modules.embeddings.providers import EmbeddingProvider
from services.api.modules.retrieval.hybrid import HybridSearchResult

logger = logging.getLogger(__name__)


DEFAULT_GROUNDED_SYSTEM_PROMPT = (
    "You answer questions using only the evidence provided. "
    "If the evidence does not support the answer, say: "
    "\"I don't have enough information\"."
)


def _truncate_for_log(text: str, max_length: int = 200) -> str:
    """Truncate text for logging, preserving structure."""
    if len(text) <= max_length:
        return text
    return text[:max_length-3].rstrip() + "..."


def _format_retrieval_debug(evidence: list[EvidenceChunk]) -> str:
    """Format evidence chunks for debug logging."""
    if not evidence:
        return "No evidence retrieved"

    parts = []
    for chunk in evidence[:3]:  # Log first 3 chunks
        title = chunk.source_title[:30]
        quote = _truncate_for_log(chunk.quote, 80)
        parts.append(f"[{chunk.citation_index}] {title}: \"{quote}\"")

    if len(evidence) > 3:
        parts.append(f"... and {len(evidence) - 3} more chunks")

    return " | ".join(parts)


class RetrievalServiceProtocol(Protocol):
    async def search(
        self,
        query: str,
        query_embedding: list[float],
        notebook_id: str,
        top_k: int = 10,
        vector_weight: float = 0.5,
        bm25_weight: float = 0.5,
        vector_top_k: int | None = None,
        bm25_top_k: int | None = None,
    ) -> list[HybridSearchResult]:
        ...


class ChatProviderProtocol(Protocol):
    def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        ...

    def chat_stream(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> Iterator[str]:
        ...


class QueryRewriterProtocol(Protocol):
    def rewrite_for_retrieval(
        self,
        query: str,
        chat_history: list[dict[str, str]] | None = None,
    ) -> QueryRewriteResult:
        ...


@dataclass(frozen=True)
class EvidenceChunk:
    """Structured evidence used to ground a response."""

    citation_index: int
    chunk_id: str
    source_title: str
    page: str | None
    quote: str
    content: str
    score: float
    source_id: str | None = None
    chunk_index: int | None = None


@dataclass(frozen=True)
class GroundedQAResponse:
    """Response payload for grounded Q&A."""

    answer: str
    evidence: list[EvidenceChunk] = field(default_factory=list)
    citations: list[EvidenceChunk] = field(default_factory=list)
    citation_indices: list[int] = field(default_factory=list)
    missing_citation_indices: list[int] = field(default_factory=list)
    raw_answer: str = ""
    messages: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class GroundedQAPreparation:
    """Prepared evidence and prompt messages for a grounded answer."""

    evidence: list[EvidenceChunk] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)
    metrics: "ChatTimingMetrics | None" = None
    query_rewrite: QueryRewriteResult | None = None


@dataclass(frozen=True)
class RetrievalDiagnostics:
    """UI-friendly retrieval summary emitted before answer generation."""

    chunk_count: int
    source_count: int
    chunks: list[EvidenceChunk] = field(default_factory=list)


@dataclass(frozen=True)
class ChatTimingMetrics:
    """Timing and delivery diagnostics for chat-stage observability."""

    model: str | None = None
    query_embedding_seconds: float | None = None
    retrieval_seconds: float | None = None
    prepare_seconds: float | None = None
    time_to_first_delta_seconds: float | None = None
    llm_stream_seconds: float | None = None
    delta_chunks_received: int | None = None
    stream_delivery: str | None = None


@dataclass(frozen=True)
class ParsedGroundedAnswer:
    """Structured answer text and citation alignment."""

    answer: str
    citations: list[EvidenceChunk]
    citation_indices: list[int]
    missing_citation_indices: list[int]
    raw_answer: str


def _format_page(metadata: dict[str, Any]) -> str | None:
    page = metadata.get("page")
    if page is None:
        return None
    return str(page)


def _extract_quote(result: HybridSearchResult) -> str:
    metadata = result.metadata or {}
    for key in ("quote", "excerpt", "highlight", "text"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    text = result.content.strip()
    if len(text) <= 220:
        return text
    return f"{text[:217].rstrip()}..."


def format_evidence_pack(results: list[HybridSearchResult]) -> list[EvidenceChunk]:
    """Convert retrieval results into numbered evidence chunks."""
    evidence: list[EvidenceChunk] = []

    for index, result in enumerate(results, start=1):
        evidence.append(
            EvidenceChunk(
                citation_index=index,
                chunk_id=result.chunk_id,
                source_title=result.source_title,
                page=_format_page(result.metadata or {}),
                quote=_extract_quote(result),
                content=result.content,
                score=result.score,
                source_id=result.source_id,
                chunk_index=result.chunk_index,
            )
        )

    return evidence


def build_retrieval_diagnostics(evidence: list[EvidenceChunk]) -> RetrievalDiagnostics:
    """Summarize retrieved evidence for chat-stream observability."""
    source_keys = {
        chunk.source_id or chunk.source_title
        for chunk in evidence
        if (chunk.source_id or chunk.source_title)
    }

    return RetrievalDiagnostics(
        chunk_count=len(evidence),
        source_count=len(source_keys),
        chunks=evidence,
    )


def merge_retrieval_results(
    result_sets: list[list[HybridSearchResult]],
    *,
    top_k: int,
) -> list[HybridSearchResult]:
    """Merge retrieval results from multiple rewritten search queries."""
    if not result_sets:
        return []

    if len(result_sets) == 1:
        return result_sets[0][:top_k]

    merged_by_chunk: dict[str, HybridSearchResult] = {}

    for results in result_sets:
        for result in results:
            existing = merged_by_chunk.get(result.chunk_id)
            if existing is None:
                merged_by_chunk[result.chunk_id] = HybridSearchResult(
                    chunk_id=result.chunk_id,
                    source_id=result.source_id,
                    notebook_id=result.notebook_id,
                    content=result.content,
                    score=result.score,
                    vector_score=result.vector_score,
                    bm25_score=result.bm25_score,
                    vector_rank=result.vector_rank,
                    bm25_rank=result.bm25_rank,
                    metadata=dict(result.metadata or {}),
                    source_title=result.source_title,
                    chunk_index=result.chunk_index,
                )
                continue

            existing.score += result.score
            if result.vector_score is not None and (
                existing.vector_score is None or result.vector_score > existing.vector_score
            ):
                existing.vector_score = result.vector_score
                existing.vector_rank = result.vector_rank
            if result.bm25_score is not None and (
                existing.bm25_score is None or result.bm25_score > existing.bm25_score
            ):
                existing.bm25_score = result.bm25_score
                existing.bm25_rank = result.bm25_rank

    merged_results = sorted(
        merged_by_chunk.values(),
        key=lambda result: result.score,
        reverse=True,
    )
    return merged_results[:top_k]


def build_grounded_messages(
    question: str,
    evidence: list[EvidenceChunk],
) -> list[dict[str, str]]:
    """Build the prompt messages for a grounded answer request."""
    if not evidence:
        return [
            {"role": "system", "content": DEFAULT_GROUNDED_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]

    evidence_lines = []
    for chunk in evidence:
        page_part = f", page {chunk.page}" if chunk.page else ""
        evidence_lines.append(
            "\n".join(
                [
                    f"[{chunk.citation_index}] {chunk.source_title}{page_part}",
                    f"Quote: {chunk.quote}",
                    f"Content: {chunk.content}",
                ]
            )
        )

    evidence_block = "\n\n".join(evidence_lines)
    user_prompt = (
        "Answer the question using only the evidence below.\n\n"
        f"Question: {question}\n\n"
        f"Evidence:\n{evidence_block}\n\n"
        "Cite claims inline with markers like [1][2]. "
        "Do not add facts that are not present in the evidence."
    )

    return [
        {"role": "system", "content": DEFAULT_GROUNDED_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def _parse_citation_indices(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []

    indices: list[int] = []
    for item in value:
        candidate: int | None = None
        if isinstance(item, int):
            candidate = item
        elif isinstance(item, str) and item.strip().isdigit():
            candidate = int(item.strip())
        elif isinstance(item, dict):
            for key in ("citation_index", "index", "id", "chunk_index"):
                candidate_value = item.get(key)
                if isinstance(candidate_value, int):
                    candidate = candidate_value
                    break
                if isinstance(candidate_value, str) and candidate_value.strip().isdigit():
                    candidate = int(candidate_value.strip())
                    break

        if candidate is not None and candidate > 0 and candidate not in indices:
            indices.append(candidate)

    return indices


def _extract_inline_citations(answer: str) -> list[int]:
    found: list[int] = []
    for match in re.finditer(r"\[(\d+)\]", answer):
        index = int(match.group(1))
        if index not in found:
            found.append(index)
    return found


def parse_grounded_answer_output(
    raw_output: str,
    evidence: list[EvidenceChunk],
) -> ParsedGroundedAnswer:
    """Parse model output and align citation markers to retrieved evidence."""
    stripped_output = raw_output.strip()
    answer_text = stripped_output
    citation_indices: list[int] = []

    if stripped_output.startswith("{") and stripped_output.endswith("}"):
        try:
            payload = json.loads(stripped_output)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            for key in ("answer", "text", "response", "content"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    answer_text = value.strip()
                    break

            citation_indices = _parse_citation_indices(
                payload.get("citations")
                if "citations" in payload
                else payload.get("citation_indices")
            )

    if not citation_indices:
        citation_indices = _extract_inline_citations(answer_text)
    else:
        inline_indices = _extract_inline_citations(answer_text)
        for index in inline_indices:
            if index not in citation_indices:
                citation_indices.append(index)

    evidence_by_index = {chunk.citation_index: chunk for chunk in evidence}
    citations = [
        evidence_by_index[index]
        for index in citation_indices
        if index in evidence_by_index
    ]
    missing_citation_indices = [
        index for index in citation_indices if index not in evidence_by_index
    ]

    return ParsedGroundedAnswer(
        answer=answer_text,
        citations=citations,
        citation_indices=citation_indices,
        missing_citation_indices=missing_citation_indices,
        raw_answer=stripped_output,
    )


def finalize_grounded_answer(
    *,
    raw_answer: str,
    evidence: list[EvidenceChunk],
    messages: list[dict[str, Any]],
) -> GroundedQAResponse:
    """Build the final grounded answer payload from raw streamed or full text."""
    stripped_raw_answer = raw_answer.strip()

    if not evidence:
        return GroundedQAResponse(
            answer="I don't have enough information",
            evidence=[],
            citations=[],
            citation_indices=[],
            missing_citation_indices=[],
            raw_answer=stripped_raw_answer,
            messages=messages,
        )

    parsed = parse_grounded_answer_output(stripped_raw_answer, evidence)
    answer = parsed.answer.strip()
    if not answer:
        return GroundedQAResponse(
            answer="I don't have enough information",
            evidence=evidence,
            citations=[],
            citation_indices=[],
            missing_citation_indices=[],
            raw_answer=parsed.raw_answer,
            messages=messages,
        )

    return GroundedQAResponse(
        answer=answer,
        evidence=evidence,
        citations=parsed.citations,
        citation_indices=parsed.citation_indices,
        missing_citation_indices=parsed.missing_citation_indices,
        raw_answer=parsed.raw_answer,
        messages=messages,
    )


class GroundedQAService:
    """Orchestrate retrieval, evidence packing, and grounded answer generation."""

    def __init__(
        self,
        retrieval_service: RetrievalServiceProtocol,
        embedding_provider: EmbeddingProvider,
        chat_provider: ChatProviderProtocol,
        query_rewriter: QueryRewriterProtocol | None = None,
    ) -> None:
        self.retrieval_service = retrieval_service
        self.embedding_provider = embedding_provider
        self.chat_provider = chat_provider
        self.query_rewriter = query_rewriter

    async def prepare_answer(
        self,
        question: str,
        notebook_id: str,
        *,
        top_k: int = 5,
        chat_history: list[dict[str, str]] | None = None,
    ) -> GroundedQAPreparation:
        """Retrieve evidence and assemble prompt messages for a grounded answer."""
        logger.info(f"[CHAT] === Preparing answer for question: \"{_truncate_for_log(question, 100)}\" ===")
        chat_history = chat_history or []
        logger.debug(f"[CHAT] Chat history has {len(chat_history)} turns")

        rewritten_query: QueryRewriteResult | None = None
        retrieval_queries = (question,)
        prompt_question = question

        if self.query_rewriter is not None:
            rewritten_query = self.query_rewriter.rewrite_for_retrieval(
                question,
                chat_history=chat_history,
            )
            if rewritten_query.search_queries:
                retrieval_queries = rewritten_query.search_queries
            if rewritten_query.standalone_query:
                prompt_question = rewritten_query.standalone_query

            # Log query rewrite details
            if rewritten_query.rewritten:
                logger.info(
                    f"[CHAT] Query rewritten: strategy={rewritten_query.strategy}, "
                    f"used_llm={rewritten_query.used_llm}"
                )
                logger.info(
                    f"[CHAT] Original: \"{_truncate_for_log(rewritten_query.original_query, 80)}\""
                )
                logger.info(
                    f"[CHAT] Standalone: \"{_truncate_for_log(rewritten_query.standalone_query, 80)}\""
                )
                logger.info(
                    f"[CHAT] Search queries: [{', '.join(f'\"{_truncate_for_log(q, 50)}\"' for q in rewritten_query.search_queries)}]"
                )
            else:
                logger.debug("[CHAT] Query not rewritten (no meaningful changes)")
        else:
            logger.debug("[CHAT] No query rewriter configured")

        logger.info(f"[CHAT] Using {len(retrieval_queries)} retrieval query/ies")
        for i, q in enumerate(retrieval_queries, 1):
            logger.info(f"[CHAT]   Query {i}: \"{_truncate_for_log(q, 80)}\"")

        embed_start = time.monotonic()
        query_embeddings = [
            self.embedding_provider.embed(retrieval_query)
            for retrieval_query in retrieval_queries
        ]
        embed_duration = time.monotonic() - embed_start
        logger.info(f"[CHAT] Embedding generation took {embed_duration:.2f}s")

        search_start = time.monotonic()
        retrieved_sets: list[list[HybridSearchResult]] = []
        for retrieval_query, query_embedding in zip(retrieval_queries, query_embeddings):
            retrieved_sets.append(
                await self.retrieval_service.search(
                    query=retrieval_query,
                    query_embedding=query_embedding,
                    notebook_id=notebook_id,
                    top_k=top_k,
                )
            )
        retrieved = merge_retrieval_results(retrieved_sets, top_k=top_k)
        search_duration = time.monotonic() - search_start
        logger.info(f"[CHAT] Vector search took {search_duration:.2f}s, found {len(retrieved)} results")

        evidence = format_evidence_pack(retrieved)

        # Log evidence chunks preview
        logger.info(f"[CHAT] Formatted {len(evidence)} evidence chunks")
        logger.debug(f"[CHAT] Evidence preview: {_format_retrieval_debug(evidence)}")

        # Log top chunks with scores for quality inspection
        for i, chunk in enumerate(evidence[:5], 1):
            logger.info(
                f"[CHAT] Chunk [{i}] score={chunk.score:.3f} "
                f"source=\"{_truncate_for_log(chunk.source_title, 25)}\" "
                f"page={chunk.page or 'N/A'} "
                f"quote=\"{_truncate_for_log(chunk.quote, 60)}\""
            )

        messages = build_grounded_messages(prompt_question, evidence)
        logger.info(f"[CHAT] Built {len(messages)} messages for LLM (system + user)")

        prepare_duration = embed_duration + search_duration
        metrics = ChatTimingMetrics(
            model=getattr(self.chat_provider, "model", None),
            query_embedding_seconds=round(embed_duration, 2),
            retrieval_seconds=round(search_duration, 2),
            prepare_seconds=round(prepare_duration, 2),
        )
        return GroundedQAPreparation(
            evidence=evidence,
            messages=messages,
            metrics=metrics,
            query_rewrite=rewritten_query,
        )

    def stream_answer(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> Iterator[str]:
        """Stream answer deltas from the chat provider."""
        return self.chat_provider.chat_stream(messages, **kwargs)

    def finalize_answer(
        self,
        raw_answer: str,
        evidence: list[EvidenceChunk],
        messages: list[dict[str, Any]],
    ) -> GroundedQAResponse:
        """Finalize a grounded answer after the raw model output is available."""
        return finalize_grounded_answer(
            raw_answer=raw_answer,
            evidence=evidence,
            messages=messages,
        )

    async def answer_question(
        self,
        question: str,
        notebook_id: str,
        *,
        top_k: int = 5,
        chat_history: list[dict[str, str]] | None = None,
    ) -> GroundedQAResponse:
        """Retrieve evidence and generate a grounded answer."""
        start_time = time.monotonic()

        logger.info(f"[CHAT] === Starting answer_question ===")
        prepared = await self.prepare_answer(
            question,
            notebook_id,
            top_k=top_k,
            chat_history=chat_history,
        )
        if not prepared.evidence:
            logger.warning(f"[CHAT] No evidence found for question: '{question[:50]}...'")
            return self.finalize_answer("", prepared.evidence, prepared.messages)

        llm_start = time.monotonic()
        logger.info(f"[CHAT] Calling LLM with {len(prepared.evidence)} evidence chunks")
        raw_answer = self.chat_provider.chat(prepared.messages)
        llm_duration = time.monotonic() - llm_start
        logger.info(f"[CHAT] LLM call took {llm_duration:.2f}s")

        # Log raw answer preview
        logger.info(f"[CHAT] Raw LLM answer ({len(raw_answer)} chars): \"{_truncate_for_log(raw_answer, 200)}\"")

        response = self.finalize_answer(
            raw_answer,
            prepared.evidence,
            prepared.messages,
        )
        if response.answer == "I don't have enough information":
            logger.warning(f"[CHAT] LLM returned empty answer for question: '{question[:50]}...'")
        else:
            logger.info(f"[CHAT] Final answer ({len(response.answer)} chars): \"{_truncate_for_log(response.answer, 200)}\"")

        # Log citation details
        logger.info(f"[CHAT] Citations: {len(response.citations)} chunks cited")
        if response.citations:
            for citation in response.citations[:5]:
                logger.info(
                    f"[CHAT]   [{citation.citation_index}] "
                    f"score={citation.score:.3f} "
                    f"source=\"{_truncate_for_log(citation.source_title, 25)}\" "
                    f"page={citation.page or 'N/A'}"
                )
            if len(response.citations) > 5:
                logger.info(f"[CHAT]   ... and {len(response.citations) - 5} more citations")

        if response.missing_citation_indices:
            logger.warning(
                f"[CHAT] Missing citation indices: {response.missing_citation_indices} "
                f"(citations referenced in answer but not found in evidence)"
            )

        total_duration = time.monotonic() - start_time
        logger.info(f"[CHAT] === answer_question completed in {total_duration:.2f}s ===")
        return response
