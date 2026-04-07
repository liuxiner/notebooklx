"""
Tests for grounded Q&A evidence packing and prompt assembly.

Feature 3.2: Grounded Q&A with Citations
"""
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from services.api.modules.chat.service import (
    DEFAULT_GROUNDED_SYSTEM_PROMPT,
    GroundedQAService,
    build_grounded_messages,
    finalize_grounded_answer,
    format_evidence_pack,
    parse_grounded_answer_output,
)
from services.api.modules.retrieval.hybrid import HybridSearchResult


def make_result(
    *,
    chunk_id: str,
    source_title: str,
    content: str,
    score: float,
    page: int | None = None,
    quote: str | None = None,
) -> HybridSearchResult:
    metadata = {}
    if page is not None:
        metadata["page"] = page
    if quote is not None:
        metadata["quote"] = quote

    return HybridSearchResult(
        chunk_id=chunk_id,
        source_id=str(uuid4()),
        notebook_id=str(uuid4()),
        content=content,
        score=score,
        metadata=metadata,
        source_title=source_title,
        chunk_index=0,
    )


class TestEvidencePacking:
    def test_format_evidence_pack_numbers_results_and_uses_quotes(self):
        results = [
            make_result(
                chunk_id="chunk-1",
                source_title="Alpha Guide",
                content="Alpha content that should not be used as the quote.",
                score=0.91,
                page=12,
                quote="Alpha quote",
            ),
            make_result(
                chunk_id="chunk-2",
                source_title="Beta Guide",
                content="Beta content is a little longer and will be truncated if needed.",
                score=0.82,
            ),
        ]

        evidence = format_evidence_pack(results)

        assert [chunk.citation_index for chunk in evidence] == [1, 2]
        assert evidence[0].source_title == "Alpha Guide"
        assert evidence[0].page == "12"
        assert evidence[0].quote == "Alpha quote"
        assert evidence[1].quote.startswith("Beta content")


class TestGroundedMessages:
    def test_build_grounded_messages_includes_system_prompt(self):
        messages = build_grounded_messages("What is Alpha?", [])

        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == DEFAULT_GROUNDED_SYSTEM_PROMPT
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "What is Alpha?"

    def test_build_grounded_messages_embeds_numbered_evidence(self):
        evidence = [
            format_evidence_pack(
                [
                    make_result(
                        chunk_id="chunk-1",
                        source_title="Alpha Guide",
                        content="Alpha content",
                        score=0.91,
                        page=12,
                        quote="Alpha quote",
                    )
                ]
            )[0]
        ]

        messages = build_grounded_messages("What is Alpha?", evidence)
        user_prompt = messages[1]["content"]

        assert "[1] Alpha Guide, page 12" in user_prompt
        assert "Quote: Alpha quote" in user_prompt
        assert "Cite claims inline with markers like [1][2]" in user_prompt


class TestStructuredAnswerParsing:
    def test_parse_grounded_answer_output_prefers_json_answer_and_citations(self):
        evidence = format_evidence_pack(
            [
                make_result(
                    chunk_id="chunk-1",
                    source_title="Alpha Guide",
                    content="Alpha content",
                    score=0.91,
                    page=12,
                    quote="Alpha quote",
                ),
                make_result(
                    chunk_id="chunk-2",
                    source_title="Beta Guide",
                    content="Beta content",
                    score=0.84,
                    page=13,
                    quote="Beta quote",
                ),
            ]
        )

        parsed = parse_grounded_answer_output(
            '{"answer": "Alpha is supported.", "citations": [2, 1]}',
            evidence,
        )

        assert parsed.answer == "Alpha is supported."
        assert parsed.citation_indices == [2, 1]
        assert [chunk.citation_index for chunk in parsed.citations] == [2, 1]
        assert parsed.missing_citation_indices == []

    def test_parse_grounded_answer_output_aligns_inline_markers(self):
        evidence = format_evidence_pack(
            [
                make_result(
                    chunk_id="chunk-1",
                    source_title="Alpha Guide",
                    content="Alpha content",
                    score=0.91,
                    page=12,
                    quote="Alpha quote",
                ),
                make_result(
                    chunk_id="chunk-2",
                    source_title="Beta Guide",
                    content="Beta content",
                    score=0.84,
                    page=13,
                    quote="Beta quote",
                ),
            ]
        )

        parsed = parse_grounded_answer_output(
            "Alpha is supported by [2], then clarified by [1] and [2] again.",
            evidence,
        )

        assert parsed.answer == "Alpha is supported by [2], then clarified by [1] and [2] again."
        assert parsed.citation_indices == [2, 1]
        assert [chunk.citation_index for chunk in parsed.citations] == [2, 1]
        assert parsed.missing_citation_indices == []

    def test_parse_grounded_answer_output_reports_missing_citations(self):
        evidence = format_evidence_pack(
            [
                make_result(
                    chunk_id="chunk-1",
                    source_title="Alpha Guide",
                    content="Alpha content",
                    score=0.91,
                    page=12,
                    quote="Alpha quote",
                )
            ]
        )

        parsed = parse_grounded_answer_output(
            "Alpha is supported by [1] and [4].",
            evidence,
        )

        assert parsed.citation_indices == [1, 4]
        assert [chunk.citation_index for chunk in parsed.citations] == [1]
        assert parsed.missing_citation_indices == [4]


