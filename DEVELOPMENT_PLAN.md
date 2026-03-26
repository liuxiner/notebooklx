# NotebookLX Development Plan

This document outlines the detailed development plan, acceptance criteria, and tasks for building NotebookLX.

---

## Phase 1: Foundation (Week 1)

### Feature 1.1: Notebook CRUD API

**Acceptance Criteria:**
- [ ] Create notebook with name and optional description
- [ ] List all notebooks for authenticated user
- [ ] Get single notebook by ID with all metadata
- [ ] Update notebook name and description
- [ ] Delete notebook (soft delete with cascade to sources)
- [ ] All endpoints return proper HTTP status codes (200, 201, 404, 400, 500)
- [ ] API responses include creation/update timestamps
- [ ] Proper error handling with meaningful error messages

**Tasks:**
1. Create database schema for notebooks table
   - id (UUID, primary key)
   - user_id (foreign key)
   - name (string, required)
   - description (text, optional)
   - created_at, updated_at timestamps
   - deleted_at (for soft delete)
2. Create SQLAlchemy model for Notebook
3. Implement POST /api/notebooks endpoint
4. Implement GET /api/notebooks endpoint (list)
5. Implement GET /api/notebooks/{id} endpoint
6. Implement PATCH /api/notebooks/{id} endpoint
7. Implement DELETE /api/notebooks/{id} endpoint
8. Add input validation with Pydantic schemas
9. Write unit tests for all endpoints
10. Add database migration script

---

### Feature 1.2: Notebook UI (Frontend)

**Acceptance Criteria:**
- [ ] Notebook list page shows all user notebooks
- [ ] Create notebook button opens modal/form
- [ ] Can create notebook with name (required) and description (optional)
- [ ] Notebook cards show name, description preview, and created date
- [ ] Click notebook card navigates to notebook detail page
- [ ] Edit/delete actions available on notebook cards
- [ ] Loading states while fetching notebooks
- [ ] Empty state when no notebooks exist
- [ ] Responsive design works on mobile and desktop

**Tasks:**
1. Create notebooks list page component (apps/web/app/notebooks/page.tsx)
2. Create notebook card component
3. Create notebook creation modal/form component
4. Implement create notebook API call using fetch/axios
5. Implement list notebooks API call
6. Add loading spinner component
7. Add empty state component
8. Implement delete confirmation dialog
9. Add error toast notifications
10. Style with Tailwind CSS
11. Add responsive grid layout
12. Implement navigation to notebook detail page

---

### Feature 1.3: Source Upload Endpoints

**Acceptance Criteria:**
- [ ] Upload PDF file (max 50MB)
- [ ] Upload plain text content
- [ ] Add URL source (validate URL format)
- [ ] Return source ID and initial status (pending)
- [ ] Store original file in MinIO/S3
- [ ] Support multiple file types (PDF, TXT, DOCX)
- [ ] Proper MIME type validation
- [ ] File size limits enforced
- [ ] Error handling for failed uploads

**Tasks:**
1. Create sources table schema
   - id (UUID)
   - notebook_id (foreign key)
   - source_type (enum: pdf, url, text, youtube, audio, gdocs)
   - title (string)
   - original_url (string, optional)
   - file_path (string, optional)
   - file_size (integer)
   - status (enum: pending, processing, ready, failed)
   - error_message (text, optional)
   - created_at, updated_at
2. Create SQLAlchemy Source model
3. Set up MinIO client for local development
4. Implement POST /api/notebooks/{id}/sources/upload endpoint
5. Implement POST /api/notebooks/{id}/sources/url endpoint
6. Implement POST /api/notebooks/{id}/sources/text endpoint
7. Add file upload validation (size, type)
8. Implement file storage to MinIO/S3
9. Create Pydantic schemas for source creation
10. Add unit tests for upload endpoints
11. Add database migration for sources table

---

### Feature 1.4: Async Ingestion Pipeline Skeleton

