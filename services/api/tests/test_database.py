"""
Tests for database configuration and local SQLite initialization.
"""
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import StaticPool

from services.api.core import database
from services.api.core.database import Base, initialize_database
from services.api.modules.notebooks.models import Notebook, User  # noqa: F401


def test_default_sqlite_database_url_is_absolute():
    """Default SQLite URL should not depend on the current working directory."""
    assert database.DEFAULT_SQLITE_PATH.is_absolute()
    assert database.DEFAULT_SQLITE_PATH.name == "notebooklx.db"
    assert database.DEFAULT_DATABASE_URL == f"sqlite:///{database.DEFAULT_SQLITE_PATH}"


def test_initialize_database_creates_sqlite_tables():
    """Local SQLite initialization should create required tables on a fresh database."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.drop_all(bind=engine)
    assert "users" not in inspect(engine).get_table_names()
    assert "notebooks" not in inspect(engine).get_table_names()

    initialize_database(bind_engine=engine)

    table_names = set(inspect(engine).get_table_names())
    assert {"users", "notebooks"} <= table_names


def test_app_startup_initializes_database(monkeypatch):
    """The FastAPI app should bootstrap local SQLite schema during startup."""
    from services.api import main

    called = False

    def fake_initialize_database(bind_engine=None):
        nonlocal called
        called = True

    monkeypatch.setattr(main, "initialize_database", fake_initialize_database)

    with TestClient(main.app):
        pass

    assert called is True
