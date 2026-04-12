"""
Tests for query rewriting functionality.

Feature 6.2: Query Rewriting
Acceptance Criteria:
- Vague queries expanded with context
- Follow-up questions include chat history
- Improved retrieval recall
"""
import logging
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from services.api.modules.chat.models import Message, MessageRole
from services.api.modules.notebooks.models import Notebook, User


class TestQueryRewriter:
    """Test query rewriting functionality."""

    def test_query_rewriter_can_be_disabled(self):
        """Configured disablement should bypass rewriting entirely."""
        from services.api.modules.query.rewriter import QueryRewriter

        mock_provider = MagicMock()
        rewriter = QueryRewriter(chat_provider=mock_provider, enabled=False)

        result = rewriter.rewrite_for_retrieval(
            "What are the risks?",
            chat_history=[{"role": "assistant", "content": "We were discussing NotebookLX risks."}],
        )

        assert result.strategy == "no_rewrite"
        assert result.used_llm is False
        assert result.rewritten is False
        assert result.search_queries == ("What are the risks?",)
        mock_provider.chat.assert_not_called()

    def test_query_rewriter_respects_allowed_strategies(self):
        """Disallowed strategies should skip rewriting instead of calling the LLM."""
        from services.api.modules.query.rewriter import QueryRewriter

        mock_provider = MagicMock()
        rewriter = QueryRewriter(
            chat_provider=mock_provider,
            allowed_strategies=frozenset({"keyword_enrichment"}),
        )

        result = rewriter.rewrite_for_retrieval(
            "What are its limitations?",
            chat_history=[
                {"role": "user", "content": "Tell me about the vector search feature"},
                {"role": "assistant", "content": "It uses pgvector in PostgreSQL."},
            ],
        )

        assert result.strategy == "no_rewrite"
        assert result.used_llm is False
        assert result.primary_query == "What are its limitations?"
        mock_provider.chat.assert_not_called()

    def test_rewrite_vague_query_returns_search_friendly_output(self):
        """AC: Vague queries expanded with retrieval-friendly context."""
        from services.api.modules.query.rewriter import QueryRewriter

        mock_provider = MagicMock()
        mock_provider.chat.return_value = """
        {
          "strategy": "keyword_enrichment",
          "standalone_query": "What are the main project risks discussed in the NotebookLX documents?",
          "search_queries": [
            "NotebookLX project risks",
            "security risks architectural risks NotebookLX"
          ]
        }
        """

        rewriter = QueryRewriter(chat_provider=mock_provider)
        result = rewriter.rewrite_for_retrieval("What are the risks?", chat_history=[])

        assert result.strategy == "keyword_enrichment"
        assert result.used_llm is True
        assert result.rewritten is True
        assert result.standalone_query == "What are the main project risks discussed in the NotebookLX documents?"
        assert result.search_queries == (
            "NotebookLX project risks",
            "security risks architectural risks NotebookLX",
        )
        assert rewriter.rewrite("What are the risks?", chat_history=[]) == "NotebookLX project risks"
        assert mock_provider.chat.call_count == 2

    def test_rewrite_with_chat_history(self):
        """AC: Follow-up questions include chat history."""
        from services.api.modules.query.rewriter import QueryRewriter

        mock_provider = MagicMock()
        mock_provider.chat.return_value = """
        {
          "strategy": "reference_resolution",
          "standalone_query": "How does the NotebookLX FastAPI backend handle authentication?",
          "search_queries": [
            "NotebookLX FastAPI authentication",
            "NotebookLX backend auth methods"
          ]
        }
        """

        rewriter = QueryRewriter(chat_provider=mock_provider)
        original_query = "How does it handle authentication?"
        chat_history = [
            {"role": "user", "content": "Tell me about the NotebookLX project"},
            {
                "role": "assistant",
                "content": "NotebookLX is a source-grounded notebook workspace with a Python FastAPI backend.",
            },
        ]

        result = rewriter.rewrite_for_retrieval(original_query, chat_history=chat_history)

        assert result.strategy == "reference_resolution"
        assert result.rewritten is True
        assert "authentication" in result.primary_query.lower()
        assert "notebooklx" in result.standalone_query.lower()
        messages = mock_provider.chat.call_args[0][0]
        assert any("NotebookLX" in str(message) for message in messages)

    def test_clear_query_skips_rewrite_gate(self):
        """Clear, specific queries should bypass LLM rewriting."""
        from services.api.modules.query.rewriter import QueryRewriter

        mock_provider = MagicMock()
        rewriter = QueryRewriter(chat_provider=mock_provider)

        original_query = "How do I create a new notebook using the NotebookLX API?"
        result = rewriter.rewrite_for_retrieval(original_query, chat_history=[])

        assert result.strategy == "no_rewrite"
        assert result.used_llm is False
        assert result.rewritten is False
        assert result.standalone_query == original_query
        assert result.search_queries == (original_query,)
        assert rewriter.rewrite(original_query, chat_history=[]) == original_query
        mock_provider.chat.assert_not_called()

    def test_summary_like_query_is_rewritten_for_retrieval(self):
        """Summary-style follow-ups should become standalone retrieval queries."""
        from services.api.modules.query.rewriter import QueryRewriter

        mock_provider = MagicMock()
        mock_provider.chat.return_value = """
        {
          "strategy": "standalone_expansion",
          "standalone_query": "Summarize the limitations of the NotebookLX vector search feature.",
          "search_queries": [
            "NotebookLX vector search limitations",
            "pgvector similarity search limitations NotebookLX"
          ]
        }
        """

        rewriter = QueryRewriter(chat_provider=mock_provider)
        chat_history = [
            {"role": "user", "content": "Tell me about the vector search feature in NotebookLX"},
            {
                "role": "assistant",
                "content": "The feature uses pgvector and can miss exact keyword matches on some queries.",
            },
        ]

        result = rewriter.rewrite_for_retrieval("Summarize this", chat_history=chat_history)

        assert result.strategy == "standalone_expansion"
        assert "vector search" in result.standalone_query.lower()
        assert any("limitations" in query.lower() for query in result.search_queries)
        assert result.rewritten is True

    def test_rewrite_pronoun_resolution(self):
        """AC: Follow-up with pronouns should resolve references."""
        from services.api.modules.query.rewriter import QueryRewriter

        mock_provider = MagicMock()
        mock_provider.chat.return_value = """
        {
          "strategy": "reference_resolution",
          "standalone_query": "What are the limitations of the vector search feature in NotebookLX?",
          "search_queries": [
            "NotebookLX vector search limitations",
            "pgvector search limitations"
          ]
        }
        """

        rewriter = QueryRewriter(chat_provider=mock_provider)
        chat_history = [
            {"role": "user", "content": "Tell me about the vector search feature"},
            {
                "role": "assistant",
                "content": "The vector search feature uses pgvector for similarity search.",
            },
        ]

        result = rewriter.rewrite_for_retrieval("What are its limitations?", chat_history=chat_history)

        assert result.rewritten is True
        assert "vector search" in result.standalone_query.lower()
        assert "pgvector" in " ".join(result.search_queries).lower()

    def test_rewrite_empty_query(self):
        """Empty or whitespace queries should return empty."""
        from services.api.modules.query.rewriter import QueryRewriter

        mock_provider = MagicMock()
        rewriter = QueryRewriter(chat_provider=mock_provider)

        result = rewriter.rewrite_for_retrieval("", chat_history=[])
        assert result.primary_query == ""

        result = rewriter.rewrite_for_retrieval("   ", chat_history=[])
        assert result.primary_query == ""

        mock_provider.chat.assert_not_called()

    def test_rewrite_preserves_special_terms(self):
        """Technical terms and proper nouns should be preserved."""
        from services.api.modules.query.rewriter import QueryRewriter

        mock_provider = MagicMock()
        rewriter = QueryRewriter(chat_provider=mock_provider)

        original_query = "How does pgvector handle cosine similarity in PostgreSQL?"
        result = rewriter.rewrite_for_retrieval(original_query, chat_history=[])

        assert result.strategy == "no_rewrite"
        assert "pgvector" in result.primary_query.lower()
        assert "postgresql" in result.primary_query.lower()
        mock_provider.chat.assert_not_called()

    def test_rewrite_sanitizes_prefixed_multiline_output(self):
        """LLM output should be sanitized before use."""
        from services.api.modules.query.rewriter import QueryRewriter

        mock_provider = MagicMock()
        mock_provider.chat.return_value = (
            "Rewritten query: Why does the NotebookLX ingestion pipeline use semantic chunking?\n"
            "Reason: it improves retrieval quality."
        )

        rewriter = QueryRewriter(chat_provider=mock_provider)
        chat_history = [
            {"role": "user", "content": "Tell me about the NotebookLX ingestion pipeline"},
            {
                "role": "assistant",
                "content": "The pipeline uses parsing, chunking, and embedding before retrieval.",
            },
        ]

        rewritten = rewriter.rewrite("Why this?", chat_history=chat_history)

        assert rewritten == "Why does the NotebookLX ingestion pipeline use semantic chunking?"

    def test_rewrite_rejects_output_that_drops_protected_terms(self):
        """If a rewrite drops protected terms, fall back to the original query."""
        from services.api.modules.query.rewriter import QueryRewriter

        mock_provider = MagicMock()
        mock_provider.chat.return_value = """
        {
          "strategy": "standalone_expansion",
          "standalone_query": "What are the limitations of vector search?",
          "search_queries": [
            "vector search limitations"
          ]
        }
        """

        rewriter = QueryRewriter(chat_provider=mock_provider)
        result = rewriter.rewrite_for_retrieval(
            "What about pgvector?",
            chat_history=[
                {"role": "user", "content": "Tell me about the vector search feature"},
                {"role": "assistant", "content": "It uses pgvector in PostgreSQL."},
            ],
        )

        assert result.used_llm is True
        assert result.rewritten is False
        assert result.primary_query == "What about pgvector?"

    def test_rewrite_result_counts_secondary_search_variants_as_rewritten(self):
        """Secondary retrieval queries should still surface rewrite transparency."""
        from services.api.modules.query.rewriter import QueryRewriteResult

        result = QueryRewriteResult(
            original_query="What are the risks?",
            standalone_query="What are the main NotebookLX project risks?",
            search_queries=(
                "What are the risks?",
                "NotebookLX project risks",
            ),
            strategy="keyword_enrichment",
            used_llm=True,
        )

        assert result.rewritten is True


