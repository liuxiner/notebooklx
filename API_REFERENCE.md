# NotebookLX API Reference

Complete API endpoint specification for the NotebookLX backend.

**Base URL:** `http://localhost:8000/api` (development)

**Authentication:** Bearer token in Authorization header
```
Authorization: Bearer <jwt_token>
```

---

## Authentication Endpoints

### POST /auth/register
Register a new user account.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securepassword",
  "full_name": "John Doe"
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "John Doe",
  "created_at": "2024-01-15T10:00:00Z"
}
```

---

### POST /auth/login
Authenticate and receive JWT token.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securepassword"
}
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "full_name": "John Doe"
  }
}
```

---

### GET /auth/me
Get current user profile.

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "John Doe",
  "created_at": "2024-01-15T10:00:00Z"
}
```

---

## Notebook Endpoints

### GET /notebooks
List all notebooks for the authenticated user.

**Query Parameters:**
- `limit` (optional): Number of results (default: 20, max: 100)
- `offset` (optional): Pagination offset (default: 0)
- `sort` (optional): `created_at` or `updated_at` (default: `created_at`)
- `order` (optional): `asc` or `desc` (default: `desc`)

**Response:** `200 OK`
```json
{
  "notebooks": [
    {
      "id": "uuid",
      "name": "Research Notes",
      "description": "Collection of research papers",
      "summary": "Auto-generated summary...",
      "source_count": 5,
      "created_at": "2024-01-15T10:00:00Z",
      "updated_at": "2024-01-16T14:30:00Z"
    }
  ],
  "total": 10,
  "limit": 20,
  "offset": 0
}
```

---

### POST /notebooks
Create a new notebook.

**Request:**
```json
{
  "name": "My Notebook",
  "description": "Optional description"
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "name": "My Notebook",
  "description": "Optional description",
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-01-15T10:00:00Z"
}
```

---

### GET /notebooks/{id}
Get a specific notebook with full details.

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "name": "Research Notes",
  "description": "Collection of research papers",
  "summary": "This notebook covers topics in AI and ML...",
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-01-16T14:30:00Z",
  "sources": [
    {
      "id": "uuid",
      "title": "Attention Is All You Need",
      "source_type": "pdf",
      "status": "ready",
      "created_at": "2024-01-15T10:05:00Z"
    }
  ],
  "topics": ["machine learning", "transformers", "attention"],
  "suggested_questions": [
    "What is the transformer architecture?",
    "How does self-attention work?"
  ]
}
```

---

### PATCH /notebooks/{id}
Update notebook metadata.

**Request:**
```json
{
  "name": "Updated Name",
  "description": "Updated description"
}
```

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "name": "Updated Name",
  "description": "Updated description",
  "updated_at": "2024-01-17T09:00:00Z"
}
```

---

### DELETE /notebooks/{id}
Delete a notebook (soft delete).

**Response:** `204 No Content`

---

## Source Endpoints

### GET /notebooks/{notebook_id}/sources
List all sources in a notebook.

**Query Parameters:**
- `status` (optional): Filter by status (`pending`, `processing`, `ready`, `failed`)
- `source_type` (optional): Filter by type (`pdf`, `url`, `text`, etc.)

**Response:** `200 OK`
```json
{
  "sources": [
    {
      "id": "uuid",
      "title": "Attention Is All You Need",
      "source_type": "pdf",
      "status": "ready",
      "file_size": 1048576,
      "summary": "This paper introduces the Transformer...",
      "chunk_count": 42,
      "created_at": "2024-01-15T10:05:00Z",
      "processed_at": "2024-01-15T10:10:00Z"
    }
  ]
}
```

---

### POST /notebooks/{notebook_id}/sources/upload
Upload a file (PDF, TXT, DOCX, etc.).

**Request:** `multipart/form-data`
```
file: <binary>
title: "Optional custom title" (uses filename if not provided)
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "title": "document.pdf",
  "source_type": "pdf",
  "status": "pending",
  "file_size": 1048576,
  "created_at": "2024-01-15T10:05:00Z"
}
```

---

### POST /notebooks/{notebook_id}/sources/url
Add a URL source.

**Request:**
```json
{
  "url": "https://example.com/article",
  "title": "Optional custom title"
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "title": "Article Title",
  "source_type": "url",
  "original_url": "https://example.com/article",
  "status": "pending",
  "created_at": "2024-01-15T10:05:00Z"
}
```

---

### POST /notebooks/{notebook_id}/sources/text
Add plain text content.

**Request:**
```json
{
  "content": "Plain text content...",
  "title": "My Notes"
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "title": "My Notes",
  "source_type": "text",
  "status": "pending",
  "created_at": "2024-01-15T10:05:00Z"
}
```

---

### GET /sources/{id}
Get source details.

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "notebook_id": "uuid",
  "title": "Attention Is All You Need",
  "source_type": "pdf",
  "status": "ready",
  "file_size": 1048576,
  "summary": "This paper introduces...",
  "metadata": {
    "pages": 15,
    "author": "Vaswani et al."
  },
  "chunk_count": 42,
  "created_at": "2024-01-15T10:05:00Z",
  "processed_at": "2024-01-15T10:10:00Z"
}
```