**Acceptance Criteria:**
- [ ] Arq worker process starts successfully
- [ ] Can enqueue ingestion tasks
- [ ] Tasks are processed asynchronously
- [ ] Task status can be queried
- [ ] Failed tasks are logged with error details
- [ ] Redis connection is properly configured
- [ ] Worker can be restarted without losing queued tasks

**Tasks:**
1. Install and configure Redis
2. Install Arq dependency
3. Create worker service directory (services/worker/)
4. Create Arq settings configuration
5. Implement basic ingestion task function
6. Set up task queue enqueue logic
7. Create worker startup script
8. Add health check endpoint for worker
9. Implement task status tracking
10. Add logging configuration
11. Create Docker Compose service for worker
12. Write documentation for running worker locally

---

## Phase 2: Ingestion (Week 2)

### Feature 2.1: Document Parsers

**Acceptance Criteria:**
- [ ] Extract text from PDF files preserving page numbers
- [ ] Extract text from web URLs with clean HTML removal
- [ ] Handle PDF with images (OCR optional for v1)
- [ ] Extract YouTube video transcripts via API
- [ ] Support Google Docs public URLs
- [ ] Return structured text with metadata (page numbers, headings)
- [ ] Handle parsing errors gracefully
- [ ] Character encoding handled correctly (UTF-8)

**Tasks:**
1. Install document parsing libraries (PyPDF2, pdfplumber, BeautifulSoup, youtube-transcript-api)
2. Create parsers module (services/api/modules/parsers/)
3. Implement PDF parser
   - Extract text by page
   - Preserve page numbers
   - Handle multi-column layouts
4. Implement URL/web parser
   - Fetch HTML content
   - Remove scripts, styles, navigation
   - Extract main content using readability or trafilatura
   - Handle redirects and timeouts
5. Implement plain text parser (normalize encoding)
6. Implement YouTube transcript parser
7. Implement Google Docs parser (via public export URL)
8. Create parser factory/registry pattern
9. Add unit tests with sample documents
10. Add error handling and logging for each parser

---

### Feature 2.2: Semantic Chunking

**Acceptance Criteria:**
- [ ] Chunks are 300-800 tokens each
- [ ] 50-120 token overlap between consecutive chunks
- [ ] Preserve heading hierarchy in chunk metadata
- [ ] Preserve page numbers in chunk metadata
- [ ] Natural boundaries respected (paragraphs, sections)
- [ ] Each chunk includes source title and chunk index
- [ ] Chunks maintain character position offsets
- [ ] No information loss between chunks

**Tasks:**
1. Install tokenizer library (tiktoken for OpenAI models)
2. Create chunking module (services/api/modules/chunking/)
3. Implement semantic chunking algorithm
   - Split by paragraphs/headings first
   - Combine small chunks to reach minimum size
   - Split large chunks at sentence boundaries
4. Implement overlap logic
5. Create chunk metadata extractor
   - Page numbers
   - Heading context
   - Character positions
6. Create SourceChunk database model
   - id, source_id, chunk_index
   - content (text)
   - metadata (JSON: page, heading, char_start, char_end)
   - token_count
   - created_at
7. Add unit tests with various document structures
8. Benchmark chunking performance
9. Add database migration for source_chunks table

---

### Feature 2.3: Embedding Generation

**Acceptance Criteria:**
- [ ] Generate embeddings for all chunks
- [ ] Use consistent embedding model (e.g., text-embedding-3-small)
- [ ] Batch processing for efficiency (32-100 chunks per batch)
- [ ] Store embeddings in database
- [ ] Handle API rate limits and retries
- [ ] Track embedding costs
- [ ] Embeddings are normalized for cosine similarity

**Tasks:**
1. Choose and configure embedding model
2. Set up OpenAI/embedding API client
3. Create embedding service module
4. Implement batch embedding generation
5. Add embedding column to source_chunks table (vector type)
6. Implement retry logic with exponential backoff
7. Add rate limiting
8. Create embedding cache (optional)
9. Add unit tests with mock API
10. Monitor and log embedding costs
11. Add database migration for vector column

---

### Feature 2.4: Vector Indexing with pgvector

