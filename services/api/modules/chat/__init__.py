"""
Chat module for grounded question answering.

Feature 3.2: Grounded Q&A with Citations
"""
from services.api.modules.chat.service import (
    DEFAULT_GROUNDED_SYSTEM_PROMPT,
    GroundedQAResponse,
    GroundedQAService,
    build_grounded_messages,
    format_evidence_pack,
)

__all__ = [
    "DEFAULT_GROUNDED_SYSTEM_PROMPT",
    "GroundedQAResponse",
    "GroundedQAService",
    "build_grounded_messages",
    "format_evidence_pack",
]
