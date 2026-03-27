"""
Test configuration and fixtures for NotebookLX API tests.
"""
import pytest
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import uuid

# These imports will be created later
# from services.api.core.database import Base, get_db
# from services.api.main import app


# Use in-memory SQLite for tests (faster than PostgreSQL)
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """
    Create a fresh database for each test.
    Uses SQLite in-memory for speed.
    """
    # Import here to avoid circular imports
    from services.api.core.database import Base
    # Import models to register them with Base
    from services.api.modules.notebooks.models import User, Notebook

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create a session
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Drop all tables after test
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db: Session) -> Generator[TestClient, None, None]:
    """
    Create a test client with dependency override for database session.
    """
    from services.api.main import app
    from services.api.core.database import get_db

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def sample_user_id() -> str:
    """Return a sample user ID for testing."""
    return str(uuid.uuid4())


@pytest.fixture
def sample_notebook_data() -> dict:
    """Return sample notebook data for testing."""
    return {
        "name": "Test Notebook",
        "description": "This is a test notebook"
    }


@pytest.fixture
def sample_notebook_data_no_description() -> dict:
    """Return sample notebook data without description."""
    return {
        "name": "Test Notebook Without Description"
    }
