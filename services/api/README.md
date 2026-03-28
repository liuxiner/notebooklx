# NotebookLX API Service

FastAPI backend service for NotebookLX - a source-grounded notebook knowledge workspace.

## Setup

### 1. Create Virtual Environment

```bash
python3 -m venv ../../venv
source ../../venv/bin/activate
```

### 2. Install Dependencies

```bash
cd ./services/api/
pip install -r requirements.txt
```

### 3. Database Setup

The API uses SQLite by default for development. No additional setup needed.

For production PostgreSQL:
```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/notebooklx"
```

For the async ingestion queue, set Redis as well:
```bash
export REDIS_URL="redis://127.0.0.1:6379/0"
export INGESTION_QUEUE_NAME="notebooklx:ingestion"
```

### 4. Run Database Migrations

```bash
alembic upgrade head
```

## Running the API

### Development Server

Run from the repository root so Python can import the `services` package:

```bash
cd ../..
uvicorn services.api.main:app --reload
```

The API will be available at `http://localhost:8000`

API docs at `http://localhost:8000/docs`

## Running the Worker

Start Redis locally, then run the Arq worker from the repository root:

```bash
redis-server --port 6379
arq services.worker.main.WorkerSettings
```

Use `POST /api/sources/{source_id}/ingest` to enqueue a source, then inspect
`GET /api/sources/{source_id}/status` or `GET /api/status/ingestion` for queue
and job state.

If you prefer Docker for the queue slice, run:

```bash
docker compose up redis worker
```

## Running Tests

### Run All Tests

```bash
cd ../..
PYTHONPATH=$(pwd) pytest services/api/tests/ -v
```

### Run Specific Test File

```bash
cd ../..
PYTHONPATH=$(pwd) pytest services/api/tests/test_notebooks.py -v
```

### Run Tests with Coverage

```bash
cd ../..
PYTHONPATH=$(pwd) pytest services/api/tests/ --cov=services.api --cov-report=html
```

View coverage report:
```bash
open htmlcov/index.html
```

### Run Tests in Watch Mode

```bash
cd ../..
PYTHONPATH=$(pwd) pytest services/api/tests/ -v --looponfail
```

## API Endpoints

### Notebooks

- **POST** `/api/notebooks` - Create a new notebook
- **GET** `/api/notebooks` - List all notebooks
- **GET** `/api/notebooks/{id}` - Get single notebook
- **PATCH** `/api/notebooks/{id}` - Update notebook
- **DELETE** `/api/notebooks/{id}` - Soft delete notebook

### Sources & Ingestion

- **POST** `/api/notebooks/{notebook_id}/sources/upload` - Upload a source file
- **POST** `/api/notebooks/{notebook_id}/sources/url` - Create a URL source
- **POST** `/api/notebooks/{notebook_id}/sources/text` - Create a text source
- **POST** `/api/sources/{source_id}/ingest` - Enqueue background ingestion
- **GET** `/api/sources/{source_id}/status` - Get source ingestion status
- **GET** `/api/status/ingestion` - Get aggregate ingestion queue counts

## Project Structure

```
services/api/
├── core/                 # Core modules (database, config)
│   ├── __init__.py
│   └── database.py      # Database connection and session
├── modules/             # Feature modules
│   └── notebooks/       # Notebook CRUD operations
│       ├── __init__.py
│       ├── models.py    # SQLAlchemy models
│       ├── schemas.py   # Pydantic schemas
│       └── routes.py    # API endpoints
├── tests/               # Test files
│   ├── __init__.py
│   ├── conftest.py      # Test fixtures
│   └── test_notebooks.py # Notebook tests
├── alembic/             # Database migrations
│   └── versions/        # Migration files
├── main.py              # FastAPI app
├── requirements.txt     # Python dependencies
├── pytest.ini           # Pytest configuration
└── alembic.ini          # Alembic configuration
```

## Development Workflow

This project follows Test-Driven Development (TDD):

1. Write tests first based on acceptance criteria
2. Run tests (they should fail - RED)
3. Implement the feature
4. Run tests until they pass - GREEN
5. Refactor if needed (keep tests passing)
6. Check off items in TASK_CHECKLIST.md

## Completed Features

### Phase 1: Foundation

✅ **Feature 1.1: Notebook CRUD API**
- Database schema for notebooks and users
- SQLAlchemy models (User, Notebook)
- Pydantic schemas for validation
- All CRUD endpoints implemented
- 24/24 tests passing
- Alembic migration scripts

## Next Steps

- [ ] Feature 2.1: Document Parsers
- [ ] Feature 2.2: Semantic Chunking
- [ ] Feature 2.3: Embedding Generation

## Environment Variables

```bash
# Database (optional - defaults to SQLite)
DATABASE_URL=sqlite:///./notebooklx.db

# For production PostgreSQL:
# DATABASE_URL=postgresql://user:pass@localhost:5432/notebooklx
```
