"""
Tests for streaming grounded chat responses.

Feature 3.2: Grounded Q&A with Citations
Slice: SSE streaming endpoint
"""
from uuid import uuid4

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
