# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NotebookLX is a source-grounded notebook knowledge workspace inspired by Google's NotebookLM. The core principles are:

1. **Notebook is a first-class citizen** - The notebook is the primary unit of organization
2. **Sources define the truth boundary** - All knowledge comes from explicitly added sources
3. **Answers must be traceable** - Every response includes citations to source material
4. **Derived content is source-grounded** - Generated assets (FAQs, summaries, etc.) are always tied to sources

## Technology Stack

### Frontend
- **Next.js** - React framework with SSR/SSG
- **React** - UI library
- **Tailwind CSS** - Utility-first CSS
- **shadcn/ui** - Component library
- **SSE / Streaming UI** - For real-time chat responses

### Backend
- **Python + FastAPI** - Main API service
- **Arq** - Asynchronous task queue for ingestion pipeline
- **PostgreSQL** - Primary database
- **pgvector** - Vector similarity search extension
- **Redis** - Task queue and caching
- **MinIO (local) / S3 or OSS (production)** - Object storage for uploaded files

### AI/ML
- Main LLM for Q&A, summarization, and generation
- Embedding model for vector search
- Optional reranker model for result refinement

## Core Data Models

### Notebook
The primary organizational unit. Each notebook contains sources and has its own chat history.

### Source
Files, URLs, or content added to a notebook. Types include:
- PDF documents
- Web URLs
- Plain text
- YouTube videos (via transcripts)
- Audio files (via transcription)
- Google Docs/Slides

### SourceChunk
Semantically meaningful segments of source content with embeddings for retrieval. Includes metadata like page numbers, section titles, and character positions for accurate citations.

### Note
User-created notes within a notebook that can be pinned.

### Message
Chat conversation history with role (user/assistant) and citations.

### Citation
Links answer segments to specific source chunks with quotes and scores.

### GeneratedAsset
Derived content like summaries, FAQs, study guides, timelines, mind maps, flashcards, and audio scripts.

## Repository Structure

```
apps/
  web/                    # Next.js frontend application

services/
  api/                    # FastAPI main service
    modules/
      notebooks/          # Notebook CRUD operations
      sources/            # Source upload and management
      ingestion/          # Document processing pipeline
      retrieval/          # Vector and hybrid search
      chat/               # Grounded Q&A with citations
      citations/          # Citation generation and alignment
      generation/         # Derived content generation
      auth/               # Authentication and authorization
  worker/                 # Background ingestion and generation workers

packages/
  shared/                 # Shared TypeScript/Python types and schemas
  prompts/                # LLM system prompts and templates

infra/
  docker/                 # Docker configurations
  sql/                    # Database migrations and schemas
```

## Development Methodology & Coding Rules

### Python Package Import Rule

The current backend uses absolute imports such as `services.api...`. Run Python entrypoints that rely on those imports from the repository root, or set `PYTHONPATH` to the repository root first. Do not run `uvicorn main:app --reload` from `services/api/` without adjusting `PYTHONPATH`, because Python will not be able to resolve the top-level `services` package.

### Test-Driven Development (TDD) Workflow

When implementing features from `DEVELOPMENT_PLAN.md`, follow this strict test-first approach:

1. **Read Acceptance Criteria**
   - Open `DEVELOPMENT_PLAN.md` and locate the feature you're implementing
   - Review all acceptance criteria for that feature
   - Understand what "done" means before writing any code

2. **Write Tests First**
   - Write tests for EACH acceptance criterion BEFORE implementing the feature
   - Tests should fail initially (red phase)
   - Cover both happy paths and error cases
   - Backend: Use pytest with fixtures
   - Frontend: Use Jest/Vitest with React Testing Library
   - Integration: Use pytest with test database

3. **Implement the Feature**
   - Write the minimum code needed to pass the tests
   - Follow SOLID principles and keep it simple
   - Don't over-engineer or add features not in the acceptance criteria

4. **Run Tests & Fix Loop**
   ```bash
   # Run from the repository root so `services.*` imports resolve

   # Backend tests
   PYTHONPATH=$(pwd) pytest services/api/tests/ -v

   # Frontend tests
   npm test --prefix apps/web

   # Run until ALL tests pass
   ```
   - If tests fail: debug, fix, and re-run
   - Loop until all acceptance criteria tests pass (green phase)
   - Don't proceed to the next feature until current feature is fully green

