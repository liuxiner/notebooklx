"""create_evaluation_tables

Revision ID: c4d5e6f7a8b9
Revises: f9cc853648a8
Create Date: 2026-04-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "f9cc853648a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


EVALUATION_STATUS_ENUM = sa.Enum(
    "pending",
    "running",
    "completed",
    "failed",
    name="evaluationstatus",
)
METRIC_TYPE_ENUM = sa.Enum(
    "recall_at_5",
    "recall_at_10",
    "recall_at_k",
    "mrr",
    "citation_support_rate",
    "wrong_citation_rate",
    "groundedness",
    "completeness",
    "faithfulness",
    name="metrictype",
)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if bind.dialect.name != "sqlite":
        EVALUATION_STATUS_ENUM.create(bind, checkfirst=True)
        METRIC_TYPE_ENUM.create(bind, checkfirst=True)

    if not inspector.has_table("evaluation_runs"):
        op.create_table(
            "evaluation_runs",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("notebook_id", sa.String(36), nullable=False),
            sa.Column("query", sa.Text(), nullable=False),
            sa.Column("ground_truth_chunk_ids", sa.JSON(), nullable=True),
            sa.Column(
                "status",
                EVALUATION_STATUS_ENUM,
                nullable=False,
                server_default="pending",
            ),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["notebook_id"], ["notebooks.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        inspector = sa.inspect(bind)
    else:
        run_columns = {column["name"] for column in inspector.get_columns("evaluation_runs")}
        if "ground_truth_chunk_ids" not in run_columns:
            op.add_column("evaluation_runs", sa.Column("ground_truth_chunk_ids", sa.JSON(), nullable=True))
            inspector = sa.inspect(bind)

    run_indexes = {index["name"] for index in inspector.get_indexes("evaluation_runs")} if inspector.has_table("evaluation_runs") else set()
    if op.f("ix_evaluation_runs_notebook_id") not in run_indexes:
        op.create_index(op.f("ix_evaluation_runs_notebook_id"), "evaluation_runs", ["notebook_id"], unique=False)

    if not inspector.has_table("evaluation_metrics"):
        op.create_table(
            "evaluation_metrics",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("evaluation_run_id", sa.String(36), nullable=False),
            sa.Column("metric_type", METRIC_TYPE_ENUM, nullable=False),
            sa.Column("metric_value", sa.Float(), nullable=False),
            sa.Column("metric_metadata", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["evaluation_run_id"], ["evaluation_runs.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        inspector = sa.inspect(bind)

    metric_indexes = {index["name"] for index in inspector.get_indexes("evaluation_metrics")} if inspector.has_table("evaluation_metrics") else set()
    if op.f("ix_evaluation_metrics_evaluation_run_id") not in metric_indexes:
        op.create_index(
            op.f("ix_evaluation_metrics_evaluation_run_id"),
            "evaluation_metrics",
            ["evaluation_run_id"],
            unique=False,
        )
    if op.f("ix_evaluation_metrics_metric_type") not in metric_indexes:
        op.create_index(
            op.f("ix_evaluation_metrics_metric_type"),
            "evaluation_metrics",
            ["metric_type"],
            unique=False,
        )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()

    op.drop_index(op.f("ix_evaluation_metrics_metric_type"), table_name="evaluation_metrics")
    op.drop_index(op.f("ix_evaluation_metrics_evaluation_run_id"), table_name="evaluation_metrics")
    op.drop_table("evaluation_metrics")
    op.drop_index(op.f("ix_evaluation_runs_notebook_id"), table_name="evaluation_runs")
    op.drop_table("evaluation_runs")

    if bind.dialect.name != "sqlite":
        METRIC_TYPE_ENUM.drop(bind, checkfirst=True)
        EVALUATION_STATUS_ENUM.drop(bind, checkfirst=True)
