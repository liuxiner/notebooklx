"""Tests for snapshot prompt budgeting and compaction."""

from __future__ import annotations

import json
import uuid
from unittest.mock import Mock

def _make_prepared_chunks(count: int) -> list[PreparedSourceChunk]:
    from services.api.modules.chunking.chunker import count_tokens
    from services.api.modules.snapshots.service import PreparedSourceChunk

    source_id = uuid.uuid4()
    prepared_chunks: list[PreparedSourceChunk] = []
    char_start = 0

    for index in range(count):
        content = " ".join(
            [f"section-{index}"]
            + [f"topic-{index}-{word_index}" for word_index in range(220)]
        )
        char_end = char_start + len(content)
        prepared_chunks.append(
            PreparedSourceChunk(
                chunk_id=uuid.uuid4(),
                source_id=source_id,
                chunk_index=index,
                content=content,
                token_count=count_tokens(content),
                char_start=char_start,
                char_end=char_end,
                page_number=index + 1,
                page_numbers=[index + 1],
                heading_context=[f"Chapter {index // 3}", f"Section {index}"],
                source_title="Long Snapshot Source",
            )
        )
        char_start = char_end + 1

    return prepared_chunks


class TestSnapshotPromptBudgetSettings:
    """Environment-driven settings for snapshot prompt budgeting."""

    def test_settings_read_environment_configuration(self, monkeypatch):
        from services.api.core.ai import get_chat_model_prompt_budget_settings

        monkeypatch.setenv("ZHIPUAI_API_MODEL_MAX_TOKENS", "128000")
        monkeypatch.setenv("NOTEBOOKLX_PROMPT_BUDGET_RATIO", "0.8")

        settings = get_chat_model_prompt_budget_settings()

        assert settings.model_max_tokens == 128000
        assert settings.prompt_budget_ratio == 0.8
        assert settings.max_input_tokens == 102400


class TestSnapshotPromptCompaction:
    """Long sources should be compacted before calling the snapshot LLM."""

    def test_build_messages_caps_prompt_tokens_for_long_sources(self, monkeypatch):
        from services.api.modules.chunking.chunker import count_tokens
        from services.api.core.ai import get_chat_model_prompt_budget_settings
        from services.api.modules.parsers import ParseResult
        from services.api.modules.snapshots.service import (
            LLMSourceSnapshotSemanticProvider,
            _build_structure_outline,
        )
        from services.api.modules.sources.models import Source, SourceType

        monkeypatch.setenv("ZHIPUAI_API_MODEL_MAX_TOKENS", "2400")
        monkeypatch.setenv("NOTEBOOKLX_PROMPT_BUDGET_RATIO", "0.5")

        prepared_chunks = _make_prepared_chunks(12)
        long_text = "\n".join(chunk.content for chunk in prepared_chunks)
        parse_result = ParseResult(
            full_text=long_text,
            pages=[],
            metadata={"parser_version": "test-parser-v1"},
            title="Long Snapshot Source",
            total_pages=12,
        )
        source = Source(
            id=uuid.uuid4(),
            notebook_id=uuid.uuid4(),
            source_type=SourceType.TEXT,
            title="Long Snapshot Source",
        )

        structure_outline = _build_structure_outline(prepared_chunks)
        deterministic_snapshot = {
            "content_metrics": {
                "char_length": len(long_text),
                "estimated_token_count": count_tokens(long_text),
                "chunk_count": len(prepared_chunks),
                "section_count": len(structure_outline),
                "heading_depth_max": 2,
                "keyword_count": 15,
                "coverage_ratio": 1.0,
            },
            "structure_outline": structure_outline,
            "traceability": {
                "representative_chunk_refs": [
                    prepared_chunks[0].to_trace_ref(),
                    prepared_chunks[len(prepared_chunks) // 2].to_trace_ref(),
                    prepared_chunks[-1].to_trace_ref(),
                ],
                "source_ranges": [{"char_start": 0, "char_end": len(long_text)}],
            },
        }

        provider = LLMSourceSnapshotSemanticProvider(chat_provider=Mock())
        messages = provider._build_messages(
            source=source,
            parse_result=parse_result,
            prepared_chunks=prepared_chunks,
            deterministic_snapshot=deterministic_snapshot,
        )

        settings = get_chat_model_prompt_budget_settings()
        payload = json.loads(messages[1]["content"])
        prompt_tokens = count_tokens(messages[0]["content"]) + count_tokens(
            messages[1]["content"]
        )

        assert prompt_tokens <= settings.max_input_tokens
        assert 0 < len(payload["chunks"]) < len(prepared_chunks)
        assert payload["deterministic_snapshot"]["structure_outline"]
        assert "chunk_refs" not in payload["deterministic_snapshot"]["structure_outline"][0]