5. **Check Off Progress**
   - Open `TASK_CHECKLIST.md`
   - Mark completed items with ✓
   - Update current sprint section
   - Document any blockers or learnings in Notes section

6. **Refactor (Optional)**
   - Once tests pass, refactor for clarity/performance
   - Re-run tests after each refactor to ensure nothing breaks
   - Keep tests passing (stay green)

### Example TDD Flow

```bash
# Feature: Notebook CRUD API (Phase 1)

# Step 1: Write tests based on acceptance criteria
# File: services/api/tests/test_notebooks.py
def test_create_notebook_with_name():
    """AC: Create notebook with name and optional description"""
    response = client.post("/api/notebooks", json={"name": "My Notebook"})
    assert response.status_code == 201
    assert response.json()["name"] == "My Notebook"

def test_list_notebooks_for_user():
    """AC: List all notebooks for authenticated user"""
    # ... test implementation

# Step 2: Run tests (should fail - RED)
PYTHONPATH=$(pwd) pytest services/api/tests/test_notebooks.py -v
# ❌ FAILED - endpoint doesn't exist yet

# Step 3: Implement minimal code
# File: services/api/modules/notebooks/routes.py
@router.post("/notebooks", status_code=201)
async def create_notebook(data: NotebookCreate):
    # ... implementation

# Step 4: Run tests again
PYTHONPATH=$(pwd) pytest services/api/tests/test_notebooks.py -v
# ✅ PASSED - all acceptance criteria met

# Step 5: Check off in TASK_CHECKLIST.md
# - ✓ API endpoints (POST, GET, PATCH, DELETE)
```

### Code Quality Rules

1. **No Code Without Tests**
   - Every API endpoint must have tests
   - Every component must have tests
   - Every critical business logic function must have tests
   - Target: >70% test coverage

2. **Acceptance Criteria = Definition of Done**
   - A feature is NOT complete until all acceptance criteria have passing tests
   - Don't add extra features beyond acceptance criteria
   - Don't skip acceptance criteria tests

3. **Integration Testing Required**
   - Test full user flows (upload → ingestion → retrieval → chat)
   - Test error scenarios (failed uploads, API timeouts, invalid inputs)
   - Use test fixtures for consistent test data

4. **Database Testing**
   - Use pytest fixtures with test database
   - Roll back transactions after each test
   - Never test against production data

5. **Track Progress Religiously**
   - Update `TASK_CHECKLIST.md` after each completed item
   - Use ✓ for complete, ⚡ for in progress, ⬜ for not started
   - Update success metrics weekly

### Testing Standards

#### Backend (pytest)
```python
# File: services/api/tests/conftest.py
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client():
    """Test client with clean database"""
    # Setup test database
    # Return test client
    # Teardown after test

@pytest.fixture
def sample_notebook():
    """Fixture for test notebook data"""
    return {"name": "Test Notebook", "description": "Test"}
```

#### Frontend (Jest/Vitest)
```typescript
// File: apps/web/__tests__/notebooks.test.tsx
import { render, screen } from '@testing-library/react'
import { NotebookList } from '@/components/NotebookList'

describe('NotebookList', () => {
  it('displays notebooks from API', async () => {
    // Arrange: mock API response
    // Act: render component
    // Assert: check rendered output
  })
})
```

#### Integration Tests
```python
# File: services/api/tests/integration/test_ingestion_flow.py
def test_complete_ingestion_pipeline():
    """AC: Upload triggers async ingestion task"""
    # 1. Upload PDF
    # 2. Wait for processing
    # 3. Verify chunks created
    # 4. Verify embeddings stored
    # 5. Verify source status = ready
```

### Commit & PR Guidelines

1. **Commit After Green Tests**
   - Only commit when tests pass
   - Commit message format: `feat: [Feature Name] - [What was implemented]`
   - Example: `feat: Notebook CRUD - Implemented POST /api/notebooks endpoint`

2. **Pull Request Requirements**
   - All acceptance criteria tests must pass
   - Coverage must not decrease
   - Update TASK_CHECKLIST.md in same PR
   - Include test results in PR description

3. **CI/CD Pipeline**
   - All tests run automatically on PR
   - PR cannot merge if tests fail
   - Coverage report generated

## Development Workflow