**Acceptance Criteria:**
- [ ] pgvector extension installed in PostgreSQL
- [ ] Vector similarity search returns relevant chunks
- [ ] Index supports cosine similarity queries
- [ ] Query performance < 200ms for typical notebook (< 1000 chunks)
- [ ] Can filter by notebook_id for scoped search
- [ ] HNSW or IVFFlat index created for performance

**Tasks:**
1. Install pgvector extension in PostgreSQL
2. Add vector column to source_chunks table
3. Create vector similarity search function
4. Create HNSW index on embedding column
5. Implement cosine similarity query with notebook filter
6. Test query performance with various dataset sizes
7. Add EXPLAIN ANALYZE for query optimization
8. Create database migration for vector index
9. Write unit tests for vector search
10. Document index maintenance procedures

---

### Feature 2.5: Complete Ingestion Workflow

**Acceptance Criteria:**
- [ ] Upload triggers async ingestion task
- [ ] Source status updates: pending → processing → ready/failed
- [ ] All steps execute in order (parse → chunk → embed → index)
- [ ] Failed ingestion updates source with error message
- [ ] Successful ingestion generates source summary
- [ ] UI shows real-time status updates
- [ ] Progress tracking (e.g., "5 of 10 chunks embedded")

**Tasks:**
1. Create main ingestion orchestrator function
2. Implement status update helper
3. Chain all ingestion steps:
   - Fetch file from storage
   - Parse document
   - Chunk text
   - Generate embeddings
   - Save chunks and embeddings
   - Generate source summary
4. Add error handling at each step
5. Implement transaction rollback on failure
6. Add progress tracking
7. Create source summary generation function
8. Update source status in database
9. Add comprehensive logging
10. Write integration tests for full pipeline
11. Add monitoring/alerting for failed jobs

---

## Phase 3: Retrieval & Chat (Week 3)

### Feature 3.1: Hybrid Retrieval (BM25 + Vector)

**Acceptance Criteria:**
- [ ] Retrieve top K chunks using vector similarity (cosine)
- [ ] Retrieve top K chunks using BM25 keyword search
- [ ] Combine results with RRF (Reciprocal Rank Fusion)
- [ ] Results scoped to current notebook only
- [ ] Return chunks with scores and metadata
- [ ] Typical query returns results in < 300ms
- [ ] Handles empty results gracefully

**Tasks:**
1. Install BM25 library (rank_bm25 or implement custom)
2. Create retrieval module (services/api/modules/retrieval/)
3. Implement vector similarity search function
   - Query embedding generation
   - Cosine similarity with notebook filter
   - Top-K selection
4. Implement BM25 search function
   - Build BM25 index for notebook chunks
   - Query BM25 index
   - Top-K selection
5. Implement RRF fusion algorithm
6. Create unified retrieval interface
7. Add caching for frequently accessed chunks
8. Add unit tests for each retrieval method
9. Benchmark retrieval performance
10. Add logging for retrieval analytics

---

### Feature 3.2: Grounded Q&A with Citations

**Acceptance Criteria:**
- [ ] User question retrieves relevant evidence chunks
- [ ] LLM generates answer based only on retrieved chunks
- [ ] Answer includes inline citation markers [1][2]
- [ ] Citation cards show source title, page, and quote
- [ ] Citations are clickable and highlight source location
- [ ] Answers stay grounded (no hallucination beyond sources)
- [ ] If no relevant sources, respond "I don't have enough information"
- [ ] Streaming response for better UX

**Tasks:**
1. Create chat module (services/api/modules/chat/)
2. Design evidence packing prompt template
3. Implement question → retrieval flow
4. Create LLM prompt with evidence chunks
5. Implement structured citation output parsing
6. Create citation alignment logic (map chunk IDs to markers)
7. Implement SSE streaming endpoint
8. Create Message model and database table
9. Create Citation model and database table
10. Implement chat history storage
11. Add groundedness validation
12. Write unit tests for chat flow
13. Add database migrations

---

### Feature 3.3: Chat UI with Citations

