"""
Regression tests for Alembic migration compatibility.
"""
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from services.api.core.database import Base
from services.api.modules.chunking.models import SourceChunk  # noqa: F401
from services.api.modules.ingestion.models import IngestionJob  # noqa: F401
from services.api.modules.notebooks.models import Notebook, User  # noqa: F401
from services.api.modules.sources.models import Source  # noqa: F401


def test_upgrade_head_skips_existing_sqlite_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Alembic upgrade should work when SQLite was already initialized via create_all.

    This matches the local development bootstrap path where the app can create
    the schema before migrations are run.
    """
    database_url = f"sqlite:///{(tmp_path / 'bootstrapped.db').as_posix()}"
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)

    monkeypatch.setenv("DATABASE_URL", database_url)

    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "head")

    head_revision = ScriptDirectory.from_config(config).get_current_head()

    with engine.connect() as connection:
        tables = {
            row[0]
            for row in connection.execute(
                text("select name from sqlite_master where type='table' order by name")
            )
        }
        assert {"users", "notebooks", "sources", "ingestion_jobs", "source_chunks", "alembic_version"} <= tables
        assert connection.execute(text("select version_num from alembic_version")).scalar_one() == head_revision

