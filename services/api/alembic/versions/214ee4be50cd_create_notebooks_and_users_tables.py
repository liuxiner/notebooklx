"""Create notebooks and users tables

Revision ID: 214ee4be50cd
Revises: 
Create Date: 2026-03-27 10:48:34.276311

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '214ee4be50cd'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("email"),
        )
        inspector = sa.inspect(bind)

    if not inspector.has_table("notebooks"):
        op.create_table(
            "notebooks",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        inspector = sa.inspect(bind)

    notebook_indexes = {index["name"] for index in inspector.get_indexes("notebooks")} if inspector.has_table("notebooks") else set()
    if op.f("ix_notebooks_user_id") not in notebook_indexes:
        op.create_index(op.f("ix_notebooks_user_id"), "notebooks", ["user_id"], unique=False)
    if op.f("ix_notebooks_deleted_at") not in notebook_indexes:
        op.create_index(op.f("ix_notebooks_deleted_at"), "notebooks", ["deleted_at"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index(op.f('ix_notebooks_deleted_at'), table_name='notebooks')
    op.drop_index(op.f('ix_notebooks_user_id'), table_name='notebooks')

    # Drop tables in reverse order (notebooks first due to foreign key)
    op.drop_table('notebooks')
    op.drop_table('users')
