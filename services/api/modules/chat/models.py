"""
SQLAlchemy models for persisted chat messages.
"""
from datetime import datetime
import enum
import uuid

from sqlalchemy import Column, DateTime, Enum as SQLEnum, ForeignKey, Text
from sqlalchemy.orm import relationship

from services.api.core.database import Base
from services.api.modules.notebooks.models import UUID


class MessageRole(str, enum.Enum):
    """Supported persisted chat roles."""

    USER = "user"
    ASSISTANT = "assistant"


class Message(Base):
    """Persist a notebook-scoped chat message."""

    __tablename__ = "messages"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    notebook_id = Column(
        UUID,
        ForeignKey("notebooks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(
        SQLEnum(MessageRole, values_callable=lambda values: [value.value for value in values]),
        nullable=False,
    )
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    notebook = relationship("Notebook", backref="messages")