---

### DELETE /sources/{id}
Delete a source and its chunks.

**Response:** `204 No Content`

---

### GET /sources/{id}/chunks
Get all chunks for a source.

**Query Parameters:**
- `limit` (optional): Number of chunks (default: 50)
- `offset` (optional): Pagination offset

**Response:** `200 OK`
```json
{
  "chunks": [
    {
      "id": "uuid",
      "chunk_index": 0,
      "content": "Abstract. The dominant sequence...",
      "token_count": 256,
      "metadata": {
        "page": 1,
        "heading": "Abstract",
        "char_start": 0,
        "char_end": 512
      }
    }
  ],
  "total": 42
}
```

---

## Chat Endpoints

### GET /notebooks/{notebook_id}/messages
Get chat history for a notebook.

**Query Parameters:**
- `limit` (optional): Number of messages (default: 50)
- `offset` (optional): Pagination offset

**Response:** `200 OK`
```json
{
  "messages": [
    {
      "id": "uuid",
      "role": "user",
      "content": "What is a transformer?",
      "created_at": "2024-01-15T11:00:00Z"
    },
    {
      "id": "uuid",
      "role": "assistant",
      "content": "A transformer is a neural network architecture [1][2]...",
      "citations": [
        {
          "citation_number": 1,
          "source_id": "uuid",
          "source_title": "Attention Is All You Need",
          "quoted_text": "The Transformer is the first...",
          "page": 2,
          "relevance_score": 0.95
        }
      ],
      "created_at": "2024-01-15T11:00:05Z"
    }
  ]
}
```

---

### POST /notebooks/{notebook_id}/chat
Send a chat message and get response (streaming).

**Request:**
```json
{
  "message": "What is a transformer?"
}
```

**Response:** `200 OK` (Server-Sent Events stream)
```
event: token
data: {"content": "A"}

event: token
data: {"content": " transformer"}

event: citation
data: {"citation_number": 1, "source_id": "uuid", "quoted_text": "..."}

event: done
data: {"message_id": "uuid"}
```

**Alternative non-streaming response:**
```json
{
  "message_id": "uuid",
  "content": "A transformer is...",
  "citations": [...]
}
```

---

### DELETE /messages/{id}
Delete a message from chat history.

**Response:** `204 No Content`

---

## Knowledge Endpoints

### GET /notebooks/{notebook_id}/topics
Get key topics for a notebook.

**Response:** `200 OK`
```json
{
  "topics": [
    {
      "topic": "machine learning",
      "importance_score": 0.95
    },
    {
      "topic": "transformers",
      "importance_score": 0.90
    }
  ]
}
```

---

### POST /notebooks/{notebook_id}/topics/generate
Regenerate topics for a notebook.

**Response:** `200 OK`
```json
{
  "status": "completed",
  "topics": [...]
}
```

---

### GET /notebooks/{notebook_id}/questions
Get suggested questions.

**Response:** `200 OK`
```json
{
  "questions": [
    {
      "id": "uuid",
      "question": "What is the transformer architecture?",
      "relevance_score": 0.92
    }
  ]
}
```

---

### POST /notebooks/{notebook_id}/questions/generate
Regenerate suggested questions.

**Response:** `200 OK`
```json
{
  "status": "completed",
  "questions": [...]
}
```

---

### GET /notebooks/{notebook_id}/overlaps
Get source overlap analysis.

**Response:** `200 OK`
```json
{
  "overlaps": [
    {
      "source_1": {
        "id": "uuid",
        "title": "Paper A"
      },
      "source_2": {
        "id": "uuid",
        "title": "Paper B"
      },
      "shared_topics": ["attention", "neural networks"],
      "overlap_score": 0.75
    }
  ]
}
```

---

## Generated Assets Endpoints

### GET /notebooks/{notebook_id}/assets
List all generated assets for a notebook.

**Query Parameters:**
- `asset_type` (optional): Filter by type

**Response:** `200 OK`
```json
{
  "assets": [
    {
      "id": "uuid",
      "asset_type": "briefing_doc",
      "title": "Executive Briefing",
      "version": 1,
      "created_at": "2024-01-15T12:00:00Z"
    }
  ]
}
```

---

### POST /notebooks/{notebook_id}/assets/briefing
Generate briefing document.

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "asset_type": "briefing_doc",
  "title": "Executive Briefing",
  "content": "# Overview\n\n...",
  "version": 1,
  "created_at": "2024-01-15T12:00:00Z"
}
```

---

### POST /notebooks/{notebook_id}/assets/faq
Generate FAQ.

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "asset_type": "faq",
  "content": "# Frequently Asked Questions\n\n...",
  "metadata": {
    "question_count": 15,
    "categories": ["General", "Technical"]
  }
}
```

---

### POST /notebooks/{notebook_id}/assets/study-guide
Generate study guide.

**Response:** `201 Created`

---

### POST /notebooks/{notebook_id}/assets/timeline
Generate timeline.

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "asset_type": "timeline",
  "content_format": "json",
  "content": "[{\"date\": \"2017-06\", \"event\": \"Transformer paper published\"}]"
}
```

---

### POST /notebooks/{notebook_id}/assets/glossary
Generate glossary.

**Response:** `201 Created`

---

### GET /assets/{id}
Get specific asset.

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "notebook_id": "uuid",
  "asset_type": "briefing_doc",
  "title": "Executive Briefing",
  "content": "# Overview\n\n...",
  "content_format": "markdown",
  "version": 1,
  "created_at": "2024-01-15T12:00:00Z"
}
```

---

### GET /assets/{id}/download
Download asset as file.

**Query Parameters:**
- `format` (optional): `pdf`, `markdown`, `json` (default: original format)

**Response:** `200 OK`
```
Content-Type: application/pdf
Content-Disposition: attachment; filename="briefing.pdf"

<binary content>
```

---

### DELETE /assets/{id}
Delete a generated asset.

**Response:** `204 No Content`

---

## Collaboration Endpoints

### GET /notebooks/{notebook_id}/collaborators
List collaborators for a notebook.

**Response:** `200 OK`
```json
{
  "collaborators": [
    {
      "user_id": "uuid",
      "email": "user@example.com",
      "role": "owner",
      "created_at": "2024-01-15T10:00:00Z"
    },
    {
      "user_id": "uuid",
      "email": "editor@example.com",
      "role": "editor",
      "invited_by": "uuid",
      "created_at": "2024-01-16T09:00:00Z"
    }
  ]
}
```

---

### POST /notebooks/{notebook_id}/collaborators
Add a collaborator.

**Request:**
```json
{
  "email": "collaborator@example.com",
  "role": "editor"
}
```

**Response:** `201 Created`
```json
{
  "user_id": "uuid",
  "email": "collaborator@example.com",
  "role": "editor",
  "invited_by": "current_user_uuid"
}
```

---

### PATCH /notebooks/{notebook_id}/collaborators/{user_id}
Update collaborator role.

**Request:**
```json
{
  "role": "viewer"
}
```

**Response:** `200 OK`

---

### DELETE /notebooks/{notebook_id}/collaborators/{user_id}
Remove a collaborator.

**Response:** `204 No Content`

---

## Evaluation Endpoints

### GET /evaluation/metrics
Get evaluation metrics.

**Query Parameters:**
- `notebook_id` (optional): Filter by notebook
- `metric_type` (optional): Filter by type
- `start_date` (optional): Filter by date range
- `end_date` (optional): Filter by date range

