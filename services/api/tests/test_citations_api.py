"""
Tests for citation API endpoints.

Feature 3.4: Two-Layer Citation System
Acceptance Criteria: Create citation API endpoint for fetching citations by message
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from services.api.modules.citations.models import Citation
from services.api.modules.chat.models import Message, MessageRole
from services.api.modules.chunking.models import SourceChunk
from services.api.modules.sources.models import Source, SourceType, SourceStatus
from services.api.modules.notebooks.models import Notebook, User


class TestCitationAPI:
    """Test citation API endpoints."""

    def test_get_citations_by_message_id(self, db: Session, client: TestClient):
        """AC: Can fetch all citations for a message via API."""
        # Create test data
        user = User(email="test@example.com")
        db.add(user)
        db.commit()

        notebook = Notebook(user_id=user.id, name="Test Notebook")
        db.add(notebook)
        db.commit()

        source = Source(
            notebook_id=notebook.id,
            source_type=SourceType.TEXT,
            title="Test Source",
            status=SourceStatus.READY,
        )
        db.add(source)
        db.commit()

        chunk1 = SourceChunk(
            source_id=source.id,
            chunk_index=0,
            content="Quote 1 content",
            token_count=3,
            char_start=0,
            char_end=14,
            chunk_metadata={"page": 1},
        )
        chunk2 = SourceChunk(
            source_id=source.id,
            chunk_index=1,
            content="Quote 2 content",
            token_count=3,
            char_start=15,
            char_end=29,
            chunk_metadata={"page": 2},
        )
        db.add_all([chunk1, chunk2])
        db.commit()

        message = Message(
            notebook_id=notebook.id,
            role=MessageRole.ASSISTANT,
            content="Answer with citations.",
        )
        db.add(message)
        db.commit()

        # Create citations
        citation1 = Citation(
            message_id=message.id,
            chunk_id=chunk1.id,
            citation_index=1,
            quote="Quote 1 content",
            score=0.95,
            page="1",
            source_title="Test Source",
        )
        citation2 = Citation(
            message_id=message.id,
            chunk_id=chunk2.id,
            citation_index=2,
            quote="Quote 2 content",
            score=0.85,
            page="2",
            source_title="Test Source",
        )
        db.add_all([citation1, citation2])
        db.commit()

        # Fetch citations via API
        response = client.get(f"/api/messages/{message.id}/citations")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert "citations" in data
        assert len(data["citations"]) == 2

        # Verify citation order (by citation_index)
        citations = data["citations"]
        assert citations[0]["citation_index"] == 1
        assert citations[0]["quote"] == "Quote 1 content"
        assert citations[0]["score"] == 0.95
        assert citations[0]["page"] == "1"
        assert citations[0]["source_title"] == "Test Source"

        assert citations[1]["citation_index"] == 2
        assert citations[1]["quote"] == "Quote 2 content"
        assert citations[1]["score"] == 0.85
        assert citations[1]["page"] == "2"

    def test_get_citations_returns_empty_list_for_message_without_citations(self, db: Session, client: TestClient):
        """AC: Returns empty list when message has no citations."""
        user = User(email="test@example.com")
        db.add(user)
        db.commit()

        notebook = Notebook(user_id=user.id, name="Test Notebook")
        db.add(notebook)
        db.commit()

        message = Message(
            notebook_id=notebook.id,
            role=MessageRole.ASSISTANT,
            content="Answer without citations.",
        )
        db.add(message)
        db.commit()

        # Fetch citations via API
        response = client.get(f"/api/messages/{message.id}/citations")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert "citations" in data
        assert len(data["citations"]) == 0

    def test_get_citations_returns_404_for_nonexistent_message(self, db: Session, client: TestClient):
        """AC: Returns 404 when message does not exist."""
        fake_id = uuid.uuid4()
        response = client.get(f"/api/messages/{fake_id}/citations")

        # Verify response
        assert response.status_code == 404
        data = response.json()
        # FastAPI wraps HTTPException details in "detail" key
        assert "detail" in data
        assert data["detail"]["error"] == "not_found"

    def test_get_citations_includes_chunk_metadata(self, db: Session, client: TestClient):
        """AC: Citations include relevant chunk metadata."""
        user = User(email="test@example.com")
        db.add(user)
        db.commit()

        notebook = Notebook(user_id=user.id, name="Test Notebook")
        db.add(notebook)
        db.commit()

        source = Source(
            notebook_id=notebook.id,
            source_type=SourceType.PDF,
            title="Test PDF",
            status=SourceStatus.READY,
        )
        db.add(source)
        db.commit()

        chunk = SourceChunk(
            source_id=source.id,
            chunk_index=0,
            content="Important content",
            token_count=2,
            char_start=0,
            char_end=17,
            chunk_metadata={"page": 5, "heading": "Introduction"},
        )
        db.add(chunk)
        db.commit()

        message = Message(
            notebook_id=notebook.id,
            role=MessageRole.ASSISTANT,
            content="Answer",
        )
        db.add(message)
        db.commit()

        citation = Citation(
            message_id=message.id,
            chunk_id=chunk.id,
            citation_index=1,
            quote="Important content",
            score=0.92,
            page="5",
            source_title="Test PDF",
        )
        db.add(citation)
        db.commit()

        # Fetch citations via API
        response = client.get(f"/api/messages/{message.id}/citations")

        # Verify response includes all expected fields
        assert response.status_code == 200
        data = response.json()
        assert len(data["citations"]) == 1

        citation_data = data["citations"][0]
        assert citation_data["id"] == str(citation.id)
        assert citation_data["chunk_id"] == str(chunk.id)
        assert citation_data["citation_index"] == 1
        assert citation_data["quote"] == "Important content"
        assert citation_data["score"] == 0.92
        assert citation_data["page"] == "5"
        assert citation_data["source_title"] == "Test PDF"
        assert "created_at" in citation_data
