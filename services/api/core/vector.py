"""
Cross-dialect vector column helpers.

SQLite keeps using JSON for local development and tests, while PostgreSQL
uses pgvector's VECTOR type once the extension is installed.
"""
import json
from typing import Iterable, Optional

from sqlalchemy import JSON
from sqlalchemy.types import TypeDecorator, UserDefinedType


def _coerce_embedding_values(value: Iterable[float]) -> list[float]:
    """Normalize any embedding payload into a plain float list."""
    return [float(item) for item in value]


def _serialize_pgvector(value: Iterable[float]) -> str:
    """Serialize a vector into pgvector's text input format."""
    coerced = _coerce_embedding_values(value)
    return "[" + ",".join(format(item, "g") for item in coerced) + "]"


def _deserialize_pgvector(value: object) -> Optional[list[float]]:
    """Deserialize pgvector output into a plain float list."""
    if value is None:
        return None
    if isinstance(value, list):
        return _coerce_embedding_values(value)
    if isinstance(value, tuple):
        return _coerce_embedding_values(value)
    if isinstance(value, bytes):
        value = value.decode()
    if isinstance(value, str):
        return _coerce_embedding_values(json.loads(value))
    raise TypeError(f"Unsupported pgvector payload type: {type(value)!r}")


class SQLiteEmbeddingJSON(JSON):
    """SQLite-local JSON storage for embeddings."""

    @property
    def python_type(self) -> type[list]:
        return list


class PgVector(UserDefinedType):
    """Minimal SQLAlchemy type for pgvector columns."""

    cache_ok = True

    def __init__(self, dimension: int | None = None):
        self.dimension = dimension

    def get_col_spec(self, **_kwargs) -> str:
        if self.dimension is None:
            return "VECTOR"
        return f"VECTOR({self.dimension})"

    @property
    def python_type(self) -> type[list]:
        return list

    def bind_processor(self, _dialect):
        def process(value):
            if value is None:
                return None
            return _serialize_pgvector(value)

        return process

    def result_processor(self, _dialect, _coltype):
        def process(value):
            return _deserialize_pgvector(value)

        return process


class EmbeddingVector(TypeDecorator):
    """Store embeddings as pgvector on PostgreSQL and JSON elsewhere."""

    impl = JSON
    cache_ok = True

    def __init__(self, dimension: int | None = None):
        super().__init__()
        self.dimension = dimension

    @property
    def python_type(self) -> type[list]:
        return list

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PgVector(self.dimension))
        return dialect.type_descriptor(SQLiteEmbeddingJSON())

