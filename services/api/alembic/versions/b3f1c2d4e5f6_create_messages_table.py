"""create messages table

Revision ID: b3f1c2d4e5f6
Revises: a7c9d2e1f4b6
Create Date: 2026-04-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b3f1c2d4e5f6"
down_revision: Union[str, None] = "a7c9d2e1f4b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


MESSAGE_ROLE_ENUM = sa.Enum("user", "assistant", name="messagerole")


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if bind.dialect.name != "sqlite":
        MESSAGE_ROLE_ENUM.create(bind, checkfirst=True)

    if not inspector.has_table("messages"):
        op.create_table(
            "messages",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("notebook_id", sa.String(36), nullable=False),
            sa.Column("role", MESSAGE_ROLE_ENUM, nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["notebook_id"], ["notebooks.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        inspector = sa.inspect(bind)

    message_indexes = {index["name"] for index in inspector.get_indexes("messages")} if inspector.has_table("messages") else set()
    if op.f("ix_messages_notebook_id") not in message_indexes:
        op.create_index(op.f("ix_messages_notebook_id"), "messages", ["notebook_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()

    op.drop_index(op.f("ix_messages_notebook_id"), table_name="messages")
    op.drop_table("messages")

    if bind.dialect.name != "sqlite":
        MESSAGE_ROLE_ENUM.drop(bind, checkfirst=True)
