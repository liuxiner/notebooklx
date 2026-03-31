"""
Tests for streaming grounded chat responses.

Feature 3.2: Grounded Q&A with Citations
Slice: SSE streaming endpoint
"""
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from services.api.modules.chat.service import (
    EvidenceChunk,
    GroundedQAResponse,
)


def _make_citation_chunk(index: int = 1) -> EvidenceChunk:
    return EvidenceChunk(
        citation_index=index,
        chunk_id=f"chunk-{index}",
        source_title="Alpha Guide",
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

            async def answer_question(
                self,
                question: str,
                notebook_id: str,
                *,
                top_k: int = 5,
            ) -> GroundedQAResponse:
                self.calls.append((question, notebook_id, top_k))
                evidence = [_make_citation_chunk()]
                return GroundedQAResponse(
                    answer="Alpha is supported.",
                    evidence=evidence,
                    citations=evidence,
                    citation_indices=[1],
                    missing_citation_indices=[],
                    raw_answer='{"answer":"Alpha is supported.","citations":[1]}',
                    messages=[],
                )

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
        assert "event: citations" in body
        assert "event: answer" in body
        assert "event: done" in body
        assert '"answer": "Alpha is supported."' in body
        assert '"citation_indices": [1]' in body
        assert service.calls == [("What is Alpha?", notebook_id, 5)]

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
            async def answer_question(
                self,
                question: str,
                notebook_id: str,
                *,
                top_k: int = 5,
            ) -> GroundedQAResponse:
                evidence = [_make_citation_chunk()]
                return GroundedQAResponse(
                    answer="Alpha is supported.",
                    evidence=evidence,
                    citations=evidence,
                    citation_indices=[1],
                    missing_citation_indices=[],
                    raw_answer='{"answer":"Alpha is supported.","citations":[1]}',
                    messages=[],
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
            async def answer_question(
                self,
                question: str,
                notebook_id: str,
                *,
                top_k: int = 5,
            ) -> GroundedQAResponse:
                return GroundedQAResponse(
                    answer="I don't have enough information",
                    evidence=[],
                    citations=[],
                    citation_indices=[],
                    missing_citation_indices=[],
                    raw_answer="",
                    messages=[],
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