**Acceptance Criteria:**
- [ ] Chat panel on right side of notebook detail page
- [ ] Message history displayed with user/assistant bubbles
- [ ] Citation markers [1][2] are clickable
- [ ] Clicking citation shows quote and source info
- [ ] Citation panel shows all sources used in answer
- [ ] Streaming messages update in real-time
- [ ] Input box always visible at bottom
- [ ] Auto-scroll to latest message
- [ ] Loading indicator while generating

**Tasks:**
1. Create chat panel component
2. Create message bubble component (user/assistant variants)
3. Create citation marker component
4. Create citation card component
5. Implement SSE client for streaming
6. Implement message rendering with citation parsing
7. Add auto-scroll behavior
8. Create chat input component with textarea
9. Implement send message action
10. Add loading/typing indicator
11. Style with Tailwind CSS
12. Add keyboard shortcuts (Enter to send, Shift+Enter for newline)
13. Implement citation click handler
14. Add responsive design

---

### Feature 3.4: Two-Layer Citation System

**Acceptance Criteria:**
- [ ] Evidence layer: candidate chunks retrieved before generation
- [ ] Binding layer: LLM output maps sentences to chunk IDs
- [ ] Citation scores reflect relevance
- [ ] Citations include exact quotes from chunks
- [ ] Multiple citations can support one statement
- [ ] Citations persist in database for audit
- [ ] UI displays both citation text and score

**Tasks:**
1. Create citation module (services/api/modules/citations/)
2. Design evidence layer schema
3. Design binding layer schema
4. Implement evidence retrieval and scoring
5. Create structured LLM output schema
   ```json
   {
     "answer_blocks": [
       {"text": "...", "citation_chunk_ids": ["chk_1", "chk_2"]}
     ]
   }
   ```
6. Implement citation extraction from LLM response
7. Implement chunk ID → citation marker mapping
8. Create citation storage logic
9. Add citation validation (check chunk IDs exist)
10. Create citation API endpoint for fetching
11. Write unit tests for citation logic
12. Add database migration for citations table

---

## Phase 4: Auto-generated Content (Week 4)

### Feature 4.1: Notebook Summary on Completion

**Acceptance Criteria:**
- [ ] Summary generated when all sources are "ready"
- [ ] Summary covers main themes across all sources
- [ ] Length: 3-5 paragraphs (200-400 words)
- [ ] Summary stored in notebook metadata
- [ ] Summary displayed on notebook detail page
- [ ] Re-generation possible when new sources added
- [ ] Citations to sources included in summary

**Tasks:**
1. Create generation module (services/api/modules/generation/)
2. Design notebook summary prompt template
3. Implement source completion detection
4. Create summary generation function
   - Fetch all source summaries
   - Create combined prompt
   - Call LLM
   - Parse and validate output
5. Add summary field to notebooks table
6. Implement trigger logic (when last source becomes ready)
7. Create manual re-generate endpoint
8. Display summary in UI
9. Add unit tests
10. Add database migration

---

### Feature 4.2: Key Topics Extraction (5-10 topics)

**Acceptance Criteria:**
- [ ] Extract 5-10 key topics from all sources
- [ ] Topics are concise (1-3 words each)
- [ ] Topics ranked by importance/frequency
- [ ] Topics displayed as tags on notebook detail
- [ ] Topics clickable to filter/search related content
- [ ] Re-extraction when sources change

**Tasks:**
1. Design key topics extraction prompt
2. Implement topics extraction function
   - Use LLM to identify main themes
   - Rank topics by relevance
3. Create NotebookTopic model and table
4. Store topics with notebook association
5. Create GET /api/notebooks/{id}/topics endpoint
6. Display topics in UI as tags/chips
7. Implement topic click → filter behavior
8. Add re-generation capability
9. Write unit tests
10. Add database migration

---

### Feature 4.3: Suggested Questions (5 questions)

**Acceptance Criteria:**
- [ ] Generate 5 relevant questions about notebook content
- [ ] Questions are answerable from sources
- [ ] Questions cover different aspects/topics
- [ ] Questions displayed on notebook overview
- [ ] Clicking question initiates chat with that question
- [ ] Re-generation possible

