"""Create ingestion jobs table

Revision ID: 8f8cbaf3c9c4
Revises: d8d0c63a8c41
Create Date: 2026-03-28 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8f8cbaf3c9c4"
down_revision: Union[str, Sequence[str], None] = "d8d0c63a8c41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


JOB_STATUS_ENUM = sa.Enum(
    "queued",
    "running",
    "completed",
    "failed",
    "retrying",
    name="ingestionjobstatus",
)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        JOB_STATUS_ENUM.create(bind, checkfirst=True)

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("source_id", sa.String(36), nullable=False),
        sa.Column(
            "status",
            JOB_STATUS_ENUM,
            nullable=False,
            server_default="queued",
        ),
        sa.Column("task_id", sa.String(length=255), nullable=True),
        sa.Column("progress", sa.JSON(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ingestion_jobs_source_id"), "ingestion_jobs", ["source_id"], unique=False)
    op.create_index(op.f("ix_ingestion_jobs_task_id"), "ingestion_jobs", ["task_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()

    op.drop_index(op.f("ix_ingestion_jobs_task_id"), table_name="ingestion_jobs")
    op.drop_index(op.f("ix_ingestion_jobs_source_id"), table_name="ingestion_jobs")
    op.drop_table("ingestion_jobs")

    if bind.dialect.name != "sqlite":
        JOB_STATUS_ENUM.drop(bind, checkfirst=True)
