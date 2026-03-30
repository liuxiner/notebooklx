"""enable pgvector for source_chunks embeddings

Revision ID: a7c9d2e1f4b6
Revises: f1a2b3c4d5e6
Create Date: 2026-03-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from services.api.core.vector import EmbeddingVector


# revision identifiers, used by Alembic.
revision: str = "a7c9d2e1f4b6"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.alter_column(
        "source_chunks",
        "embedding",
        existing_type=sa.JSON(),
        type_=EmbeddingVector(),
        existing_nullable=True,
        postgresql_using="embedding::text::vector",
    )

    # Create HNSW index for fast approximate nearest neighbor search
    # Using cosine distance (vector_cosine_ops) for semantic similarity
    # HNSW parameters: m=16 (connections per layer), ef_construction=64 (build-time quality)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_source_chunks_embedding_hnsw
        ON source_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    # Drop HNSW index first
    op.execute("DROP INDEX IF EXISTS idx_source_chunks_embedding_hnsw")

    op.alter_column(
        "source_chunks",
        "embedding",
        existing_type=EmbeddingVector(),
        type_=sa.JSON(),
        existing_nullable=True,
        postgresql_using="embedding::text::json",
    )
