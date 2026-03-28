"""
Database connection and session management.
"""
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
import os
from pathlib import Path

# Default SQLite database location is anchored at the repository root so it is
# stable regardless of the current working directory.
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SQLITE_PATH = REPO_ROOT / "notebooklx.db"
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_SQLITE_PATH}"

# Database URL from environment variable
# Default to SQLite for development/testing if not specified
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

# Create SQLAlchemy engine
if DATABASE_URL.startswith("sqlite"):
    # SQLite-specific configuration
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}  # Needed for SQLite
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
        """Keep SQLite foreign key constraints enabled across all connections."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    # PostgreSQL or other databases
    engine = create_engine(DATABASE_URL)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for declarative models
Base = declarative_base()


def initialize_database(bind_engine: Engine | None = None) -> None:
    """
    Ensure the local SQLite schema exists for development and tests.

    PostgreSQL and other non-SQLite environments should still use Alembic
    migrations as the source of truth.
    """
    active_engine = bind_engine or engine

    if active_engine.dialect.name != "sqlite":
        return

    # Import models here so their tables are registered on Base.metadata before
    # create_all runs.
    from services.api.modules.notebooks.models import Notebook, User  # noqa: F401
    from services.api.modules.sources.models import Source  # noqa: F401
    from services.api.modules.ingestion.models import IngestionJob  # noqa: F401
    from services.api.modules.chunking.models import SourceChunk  # noqa: F401

    Base.metadata.create_all(bind=active_engine)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get database session.
    Yields a database session and ensures it's closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
