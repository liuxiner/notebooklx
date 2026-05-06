# NotebookLX Database Schema

Complete database schema reference for all models in the system.

---

## Core Models

### users
User accounts and authentication.

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE,
    full_name VARCHAR(255),
    hashed_password VARCHAR(255), -- if using local auth
    auth_provider VARCHAR(50), -- 'local', 'google', 'github'
    auth_provider_id VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    is_verified BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_auth_provider ON users(auth_provider, auth_provider_id);
```

---

### notebooks
Primary organizational unit for sources and content.

```sql
CREATE TABLE notebooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    summary TEXT, -- auto-generated summary
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deleted_at TIMESTAMP WITH TIME ZONE -- soft delete
);

CREATE INDEX idx_notebooks_user_id ON notebooks(user_id);
CREATE INDEX idx_notebooks_deleted_at ON notebooks(deleted_at);
CREATE INDEX idx_notebooks_created_at ON notebooks(created_at DESC);
```

---

### sources
Files, URLs, and content added to notebooks.

```sql
CREATE TYPE source_type_enum AS ENUM (
    'pdf',
    'url',
    'text',
    'youtube',
    'audio',
    'gdocs',
    'gslides'
);

CREATE TYPE source_status_enum AS ENUM (
    'pending',
    'processing',
    'ready',
    'failed'
);

CREATE TABLE sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notebook_id UUID NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    source_type source_type_enum NOT NULL,
    title VARCHAR(500) NOT NULL,
    original_url TEXT, -- for URL-based sources
    file_path TEXT, -- storage path for uploaded files
    file_size BIGINT, -- bytes
    mime_type VARCHAR(100),
    status source_status_enum DEFAULT 'pending',
    error_message TEXT,
    summary TEXT, -- source-level summary
    metadata JSONB, -- flexible metadata storage
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_sources_notebook_id ON sources(notebook_id);
CREATE INDEX idx_sources_status ON sources(status);
CREATE INDEX idx_sources_created_at ON sources(created_at DESC);
CREATE INDEX idx_sources_metadata ON sources USING GIN(metadata);
```

---

### source_chunks
Semantically meaningful segments with embeddings.

```sql
CREATE TABLE source_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL, -- order within source
    content TEXT NOT NULL,
    token_count INTEGER,
    embedding VECTOR(1536), -- dimension depends on model (1536 for text-embedding-3-small)
    metadata JSONB, -- {page, heading, char_start, char_end, section}
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_source_chunks_source_id ON source_chunks(source_id);
CREATE INDEX idx_source_chunks_chunk_index ON source_chunks(source_id, chunk_index);
CREATE INDEX idx_source_chunks_metadata ON source_chunks USING GIN(metadata);

-- Vector similarity index (HNSW for better performance)
CREATE INDEX idx_source_chunks_embedding ON source_chunks
USING hnsw (embedding vector_cosine_ops);

-- Alternative: IVFFlat index (faster build, slower query)
-- CREATE INDEX idx_source_chunks_embedding ON source_chunks
-- USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

---

## Chat & Retrieval Models

### messages
Chat conversation history.

```sql
CREATE TYPE message_role_enum AS ENUM ('user', 'assistant', 'system');

CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notebook_id UUID NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    role message_role_enum NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB, -- query rewrite info, retrieval stats, etc.
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_messages_notebook_id ON messages(notebook_id);
CREATE INDEX idx_messages_created_at ON messages(notebook_id, created_at DESC);
```

---

### citations
Links answer segments to source chunks.

```sql
CREATE TABLE citations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    chunk_id UUID NOT NULL REFERENCES source_chunks(id) ON DELETE CASCADE,
    citation_number INTEGER NOT NULL, -- [1], [2], etc.
    quoted_text TEXT, -- exact quote from chunk
    relevance_score FLOAT, -- 0-1 relevance score
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_citations_message_id ON citations(message_id);
CREATE INDEX idx_citations_chunk_id ON citations(chunk_id);
CREATE INDEX idx_citations_source_id ON citations(source_id);
```

---

## Knowledge Models

### notes
User-created notes within notebooks.

```sql
CREATE TABLE notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notebook_id UUID NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    title VARCHAR(500),
    content TEXT NOT NULL,
    is_pinned BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_notes_notebook_id ON notes(notebook_id);
CREATE INDEX idx_notes_is_pinned ON notes(notebook_id, is_pinned);
```

