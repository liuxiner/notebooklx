"""
API routes for grounded chat streaming.

Feature 3.2: Grounded Q&A with Citations
"""
from __future__ import annotations

import json
from dataclasses import asdict
import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from services.api.core.ai import BigModelChatProvider

logger = logging.getLogger(__name__)

try:
    from openai import APIConnectionError, APIError, RateLimitError, APITimeoutError
except ImportError:  # pragma: no cover
    APIConnectionError = APIError = RateLimitError = APITimeoutError = None
from services.api.core.database import get_db
from services.api.modules.chat.models import Message, MessageRole
from services.api.modules.chat.service import GroundedQAService
from services.api.modules.embeddings.providers import BigModelEmbeddingProvider
from services.api.modules.notebooks.models import Notebook
from services.api.modules.notebooks.routes import get_current_user_id
from services.api.modules.retrieval.hybrid import HybridSearchService


router = APIRouter(prefix="/api/notebooks", tags=["chat"])


class ChatStreamRequest(BaseModel):
    """Incoming grounded chat request."""

    question: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


def build_error(status_code: int, error: str, message: str) -> HTTPException:
    """Create a consistent HTTPException payload."""
    return HTTPException(
        status_code=status_code,
        detail={"error": error, "message": message},
    )


def get_grounded_qa_service(db: Session) -> GroundedQAService:
    """Construct the default grounded Q&A service stack."""
    retrieval_service = HybridSearchService(db)
    embedding_provider = BigModelEmbeddingProvider()
    chat_provider = BigModelChatProvider()
    return GroundedQAService(retrieval_service, embedding_provider, chat_provider)


def _get_notebook_for_user(
    notebook_id: uuid.UUID,
    db: Session,
    user_id: uuid.UUID,
) -> Notebook:
    notebook = (
        db.query(Notebook)
        .filter(
            Notebook.id == notebook_id,
            Notebook.user_id == user_id,
            Notebook.deleted_at.is_(None),
        )
        .first()
    )

    if not notebook:
        raise build_error(
            status.HTTP_404_NOT_FOUND,
            "not_found",
            f"Notebook {notebook_id} not found",
        )

    return notebook


def _format_sse_event(event: str, data: dict) -> str:
    """Serialize a Server-Sent Event payload."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _persist_chat_exchange(
    db: Session,
    notebook_id: uuid.UUID,
    question: str,
    answer: str,
) -> None:
    """Store a completed user/assistant exchange for the notebook."""
    db.add_all(
        [
            Message(
                notebook_id=notebook_id,
                role=MessageRole.USER,
                content=question,
            ),
            Message(
                notebook_id=notebook_id,
                role=MessageRole.ASSISTANT,
                content=answer,
            ),
        ]
    )
    db.commit()


@router.post("/{notebook_id}/chat/stream")
async def stream_grounded_chat(
    notebook_id: uuid.UUID,
    payload: ChatStreamRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """
    Stream a grounded answer using SSE.

    AC: User question retrieves relevant evidence chunks
    AC: LLM generates answer based only on retrieved chunks
    AC: Streaming response for better UX
    """
    notebook = _get_notebook_for_user(notebook_id, db, user_id)
    try:
        grounded_qa_service = get_grounded_qa_service(db)
    except (ImportError, ValueError) as exc:
        raise build_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "ai_not_configured",
            str(exc),
        ) from exc

    async def event_stream():
        yield _format_sse_event(
            "status",
            {
                "stage": "retrieving",
                "message": f"Searching sources in notebook {notebook.id}",
            },
        )

        try:
            response = await grounded_qa_service.answer_question(
                payload.question,
                str(notebook.id),
                top_k=payload.top_k,
            )
            _persist_chat_exchange(db, notebook.id, payload.question, response.answer)

            yield _format_sse_event(
                "citations",
                {
                    "citations": [asdict(chunk) for chunk in response.citations],
                    "citation_indices": response.citation_indices,
                    "missing_citation_indices": response.missing_citation_indices,
                },
            )
            yield _format_sse_event(
                "answer",
                {
                    "answer": response.answer,
                    "raw_answer": response.raw_answer,
                },
            )
            yield _format_sse_event("done", {"status": "complete"})
        except (APIConnectionError, APIError, RateLimitError, APITimeoutError) as exc:
            logger.exception("AI API error during chat stream")
            yield _format_sse_event(
                "error",
                {
                    "error": type(exc).__name__,
                    "message": str(exc),
                },
            )
            raise
        except Exception as exc:
            logger.exception("Unexpected error during chat stream")
            yield _format_sse_event(
                "error",
                {
                    "error": "internal_error",
                    "message": "An unexpected error occurred",
                },
            )
            raise

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )
