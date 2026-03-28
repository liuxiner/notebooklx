"""create source_chunks table

Revision ID: c9e4f7a2b3d1
Revises: 8f8cbaf3c9c4
Create Date: 2026-03-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9e4f7a2b3d1'
down_revision: Union[str, None] = '8f8cbaf3c9c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'source_chunks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('source_id', sa.String(36), sa.ForeignKey('sources.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('token_count', sa.Integer(), nullable=False),
        sa.Column('char_start', sa.Integer(), nullable=False),
        sa.Column('char_end', sa.Integer(), nullable=False),
        sa.Column('chunk_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    # Create index for efficient source-based queries
    op.create_index('ix_source_chunks_source_index', 'source_chunks', ['source_id', 'chunk_index'])


def downgrade() -> None:
    op.drop_index('ix_source_chunks_source_index', table_name='source_chunks')
    op.drop_table('source_chunks')