### Phase 1: Foundation (Week 1)
- Notebook CRUD API and UI
- Source upload endpoints
- Async ingestion pipeline skeleton

### Phase 2: Ingestion (Week 2)
- PDF/URL/text parsers
- Semantic chunking (300-800 tokens with 50-120 token overlap)
- Embedding generation
- Vector indexing
- Source status workflow (pending → processing → ready → failed)

### Phase 3: Retrieval & Chat (Week 3)
- Notebook-scoped retrieval (hybrid BM25 + vector)
- Grounded Q&A with evidence packing
- Citation UI with inline references
- Two-layer citation system:
  1. Retrieval evidence layer (candidate chunks)
  2. Answer binding layer (aligning sentences to chunks)

### Phase 4: Auto-generated Content (Week 4)
- Notebook summary on source completion
- Key topics extraction (5-10 topics)
- Suggested questions (5 questions)
- Source overlap analysis

### Phase 5: Derived Outputs (Week 5)
Priority order:
1. Briefing doc
2. FAQ
3. Study guide
4. Timeline
5. Glossary

Later: Mind maps, flashcards, quizzes, audio scripts

### Phase 6: Refinement (Week 6)
- Reranking for improved relevance
- Query rewriting
- Evaluation dashboard
- Retry mechanisms
- Basic permissions

## Ingestion Pipeline

Standard flow for all source types:
```
Upload source
→ Save original file/link
→ Extract text
→ Clean and normalize
→ Chunk by semantics/paragraphs (preserve headings, page numbers)
→ Generate embeddings
→ Write to vector index
→ Generate source-level summary
→ Mark as ready
```

### Chunking Strategy
- Prioritize natural boundaries (headings, paragraphs)
- Target 300-800 tokens per chunk
- 50-120 token overlap between chunks
- Preserve metadata: page numbers, heading hierarchy, source title, chunk index

## Chat & Retrieval Flow

```
User question
→ (Optional) Query rewrite
→ Retrieve within current notebook scope only
→ Hybrid retrieval (BM25 + vector similarity)
→ Rerank results
→ Assemble evidence pack
→ LLM generates answer with structured citations
→ Insert citation markers [1][2]
→ Return answer + citation cards with quotes
```

**Critical**: Retrieval is always scoped to the current notebook. Cross-notebook search is a v2 feature.

## Citation System

Citations must be a product feature, not just LLM output.

### Evidence Layer
Before generation, identify candidate evidence chunks with:
- chunkId, sourceId, sourceTitle
- content, page, score

### Binding Layer
Use structured LLM output:
```json
{
  "answer_blocks": [
    {
      "text": "Risk statement here.",
      "citation_chunk_ids": ["chk_8", "chk_11"]
    }
  ]
}
```

Backend maps chunk IDs to UI citation markers `[1][2]`.

## Evaluation Strategy

### 1. Retrieval Metrics
- recall@5, recall@10
- Mean Reciprocal Rank (MRR)

### 2. Citation Quality
- Support rate (citation actually supports statement)
- Wrong citation rate

### 3. Answer Quality
- Groundedness (answer stays within sources)
- Completeness
- Conciseness
- Faithfulness

**Always test retrieval before generation.** Most hallucinations come from poor retrieval, not the LLM.

## Privacy & Permissions

### Access Control
- Notebook owner
- Notebook collaborators (editor/viewer roles)
- Source visibility inherits from notebook

### Data Principles
- Sources are private by default
- Content only used for notebook-scoped retrieval and generation
- Never used for model training
- Clear deletion policy

## Key UI Pages

### Notebook List
- Create new notebook
- Recent notebooks

### Notebook Detail (3-panel layout)
- **Left**: Source list with status and summaries
- **Center**: Notebook overview, key topics, suggested questions, pinned notes
- **Right**: Chat panel with citations

### Source Detail
- Source summary
- Original text preview
- Chunk list

### Generated Assets
- FAQ, briefing docs, glossaries, timelines
- Later: mind maps, flashcards, quizzes, audio overviews

## Priority Rules

Development priority:
1. Notebook abstraction
2. Ingestion quality
3. Retrieval + Citations
4. Chat
5. Derived content
6. Advanced multimodal features

**Never** start with fancy features. Build the source-grounding foundation first.

---

## Technical Requirements & Standards

