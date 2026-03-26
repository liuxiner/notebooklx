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