**Tasks:**
1. Design suggested questions prompt template
2. Implement question generation function
   - Analyze source content
   - Generate diverse questions
   - Validate questions are answerable
3. Create SuggestedQuestion model and table
4. Store questions with notebook association
5. Create GET /api/notebooks/{id}/questions endpoint
6. Display questions in UI
7. Implement click → ask in chat behavior
8. Add re-generation endpoint
9. Write unit tests
10. Add database migration

---

### Feature 4.4: Source Overlap Analysis

**Acceptance Criteria:**
- [ ] Identify topics/themes covered by multiple sources
- [ ] Show which sources discuss each overlapping topic
- [ ] Visual representation of source relationships
- [ ] Helps users understand source redundancy and coverage
- [ ] Updated when new sources added

**Tasks:**
1. Design overlap analysis algorithm
   - Extract topics from each source
   - Find common topics across sources
   - Calculate overlap scores
2. Create SourceOverlap model and table
3. Implement analysis function
4. Create visualization data structure
5. Create GET /api/notebooks/{id}/overlaps endpoint
6. Design UI visualization (network graph or Venn diagram)
7. Implement visualization component
8. Add re-analysis capability
9. Write unit tests
10. Add database migration

---

## Phase 5: Derived Outputs (Week 5)

### Feature 5.1: Briefing Doc Generation

**Acceptance Criteria:**
- [ ] Generate executive summary briefing (1-2 pages)
- [ ] Includes: overview, key findings, recommendations
- [ ] Structured format with sections
- [ ] Citations to sources throughout
- [ ] Downloadable as PDF or Markdown
- [ ] Generated on-demand
- [ ] Cached and versioned

**Tasks:**
1. Create GeneratedAsset model and table
   - id, notebook_id, asset_type, content, metadata, version, created_at
2. Design briefing doc prompt template
3. Implement briefing doc generation function
4. Create POST /api/notebooks/{id}/assets/briefing endpoint
5. Implement markdown → PDF conversion
6. Create download endpoint
7. Add version tracking
8. Display in UI with preview
9. Add regenerate capability
10. Write unit tests
11. Add database migration

---

### Feature 5.2: FAQ Generation

**Acceptance Criteria:**
- [ ] Generate 10-15 frequently asked questions
- [ ] Each question has detailed answer
- [ ] Answers include citations
- [ ] FAQ organized by category/topic
- [ ] Searchable FAQ list
- [ ] Exportable format

**Tasks:**
1. Design FAQ generation prompt
2. Implement FAQ generation function
   - Generate questions
   - Generate answers with citations
   - Categorize questions
3. Create POST /api/notebooks/{id}/assets/faq endpoint
4. Create FAQ display component
5. Implement search/filter for FAQ
6. Add category organization
7. Implement export (markdown/PDF)
8. Add regenerate capability
9. Write unit tests

---

### Feature 5.3: Study Guide Generation

**Acceptance Criteria:**
- [ ] Generate structured study guide
- [ ] Sections: overview, key concepts, important details, practice questions
- [ ] Organized hierarchically
- [ ] Citations included
- [ ] Printable format
- [ ] Suitable for learning/review

**Tasks:**
1. Design study guide prompt template
2. Implement study guide generation function
   - Extract key concepts
   - Organize into sections
   - Generate practice questions
3. Create POST /api/notebooks/{id}/assets/study-guide endpoint
4. Design study guide UI layout
5. Implement expandable sections
6. Add print stylesheet
7. Implement export functionality
8. Add regenerate capability
9. Write unit tests

---

### Feature 5.4: Timeline Generation

**Acceptance Criteria:**
- [ ] Extract chronological events from sources
- [ ] Display events on visual timeline
- [ ] Each event shows date, description, source
- [ ] Timeline zoomable and scrollable
- [ ] Events clickable to see full context
- [ ] Export timeline as image or list

**Tasks:**
1. Design timeline extraction prompt
2. Implement timeline generation function
   - Extract dated events
   - Sort chronologically
   - Validate dates
