# NotebookLX Task Checklist

Quick reference checklist for tracking development progress. Check off items as you complete them.

## Phase 1: Foundation ✓ = Complete, ⚡ = In Progress, ⬜ = Not Started

### Week 1 - Core Infrastructure

**Notebook CRUD**
- ✓ Database schema & migrations
- ✓ API endpoints (POST, GET, PATCH, DELETE)
- ✓ Unit tests
- ✓ Frontend list page
- ✓ Create/edit/delete UI

**Source Upload** ✓
- ✓ Sources table schema
- ✓ MinIO/S3 setup
- ✓ PDF upload endpoint
- ✓ URL upload endpoint
- ✓ Text upload endpoint
- ✓ File validation
- ✓ Source delete endpoint

**Worker Pipeline** ✓
- ✓ Redis setup
- ✓ Arq worker configuration
- ✓ Task queue implementation
- ✓ Status tracking
- ✓ Docker setup

---

## Phase 2: Ingestion

### Week 2 - Document Processing

**Parsers**
- ✓ PDF parser (with page numbers)
- ✓ Web/URL parser
- ✓ YouTube transcript parser
- ✓ Google Docs parser
- ✓ Parser tests

**Chunking** ⚡
- ✓ Semantic chunking algorithm
- ✓ Overlap implementation
- ✓ Metadata extraction (page numbers, headings)
- ✓ SourceChunk model
- ⚡ Offline-safe tokenizer loading
- ⚡ Chunking tests in no-network environment
- ⬜ Benchmark chunking performance

**Embeddings** ⚡
- ✓ Embedding model setup
- ✓ Batch generation
- ✓ Rate limiting
- ✓ Cost tracking
- ✓ Vector storage
- ⚡ Offline-safe token counting integration
- ⚡ Embedding tests in no-network environment

**Vector Search**
- ✓ pgvector installation
- ✓ Vector index creation (HNSW)
- ✓ Similarity search function
- ✓ Performance optimization
- ✓ Search tests

**End-to-End**
- ✓ Complete ingestion workflow
- ✓ Status updates
- ✓ Error handling
- ✓ Progress tracking
- ✓ Integration tests

**Source Snapshots & Content Map** ⚡
- ✓ SourceSnapshot schema & persistence
- ✓ Snapshot stage in ingestion pipeline
- ⚡ Snapshot failure/status visibility
- ⬜ NotebookContentMap aggregation
- ⬜ Sitemap projection & budget compaction
- ⬜ Source mutation regeneration triggers

---

## Phase 3: Retrieval & Chat

### Week 3 - Q&A System

**Hybrid Retrieval** ✓
- ✓ Vector similarity search
- ✓ BM25 keyword search
- ✓ RRF fusion
- ✓ Notebook scoping
- ✓ Performance benchmarks

**Grounded Q&A** ⚡
- ✓ Evidence packing
- ✓ LLM prompt templates
- ✓ Structured output parsing
- ✓ Citation extraction
- ✓ SSE streaming
- ✓ Message storage

**Citation System**
- ✓ Citation database model
- ✓ Citation API
- ✓ Citation validation

**Chat UI**
- ✓ Chat panel component
- ✓ Message bubbles
- ✓ Citation markers
- ✓ Citation cards
- ✓ SSE client
- ✓ Real-time answer updates
- ✓ Citation text + score visibility
- ✓ Auto-scroll
- ✓ Input component

**Notebook Workspace** ✓
- ✓ Source list in notebook detail
- ✓ Ingestion status badges
- ✓ Progress/error state display
- ✓ Empty state for no sources
- ✓ Reserved summary section
- ✓ Reserved generated-assets section
- ✓ Workspace refresh behavior
- ✓ Frontend tests
- ✓ Source snapshot preview card

**Source Management UI** ✓
- ✓ Add-source entry point
- ✓ PDF upload flow
- ✓ Filename-based default upload title
- ✓ Text paste flow
- ✓ URL paste/manual entry flow
- ✓ Validation and loading states
- ✓ Auto-enqueue ingestion after upload
- ✓ Poll upload-started ingestion status to terminal state
- ✓ Delete action per source
- ✓ Confirm delete modal
- ✓ Refresh source list after create/delete
- ✓ Frontend tests

**Source Management UI - Bulk Upload** ✓
- ✓ Bulk PDF/TXT upload endpoint
- ✓ Multi-file upload selection in web UI
- ✓ Per-file validation for mixed upload batches
- ✓ Fan-out ingestion calls for created sources
- ✓ Multi-source polling in workspace
- ✓ Backend and frontend tests

