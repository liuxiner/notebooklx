"""create source_snapshots table

Revision ID: e2f6a9c1b4d7
Revises: a7c9d2e1f4b6
Create Date: 2026-04-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e2f6a9c1b4d7"
down_revision: Union[str, Sequence[str], None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("source_snapshots"):
        op.create_table(
            "source_snapshots",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("source_id", sa.String(36), nullable=False),
            sa.Column("notebook_id", sa.String(36), nullable=False),
            sa.Column("schema_version", sa.String(length=32), nullable=False),
            sa.Column("source_content_hash", sa.String(length=64), nullable=False),
            sa.Column("generation_method", sa.String(length=32), nullable=False),
            sa.Column("model_name", sa.String(length=128), nullable=True),
            sa.Column("snapshot_data", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["notebook_id"], ["notebooks.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("source_id"),
        )
        inspector = sa.inspect(bind)

    indexes = (
        {index["name"] for index in inspector.get_indexes("source_snapshots")}
        if inspector.has_table("source_snapshots")
        else set()
    )
    if op.f("ix_source_snapshots_source_id") not in indexes:
        op.create_index(
            op.f("ix_source_snapshots_source_id"),
            "source_snapshots",
            ["source_id"],
            unique=True,
        )
    if op.f("ix_source_snapshots_notebook_id") not in indexes:
        op.create_index(
            op.f("ix_source_snapshots_notebook_id"),
            "source_snapshots",
            ["notebook_id"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_source_snapshots_notebook_id"), table_name="source_snapshots")
    op.drop_index(op.f("ix_source_snapshots_source_id"), table_name="source_snapshots")
    op.drop_table("source_snapshots")
