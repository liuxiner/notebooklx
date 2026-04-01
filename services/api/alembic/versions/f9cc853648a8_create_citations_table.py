"""create_citations_table

Revision ID: f9cc853648a8
Revises: b3f1c2d4e5f6
Create Date: 2026-04-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f9cc853648a8'
down_revision: Union[str, None] = 'b3f1c2d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("citations"):
        op.create_table(
            "citations",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("message_id", sa.String(36), nullable=False),
            sa.Column("chunk_id", sa.String(36), nullable=False),
            sa.Column("citation_index", sa.Integer(), nullable=False),
            sa.Column("quote", sa.Text(), nullable=False),
            sa.Column("score", sa.Float(), nullable=False),
            sa.Column("page", sa.String(50), nullable=True),
            sa.Column("source_title", sa.String(500), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["chunk_id"], ["source_chunks.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    # Create indexes
    citation_indexes = {index["name"] for index in inspector.get_indexes("citations")} if inspector.has_table("citations") else set()
    if op.f("ix_citations_message_id") not in citation_indexes:
        op.create_index(op.f("ix_citations_message_id"), "citations", ["message_id"], unique=False)
    if op.f("ix_citations_chunk_id") not in citation_indexes:
        op.create_index(op.f("ix_citations_chunk_id"), "citations", ["chunk_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_citations_chunk_id"), table_name="citations")
    op.drop_index(op.f("ix_citations_message_id"), table_name="citations")
    op.drop_table("citations")