3. Create POST /api/notebooks/{id}/assets/timeline endpoint
4. Choose timeline visualization library
5. Implement timeline component
6. Add zoom and pan controls
7. Implement event detail view
8. Add export functionality
9. Write unit tests

---

### Feature 5.5: Glossary Generation

**Acceptance Criteria:**
- [ ] Extract key terms and definitions
- [ ] Alphabetically organized
- [ ] Each term includes definition and source citation
- [ ] Searchable glossary
- [ ] 20-50 terms depending on content
- [ ] Exportable

**Tasks:**
1. Design glossary extraction prompt
2. Implement glossary generation function
   - Extract important terms
   - Generate definitions
   - Cite sources
3. Create POST /api/notebooks/{id}/assets/glossary endpoint
4. Create glossary UI component
5. Implement alphabetical navigation
6. Add search functionality
7. Implement export
8. Add regenerate capability
9. Write unit tests

---

## Phase 6: Refinement (Week 6)

### Feature 6.1: Reranking for Improved Relevance

**Acceptance Criteria:**
- [ ] Retrieved chunks reranked before LLM generation
- [ ] Reranking improves answer quality (measured by eval)
- [ ] Reranker model integrated (e.g., Cohere rerank, cross-encoder)
- [ ] Performance impact acceptable (< 100ms added latency)
- [ ] Configurable on/off per notebook

**Tasks:**
1. Choose reranking model (Cohere API or local cross-encoder)
2. Install reranker dependencies
3. Create reranking module
4. Implement reranking function
   - Takes query + candidate chunks
   - Returns reranked chunks with new scores
5. Integrate into retrieval pipeline
6. Add configuration option
7. Benchmark reranking performance
8. Run A/B test with eval dataset
9. Write unit tests
10. Document reranking approach

---

### Feature 6.2: Query Rewriting

**Acceptance Criteria:**
- [ ] Vague queries expanded with context
- [ ] Follow-up questions include chat history
- [ ] Improved retrieval recall
- [ ] User can see rewritten query (optional transparency)
- [ ] Configurable rewriting strategies

**Tasks:**
1. Design query rewriting prompt
2. Implement query rewriter function
   - Analyze user query
   - Include chat history context
   - Generate improved query
3. Integrate into chat flow (before retrieval)
4. Add transparency option (show rewritten query)
5. Test with various query types
6. Measure impact on retrieval quality
7. Write unit tests
8. Add configuration options

---

### Feature 6.3: Evaluation Dashboard

**Acceptance Criteria:**
- [ ] Track retrieval metrics: recall@5, recall@10, MRR
- [ ] Track citation metrics: support rate, wrong citation rate
- [ ] Track answer quality: groundedness, completeness, faithfulness
- [ ] Dashboard shows trends over time
- [ ] Filterable by notebook, time range
- [ ] Export metrics as CSV

**Tasks:**
1. Create evaluation dataset
   - 20-50 question-answer pairs
   - Ground truth chunk IDs
2. Create evaluation module
3. Implement retrieval evaluation
   - Calculate recall@K
   - Calculate MRR
4. Implement citation evaluation
   - Manual or LLM-based support checking
5. Implement answer quality evaluation
   - LLM-based grading
6. Create metrics storage (EvaluationMetric table)
7. Create evaluation dashboard UI
8. Implement charts (Chart.js or Recharts)
9. Add filtering and date range selection
10. Implement CSV export
11. Schedule automated evaluation runs
12. Write unit tests
13. Add database migration

---

### Feature 6.4: Retry Mechanisms

**Acceptance Criteria:**
- [ ] Failed ingestion tasks auto-retry (3 attempts)
- [ ] Exponential backoff between retries
- [ ] Failed API calls to LLM/embedding retry
- [ ] Max retry limit configurable
- [ ] Retry history logged
- [ ] Manual retry option in UI

**Tasks:**
1. Implement retry decorator/utility
2. Add retry logic to ingestion tasks
3. Configure exponential backoff
4. Add retry to LLM API calls
5. Add retry to embedding API calls
6. Log retry attempts
7. Store retry count in database
8. Create manual retry endpoint
9. Add retry button in UI for failed sources
10. Write unit tests
11. Monitor retry rates