class TestQueryRewriterIntegration:
    """Integration tests for query rewriting with database."""

    def test_rewrite_with_message_history_from_db(self, db: Session):
        """AC: Can use actual message history from database."""
        from services.api.modules.query.rewriter import get_recent_chat_history

        user = User(email="test@example.com")
        db.add(user)
        db.commit()

        notebook = Notebook(user_id=user.id, name="Test Notebook")
        db.add(notebook)
        db.commit()

        db.add_all(
            [
                Message(
                    notebook_id=notebook.id,
                    role=MessageRole.USER,
                    content="What is the ingestion pipeline?",
                ),
                Message(
                    notebook_id=notebook.id,
                    role=MessageRole.ASSISTANT,
                    content="The ingestion pipeline processes documents through parsing, chunking, and embedding.",
                ),
                Message(
                    notebook_id=notebook.id,
                    role=MessageRole.USER,
                    content="How long does it take?",
                ),
            ]
        )
        db.commit()

        history = get_recent_chat_history(db, str(notebook.id), limit=10)

        assert len(history) == 3
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "What is the ingestion pipeline?"
        assert history[1]["role"] == "assistant"
        assert history[2]["role"] == "user"

    def test_get_recent_chat_history_limits(self, db: Session):
        """Chat history retrieval should respect limit parameter."""
        from services.api.modules.query.rewriter import get_recent_chat_history

        user = User(email="test@example.com")
        db.add(user)
        db.commit()

        notebook = Notebook(user_id=user.id, name="Test Notebook")
        db.add(notebook)
        db.commit()

        for i in range(10):
            role = MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT
            db.add(
                Message(
                    notebook_id=notebook.id,
                    role=role,
                    content=f"Message {i}",
                )
            )
        db.commit()

        history = get_recent_chat_history(db, str(notebook.id), limit=5)

        assert len(history) == 5
        assert [message["content"] for message in history] == [
            "Message 5",
            "Message 6",
            "Message 7",
            "Message 8",
            "Message 9",
        ]

    def test_get_recent_chat_history_empty_notebook(self, db: Session):
        """Empty notebook should return empty history."""
        from services.api.modules.query.rewriter import get_recent_chat_history

        user = User(email="test@example.com")
        db.add(user)
        db.commit()

        notebook = Notebook(user_id=user.id, name="Empty Notebook")
        db.add(notebook)
        db.commit()

        history = get_recent_chat_history(db, str(notebook.id), limit=10)

        assert history == []

    def test_get_recent_chat_history_invalid_notebook_id_returns_empty(
        self,
        db: Session,
        caplog,
    ):
        """Invalid notebook IDs should not crash the rewrite helper."""
        from services.api.modules.query.rewriter import get_recent_chat_history

        with caplog.at_level(logging.WARNING):
            history = get_recent_chat_history(db, "not-a-uuid", limit=10)

        assert history == []
        assert "invalid notebook_id" in caplog.text.lower()