**Response:** `200 OK`
```json
{
  "metrics": [
    {
      "metric_type": "retrieval_recall_10",
      "value": 0.92,
      "notebook_id": "uuid",
      "created_at": "2024-01-15T12:00:00Z"
    }
  ]
}
```

---

### POST /evaluation/run
Run evaluation on current system.

**Request:**
```json
{
  "notebook_id": "uuid",
  "dataset_id": "uuid"
}
```

**Response:** `200 OK`
```json
{
  "results": {
    "retrieval_recall_10": 0.92,
    "citation_support_rate": 0.95,
    "answer_groundedness": 0.88
  }
}
```

---

## Search Endpoints

### POST /notebooks/{notebook_id}/search
Search within a notebook's sources.

**Request:**
```json
{
  "query": "transformer architecture",
  "limit": 10,
  "filters": {
    "source_ids": ["uuid1", "uuid2"]
  }
}
```

**Response:** `200 OK`
```json
{
  "results": [
    {
      "chunk_id": "uuid",
      "source_id": "uuid",
      "source_title": "Attention Is All You Need",
      "content": "The Transformer architecture...",
      "score": 0.95,
      "metadata": {
        "page": 3,
        "heading": "Model Architecture"
      }
    }
  ]
}
```

---

## Health & Status Endpoints

### GET /health
Health check endpoint.

**Response:** `200 OK`
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "storage": "connected"
}
```

---

### GET /status/ingestion
Get ingestion queue status.

**Response:** `200 OK`
```json
{
  "queued_jobs": 5,
  "running_jobs": 2,
  "failed_jobs": 1
}
```

---

### GET /sources/{id}/status
Get detailed ingestion status for a source.

**Response:** `200 OK`
```json
{
  "source_id": "uuid",
  "status": "processing",
  "progress": {
    "step": "embedding",
    "chunks_processed": 25,
    "total_chunks": 42,
    "percentage": 59.5
  },
  "started_at": "2024-01-15T10:06:00Z",
  "estimated_completion": "2024-01-15T10:08:00Z"
}
```

---

## Error Responses

All endpoints use standard HTTP status codes and return errors in this format:

**400 Bad Request**
```json
{
  "error": "validation_error",
  "message": "Invalid request parameters",
  "details": {
    "name": ["This field is required"]
  }
}
```

**401 Unauthorized**
```json
{
  "error": "unauthorized",
  "message": "Invalid or expired token"
}
```

**403 Forbidden**
```json
{
  "error": "forbidden",
  "message": "You don't have permission to access this resource"
}
```

**404 Not Found**
```json
{
  "error": "not_found",
  "message": "Notebook not found"
}
```

**500 Internal Server Error**
```json
{
  "error": "internal_error",
  "message": "An unexpected error occurred",
  "request_id": "uuid"
}
```

---

## Rate Limiting

**Rate Limits:**
- Authenticated: 1000 requests per hour
- Chat endpoints: 60 requests per minute
- Upload endpoints: 100 MB per hour

**Rate Limit Headers:**
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 995
X-RateLimit-Reset: 1642260000
```

**429 Too Many Requests**
```json
{
  "error": "rate_limit_exceeded",
  "message": "Too many requests",
  "retry_after": 3600
}
```

---

## Webhooks (Future)

For async job completion notifications:

**POST {webhook_url}**
```json
{
  "event": "source.ingestion.completed",
  "source_id": "uuid",
  "notebook_id": "uuid",
  "timestamp": "2024-01-15T10:10:00Z"
}
```

Events:
- `source.ingestion.completed`
- `source.ingestion.failed`
- `asset.generation.completed`

---

## API Versioning

Current version: `v1`

Versioning strategy:
- URL-based: `/api/v1/notebooks`
- Header-based (future): `Accept: application/vnd.notebooklx.v1+json`

Breaking changes will increment version number.

---

## SDK Support (Future)

Official SDKs planned for:
- Python
- JavaScript/TypeScript
- Go

Example (Python):
```python
from notebooklx import Client

client = Client(api_key="...")
notebook = client.notebooks.create(name="My Notebook")
source = notebook.sources.upload(file="paper.pdf")
response = notebook.chat("What is this about?")
```