### Database Design
- Use **UUID** for all primary keys
- **Soft delete** for notebooks (deleted_at timestamp)
- **Cascade deletes** for sources and chunks (ON DELETE CASCADE)
- All tables include `created_at` and `updated_at` timestamps
- Use **JSONB** for flexible metadata storage
- Index all foreign keys and common query patterns
- Use **pgvector** extension for embeddings (vector(1536) for text-embedding-3-small)
- Create **HNSW indexes** on embedding columns for performance

### API Standards
- REST conventions: POST (create), GET (read), PATCH (update), DELETE (delete)
- Return proper HTTP status codes:
  - 200 OK (successful read/update)
  - 201 Created (successful create)
  - 204 No Content (successful delete)
  - 400 Bad Request (validation error)
  - 401 Unauthorized (missing/invalid auth)
  - 403 Forbidden (insufficient permissions)
  - 404 Not Found (resource doesn't exist)
  - 500 Internal Server Error (unexpected error)
- Use **Pydantic** schemas for request/response validation
- Return timestamps in **ISO 8601** format with timezone
- Support **pagination** with limit/offset parameters (default: limit=20, max=100)
- Implement **SSE (Server-Sent Events)** for streaming chat responses

### File Upload Constraints
- **PDF**: Max 50MB
- **Text**: Max 10MB
- **Total per user**: 100MB per hour (rate limit)
- Validate MIME types: `application/pdf`, `text/plain`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- Store original files in MinIO (local) or S3/OSS (production)
- Generate unique file paths: `{notebook_id}/{source_id}/{filename}`

### Chunking Requirements
- **Target size**: 300-800 tokens per chunk
- **Overlap**: 50-120 tokens between consecutive chunks
- **Boundaries**: Respect paragraph and heading breaks
- **Metadata preservation**:
  - Page numbers (for PDFs)
  - Heading hierarchy (H1, H2, H3)
  - Character positions (char_start, char_end)
  - Source title and chunk index
- **Tokenizer**: Use tiktoken for OpenAI models

### Embedding Generation
- **Model**: text-embedding-3-small (1536 dimensions) or equivalent
- **Batch size**: 32-100 chunks per API call
- **Rate limiting**: Implement exponential backoff
- **Cost tracking**: Log token usage for monitoring
- **Storage**: Use pgvector with cosine similarity
- **Normalization**: Embeddings should be normalized for cosine distance

### Vector Search
- **Algorithm**: Hybrid retrieval (BM25 + vector similarity + RRF fusion)
- **Scope**: Always filter by notebook_id (no cross-notebook search)
- **Top-K**: Retrieve 10-20 candidates before reranking
- **Index**: HNSW for query performance (<200ms target)
- **Distance metric**: Cosine similarity (1 - cosine_distance)

---

## Quality Metrics & Performance Targets

### Technical Performance
| Metric | Target | Critical |
|--------|--------|----------|
| Ingestion success rate | >95% | Yes |
| Retrieval latency | <300ms | Yes |
| Chat first token | <2s | Yes |
| API uptime | >99.5% | Yes |
| Test coverage | >70% | No |

### Retrieval Quality
| Metric | Target | Measurement |
|--------|--------|-------------|
| Recall@10 | >90% | % of relevant chunks in top 10 |
| MRR (Mean Reciprocal Rank) | >0.8 | Position of first relevant result |
| Citation support rate | >95% | % of citations that support claim |
| Wrong citation rate | <5% | % of citations that don't support claim |

### Answer Quality
| Metric | Target | Definition |
|--------|--------|------------|
| Groundedness | >90% | Answer only uses source content |
| Completeness | >85% | Answer addresses full question |
| Faithfulness | >95% | No contradictions with sources |

### User Experience
| Metric | Target | Notes |
|--------|--------|-------|
| Time to first answer | <2 min | From upload to ready status |
| Sources per notebook | 3-5 avg | Typical user behavior |
| Questions per session | 5-10 avg | Engagement metric |
| Week 2 retention | >60% | User comes back after 1 week |

---

## Development Guidelines

### Code Organization
```
services/api/modules/
  ├── notebooks/       # CRUD for notebooks
  ├── sources/         # Upload and management
  ├── ingestion/       # Document processing
  │   ├── parsers/     # PDF, URL, text extractors
  │   ├── chunking/    # Semantic chunking logic
  │   └── embeddings/  # Embedding generation
  ├── retrieval/       # Hybrid search (BM25 + vector)
  ├── chat/            # Q&A with evidence packing
  ├── citations/       # Two-layer citation system
  ├── generation/      # Derived content (FAQ, summaries)
  └── auth/            # Authentication & permissions
```

### Testing Requirements
- **Unit tests**: pytest for backend, Jest/Vitest for frontend
- **Coverage target**: >70% for core modules (ingestion, retrieval, chat)
- **Integration tests**: Full ingestion pipeline, end-to-end chat flow
- **E2E tests**: Critical user journeys (Playwright)
- **Test data**: Maintain test document corpus (PDF, URL, text samples)
- **Evaluation dataset**: 20-50 ground-truth Q&A pairs for retrieval metrics

### Error Handling
- All API endpoints must handle errors gracefully
- Use structured error responses:
  ```json
  {
    "error": "error_code",
    "message": "Human-readable message",
    "details": {...}
  }
  ```
- Log errors with context (request_id, user_id, notebook_id)
- Implement retry logic for:
  - LLM API calls (3 retries with exponential backoff)
  - Embedding API calls (3 retries)
  - Ingestion tasks (3 retries, then mark failed)

### Security & Privacy
- **Authentication**: JWT tokens with expiration
- **Authorization**: Check notebook ownership/collaboration on all endpoints
- **Data isolation**: Notebook-scoped queries (always filter by notebook_id)
- **File storage**: Private buckets with signed URLs for access
- **Secrets**: Use environment variables, never commit to git
- **Rate limiting**: 1000 requests/hour per user, 60 requests/minute for chat

### Logging & Monitoring
- **Structured logging**: Use structlog (Python) or winston (Node.js)
- **Log levels**: DEBUG (dev), INFO (important events), WARNING (recoverable issues), ERROR (failures)
- **Metrics to track**:
  - Ingestion job duration and success rate
  - Retrieval latency (p50, p95, p99)
  - LLM API latency and costs
  - Embedding API costs
  - Database query performance
- **Alerting**: Set up alerts for:
  - Ingestion failure rate >10%
  - API error rate >1%
  - Database connection failures
  - Disk space <20%

---

## Risk Management

### High-Risk Areas
1. **Embedding costs**: LLM API usage can scale quickly
   - **Mitigation**: Implement per-user quotas, cache embeddings, monitor costs daily

2. **Chunking quality**: Poor chunking causes bad retrieval
   - **Mitigation**: Test with diverse document types (academic papers, blogs, transcripts), measure recall@10

3. **Citation accuracy**: Incorrect citations erode trust
   - **Mitigation**: Two-layer citation system, validation layer, user feedback mechanism

4. **Performance at scale**: Large notebooks (1000+ chunks) may be slow
   - **Mitigation**: HNSW indexing, query optimization, consider read replicas

### Testing Strategy
- **Test retrieval BEFORE generation**: Most hallucinations stem from poor retrieval
- **Build evaluation dataset early**: Ground-truth Q&A pairs for measuring quality
- **Monitor metrics continuously**: Track recall@10, citation support rate, answer groundedness
- **User feedback loop**: Allow users to report incorrect answers/citations

---

## Quick Reference

### Ingestion Status Workflow
```
pending → processing → ready
                   ↓
                 failed (with error_message)
```

### Citation System Architecture
```
1. Evidence Layer (Retrieval)
   - Retrieve top-K chunks
   - Score and rank candidates

2. Binding Layer (Generation)
   - LLM generates answer blocks
   - Each block links to chunk IDs
   - Backend maps to citation markers [1][2]
```

### TDD Workflow (Per Feature)
```
1. Read acceptance criteria from DEVELOPMENT_PLAN.md
2. Write tests for each criterion (tests should fail)
3. Implement feature code
4. Run tests: pytest / npm test
5. Fix until all tests pass ✅
6. Check off in TASK_CHECKLIST.md with ✓
7. Refactor if needed (keep tests green)
8. Commit only when green

🔁 LOOP on step 4-5 until all acceptance criteria pass
❌ NEVER proceed to next feature with failing tests
```

### Environment Variables (Required)
```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/notebooklx

# Redis
REDIS_URL=redis://localhost:6379

# Object Storage
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# LLM API
OPENAI_API_KEY=sk-...
EMBEDDING_MODEL=text-embedding-3-small
CHAT_MODEL=gpt-4o-mini

# Auth
JWT_SECRET=random-secret-key
JWT_EXPIRATION=86400  # 24 hours
```

### Common Commands
```bash
# Run these from the repository root unless noted otherwise

# Database migrations
alembic upgrade head

# Run API server
uvicorn services.api.main:app --reload

# Run worker
arq services.worker.main.WorkerSettings

# Run tests (run these frequently!)
PYTHONPATH=$(pwd) pytest services/api/tests/ -v                    # All backend tests
PYTHONPATH=$(pwd) pytest services/api/tests/test_notebooks.py -v   # Specific module
PYTHONPATH=$(pwd) pytest services/api/tests/ --cov                 # With coverage
npm test --prefix apps/web                       # All frontend tests
npm test --prefix apps/web -- NotebookList       # Specific component

# Run tests in watch mode (during development)
PYTHONPATH=$(pwd) pytest services/api/tests/ -v --looponfail       # Auto-rerun on save
npm test --prefix apps/web -- --watch            # Auto-rerun on save

# Integration tests
PYTHONPATH=$(pwd) pytest services/api/tests/integration/ -v

# Check test coverage
PYTHONPATH=$(pwd) pytest services/api/tests/ --cov=services.api --cov-report=html
open htmlcov/index.html                          # View coverage report
```

### Progress Tracking
```bash
# Update TASK_CHECKLIST.md after completing each item
# - ⬜ Not started
# - ⚡ In progress
# - ✓ Complete (only mark when tests pass!)

# Example workflow:
# 1. Start feature: Change ⬜ to ⚡ in TASK_CHECKLIST.md
# 2. Write tests + implement + fix until green
# 3. All tests pass: Change ⚡ to ✓ in TASK_CHECKLIST.md
# 4. Commit with message: "feat: [Feature] - [Description]"
```

---

## Development Philosophy: The NotebookLX Way

### Core Beliefs

1. **Tests Define Truth**
   - Acceptance criteria in DEVELOPMENT_PLAN.md are the contract
   - Tests are written BEFORE code, not after
   - A feature without tests is not a feature, it's a liability
   - Green tests = feature complete, red tests = keep working

2. **Fail Fast, Fix Fast**
   - Run tests after every small change
   - Don't accumulate broken code
   - Fix failing tests immediately, don't pile up more changes
   - The test-fix loop is your heartbeat

3. **Progress Is Visible**
   - TASK_CHECKLIST.md is the single source of truth for what's done
   - ✓ means "tests pass and feature works", not "code exists"
   - Update the checklist in the same commit as the passing tests
   - The team (and future you) should always know what's working

4. **Quality Over Speed**
   - It's better to have 3 features with 100% passing tests than 10 features with 50% passing tests
   - Broken code that "mostly works" is more expensive than no code
   - Skipping tests to "go faster" always slows you down later
   - The retrieval system is the foundation - if it's broken, everything else is broken too

5. **Simplicity Wins**
   - Implement what's in the acceptance criteria, nothing more
   - Resist the urge to add "just one more feature"
   - Simple code with tests beats clever code without tests
   - You can always add more later (when you have tests for it)

### Red Flags to Avoid

❌ "I'll add tests later" → No. Tests first, always.
❌ "The tests are flaky" → Fix the tests, don't disable them.
❌ "It works on my machine" → If tests don't pass in CI, it doesn't work.
❌ "I'm 90% done" → You're either done (tests pass) or not done (tests fail).
❌ "Just one more feature before tests" → You're building a house of cards.

### Green Lights to Follow

✅ "All acceptance criteria have tests" → Good start.
✅ "Tests fail before implementation" → You're on the right track.
✅ "Refactored and tests still pass" → Beautiful.
✅ "Checked off in TASK_CHECKLIST.md" → Ship it.
✅ "Added integration test for the full flow" → Chef's kiss.

---

## References

- **Full Development Plan**: See `DEVELOPMENT_PLAN.md` for detailed features and tasks
- **Task Checklist**: See `TASK_CHECKLIST.md` for sprint planning
- **Database Schema**: See `DATABASE_SCHEMA.md` for complete data model
- **API Specification**: See `API_REFERENCE.md` for endpoint documentation