---

### Feature 6.5: Basic Permissions

**Acceptance Criteria:**
- [ ] Notebook has owner (creator)
- [ ] Owner can add collaborators (editor/viewer roles)
- [ ] Editors can add sources, chat, generate assets
- [ ] Viewers can only view and chat
- [ ] Non-collaborators cannot access notebook
- [ ] Permission checks on all API endpoints
- [ ] UI shows different actions based on role

**Tasks:**
1. Create NotebookCollaborator model and table
   - notebook_id, user_id, role (owner/editor/viewer)
2. Implement permission check middleware
3. Add permission decorators for endpoints
4. Update all notebook endpoints with permission checks
5. Create collaborator management endpoints
   - POST /api/notebooks/{id}/collaborators
   - DELETE /api/notebooks/{id}/collaborators/{user_id}
6. Create collaborator UI component
7. Implement invite flow
8. Add role-based UI hiding
9. Write unit tests for permissions
10. Add database migration

---

## Additional Features (Later Phases)

### Mind Maps (v2)
**Tasks:**
- Extract hierarchical relationships
- Generate mind map structure
- Implement visual mind map component
- Export as image

### Flashcards (v2)
**Tasks:**
- Generate Q&A flashcard pairs
- Implement flashcard UI with flip animation
- Add spaced repetition logic
- Track review progress

### Quizzes (v2)
**Tasks:**
- Generate multiple choice questions
- Implement quiz UI
- Add scoring and feedback
- Store quiz results

### Audio Overview (v2)
**Tasks:**
- Generate audio script from summary
- Integrate TTS API
- Create audio player UI
- Download audio file

---

## Cross-Cutting Concerns

### Authentication
**Tasks:**
- Set up auth provider (Clerk, Auth0, or custom)
- Implement JWT token validation
- Add user registration/login
- Create user profile management
- Add session management

### Error Handling
**Tasks:**
- Standardize error response format
- Add global error handler middleware
- Implement error logging (Sentry)
- Create user-friendly error messages
- Add error boundary components in UI

### Logging & Monitoring
**Tasks:**
- Set up structured logging (Python: structlog, Node: winston)
- Add request/response logging
- Implement performance monitoring
- Set up APM (Application Performance Monitoring)
- Add alerting for critical errors

### Testing
**Tasks:**
- Set up pytest for backend
- Set up Jest/Vitest for frontend
- Write unit tests (target 70%+ coverage)
- Write integration tests
- Write E2E tests (Playwright)
- Set up CI/CD pipeline

### Documentation
**Tasks:**
- API documentation (OpenAPI/Swagger)
- README with setup instructions
- Architecture documentation
- Deployment guide
- User guide

### Deployment
**Tasks:**
- Containerize all services (Docker)
- Set up Docker Compose for local dev
- Configure production environment
- Set up CI/CD (GitHub Actions)
- Implement blue-green deployment
- Set up monitoring and alerting

---

## Success Metrics

### Technical Metrics
- Ingestion success rate > 95%
- Average retrieval latency < 300ms
- Chat response latency < 2s (first token)
- API uptime > 99.5%
- Test coverage > 70%

### Quality Metrics
- Retrieval recall@10 > 90%
- Citation support rate > 95%
- Answer groundedness > 90%
- User-reported accuracy > 85%

### User Metrics
- Time to first answer < 2 minutes (after upload)
- Average sources per notebook: 3-5
- Average questions per session: 5-10
- User retention rate (week 2) > 60%

---

## Risk Management

### High-Risk Areas
1. **Embedding costs** - Monitor and cap usage
2. **Chunking quality** - Validate with diverse document types
3. **Citation accuracy** - Regular evaluation and user feedback
4. **Performance at scale** - Load testing with large notebooks

### Mitigation Strategies
- Implement usage quotas per user
- Build comprehensive test document corpus
- Implement citation validation layer
- Optimize database queries and add caching
- Consider read replicas for scalability