**Bulk Ingestion Enqueue** ✓
- ✓ Bulk ingestion API route
- ✓ Batch upload uses one bulk-ingestion request
- ✓ Single-source ingestion regression coverage
- ✓ Backend and frontend tests

**Bulk Ingestion Status Polling** ✓
- ✓ Bulk status API route
- ✓ Workspace status hydration uses bulk status
- ✓ Tracked polling stops when all ingestions resolve
- ✓ Single-source status regression coverage
- ✓ Backend and frontend tests

**Chat Guardrails & Workflow UX** ✓
- ✓ Structured chat error categories
- ✓ Friendly quota / balance handling
- ✓ Friendly safety / policy handling
- ✓ Transient failure retry guidance
- ✓ Notebook-oriented workflow status copy
- ✓ Empty-state starter prompts
- ✓ Retry CTA for transient chat failures
- ✓ Backend and frontend tests

**Streaming Observability & Retrieval Transparency** ✓
- ✓ Chat preparation timing visibility
- ✓ Query embedding token and optional cost visibility with model-aware embedding pricing
- ✓ Chat query top-k control with default 5
- ✓ Time-to-first-answer visibility
- ✓ Stream delivery mode visibility
- ✓ Retrieved chunk count visibility
- ✓ Chunk-to-source relationship panel
- ✓ Chat token usage and optional cost visibility with provider-first reporting plus local fallback estimation
- ✓ Incremental assistant bubble streaming
- ✓ Stable stream finalization without duplicate bubbles
- ✓ Backend and frontend tests

---

## Phase 4: Auto-generated Content

### Week 4 - Intelligence Layer

**Notebook Summary**
- ⬜ Summary generation function
- ⬜ Trigger on completion
- ⬜ Storage in DB
- ⬜ UI display
- ⬜ Re-generation API

**Key Topics**
- ⬜ Topic extraction
- ⬜ NotebookTopic model
- ⬜ Topics API
- ⬜ Tag display UI
- ⬜ Click to filter

**Suggested Questions**
- ⬜ Question generation
- ⬜ SuggestedQuestion model
- ⬜ Questions API
- ⬜ Question display UI
- ⬜ Click to ask

**Source Overlap**
- ⬜ Overlap analysis algorithm
- ⬜ SourceOverlap model
- ⬜ Analysis API
- ⬜ Visualization UI
- ⬜ Re-analysis capability

---

## Phase 5: Derived Outputs

### Week 5 - Content Generation

**GeneratedAsset System**
- ⬜ GeneratedAsset model
- ⬜ Version tracking
- ⬜ Download endpoints
- ⬜ PDF export
- ⬜ Asset UI components

**Priority Assets**
1. ⬜ Briefing Doc (overview, findings, recommendations)
2. ⬜ FAQ (10-15 Q&As with citations)
3. ⬜ Study Guide (concepts, details, practice questions)
4. ⬜ Timeline (chronological events)
5. ⬜ Glossary (key terms and definitions)

**Later Assets**
- ⬜ Mind Maps
- ⬜ Flashcards
- ⬜ Quizzes
- ⬜ Audio Overview

---

## Phase 6: Refinement

### Week 6 - Quality & Scale

**Reranking**
- ⬜ Reranker model integration
- ⬜ Reranking pipeline
- ⬜ Configuration options
- ⬜ Performance testing
- ⬜ A/B evaluation

**Query Rewriting** ⚡
- ✓ Rewriter function
- ✓ Chat history integration
- ✓ Chat flow integration before retrieval
- ✓ Backend transparency payload
- ✓ Rewritten query UI/UX
- ✓ Frontend transparency tests
- ✓ Rewriter configuration options
- ⬜ Quality testing

**Evaluation Dashboard - Manual Create UX** ✓
- ✓ Manual evaluation create flow tracked in DEVELOPMENT_PLAN.md
- ✓ Notebook picker in dashboard filters
- ✓ Required notebook picker in create-evaluation dialog
- ✓ Notebook-scoped ground-truth chunk multi-selector
- ✓ Clear chunk selections when notebook changes
- ✓ Start evaluation action in runs table
- ✓ Retry evaluation action in runs table
- ✓ Frontend tests for evaluation create/start/retry flow and chunk selector loop regression

**Evaluation**
- ⬜ Evaluation dataset (20-50 Q&As)
- ✓ Retrieval metrics (recall, MRR)
- ⬜ Citation metrics
- ⬜ Answer quality metrics
- ⬜ Dashboard UI
- ⬜ Automated runs

**Reliability**
- ⬜ Retry mechanisms
- ⬜ Exponential backoff
- ⬜ Manual retry UI
- ⬜ Retry logging

