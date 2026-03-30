"""
Grounded Q&A orchestration helpers.

Feature 3.2: Grounded Q&A with Citations
"""
from __future__ import annotations

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
    messages: list[dict[str, Any]] = field(default_factory=list)


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
                messages=messages,
            )

        messages = build_grounded_messages(question, evidence)
        answer = self.chat_provider.chat(messages)
        if not answer.strip():
            answer = "I don't have enough information"

        return GroundedQAResponse(
            answer=answer,
            evidence=evidence,
            messages=messages,
        )
