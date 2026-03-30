"""add embedding column to source_chunks

Revision ID: f1a2b3c4d5e6
Revises: c9e4f7a2b3d1
Create Date: 2026-03-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "c9e4f7a2b3d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("source_chunks"):
        return

    columns = {column["name"] for column in inspector.get_columns("source_chunks")}
    if "embedding" not in columns:
        op.add_column("source_chunks", sa.Column("embedding", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("source_chunks", "embedding")