class TestQueryRewriterPrompt:
    """Test the query rewriting prompt construction."""

    def test_build_rewrite_prompt_without_history_mentions_retrieval(self):
        """Prompt should emphasize retrieval instead of normal QA."""
        from services.api.modules.query.rewriter import build_rewrite_prompt

        prompt = build_rewrite_prompt("What are the risks?", chat_history=[])
        prompt_str = str(prompt).lower()

        assert "document retrieval" in prompt_str
        assert "bm25" in prompt_str
        assert "search_queries" in prompt_str

    def test_build_rewrite_prompt_with_history_uses_recent_turns_and_topics(self):
        """Prompt should prioritize recent turns and topic hints."""
        from services.api.modules.query.rewriter import build_rewrite_prompt

        chat_history = [
            {"role": "user", "content": "Tell me about OCR parsing"},
            {"role": "assistant", "content": "OCR parsing is optional for image-heavy PDFs."},
            {"role": "user", "content": "Tell me about the NotebookLX vector search feature"},
            {"role": "assistant", "content": "The vector search feature uses pgvector for similarity search."},
            {"role": "user", "content": "What are the limitations of vector search?"},
            {"role": "assistant", "content": "It can miss exact keyword matches on some queries."},
        ]

        prompt = build_rewrite_prompt(
            "How does that work?",
            chat_history=chat_history,
            max_history_turns=2,
        )
        prompt_str = str(prompt).lower()

        assert "recent topics/entities" in prompt_str
        assert "vector search" in prompt_str
        assert "pgvector" in prompt_str
        assert "ocr parsing" not in prompt_str

    def test_build_rewrite_prompt_limits_history_tokens(self):
        """Prompt should limit chat history to avoid token overflow."""
        from services.api.modules.query.rewriter import build_rewrite_prompt

        query = "Follow up question"
        chat_history = [
            {"role": "user", "content": "Question " * 100},
            {"role": "assistant", "content": "Answer " * 100},
        ] * 10

        prompt = build_rewrite_prompt(query, chat_history=chat_history)

        assert len(str(prompt)) < 10000


