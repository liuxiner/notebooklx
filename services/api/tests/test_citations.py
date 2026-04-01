"""
Tests for citation database persistence.

Feature 3.4: Two-Layer Citation System
Acceptance Criteria: Citations persist in database for audit
"""
import uuid
import pytest
from sqlalchemy.orm import Session

from services.api.modules.citations.models import Citation
from services.api.modules.chat.models import Message, MessageRole
from services.api.modules.chunking.models import SourceChunk
from services.api.modules.sources.models import Source, SourceType, SourceStatus
from services.api.modules.notebooks.models import Notebook, User


class TestCitationModel:
    """Test Citation database model and relationships."""

    def test_create_citation_with_required_fields(self, db: Session):
        """AC: Citations persist in database for audit."""
        # Create a user, notebook, source, chunk, and message first
        user = User(email="test@example.com")
        db.add(user)
        db.commit()

        notebook = Notebook(
            user_id=user.id,
            name="Test Notebook",
            description="Test description"
        )
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

        chunk = SourceChunk(
            source_id=source.id,
            chunk_index=0,
            content="Test chunk content",
            token_count=5,
            char_start=0,
            char_end=20,
            chunk_metadata={"page": 1},
        )
        db.add(chunk)
        db.commit()

        message = Message(
            notebook_id=notebook.id,
            role=MessageRole.ASSISTANT,
            content="Test answer with citation.",
        )
        db.add(message)
        db.commit()

        # Create citation
        citation = Citation(
            message_id=message.id,
            chunk_id=chunk.id,
            citation_index=1,
            quote="Test chunk content",
            score=0.95,
            page="1",
            source_title="Test Source",
        )
        db.add(citation)
        db.commit()
        db.refresh(citation)

        # Verify citation was persisted
        assert citation.id is not None
        assert citation.message_id == message.id
        assert citation.chunk_id == chunk.id
        assert citation.citation_index == 1
        assert citation.quote == "Test chunk content"
        assert citation.score == 0.95
        assert citation.page == "1"
        assert citation.source_title == "Test Source"

    def test_citation_message_relationship(self, db: Session):
        """AC: Can retrieve citations for a message."""
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

        chunk = SourceChunk(
            source_id=source.id,
            chunk_index=0,
            content="Content 1",
            token_count=2,
            char_start=0,
            char_end=9,
        )
        db.add(chunk)
        db.commit()

        message = Message(
            notebook_id=notebook.id,
            role=MessageRole.ASSISTANT,
            content="Answer with citations.",
        )
        db.add(message)
        db.commit()

        # Create multiple citations for the same message
        for i in range(3):
            citation = Citation(
                message_id=message.id,
                chunk_id=chunk.id,
                citation_index=i + 1,
                quote=f"Quote {i + 1}",
                score=0.9 - (i * 0.1),
                source_title="Test Source",
            )
            db.add(citation)
        db.commit()

        # Verify relationship works
        retrieved_message = db.query(Message).filter(Message.id == message.id).first()
        assert len(retrieved_message.citations) == 3
        assert [c.citation_index for c in retrieved_message.citations] == [1, 2, 3]

    def test_citation_chunk_relationship(self, db: Session):
        """AC: Can retrieve which messages cited a chunk."""
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

        chunk = SourceChunk(
            source_id=source.id,
            chunk_index=0,
            content="Important content",
            token_count=2,
            char_start=0,
            char_end=18,
        )
        db.add(chunk)
        db.commit()

        # Create multiple messages that cite the same chunk
        for i in range(2):
            message = Message(
                notebook_id=notebook.id,
                role=MessageRole.ASSISTANT,
                content=f"Answer {i + 1}",
            )
            db.add(message)
            db.flush()

            citation = Citation(
                message_id=message.id,
                chunk_id=chunk.id,
                citation_index=1,
                quote="Important content",
                score=0.95,
                source_title="Test Source",
            )
            db.add(citation)
        db.commit()

        # Verify relationship works
        retrieved_chunk = db.query(SourceChunk).filter(SourceChunk.id == chunk.id).first()
        assert len(retrieved_chunk.citations) == 2

    def test_citation_can_be_deleted(self, db: Session):
        """AC: Citations can be deleted from database."""
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

        chunk = SourceChunk(
            source_id=source.id,
            chunk_index=0,
            content="Content",
            token_count=1,
            char_start=0,
            char_end=7,
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
            quote="Content",
            score=0.9,
            source_title="Test Source",
        )
        db.add(citation)
        db.commit()

        citation_id = citation.id

        # Delete citation directly
        db.delete(citation)
        db.commit()

        # Verify citation was deleted
        remaining = db.query(Citation).filter(Citation.id == citation_id).first()
        assert remaining is None
