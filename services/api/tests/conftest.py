"""
Test configuration and fixtures for NotebookLX API tests.
"""
import pytest
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
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


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
    """Ensure SQLite enforces foreign keys during tests."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


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
    # Import Source model for sources tests
    try:
        from services.api.modules.sources.models import Source  # noqa: F401
    except ImportError:
        pass  # Source module not yet created
    try:
        from services.api.modules.ingestion.models import IngestionJob  # noqa: F401
    except ImportError:
        pass  # Ingestion module not yet created
    try:
        from services.api.modules.chunking.models import SourceChunk  # noqa: F401
    except ImportError:
        pass  # Chunking module not yet created
    try:
        from services.api.modules.snapshots.models import SourceSnapshot  # noqa: F401
    except ImportError:
        pass  # Snapshot module may not exist yet
    try:
        from services.api.modules.chat.models import Message  # noqa: F401
    except ImportError:
        pass  # Chat message storage may not exist yet
    try:
        from services.api.modules.citations.models import Citation  # noqa: F401
    except ImportError:
        pass  # Citation module may not exist yet
    try:
        from services.api.modules.evaluation.models import EvaluationRun, EvaluationMetric  # noqa: F401
    except ImportError:
        pass  # Evaluation module may not exist yet

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


@pytest.fixture
def sample_user(db: Session):
    """Create and return a sample user for testing."""
    from services.api.modules.notebooks.models import User
    user = User(email="test@example.com")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def sample_notebook(db: Session, sample_user):
    """Create and return a sample notebook for testing."""
    from services.api.modules.notebooks.models import Notebook
    notebook = Notebook(
        user_id=sample_user.id,
        name="Test Notebook",
        description="Test description"
    )
    db.add(notebook)
    db.commit()
    db.refresh(notebook)
    return notebook


@pytest.fixture
def sample_source(db: Session, sample_notebook):
    """Create and return a sample source for testing."""
    from services.api.modules.sources.models import Source, SourceType, SourceStatus
    source = Source(
        notebook_id=sample_notebook.id,
        source_type=SourceType.TEXT,
        title="Test Source",
        status=SourceStatus.READY,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source