class TestQueryRewriteSettings:
    """Test environment-driven query rewrite settings."""

    def test_settings_read_environment_configuration(self, monkeypatch):
        """Rewrite settings should resolve from environment variables."""
        from services.api.modules.query.rewriter import get_query_rewrite_settings

        monkeypatch.setenv("NOTEBOOKLX_QUERY_REWRITE_ENABLED", "false")
        monkeypatch.setenv(
            "NOTEBOOKLX_QUERY_REWRITE_STRATEGIES",
            "keyword_enrichment, reference_resolution",
        )
        monkeypatch.setenv("NOTEBOOKLX_QUERY_REWRITE_MAX_HISTORY_TURNS", "2")
        monkeypatch.setenv("NOTEBOOKLX_QUERY_REWRITE_MAX_SEARCH_QUERIES", "2")
        monkeypatch.setenv("NOTEBOOKLX_QUERY_REWRITE_SHORT_QUERY_TOKEN_THRESHOLD", "7")

        settings = get_query_rewrite_settings()

        assert settings.enabled is False
        assert settings.allowed_strategies == frozenset(
            {"keyword_enrichment", "reference_resolution"}
        )
        assert settings.max_history_turns == 2
        assert settings.max_search_queries == 2
        assert settings.short_query_token_threshold == 7

    def test_settings_reject_unknown_strategies(self, monkeypatch):
        """Invalid strategy names should fail fast."""
        from services.api.modules.query.rewriter import get_query_rewrite_settings

        monkeypatch.setenv("NOTEBOOKLX_QUERY_REWRITE_STRATEGIES", "keyword_enrichment,unknown")

        with pytest.raises(ValueError, match="Unknown query rewrite strategies"):
            get_query_rewrite_settings()