**Permissions**
- ⬜ NotebookCollaborator model
- ⬜ Permission middleware
- ⬜ Collaborator endpoints
- ⬜ Invite flow
- ⬜ Role-based UI

---

## Cross-Cutting Concerns

**Authentication**
- ⬜ Auth provider setup
- ⬜ JWT validation
- ⬜ Login/registration
- ⬜ User profile
- ⬜ Session management

**Error Handling**
- ⬜ Standard error format
- ⬜ Global error handler
- ⬜ Error logging (Sentry)
- ⬜ User-friendly messages
- ⬜ Error boundaries

**Logging & Monitoring**
- ⬜ Structured logging
- ⬜ Request/response logs
- ⬜ Performance monitoring
- ⬜ APM setup
- ⬜ Alerting

**Testing**
- ⬜ Test framework setup (pytest, Jest)
- ⬜ Unit tests (70%+ coverage)
- ⬜ Integration tests
- ⬜ E2E tests (Playwright)
- ⬜ CI/CD pipeline

**Documentation**
- ⬜ API docs (OpenAPI)
- ⬜ Setup README
- ⬜ Architecture docs
- ⬜ Deployment guide
- ⬜ User guide
- ✓ Design system (apps/web/DESIGN.md) - Run /design-consultation

**Deployment**
- ⬜ Docker setup
- ⬜ Docker Compose
- ⬜ Production config
- ⬜ CI/CD (GitHub Actions)
- ⬜ Monitoring/alerting

---

## Success Criteria Tracking

### Technical Health
- [ ] Ingestion success rate: ___% (target: >95%)
- [ ] Retrieval latency: ___ms (target: <300ms)
- [ ] Chat first token: ___s (target: <2s)
- [ ] API uptime: ___% (target: >99.5%)
- [ ] Test coverage: ___% (target: >70%)

### Quality Metrics
- [ ] Retrieval recall@10: ___% (target: >90%)
- [ ] Citation support rate: ___% (target: >95%)
- [ ] Answer groundedness: ___% (target: >90%)
- [ ] User accuracy rating: ___% (target: >85%)

### Usage Metrics
- [ ] Time to first answer: ___ min (target: <2min)
- [ ] Avg sources/notebook: ___ (target: 3-5)
- [ ] Avg questions/session: ___ (target: 5-10)
- [ ] Week 2 retention: ___% (target: >60%)

---

## Current Sprint

**Sprint Goal:** ___________________________

**This Week's Focus:**
- [ ] Task 1
- [ ] Task 2
- [ ] Task 3

**Blockers:**
-

**Next Week Preview:**
-

---

## Notes

_Use this section for development notes, decisions, and learnings._

- 2026-04-14: Snapshot LLM parsing now tolerates markdown-wrapped JSON responses during ingestion; unrecoverable snapshot errors still fail before embeddings/indexing.
- 2026-04-14: Ingestion now logs per-step monitor events (`starting → fetching → parsing → chunking → snapshot → embedding → saving → completed`), snapshot-provider parse failures include a short output preview in logs, and API-visible ingestion failures are reduced to user-facing step summaries like "Ingestion failed during snapshot generation."
- 2026-04-14: Snapshot ingestion now ranks multiple JSON objects by schema match, so chunk-like blobs no longer win over the final snapshot object; when the LLM payload is still malformed, the pipeline falls back to the heuristic snapshot instead of failing the source.
- 2026-04-14: Bulk source ingestion/upload now accepts up to 50 items per request with explicit validation; worker concurrency defaults to `INGESTION_MAX_JOBS=4` (configurable) so queued jobs are processed in a controlled way; snapshot LLM calls now run via async thread offloading to avoid blocking the event loop while waiting on provider responses.
- 2026-04-14: Notebook deletion now removes source-backed resources end-to-end: uploaded objects are deleted, source rows are hard-deleted so cascades clear chunks/snapshots/ingestion jobs, and worker tasks return `cancelled` if the source or notebook disappears mid-flight.
- 2026-04-21: Shared model budgeting now reads `ZHIPUAI_API_MODEL_MAX_TOKENS` plus global `NOTEBOOKLX_PROMPT_BUDGET_RATIO` from `.env`; snapshot prompt assembly compacts long documents to stay within budget, and shared chat/embedding providers now reject over-budget inputs before making API calls (`embedding-2`/`embedding-3` default to 8K context with the same ratio applied).
- 2026-04-21: Worker ingestion failures now always persist terminal `failed` status to both the source and ingestion job even if error summarization/imports break; unexpected worker exceptions keep their concrete message so UI polling no longer gets stuck on `processing` while Arq reports failed jobs.
