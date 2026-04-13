"""
Tests for streaming grounded chat responses.

Feature 3.2: Grounded Q&A with Citations
Slice: SSE streaming endpoint
"""
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from services.api.modules.chat.service import (
    ChatTimingMetrics,
    EvidenceChunk,
    GroundedQAPreparation,
    GroundedQAResponse,
)
from services.api.core.ai import ChatUsage
from services.api.modules.chunking import count_tokens


def _make_citation_chunk(index: int = 1) -> EvidenceChunk:
    return EvidenceChunk(
        citation_index=index,
        chunk_id=f"chunk-{index}",
        source_id=f"source-{index}",
        source_title="Alpha Guide",
        chunk_index=index - 1,
        page="12",
        quote="Alpha is supported here.",
        content="Alpha is supported here in full context.",
        score=0.99,
    )


class TestGroundedChatStream:
    def test_stream_endpoint_emits_sse_events(
        self,
        client: TestClient,
        sample_notebook_data: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        AC: Streaming response for better UX.
        AC: User question retrieves relevant evidence chunks.
        """
        from services.api.modules.chat import routes as chat_routes

        notebook_response = client.post("/api/notebooks", json=sample_notebook_data)
        assert notebook_response.status_code == 201
        notebook_id = notebook_response.json()["id"]

        class FakeGroundedQAService:
            def __init__(self) -> None:
                self.calls: list[tuple[str, str, int]] = []
                self.stream_calls: list[list[dict[str, str]]] = []
                self.finalize_calls: list[str] = []
                self.usage_queue = [
                    None,
                    ChatUsage(
                        prompt_tokens=120,
                        completion_tokens=34,
                        total_tokens=154,
                        cached_tokens=10,
                        usage_source="provider",
                        estimated_cost_usd=0.0012,
                    ),
                ]

            async def prepare_answer(
                self,
                question: str,
                notebook_id: str,
                *,
                top_k: int = 5,
                chat_history=None,
            ):
                _ = chat_history
                self.calls.append((question, notebook_id, top_k))
                evidence = [_make_citation_chunk()]
                return GroundedQAPreparation(
                    evidence=evidence,
                    messages=[
                        {"role": "system", "content": "Use evidence only."},
                        {"role": "user", "content": question},
                    ],
                    metrics=ChatTimingMetrics(
                        model="glm-4.7",
                        query_embedding_seconds=6.41,
                        query_embedding_model="embedding-3",
                        query_embedding_token_count=18,
                        query_embedding_estimated_cost_usd=0.00036,
                        query_embedding_requests=2,
                        retrieval_seconds=0.16,
                        prepare_seconds=6.57,
                    ),
                )

            def stream_answer(self, messages):
                self.stream_calls.append(messages)
                yield "Alpha "
                yield "is supported."

            def finalize_answer(self, raw_answer, evidence, messages) -> GroundedQAResponse:
                self.finalize_calls.append(raw_answer)
                return GroundedQAResponse(
                    answer=raw_answer,
                    evidence=evidence,
                    citations=evidence,
                    citation_indices=[1],
                    missing_citation_indices=[],
                    raw_answer=raw_answer,
                    messages=messages,
                )

            def consume_chat_usage(self):
                return self.usage_queue.pop(0) if self.usage_queue else None

        service = FakeGroundedQAService()
        monkeypatch.setattr(chat_routes, "get_grounded_qa_service", lambda _db: service)

        response = client.stream(
            "POST",
            f"/api/notebooks/{notebook_id}/chat/stream",
            json={"question": "What is Alpha?"},
        )

        with response as stream:
            assert stream.status_code == 200
            assert stream.headers["content-type"].startswith("text/event-stream")

            body = "".join(stream.iter_text())

        assert "event: status" in body
        assert "event: metrics" in body
        assert "event: retrieval" in body
        assert body.count("event: answer_delta") == 2
        assert "event: citations" in body
        assert "event: answer" in body
        assert "event: done" in body
        assert '"stage": "embedding_query"' in body
        assert '"stage": "waiting_model"' in body
        assert '"stage": "streaming"' in body
        assert '"stage": "grounding"' in body
        assert '"model": "glm-4.7"' in body
        assert '"query_embedding_seconds": 6.41' in body
        assert '"query_embedding_model": "embedding-3"' in body
        assert '"query_embedding_token_count": 18' in body
        assert '"query_embedding_estimated_cost_usd": 0.00036' in body
        assert '"query_embedding_requests": 2' in body
        assert '"retrieval_seconds": 0.16' in body
        assert '"prepare_seconds": 6.57' in body
        assert '"chunk_count": 1' in body
        assert '"source_count": 1' in body
        assert '"source_id": "source-1"' in body
        assert '"delta_chunks_received": 2' in body
        assert '"stream_delivery": "streaming"' in body
        assert '"prompt_tokens": 120' in body
        assert '"completion_tokens": 34' in body
        assert '"total_tokens": 154' in body
        assert '"cached_tokens": 10' in body
        assert '"usage_source": "provider"' in body
        assert '"estimated_cost_usd": 0.0012' in body
        assert '"answer": "Alpha is supported."' in body
        assert '"delta": "Alpha "' in body
        assert '"delta": "is supported."' in body
        assert '"citation_indices": [1]' in body
        assert service.calls == [("What is Alpha?", notebook_id, 5)]
        assert service.finalize_calls == ["Alpha is supported."]

        assert body.index('"stage": "embedding_query"') < body.index('"query_embedding_seconds": 6.41')
        assert body.index('"query_embedding_seconds": 6.41') < body.index("event: retrieval")
        assert body.index("event: retrieval") < body.index('"stage": "waiting_model"')
        assert body.index('"stage": "waiting_model"') < body.index('"stage": "streaming"')
        assert body.index('"stage": "streaming"') < body.index("event: answer_delta")

    def test_stream_endpoint_estimates_usage_when_provider_usage_is_missing(
        self,
        client: TestClient,
        sample_notebook_data: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Chat streams should fall back to local token estimates when usage is absent."""
        from services.api.modules.chat import routes as chat_routes

        notebook_response = client.post("/api/notebooks", json=sample_notebook_data)
        assert notebook_response.status_code == 201
        notebook_id = notebook_response.json()["id"]

        class FakeGroundedQAService:
            async def prepare_answer(
                self,
                question: str,
                notebook_id: str,
                *,
                top_k: int = 5,
                chat_history=None,
            ):
                _ = (notebook_id, top_k, chat_history)
                evidence = [_make_citation_chunk()]
                return GroundedQAPreparation(
                    evidence=evidence,
                    messages=[
                        {"role": "system", "content": "Use evidence only."},
                        {"role": "user", "content": question},
                    ],
                )

            def stream_answer(self, messages):
                _ = messages
                yield "Alpha is supported."

            def finalize_answer(self, raw_answer, evidence, messages) -> GroundedQAResponse:
                return GroundedQAResponse(
                    answer=raw_answer,
                    evidence=evidence,
                    citations=evidence,
                    citation_indices=[1],
                    missing_citation_indices=[],
                    raw_answer=raw_answer,
                    messages=messages,
                )

        monkeypatch.setattr(
            chat_routes,
            "get_grounded_qa_service",
            lambda _db: FakeGroundedQAService(),
        )

        response = client.stream(
            "POST",
            f"/api/notebooks/{notebook_id}/chat/stream",
            json={"question": "What is Alpha?"},
        )

        with response as stream:
            assert stream.status_code == 200
            body = "".join(stream.iter_text())

        expected_prompt_tokens = count_tokens("system\nUse evidence only.\n\nuser\nWhat is Alpha?")
        expected_completion_tokens = count_tokens("Alpha is supported.")
        assert f'"prompt_tokens": {expected_prompt_tokens}' in body
        assert f'"completion_tokens": {expected_completion_tokens}' in body
        assert f'"total_tokens": {expected_prompt_tokens + expected_completion_tokens}' in body
        assert '"usage_source": "estimated"' in body

    def test_stream_endpoint_sets_sse_no_buffering_headers(
        self,
        client: TestClient,
        sample_notebook_data: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        AC: Streaming response for better UX.

        The SSE endpoint should send anti-buffering headers so browsers and
        reverse proxies do not coalesce the stream into a single late response.
        """
        from services.api.modules.chat import routes as chat_routes

        notebook_response = client.post("/api/notebooks", json=sample_notebook_data)
        assert notebook_response.status_code == 201
        notebook_id = notebook_response.json()["id"]

        class FakeGroundedQAService:
            async def prepare_answer(
                self,
                question: str,
                notebook_id: str,
                *,
                top_k: int = 5,
                chat_history=None,
            ):
                _ = chat_history
                evidence = [_make_citation_chunk()]
                return GroundedQAPreparation(
                    evidence=evidence,
                    messages=[
                        {"role": "system", "content": "Use evidence only."},
                        {"role": "user", "content": question},
                    ],
                )

            def stream_answer(self, messages):
                _ = messages
                yield "Alpha is supported."

            def finalize_answer(self, raw_answer, evidence, messages) -> GroundedQAResponse:
                return GroundedQAResponse(
                    answer=raw_answer,
                    evidence=evidence,
                    citations=evidence,
                    citation_indices=[1],
                    missing_citation_indices=[],
                    raw_answer=raw_answer,
                    messages=messages,
                )

        monkeypatch.setattr(
            chat_routes,
            "get_grounded_qa_service",
            lambda _db: FakeGroundedQAService(),
        )

        response = client.stream(
            "POST",
            f"/api/notebooks/{notebook_id}/chat/stream",
            json={"question": "What is Alpha?"},
        )

        with response as stream:
            assert stream.status_code == 200
            assert stream.headers["cache-control"] == "no-cache, no-transform"
            assert stream.headers["x-accel-buffering"] == "no"
            _ = "".join(stream.iter_text())

    def test_stream_endpoint_emits_query_rewrite_transparency_event(
        self,
        client: TestClient,
        sample_notebook_data: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        AC: User can see rewritten query (optional transparency).
        """
        from services.api.modules.chat import routes as chat_routes
        from services.api.modules.query.rewriter import QueryRewriteResult

        notebook_response = client.post("/api/notebooks", json=sample_notebook_data)
        assert notebook_response.status_code == 201
        notebook_id = notebook_response.json()["id"]

        class FakeGroundedQAService:
            async def prepare_answer(
                self,
                question: str,
                notebook_id: str,
                *,
                top_k: int = 5,
                chat_history=None,
            ):
                _ = (question, notebook_id, top_k, chat_history)
                evidence = [_make_citation_chunk()]
                return GroundedQAPreparation(
                    evidence=evidence,
                    messages=[
                        {"role": "system", "content": "Use evidence only."},
                        {"role": "user", "content": "Question: What are the NotebookLX project risks?"},
                    ],
                    query_rewrite=QueryRewriteResult(
                        original_query="What are the risks?",
                        standalone_query="What are the NotebookLX project risks?",
                        search_queries=(
                            "NotebookLX project risks",
                            "NotebookLX architecture risks",
                        ),
                        strategy="keyword_enrichment",
                        used_llm=True,
                    ),
                )

            def stream_answer(self, messages):
                _ = messages
                yield "Alpha is supported."

            def finalize_answer(self, raw_answer, evidence, messages) -> GroundedQAResponse:
                return GroundedQAResponse(
                    answer=raw_answer,
                    evidence=evidence,
                    citations=evidence,
                    citation_indices=[1],
                    missing_citation_indices=[],
                    raw_answer=raw_answer,
                    messages=messages,
                )

        monkeypatch.setattr(
            chat_routes,
            "get_grounded_qa_service",
            lambda _db: FakeGroundedQAService(),
        )

        response = client.stream(
            "POST",
            f"/api/notebooks/{notebook_id}/chat/stream",
            json={"question": "What are the risks?"},
        )

        with response as stream:
            assert stream.status_code == 200
            body = "".join(stream.iter_text())

        assert "event: query_rewrite" in body
        assert '"original_query": "What are the risks?"' in body
        assert '"standalone_query": "What are the NotebookLX project risks?"' in body
        assert '"search_queries": ["NotebookLX project risks", "NotebookLX architecture risks"]' in body
        assert '"strategy": "keyword_enrichment"' in body
        assert body.index("event: query_rewrite") < body.index("event: retrieval")

    def test_stream_endpoint_emits_query_rewrite_when_secondary_search_query_changes(
        self,
        client: TestClient,
        sample_notebook_data: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        AC: Rewrite metadata is exposed whenever retrieval inputs actually change.
        """
        from services.api.modules.chat import routes as chat_routes
        from services.api.modules.query.rewriter import QueryRewriteResult

        notebook_response = client.post("/api/notebooks", json=sample_notebook_data)
        assert notebook_response.status_code == 201
        notebook_id = notebook_response.json()["id"]

        class FakeGroundedQAService:
            async def prepare_answer(
                self,
                question: str,
                notebook_id: str,
                *,
                top_k: int = 5,
                chat_history=None,
            ):
                _ = (question, notebook_id, top_k, chat_history)
                evidence = [_make_citation_chunk()]
                return GroundedQAPreparation(
                    evidence=evidence,
                    messages=[
                        {"role": "system", "content": "Use evidence only."},
                        {"role": "user", "content": "Question: What are the main NotebookLX project risks?"},
                    ],
                    query_rewrite=QueryRewriteResult(
                        original_query="What are the risks?",
                        standalone_query="What are the main NotebookLX project risks?",
                        search_queries=(
                            "What are the risks?",
                            "NotebookLX project risks",
                        ),
                        strategy="keyword_enrichment",
                        used_llm=True,
                    ),
                )

            def stream_answer(self, messages):
                _ = messages
                yield "Alpha is supported."

            def finalize_answer(self, raw_answer, evidence, messages) -> GroundedQAResponse:
                return GroundedQAResponse(
                    answer=raw_answer,
                    evidence=evidence,
                    citations=evidence,
                    citation_indices=[1],
                    missing_citation_indices=[],
                    raw_answer=raw_answer,
                    messages=messages,
                )

        monkeypatch.setattr(
            chat_routes,
            "get_grounded_qa_service",
            lambda _db: FakeGroundedQAService(),
        )

        response = client.stream(
            "POST",
            f"/api/notebooks/{notebook_id}/chat/stream",
            json={"question": "What are the risks?"},
        )

        with response as stream:
            assert stream.status_code == 200
            body = "".join(stream.iter_text())

        assert "event: query_rewrite" in body
        assert '"search_queries": ["What are the risks?", "NotebookLX project risks"]' in body
        assert body.index("event: query_rewrite") < body.index("event: retrieval")

    def test_stream_endpoint_emits_error_event_without_aborting_connection(
        self,
        client: TestClient,
        sample_notebook_data: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        AC: Streaming response for better UX.

        If the upstream AI call fails after the stream has started, the endpoint
        should emit an SSE error event and end cleanly so clients can surface the
        error instead of treating it as a transport failure.
        """
        from services.api.modules.chat import routes as chat_routes

        notebook_response = client.post("/api/notebooks", json=sample_notebook_data)
        assert notebook_response.status_code == 201
        notebook_id = notebook_response.json()["id"]

        class FakeGroundedQAService:
            async def prepare_answer(
                self,
                question: str,
                notebook_id: str,
                *,
                top_k: int = 5,
                chat_history=None,
            ):
                _ = (question, notebook_id, top_k, chat_history)
                raise RuntimeError("Unexpected upstream failure")

        monkeypatch.setattr(
            chat_routes,
            "get_grounded_qa_service",
            lambda _db: FakeGroundedQAService(),
        )

        response = client.stream(
            "POST",
            f"/api/notebooks/{notebook_id}/chat/stream",
            json={"question": "What is Alpha?"},
        )

        with response as stream:
            assert stream.status_code == 200
            body = "".join(stream.iter_text())

        assert "event: status" in body
        assert "event: error" in body
        assert '"error": "internal_error"' in body
        assert '"message": "An unexpected error occurred"' in body

    def test_stream_endpoint_maps_provider_quota_errors_to_guardrail_payload(
        self,
        client: TestClient,
        sample_notebook_data: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        AC: Provider quota/balance failures return a user-friendly guardrail payload.
        """
        from services.api.modules.chat import routes as chat_routes

        notebook_response = client.post("/api/notebooks", json=sample_notebook_data)
        assert notebook_response.status_code == 201
        notebook_id = notebook_response.json()["id"]

        class FakeGroundedQAService:
            async def prepare_answer(
                self,
                question: str,
                notebook_id: str,
                *,
                top_k: int = 5,
                chat_history=None,
            ):
                _ = (question, notebook_id, top_k, chat_history)
                raise RuntimeError(
                    "openai.RateLimitError: Error code: 429 - "
                    "{'error': {'code': '1113', 'message': '余额不足或无可用资源包,请充值。'}}"
                )

        monkeypatch.setattr(
            chat_routes,
            "get_grounded_qa_service",
            lambda _db: FakeGroundedQAService(),
        )

        response = client.stream(
            "POST",
            f"/api/notebooks/{notebook_id}/chat/stream",
            json={"question": "What is Alpha?"},
        )

        with response as stream:
            assert stream.status_code == 200
            body = "".join(stream.iter_text())

        assert "event: error" in body
        assert '"error": "quota_exhausted"' in body
        assert '"title": "AI credits unavailable"' in body
        assert '"retryable": false' in body
        assert "余额不足或无可用资源包" not in body

    def test_stream_endpoint_maps_safety_errors_to_rephrase_guardrail(
        self,
        client: TestClient,
        sample_notebook_data: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        AC: Safety/policy failures tell the user to rephrase instead of leaking provider text.
        """
        from services.api.modules.chat import routes as chat_routes

        notebook_response = client.post("/api/notebooks", json=sample_notebook_data)
        assert notebook_response.status_code == 201
        notebook_id = notebook_response.json()["id"]

        class FakeGroundedQAService:
            async def prepare_answer(
                self,
                question: str,
                notebook_id: str,
                *,
                top_k: int = 5,
                chat_history=None,
            ):
                _ = (question, notebook_id, top_k, chat_history)
                raise RuntimeError(
                    "Request blocked by content policy because it may contain violative terms."
                )

        monkeypatch.setattr(
            chat_routes,
            "get_grounded_qa_service",
            lambda _db: FakeGroundedQAService(),
        )

        response = client.stream(
            "POST",
            f"/api/notebooks/{notebook_id}/chat/stream",
            json={"question": "What is Alpha?"},
        )

        with response as stream:
            assert stream.status_code == 200
            body = "".join(stream.iter_text())

        assert "event: error" in body
        assert '"error": "input_not_allowed"' in body
        assert '"title": "Question needs rewording"' in body
        assert '"retryable": true' in body

    def test_stream_endpoint_persists_completed_chat_exchange(
        self,
        client: TestClient,
        db,
        sample_notebook_data: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        AC: Completed grounded answers are stored in chat history.
        """
        from services.api.modules.chat import routes as chat_routes
        from services.api.modules.chat.models import Message, MessageRole

        notebook_response = client.post("/api/notebooks", json=sample_notebook_data)
        assert notebook_response.status_code == 201
        notebook_id = notebook_response.json()["id"]

        class FakeGroundedQAService:
            async def prepare_answer(
                self,
                question: str,
                notebook_id: str,
                *,
                top_k: int = 5,
                chat_history=None,
            ):
                _ = chat_history
                evidence = [_make_citation_chunk()]
                return GroundedQAPreparation(
                    evidence=evidence,
                    messages=[{"role": "user", "content": question}],
                )

            def stream_answer(self, messages):
                _ = messages
                yield "Alpha "
                yield "is supported."

            def finalize_answer(self, raw_answer, evidence, messages) -> GroundedQAResponse:
                return GroundedQAResponse(
                    answer=raw_answer,
                    evidence=evidence,
                    citations=evidence,
                    citation_indices=[1],
                    missing_citation_indices=[],
                    raw_answer=raw_answer,
                    messages=messages,
                )

        monkeypatch.setattr(
            chat_routes,
            "get_grounded_qa_service",
            lambda _db: FakeGroundedQAService(),
        )

        response = client.stream(
            "POST",
            f"/api/notebooks/{notebook_id}/chat/stream",
            json={"question": "What is Alpha?"},
        )

        with response as stream:
            assert stream.status_code == 200
            _ = "".join(stream.iter_text())

        messages = (
            db.query(Message)
            .filter(Message.notebook_id == UUID(notebook_id))
            .order_by(Message.created_at.asc(), Message.id.asc())
            .all()
        )

        assert len(messages) == 2
        assert [message.role for message in messages] == [
            MessageRole.USER,
            MessageRole.ASSISTANT,
        ]
        assert [message.content for message in messages] == [
            "What is Alpha?",
            "Alpha is supported.",
        ]

    def test_stream_endpoint_persists_fallback_answer_in_chat_history(
        self,
        client: TestClient,
        db,
        sample_notebook_data: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        AC: Fallback answers are still stored in chat history.
        """
        from services.api.modules.chat import routes as chat_routes
        from services.api.modules.chat.models import Message, MessageRole

        notebook_response = client.post("/api/notebooks", json=sample_notebook_data)
        assert notebook_response.status_code == 201
        notebook_id = notebook_response.json()["id"]

        class FakeGroundedQAService:
            async def prepare_answer(
                self,
                question: str,
                notebook_id: str,
                *,
                top_k: int = 5,
                chat_history=None,
            ):
                _ = chat_history
                return GroundedQAPreparation(
                    evidence=[],
                    messages=[{"role": "user", "content": question}],
                )

            def stream_answer(self, messages):
                _ = messages
                return iter(())

            def finalize_answer(self, raw_answer, evidence, messages) -> GroundedQAResponse:
                return GroundedQAResponse(
                    answer="I don't have enough information",
                    evidence=evidence,
                    citations=[],
                    citation_indices=[],
                    missing_citation_indices=[],
                    raw_answer=raw_answer,
                    messages=messages,
                )

        monkeypatch.setattr(
            chat_routes,
            "get_grounded_qa_service",
            lambda _db: FakeGroundedQAService(),
        )

        response = client.stream(
            "POST",
            f"/api/notebooks/{notebook_id}/chat/stream",
            json={"question": "What is Alpha?"},
        )

        with response as stream:
            assert stream.status_code == 200
            _ = "".join(stream.iter_text())

        messages = (
            db.query(Message)
            .filter(Message.notebook_id == UUID(notebook_id))
            .order_by(Message.created_at.asc(), Message.id.asc())
            .all()
        )

        assert len(messages) == 2
        assert [message.role for message in messages] == [
            MessageRole.USER,
            MessageRole.ASSISTANT,
        ]
        assert messages[1].content == "I don't have enough information"

    def test_stream_endpoint_returns_404_for_missing_notebook(
        self,
        client: TestClient,
    ) -> None:
        """
        AC: Proper error handling when the notebook does not exist.
        """
        response = client.post(
            f"/api/notebooks/{uuid4()}/chat/stream",
            json={"question": "What is Alpha?"},
        )

        assert response.status_code == 404
        assert response.json()["detail"]["error"] == "not_found"

    def test_stream_endpoint_returns_503_when_ai_client_is_not_configured(
        self,
        client: TestClient,
        sample_notebook_data: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        AC: Chat returns a controlled error when AI providers are not configured.
        """
        from services.api.modules.chat import routes as chat_routes

        notebook_response = client.post("/api/notebooks", json=sample_notebook_data)
        assert notebook_response.status_code == 201
        notebook_id = notebook_response.json()["id"]

        def fail_to_build_service(_db):
            raise ValueError("BigModel API key is required.")

        monkeypatch.setattr(chat_routes, "get_grounded_qa_service", fail_to_build_service)

        response = client.post(
            f"/api/notebooks/{notebook_id}/chat/stream",
            json={"question": "What is Alpha?"},
        )

        assert response.status_code == 503
        assert response.json()["detail"] == {
            "error": "ai_not_configured",
            "message": "BigModel API key is required.",
        }


class TestGroundedQAServiceBuilder:
    def test_get_grounded_qa_service_disables_query_rewriter_when_configured(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from services.api.modules.chat import routes as chat_routes
        from services.api.modules.query.rewriter import QueryRewriteSettings

        fake_retrieval_service = object()
        fake_embedding_provider = object()
        fake_chat_provider = object()

        monkeypatch.setattr(chat_routes, "HybridSearchService", lambda db: fake_retrieval_service)
        monkeypatch.setattr(chat_routes, "BigModelEmbeddingProvider", lambda: fake_embedding_provider)
        monkeypatch.setattr(chat_routes, "BigModelChatProvider", lambda: fake_chat_provider)
        monkeypatch.setattr(
            chat_routes,
            "get_query_rewrite_settings",
            lambda: QueryRewriteSettings(enabled=False),
        )

        service = chat_routes.get_grounded_qa_service(object())

        assert service.retrieval_service is fake_retrieval_service
        assert service.embedding_provider is fake_embedding_provider
        assert service.chat_provider is fake_chat_provider
        assert service.query_rewriter is None

    def test_get_grounded_qa_service_applies_query_rewriter_settings(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from services.api.modules.chat import routes as chat_routes
        from services.api.modules.query.rewriter import QueryRewriteSettings

        fake_chat_provider = object()

        monkeypatch.setattr(chat_routes, "HybridSearchService", lambda db: object())
        monkeypatch.setattr(chat_routes, "BigModelEmbeddingProvider", lambda: object())
        monkeypatch.setattr(chat_routes, "BigModelChatProvider", lambda: fake_chat_provider)
        monkeypatch.setattr(
            chat_routes,
            "get_query_rewrite_settings",
            lambda: QueryRewriteSettings(
                enabled=True,
                max_history_turns=2,
                max_search_queries=2,
                short_query_token_threshold=6,
                allowed_strategies=frozenset({"keyword_enrichment", "reference_resolution"}),
            ),
        )

        service = chat_routes.get_grounded_qa_service(object())

        assert service.query_rewriter is not None
        assert service.query_rewriter.chat_provider is fake_chat_provider
        assert service.query_rewriter.max_history_turns == 2
        assert service.query_rewriter.max_search_queries == 2
        assert service.query_rewriter.short_query_token_threshold == 6
        assert service.query_rewriter.allowed_strategies == frozenset(
            {"keyword_enrichment", "reference_resolution"}
        )