---

### notebook_topics
Auto-extracted key topics from notebook content.

```sql
CREATE TABLE notebook_topics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notebook_id UUID NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    topic VARCHAR(200) NOT NULL,
    importance_score FLOAT, -- 0-1 ranking
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_notebook_topics_notebook_id ON notebook_topics(notebook_id);
CREATE INDEX idx_notebook_topics_importance ON notebook_topics(notebook_id, importance_score DESC);
```

---

### suggested_questions
Auto-generated questions about notebook content.

```sql
CREATE TABLE suggested_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notebook_id UUID NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    relevance_score FLOAT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_suggested_questions_notebook_id ON suggested_questions(notebook_id);
```

---

### source_overlaps
Analysis of topic overlap between sources.

```sql
CREATE TABLE source_overlaps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notebook_id UUID NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    source_id_1 UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    source_id_2 UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    shared_topics JSONB, -- array of overlapping topics
    overlap_score FLOAT, -- 0-1 similarity score
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_source_overlaps_notebook_id ON source_overlaps(notebook_id);
CREATE INDEX idx_source_overlaps_sources ON source_overlaps(source_id_1, source_id_2);
```

---

## Generated Content Models

### generated_assets
Derived content like FAQs, summaries, study guides.

```sql
CREATE TYPE asset_type_enum AS ENUM (
    'briefing_doc',
    'faq',
    'study_guide',
    'timeline',
    'glossary',
    'mind_map',
    'flashcards',
    'quiz',
    'audio_script'
);

CREATE TABLE generated_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notebook_id UUID NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    asset_type asset_type_enum NOT NULL,
    title VARCHAR(500),
    content TEXT NOT NULL,
    content_format VARCHAR(50) DEFAULT 'markdown', -- 'markdown', 'json', 'html'
    metadata JSONB, -- structure depends on asset type
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_generated_assets_notebook_id ON generated_assets(notebook_id);
CREATE INDEX idx_generated_assets_type ON generated_assets(notebook_id, asset_type);
CREATE INDEX idx_generated_assets_version ON generated_assets(notebook_id, asset_type, version DESC);
```

---

## Permissions Models

### notebook_collaborators
Multi-user access control for notebooks.

```sql
CREATE TYPE collaborator_role_enum AS ENUM ('owner', 'editor', 'viewer');

CREATE TABLE notebook_collaborators (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notebook_id UUID NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role collaborator_role_enum NOT NULL,
    invited_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(notebook_id, user_id)
);

CREATE INDEX idx_notebook_collaborators_notebook_id ON notebook_collaborators(notebook_id);
CREATE INDEX idx_notebook_collaborators_user_id ON notebook_collaborators(user_id);
```

---

## Evaluation Models

### evaluation_metrics
Track system performance over time.

```sql
CREATE TYPE metric_type_enum AS ENUM (
    'retrieval_recall_5',
    'retrieval_recall_10',
    'retrieval_mrr',
    'citation_support_rate',
    'citation_wrong_rate',
    'answer_groundedness',
    'answer_completeness',
    'answer_faithfulness'
);

CREATE TABLE evaluation_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notebook_id UUID REFERENCES notebooks(id) ON DELETE SET NULL,
    metric_type metric_type_enum NOT NULL,
    value FLOAT NOT NULL,
    metadata JSONB, -- context about measurement
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_evaluation_metrics_type ON evaluation_metrics(metric_type);
CREATE INDEX idx_evaluation_metrics_created_at ON evaluation_metrics(created_at DESC);
CREATE INDEX idx_evaluation_metrics_notebook ON evaluation_metrics(notebook_id, metric_type);
```

---

### evaluation_datasets
Ground truth Q&A pairs for testing.

```sql
CREATE TABLE evaluation_datasets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notebook_id UUID REFERENCES notebooks(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    expected_answer TEXT,
    ground_truth_chunk_ids UUID[], -- array of chunk IDs
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_evaluation_datasets_notebook_id ON evaluation_datasets(notebook_id);
```

---

## Background Jobs Models

### ingestion_jobs
Track async ingestion tasks.