class TestGroundedQAService:
    def test_finalize_grounded_answer_uses_streamed_text_and_aligns_citations(self):
        evidence = format_evidence_pack(
            [
                make_result(
                    chunk_id="chunk-1",
                    source_title="Alpha Guide",
                    content="Alpha content",
                    score=0.91,
                    page=12,
                    quote="Alpha quote",
                ),
                make_result(
                    chunk_id="chunk-2",
                    source_title="Beta Guide",
                    content="Beta content",
                    score=0.84,
                    page=13,
                    quote="Beta quote",
                ),
            ]
        )
        messages = build_grounded_messages("What is Alpha?", evidence)

        response = finalize_grounded_answer(
            raw_answer="Alpha is supported by [2] and [1].",
            evidence=evidence,
            messages=messages,
        )

        assert response.answer == "Alpha is supported by [2] and [1]."
        assert [chunk.citation_index for chunk in response.citations] == [2, 1]
        assert response.raw_answer == "Alpha is supported by [2] and [1]."

    @pytest.mark.asyncio
    async def test_answer_question_retrieves_evidence_and_calls_chat(self):
        retriever = AsyncMock()
        retriever.search.return_value = [
            make_result(
                chunk_id="chunk-1",
                source_title="Alpha Guide",
                content="Alpha is the primary topic.",
                score=0.93,
                page=4,
            )
        ]
        embedding_provider = MagicMock()
        embedding_provider.embed.return_value = [0.1, 0.2, 0.3]
        chat_provider = MagicMock()
        chat_provider.chat.return_value = "Alpha is the primary topic."

        service = GroundedQAService(retriever, embedding_provider, chat_provider)
        response = await service.answer_question("What is Alpha?", str(uuid4()))

        assert response.answer == "Alpha is the primary topic."
        assert len(response.evidence) == 1
        assert [chunk.citation_index for chunk in response.citations] == []
        embedding_provider.embed.assert_called_once_with("What is Alpha?")
        retriever.search.assert_awaited_once()
        chat_provider.chat.assert_called_once()
        messages = chat_provider.chat.call_args.args[0]
        assert messages[0]["role"] == "system"
        assert "Alpha Guide" in messages[1]["content"]

    @pytest.mark.asyncio
    async def test_answer_question_returns_fallback_when_no_evidence(self):
        retriever = AsyncMock()
        retriever.search.return_value = []
        embedding_provider = MagicMock()
        embedding_provider.embed.return_value = [0.1, 0.2, 0.3]
        chat_provider = MagicMock()

        service = GroundedQAService(retriever, embedding_provider, chat_provider)
        response = await service.answer_question("What is missing?", str(uuid4()))

        assert response.answer == "I don't have enough information"
        assert response.evidence == []
        chat_provider.chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_answer_question_aligns_structured_citations(self):
        retriever = AsyncMock()
        retriever.search.return_value = [
            make_result(
                chunk_id="chunk-1",
                source_title="Alpha Guide",
                content="Alpha is the primary topic.",
                score=0.93,
                page=4,
            ),
            make_result(
                chunk_id="chunk-2",
                source_title="Beta Guide",
                content="Beta provides a secondary detail.",
                score=0.88,
                page=5,
            ),
        ]
        embedding_provider = MagicMock()
        embedding_provider.embed.return_value = [0.1, 0.2, 0.3]
        chat_provider = MagicMock()
        chat_provider.chat.return_value = (
            '{"answer": "Alpha is primary.", "citations": [2, 1, 9]}'
        )

        service = GroundedQAService(retriever, embedding_provider, chat_provider)
        response = await service.answer_question("What is Alpha?", str(uuid4()))

        assert response.answer == "Alpha is primary."
        assert [chunk.citation_index for chunk in response.citations] == [2, 1]
        assert response.citation_indices == [2, 1, 9]
        assert response.missing_citation_indices == [9]
        assert response.raw_answer == '{"answer": "Alpha is primary.", "citations": [2, 1, 9]}'
