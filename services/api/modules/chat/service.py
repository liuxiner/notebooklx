"""
Grounded Q&A orchestration helpers.

Feature 3.2: Grounded Q&A with Citations
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from services.api.modules.embeddings.providers import EmbeddingProvider
from services.api.modules.retrieval.hybrid import HybridSearchResult


DEFAULT_GROUNDED_SYSTEM_PROMPT = (
    "You answer questions using only the evidence provided. "
    "If the evidence does not support the answer, say: "
    "\"I don't have enough information\"."
)


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
            )
        )

    return evidence


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


class GroundedQAService:
    """Orchestrate retrieval, evidence packing, and grounded answer generation."""

    def __init__(
        self,
        retrieval_service: RetrievalServiceProtocol,
        embedding_provider: EmbeddingProvider,
        chat_provider: ChatProviderProtocol,
    ) -> None:
        self.retrieval_service = retrieval_service
        self.embedding_provider = embedding_provider
        self.chat_provider = chat_provider

    async def answer_question(
        self,
        question: str,
        notebook_id: str,
        *,
        top_k: int = 5,
    ) -> GroundedQAResponse:
        """Retrieve evidence and generate a grounded answer."""
        query_embedding = self.embedding_provider.embed(question)
        retrieved = await self.retrieval_service.search(
            query=question,
            query_embedding=query_embedding,
            notebook_id=notebook_id,
            top_k=top_k,
        )

        evidence = format_evidence_pack(retrieved)
        if not evidence:
            messages = build_grounded_messages(question, evidence)
            return GroundedQAResponse(
                answer="I don't have enough information",
                evidence=[],
                citations=[],
                citation_indices=[],
                missing_citation_indices=[],
                raw_answer="",
                messages=messages,
            )

        messages = build_grounded_messages(question, evidence)
        raw_answer = self.chat_provider.chat(messages)
        parsed = parse_grounded_answer_output(raw_answer, evidence)
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
