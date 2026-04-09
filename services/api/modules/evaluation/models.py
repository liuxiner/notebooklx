"""
SQLAlchemy models for evaluation and metrics.

Feature 6.3: Evaluation Dashboard
"""
import uuid
from datetime import datetime
import enum

from sqlalchemy import Column, DateTime, Enum as SQLEnum, Float, ForeignKey, Integer, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as pgUUID
from sqlalchemy.dialects.sqlite import CHAR
from sqlalchemy.orm import relationship

from services.api.core.database import Base
from services.api.modules.notebooks.models import UUID


class MetricType(str, enum.Enum):
    """Enumeration of evaluation metric types."""
    RECALL_AT_5 = "recall_at_5"
    RECALL_AT_10 = "recall_at_10"
    RECALL_AT_K = "recall_at_k"
    MRR = "mrr"
    CITATION_SUPPORT_RATE = "citation_support_rate"
    WRONG_CITATION_RATE = "wrong_citation_rate"
    GROUNDEDNESS = "groundedness"
    COMPLETENESS = "completeness"
    FAITHFULNESS = "faithfulness"


class EvaluationStatus(str, enum.Enum):
    """Enumeration of evaluation run statuses."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EvaluationRun(Base):
    """Represents a complete evaluation run for a notebook."""
    __tablename__ = "evaluation_runs"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    notebook_id = Column(
        UUID,
        ForeignKey("notebooks.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    query = Column(Text, nullable=False)
    ground_truth_chunk_ids = Column(JSON, nullable=True)
    status = Column(
        SQLEnum(EvaluationStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=EvaluationStatus.PENDING
    )
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    notebook = relationship("Notebook")
    metrics = relationship("EvaluationMetric", back_populates="evaluation_run", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<EvaluationRun(id={self.id}, notebook_id={self.notebook_id}, status={self.status})>"


class EvaluationMetric(Base):
    """Represents a specific metric value from an evaluation run."""
    __tablename__ = "evaluation_metrics"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    evaluation_run_id = Column(
        UUID,
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    metric_type = Column(
        SQLEnum(MetricType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True
    )
    metric_value = Column(Float, nullable=False)
    metric_metadata = Column(Text, nullable=True)  # JSON string for additional context
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    evaluation_run = relationship("EvaluationRun", back_populates="metrics")

    def __repr__(self) -> str:
        return f"<EvaluationMetric(id={self.id}, type={self.metric_type}, value={self.metric_value})>"
