"""
API routes for grounded chat streaming.

Feature 3.2: Grounded Q&A with Citations
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from dataclasses import dataclass
import logging
import time
import uuid

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
from services.api.modules.chat.service import build_retrieval_diagnostics
from services.api.modules.embeddings.providers import BigModelEmbeddingProvider
from services.api.modules.notebooks.models import Notebook
from services.api.modules.notebooks.routes import get_current_user_id
from services.api.modules.query import QueryRewriter, get_recent_chat_history
from services.api.modules.retrieval.hybrid import HybridSearchService


router = APIRouter(prefix="/api/notebooks", tags=["chat"])
OPENAI_STREAM_ERROR_TYPES = tuple(
    error_type
    for error_type in (APIConnectionError, APIError, RateLimitError, APITimeoutError)
    if error_type is not None
)


class ChatStreamRequest(BaseModel):
    """Incoming grounded chat request."""

    question: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


@dataclass(frozen=True)
class ChatGuardrailError:
    """User-facing chat failure payload for SSE error events."""

    error: str
    title: str
    message: str
    hint: str | None = None
    retryable: bool = True


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
    query_rewriter = QueryRewriter(chat_provider=chat_provider)
    return GroundedQAService(
        retrieval_service,
        embedding_provider,
        chat_provider,
        query_rewriter=query_rewriter,
    )


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


def _error_status_code(exc: Exception) -> int | None:
    value = getattr(exc, "status_code", None)
    return value if isinstance(value, int) else None


def _error_type_name(exc: Exception) -> str:
    return type(exc).__name__.lower()


def _error_text(exc: Exception) -> str:
    return str(exc).strip().lower()


def _is_quota_error(exc: Exception) -> bool:
    message = _error_text(exc)
    status_code = _error_status_code(exc)
    keywords = (
        "quota",
        "credit",
        "balance",
        "insufficient",
        "resource package",
        "余额不足",
        "无可用资源包",
        "1113",
    )
    return (
        status_code == 429
        or "ratelimiterror" in _error_type_name(exc)
        or "429" in message
    ) and any(keyword in message for keyword in keywords)


def _is_safety_error(exc: Exception) -> bool:
    message = _error_text(exc)
    keywords = (
        "content policy",
        "policy",
        "violative",
        "violation",
        "违规",
        "safety",
        "content_filter",
        "sensitive",
    )
    return any(keyword in message for keyword in keywords)


def _is_temporary_upstream_error(exc: Exception) -> bool:
    message = _error_text(exc)
    type_name = _error_type_name(exc)
    status_code = _error_status_code(exc)
    keywords = (
        "timeout",
        "timed out",
        "connection",
        "temporarily unavailable",
        "service unavailable",
        "gateway",
        "bad gateway",
        "overloaded",
    )
    is_known_upstream_type = (
        "apitimeouterror" in type_name or "apiconnectionerror" in type_name
    )
    has_retryable_status = status_code in {408, 409, 425, 429, 500, 502, 503, 504}
    has_temporary_keyword = any(keyword in message for keyword in keywords)
    return is_known_upstream_type or (has_retryable_status and has_temporary_keyword)


def _classify_chat_exception(exc: Exception) -> ChatGuardrailError:
    if _is_quota_error(exc):
        return ChatGuardrailError(
            error="quota_exhausted",
            title="AI credits unavailable",
            message="The AI provider account has no available balance or package quota.",
            hint="Recharge the provider account or switch to another configured model, then try again.",
            retryable=False,
        )

    if _is_safety_error(exc):
        return ChatGuardrailError(
            error="input_not_allowed",
            title="Question needs rewording",
            message="This request may violate the provider safety policy, so no answer was generated.",
            hint="Rephrase the question in neutral terms and keep it focused on the notebook sources.",
            retryable=True,
        )

    if _is_temporary_upstream_error(exc):
        return ChatGuardrailError(
            error="temporary_unavailable",
            title="Model temporarily unavailable",
            message="The model did not complete this request. Your notebook data is unchanged.",
            hint="Wait a moment and try again.",
            retryable=True,
        )

    return ChatGuardrailError(
        error="internal_error",
        title="Chat could not complete",
        message="An unexpected error occurred",
        hint="Try again in a moment.",
        retryable=True,
    )


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
                "stage": "embedding_query",
                "message": "Embedding your question for notebook retrieval",
            },
        )
        await asyncio.sleep(0)

        try:
            chat_history = get_recent_chat_history(db, str(notebook.id))
            preparation = await grounded_qa_service.prepare_answer(
                payload.question,
                str(notebook.id),
                top_k=payload.top_k,
                chat_history=chat_history,
            )
            if preparation.metrics is not None:
                yield _format_sse_event(
                    "metrics",
                    asdict(preparation.metrics),
                )
                await asyncio.sleep(0)

            if preparation.query_rewrite is not None:
                rewrite_payload = asdict(preparation.query_rewrite)
                rewrite_payload["rewritten"] = preparation.query_rewrite.rewritten
                yield _format_sse_event(
                    "query_rewrite",
                    rewrite_payload,
                )
                await asyncio.sleep(0)

            retrieval = build_retrieval_diagnostics(preparation.evidence)
            yield _format_sse_event(
                "retrieval",
                asdict(retrieval),
            )
            await asyncio.sleep(0)
            raw_answer_parts: list[str] = []

            if preparation.evidence:
                yield _format_sse_event(
                    "status",
                    {
                        "stage": "waiting_model",
                        "message": "Waiting for the model to send the first answer chunk",
                    },
                )
                await asyncio.sleep(0)
                llm_stream_started_at = time.monotonic()
                first_delta_at: float | None = None
                delta_chunks_received = 0

                for delta in grounded_qa_service.stream_answer(preparation.messages):
                    if not delta:
                        continue

                    delta_chunks_received += 1
                    if first_delta_at is None:
                        first_delta_at = time.monotonic()
                        yield _format_sse_event(
                            "metrics",
                            {
                                "time_to_first_delta_seconds": round(
                                    first_delta_at - llm_stream_started_at,
                                    2,
                                ),
                                "delta_chunks_received": delta_chunks_received,
                                "stream_delivery": "streaming",
                            },
                        )
                        await asyncio.sleep(0)
                        yield _format_sse_event(
                            "status",
                            {
                                "stage": "streaming",
                                "message": "Streaming the answer into the chat",
                            },
                        )
                        await asyncio.sleep(0)

                    raw_answer_parts.append(delta)
                    yield _format_sse_event("answer_delta", {"delta": delta})
                    await asyncio.sleep(0)

                llm_stream_seconds = round(time.monotonic() - llm_stream_started_at, 2)
                stream_delivery = (
                    "single_chunk"
                    if delta_chunks_received == 1
                    else "streaming"
                    if delta_chunks_received > 1
                    else "no_chunks"
                )
                yield _format_sse_event(
                    "metrics",
                    {
                        "llm_stream_seconds": llm_stream_seconds,
                        "delta_chunks_received": delta_chunks_received,
                        "stream_delivery": stream_delivery,
                    },
                )
                await asyncio.sleep(0)

            yield _format_sse_event(
                "status",
                {
                    "stage": "grounding",
                    "message": "Checking citation alignment",
                },
            )
            await asyncio.sleep(0)
            response = grounded_qa_service.finalize_answer(
                "".join(raw_answer_parts),
                preparation.evidence,
                preparation.messages,
            )
            _persist_chat_exchange(db, notebook.id, payload.question, response.answer)

            if not preparation.evidence and response.answer:
                yield _format_sse_event("answer_delta", {"delta": response.answer})
                await asyncio.sleep(0)

            yield _format_sse_event(
                "citations",
                {
                    "citations": [asdict(chunk) for chunk in response.citations],
                    "citation_indices": response.citation_indices,
                    "missing_citation_indices": response.missing_citation_indices,
                },
            )
            await asyncio.sleep(0)
            yield _format_sse_event(
                "answer",
                {
                    "answer": response.answer,
                    "raw_answer": response.raw_answer,
                },
            )
            await asyncio.sleep(0)
            yield _format_sse_event("done", {"status": "complete"})
            await asyncio.sleep(0)
        except OPENAI_STREAM_ERROR_TYPES as exc:
            guardrail = _classify_chat_exception(exc)
            logger.exception("AI API error during chat stream")
            yield _format_sse_event(
                "error",
                asdict(guardrail),
            )
            await asyncio.sleep(0)
            return
        except Exception as exc:
            guardrail = _classify_chat_exception(exc)
            logger.exception("Unexpected error during chat stream")
            yield _format_sse_event(
                "error",
                asdict(guardrail),
            )
            await asyncio.sleep(0)
            return

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )
