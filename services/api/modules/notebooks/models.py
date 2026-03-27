"""
SQLAlchemy models for notebooks and users.
"""
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as pgUUID
from sqlalchemy.dialects.sqlite import CHAR
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from services.api.core.database import Base


# Custom UUID type that works with both PostgreSQL and SQLite
class UUID(pgUUID):
    """Platform-independent UUID type.
    Uses PostgreSQL's UUID type when available, otherwise uses CHAR(36).
    """
    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(pgUUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value) if isinstance(value, uuid.UUID) else value
        else:
            return str(value) if isinstance(value, uuid.UUID) else value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            return uuid.UUID(value)
        return value


class User(Base):
    """User model for authentication."""
    __tablename__ = "users"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    notebooks = relationship("Notebook", back_populates="user", cascade="all, delete-orphan")


class Notebook(Base):
    """Notebook model - the primary organizational unit."""
    __tablename__ = "notebooks"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True)  # For soft delete

    # Relationships
    user = relationship("User", back_populates="notebooks")
