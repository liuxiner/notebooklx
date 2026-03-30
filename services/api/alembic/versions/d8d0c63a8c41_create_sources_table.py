"""Create sources table

Revision ID: d8d0c63a8c41
Revises: 214ee4be50cd
Create Date: 2026-03-28 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d8d0c63a8c41"
down_revision: Union[str, Sequence[str], None] = "214ee4be50cd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SOURCE_TYPE_ENUM = sa.Enum(
    "pdf",
    "url",
    "text",
    "youtube",
    "audio",
    "gdocs",
    name="sourcetype",
)
SOURCE_STATUS_ENUM = sa.Enum(
    "pending",
    "processing",
    "ready",
    "failed",
    name="sourcestatus",
)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if bind.dialect.name != "sqlite":
        SOURCE_TYPE_ENUM.create(bind, checkfirst=True)
        SOURCE_STATUS_ENUM.create(bind, checkfirst=True)

    if not inspector.has_table("sources"):
        op.create_table(
            "sources",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("notebook_id", sa.String(36), nullable=False),
            sa.Column("source_type", SOURCE_TYPE_ENUM, nullable=False),
            sa.Column("title", sa.String(length=512), nullable=False),
            sa.Column("original_url", sa.String(length=2048), nullable=True),
            sa.Column("file_path", sa.String(length=1024), nullable=True),
            sa.Column("file_size", sa.Integer(), nullable=True),
            sa.Column(
                "status",
                SOURCE_STATUS_ENUM,
                nullable=False,
                server_default="pending",
            ),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["notebook_id"], ["notebooks.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        inspector = sa.inspect(bind)

    source_indexes = {index["name"] for index in inspector.get_indexes("sources")} if inspector.has_table("sources") else set()
    if op.f("ix_sources_notebook_id") not in source_indexes:
        op.create_index(op.f("ix_sources_notebook_id"), "sources", ["notebook_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()

    op.drop_index(op.f("ix_sources_notebook_id"), table_name="sources")
    op.drop_table("sources")

    if bind.dialect.name != "sqlite":
        SOURCE_STATUS_ENUM.drop(bind, checkfirst=True)
        SOURCE_TYPE_ENUM.drop(bind, checkfirst=True)
