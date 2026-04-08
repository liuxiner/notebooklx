# Query Rewriting Integration Plan
Engineering Review for Feature 6.2: Query Rewriting Transparency

**Status:** Integration Required
**Branch:** main
**Date:** 2026-04-08

## Overview

The query rewriter module exists and is well-tested, but is **not integrated** into the chat streaming flow. This plan addresses the integration work required to complete Feature 6.2 with full transparency UX.

## Architecture Issues

### 1. Missing Query Rewriter Integration (CRITICAL)
**Current state:** `services/api/modules/chat/routes.py:277-281`
```python
preparation = await grounded_qa_service.prepare_answer(
    payload.question,  # ← Original question, NOT rewritten
    str(notebook.id),
    top_k=payload.top_k,
)
```

**Required change:**
```python
# 1. Fetch chat history
history = get_recent_chat_history(db, str(notebook.id), limit=10)

# 2. Rewrite query
rewriter = QueryRewriter(chat_provider=chat_provider)
rewrite_result = rewriter.rewrite_for_retrieval(payload.question, history)
effective_query = rewrite_result.primary_query

# 3. Use rewritten query for retrieval
preparation = await grounded_qa_service.prepare_answer(
    effective_query,
    str(notebook.id),
    top_k=payload.top_k,
)
```

### 2. No SSE Event for Query Rewrite Transparency (CRITICAL)
**Required event type:**
```typescript
export interface ChatRewriteEvent {
  original_query: string;
  rewritten_query: string;
  strategy: string;
}
```

**SSE emission:**
```python
yield _format_sse_event("query_rewrite", {
    "original_query": payload.question,
    "rewritten_query": effective_query,
    "strategy": rewrite_result.strategy,
})
```

### 3. Chat History Not Fetched (CRITICAL)
- `get_recent_chat_history()` helper exists but isn't called
- Need to fetch before rewrite step

### 4. Service Layer Coupling Decision (MODERATE)
**Two options:**

**Option A (Recommended):** Call rewriter before `prepare_answer()` in routes.py
- Pro: Keeps service layer unchanged
- Pro: Clear separation of concerns
- Con: Routes handle orchestration logic

**Option B:** Pass rewriter into `GroundedQAService`
- Pro: Service owns full pipeline
- Con: Tighter coupling, harder to test

**Decision:** Use Option A for clearer separation.

### 5. Rewrite Failure Handling (CRITICAL)
**Current:** No handling if rewriter LLM fails

**Required:**
```python
try:
    rewrite_result = rewriter.rewrite_for_retrieval(payload.question, history)
    effective_query = rewrite_result.primary_query
except Exception as exc:
    logger.error("Query rewrite failed: %s. Using original query.", exc)
    effective_query = payload.question
```

### 6. Missing Rewrite Timing Metric (MINOR)
**Add to `ChatTimingMetrics`:**
```python
@dataclass(frozen=True)
class ChatTimingMetrics:
    # ... existing fields ...
    rewrite_seconds: float | None = None  # NEW
```

## Code Quality

No issues found. The query rewriter module is well-engineered:
- ✅ Proper error handling with graceful fallbacks
- ✅ Immutable dataclass for results
- ✅ Protocol-based dependency injection
- ✅ Comprehensive regex patterns
- ✅ Proper logging at appropriate levels
- ✅ Protected term preservation logic

## Test Coverage

### Current Coverage: 79%
- Code paths: 91% (20/22)
- User flows: 43% (3/7)

### Test Gaps (6 paths)

**Critical Gaps:**
1. **[→E2E]** Query rewrite integration in chat flow
2. **[→E2E]** Rewrite SSE event emission
3. **[→E2E]** User sees "📝 Rewrote: X → Y" in UI

**Moderate Gaps:**
4. Chat history fetching in chat endpoint
5. Rewrite timing metrics
6. Temporary upstream error mapping

### Test Files to Create
- `services/api/tests/test_chat_stream_rewrite_integration.py`
- `apps/web/components/chat/chat-panel-rewrite.test.tsx`

## Performance Implications

### Database Query
- `get_recent_chat_history()` adds ~50-100ms per request
- **Mitigation:** Ensure index exists on `(notebook_id, created_at DESC)`

### LLM Call
- Rewrite adds ~500-2000ms latency per message
- Cost: ~$0.0001-$0.001 per message
- **Mitigation (deferred):** Cache rewrites keyed by (query, history_hash)

### No Rewrite Caching
- Same question + same history = repeated LLM calls
- **Future optimization:** Add Redis caching for rewrites

## Implementation Tasks

### Backend Changes
1. **routes.py**
   - Import `QueryRewriter`, `get_recent_chat_history`
   - Fetch chat history before `prepare_answer()`
   - Instantiate rewriter with chat provider
   - Call `rewrite_for_retrieval()`
   - Emit `query_rewrite` SSE event
   - Handle rewrite failures gracefully
   - Track `rewrite_seconds` metric

2. **service.py**
   - Add `rewrite_seconds` to `ChatTimingMetrics`

3. **chat-stream.ts**
   - Add `ChatRewriteEvent` interface
   - Add `onRewrite` callback to `StreamNotebookChatOptions`
   - Dispatch `query_rewrite` events

### Frontend Changes
4. **chat-panel.tsx**
   - Add `originalQuery` and `rewrittenQuery` state
   - Display inline rewrite status below input
   - Implement auto-collapse after 3 seconds
   - Add settings toggle for "Always show rewritten queries"

5. **message-bubble.tsx**
   - No changes needed

6. **chat-stream.test.ts**
   - Add tests for rewrite event handling

### Database Migration
7. **Optional: Add index**
   ```sql
   CREATE INDEX ix_message_notebook_created
   ON message (notebook_id, created_at DESC)
   IF NOT EXISTS;
   ```

## NOT in Scope

- Query rewrite caching (defer to future sprint)
- User feedback mechanism for rewrites (defer to future)
- Rewrite strategy configuration UI (defer to future)
- A/B testing for rewrite effectiveness (defer to future)

## What Already Exists

✅ Query rewriter module (`services/api/modules/query/rewriter.py`)
✅ Chat history helper (`get_recent_chat_history()`)
✅ SSE streaming infrastructure
✅ Error classification system
✅ Test infrastructure
✅ DESIGN.md with transparency UX specification

## Acceptance Criteria

After integration:
- [ ] User sends follow-up question → System rewrites using history
- [ ] User sees "📝 Rewrote: original → rewritten" below input
- [ ] Rewrite event appears in SSE stream
- [ ] Rewrite failure falls back to original query gracefully
- [ ] `rewrite_seconds` tracked in metrics
- [ ] E2E tests pass for rewrite integration
- [ ] Frontend tests pass for rewrite UI

## Success Metrics

- Rewrite rate: Target 40-60% of queries should be rewritten (not all need it)
- Rewrite latency: <2s for 95th percentile
- Rewrite fallback rate: <5% (most rewrites should succeed)
- Retrieval improvement: +10% recall@10 for rewritten queries

## References

- DEVELOPMENT_PLAN.md — Feature 6.2: Query Rewriting
- DESIGN.md — Query Rewriting Transparency UX
- TASK_CHECKLIST.md — Current progress tracking