```sql
CREATE TYPE job_status_enum AS ENUM (
    'queued',
    'running',
    'completed',
    'failed',
    'retrying'
);

CREATE TABLE ingestion_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    status job_status_enum DEFAULT 'queued',
    task_id VARCHAR(255), -- Arq task ID
    progress JSONB, -- {step: 'chunking', chunks_processed: 50, total_chunks: 100}
    retry_count INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_ingestion_jobs_source_id ON ingestion_jobs(source_id);
CREATE INDEX idx_ingestion_jobs_status ON ingestion_jobs(status);
CREATE INDEX idx_ingestion_jobs_task_id ON ingestion_jobs(task_id);
```

---

## Relationships Diagram

```
users (1) ─────< (many) notebooks
                   │
                   ├─< sources
                   │     └─< source_chunks (with embeddings)
                   │
                   ├─< messages
                   │     └─< citations ─> source_chunks
                   │
                   ├─< notes
                   ├─< notebook_topics
                   ├─< suggested_questions
                   ├─< source_overlaps
                   ├─< generated_assets
                   └─< notebook_collaborators ─> users
```

---

## Key Features

### Vector Search
- Uses pgvector extension
- HNSW index for fast similarity search
- Cosine similarity for semantic search
- Scoped to notebook_id for isolation

### Soft Deletes
- Notebooks use `deleted_at` for soft deletion
- Cascade deletes to sources and chunks handled by DB

### JSONB Metadata
- Flexible schema for source metadata
- Fast indexed queries with GIN indexes
- Stores page numbers, headings, timestamps

### Indexing Strategy
- Primary indexes on foreign keys
- Composite indexes for common queries
- GIN indexes for JSONB columns
- Vector indexes for similarity search

### Audit Trail
- `created_at` on all tables
- `updated_at` on mutable tables
- `processed_at` for async workflows

---

## Migration Strategy

Use Alembic for Python/SQLAlchemy migrations:

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Migration Ordering
1. Core tables (users, notebooks)
2. Source tables (sources, source_chunks with vector extension)
3. Chat tables (messages, citations)
4. Knowledge tables (notes, topics, questions)
5. Generated content tables
6. Permission tables
7. Evaluation tables
8. Job tracking tables

---

## Sample Queries

### Find similar chunks (vector search)
```sql
SELECT
    sc.id,
    sc.content,
    s.title as source_title,
    sc.metadata->>'page' as page,
    1 - (sc.embedding <=> $1::vector) as similarity
FROM source_chunks sc
JOIN sources s ON sc.source_id = s.id
WHERE s.notebook_id = $2
ORDER BY sc.embedding <=> $1::vector
LIMIT 10;
```

### Get notebook with stats
```sql
SELECT
    n.*,
    COUNT(DISTINCT s.id) as source_count,
    COUNT(sc.id) as chunk_count,
    COUNT(m.id) as message_count
FROM notebooks n
LEFT JOIN sources s ON n.id = s.notebook_id AND s.status = 'ready'
LEFT JOIN source_chunks sc ON s.id = sc.source_id
LEFT JOIN messages m ON n.id = m.notebook_id
WHERE n.id = $1
GROUP BY n.id;
```

### Recent messages with citations
```sql
SELECT
    m.*,
    json_agg(
        json_build_object(
            'citation_number', c.citation_number,
            'source_title', s.title,
            'quote', c.quoted_text,
            'page', (sc.metadata->>'page')::integer
        )
        ORDER BY c.citation_number
    ) FILTER (WHERE c.id IS NOT NULL) as citations
FROM messages m
LEFT JOIN citations c ON m.id = c.message_id
LEFT JOIN sources s ON c.source_id = s.id
LEFT JOIN source_chunks sc ON c.chunk_id = sc.id
WHERE m.notebook_id = $1
GROUP BY m.id
ORDER BY m.created_at DESC
LIMIT 20;
```

---

## Performance Considerations

### Recommended Indexes
All indexes listed above are recommended for production.

### Query Optimization
- Use `EXPLAIN ANALYZE` for slow queries
- Consider materialized views for complex aggregations
- Partition large tables (e.g., messages) by date if needed

### Scaling Strategy
- Read replicas for query-heavy workloads
- Connection pooling (PgBouncer)
- Vacuum and analyze regularly
- Monitor index usage and bloat

### Vector Search Performance
- HNSW index is faster than IVFFlat for queries
- Consider smaller embedding dimensions if storage is concern
- Benchmark with expected notebook sizes (100-10,000 chunks)

