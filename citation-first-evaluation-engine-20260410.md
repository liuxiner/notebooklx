# Citation-First Evaluation Engine

**Date**: 2026-04-10
**Status**: Draft
**Author**: Office Hours Session
**Project**: NotebookLX

---

## 1. Problem Statement

NotebookLX's evaluation dashboard exists but produces unreliable metrics. The generation quality metrics (groundedness, completeness, faithfulness, citation support) use keyword-overlap heuristics that produce meaningless numbers. The retrieval metrics (recall@K, MRR) are computationally correct but are only ever run against single queries, not evaluation datasets.

Meanwhile, the evaluation system needs to serve two purposes:
1. **Resume/interview showcase** — demonstrate systematic ML infrastructure engineering in job applications
2. **Real quality improvement** — catch regressions and guide tuning of the RAG pipeline for potential company adoption

## 2. Core Insight

**Citation quality evaluation is the novel contribution.** No existing framework (RAGAS, TruLens, DeepEval) evaluates whether citations actually support the claims they're attached to. This is the centerpiece metric that makes NotebookLX's evaluation unique and interview-worthy.

Standard metrics (faithfulness, groundedness, completeness) will use LLM-as-judge with prompts inspired by established frameworks, but the citation metrics (citation precision, citation recall, citation grounding accuracy) are custom-built for this product's source-grounding architecture.

## 3. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Evaluation Dashboard                       │
│  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌───────────────┐ │
│  │ Datasets  │ │ Runs List  │ │ Trends   │ │ A/B Compare   │ │
│  └──────────┘ └───────────┘ └──────────┘ └───────────────┘ │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   Evaluation API                              │
│  ┌────────────┐ ┌──────────────┐ ┌────────────────────────┐ │
│  │ Dataset Mgmt│ │ Run Orchestr.│ │ Results & Aggregation  │ │
│  └────────────┘ └──────────────┘ └────────────────────────┘ │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   Metric Evaluators                           │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────────────┐ │
│  │ Retrieval    │ │ LLM-as-Judge │ │ Citation Evaluator   │ │
│  │ (determinist)│ │ (generation) │ │ (novel, core IP)     │ │
│  │             │ │              │ │                      │ │
│  │ recall@K    │ │ faithfulness │ │ citation_precision   │ │
│  │ MRR         │ │ groundedness │ │ citation_recall      │ │
│  │ precision@K │ │ completeness │ │ citation_grounding   │ │
│  │ hit_rate    │ │ relevance    │ │ claim-chunk-align    │ │
│  │ NDCG        │ │              │ │                      │ │
│  └─────────────┘ └──────────────┘ └──────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 4. Data Model Changes

### 4.1 New: EvaluationDataset

Stores reusable test question sets with ground truth annotations.

```python
class EvaluationDataset(Base):
    __tablename__ = "evaluation_datasets"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    notebook_id = Column(UUID, ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    version = Column(Integer, default=1)            # Dataset versioning
    question_count = Column(Integer, default=0)
    is_synthetic = Column(Boolean, default=False)    # Generated vs. curated
    created_at = Column(DateTime, default=datetime.utcnow)

    questions = relationship("DatasetQuestion", back_populates="dataset", cascade="all, delete-orphan")
```

### 4.2 New: DatasetQuestion

Individual test questions with ground truth.

```python
class DatasetQuestion(Base):
    __tablename__ = "dataset_questions"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    dataset_id = Column(UUID, ForeignKey("evaluation_datasets.id", ondelete="CASCADE"), nullable=False)
    question = Column(Text, nullable=False)
    ground_truth_answer = Column(Text, nullable=True)           # Reference answer
    ground_truth_chunk_ids = Column(JSON, nullable=True)        # Relevant chunk IDs
    ground_truth_citation_spans = Column(JSON, nullable=True)   # Which parts of answer cite which chunks
    difficulty = Column(Text, nullable=True)                    # "easy", "medium", "hard"
    category = Column(Text, nullable=True)                      # Topic category
    source_chunk_id = Column(UUID, nullable=True)               # Origin chunk for synthetic Qs
```

### 4.3 Modified: EvaluationRun

Add batch support, config snapshots, and statistical aggregates.

```python
class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    notebook_id = Column(UUID, ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False)
    dataset_id = Column(UUID, ForeignKey("evaluation_datasets.id"), nullable=True)  # NEW
    name = Column(Text, nullable=True)                    # NEW: Human-readable name
    config_snapshot = Column(JSON, nullable=True)          # NEW: Retrieval params, model, etc.
    status = Column(SQLEnum(EvaluationStatus), default=EvaluationStatus.PENDING)
    error_message = Column(Text, nullable=True)

    # Aggregated results (NEW)
    summary = Column(JSON, nullable=True)  # {metric_type: {mean, std, min, max, ci_lower, ci_upper}}

    # Cost tracking (NEW)
    total_tokens = Column(Integer, default=0)
    total_cost_usd = Column(Float, default=0.0)
    judge_model = Column(Text, nullable=True)
    judge_call_count = Column(Integer, default=0)

    # Timing
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    metrics = relationship("EvaluationMetric", back_populates="evaluation_run", cascade="all, delete-orphan")
    query_results = relationship("EvaluationQueryResult", back_populates="evaluation_run", cascade="all, delete-orphan")
```

### 4.4 New: EvaluationQueryResult

Per-question results within a batch run.

```python
class EvaluationQueryResult(Base):
    __tablename__ = "evaluation_query_results"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    evaluation_run_id = Column(UUID, ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False)
    dataset_question_id = Column(UUID, ForeignKey("dataset_questions.id"), nullable=True)
    query = Column(Text, nullable=False)
    generated_answer = Column(Text, nullable=True)
    retrieved_chunk_ids = Column(JSON, nullable=True)
    retrieved_chunks_content = Column(JSON, nullable=True)  # For judge context
    citations = Column(JSON, nullable=True)                 # Citation markers and bindings
    latency_ms = Column(Float, nullable=True)
    error = Column(Text, nullable=True)

    per_question_metrics = relationship("EvaluationMetric", back_populates="query_result")
```

### 4.5 Modified: EvaluationMetric

Add statistical context and per-question support.

```python
class EvaluationMetric(Base):
    __tablename__ = "evaluation_metrics"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    evaluation_run_id = Column(UUID, ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False)
    query_result_id = Column(UUID, ForeignKey("evaluation_query_results.id"), nullable=True)  # NEW: null for aggregate
    metric_type = Column(SQLEnum(MetricType), nullable=False)
    metric_value = Column(Float, nullable=False)
    metric_metadata = Column(JSON, nullable=True)    # Changed from Text to JSON
    judge_reasoning = Column(Text, nullable=True)     # NEW: LLM judge's explanation
    created_at = Column(DateTime, default=datetime.utcnow)
```

### 4.6 New MetricType Values

```python
class MetricType(str, enum.Enum):
    # Retrieval (deterministic, no LLM needed)
    RECALL_AT_5 = "recall_at_5"
    RECALL_AT_10 = "recall_at_10"
    RECALL_AT_K = "recall_at_k"
    MRR = "mrr"
    PRECISION_AT_5 = "precision_at_5"       # NEW
    PRECISION_AT_10 = "precision_at_10"     # NEW
    HIT_RATE = "hit_rate"                    # NEW
    NDCG_AT_10 = "ndcg_at_10"               # NEW

    # Generation quality (LLM-as-judge)
    GROUNDEDNESS = "groundedness"
    COMPLETENESS = "completeness"
    FAITHFULNESS = "faithfulness"
    ANSWER_RELEVANCE = "answer_relevance"    # NEW

    # Citation quality (custom, core IP)
    CITATION_SUPPORT_RATE = "citation_support_rate"
    WRONG_CITATION_RATE = "wrong_citation_rate"
    CITATION_PRECISION = "citation_precision"       # NEW
    CITATION_RECALL = "citation_recall"             # NEW
    CITATION_GROUNDING = "citation_grounding"       # NEW
```

## 5. Metric Definitions

### 5.1 Retrieval Metrics (Deterministic — No LLM)

All computed via set intersection and ranking. Fast, free, reproducible.

| Metric | Formula | What it measures |
|--------|---------|-----------------|
| Recall@K | `\|relevant ∩ retrieved[:K]\| / \|relevant\|` | Coverage: did we find the right chunks? |
| Precision@K | `\|relevant ∩ retrieved[:K]\| / K` | Efficiency: how much noise in top-K? |
| MRR | `avg(1/rank_of_first_relevant)` | How high is the first good result? |
| Hit Rate | `fraction of queries with ≥1 relevant in top-K` | Basic effectiveness |
| NDCG@K | Normalized DCG accounting for position | Ranking quality considering graded relevance |

### 5.2 Generation Quality Metrics (LLM-as-Judge)

Each uses a structured prompt that returns a score (0-1) with reasoning.

**Faithfulness**: Decompose answer into atomic claims. For each claim, judge whether it's supported by the retrieved chunks, contradicted, or unverifiable.

```
Prompt structure:
- Input: question, answer, retrieved chunks
- Task: Extract claims, check each against chunks
- Output: {claims: [{claim, verdict: "supported"|"contradicted"|"unverifiable", evidence}], score: 0-1}
- Score = supported_claims / total_claims
```

**Groundedness**: Does the answer contain information not present in any retrieved chunk? Unlike faithfulness (which checks for contradictions), groundedness checks for additions.

```
Prompt structure:
- Input: answer, retrieved chunks
- Task: Identify sentences in the answer that are not grounded in any chunk
- Output: {ungrounded_sentences: [...], grounded_sentences: [...], score: 0-1}
- Score = grounded_sentences / total_sentences
```

**Completeness**: Does the answer address all aspects of the question? Requires understanding what a complete answer would contain.

```
Prompt structure:
- Input: question, answer, retrieved chunks (as reference for what's available)
- Task: List expected answer components, check which are covered
- Output: {expected_aspects: [...], covered_aspects: [...], score: 0-1}
- Score = covered_aspects / expected_aspects
```

**Answer Relevance**: Is the answer actually responsive to the question? (Distinct from completeness — an answer can be complete but contain irrelevant tangents.)

```
Prompt structure:
- Input: question, answer
- Task: Rate how directly the answer addresses the specific question asked
- Output: {relevance_score: 0-1, tangential_content: [...]}
```

### 5.3 Citation Quality Metrics (Custom — Core IP)

These are the novel contribution. No existing framework measures citation quality this way.

**Citation Precision**: Of the citations in the answer, what fraction actually support the claims they're attached to?

```python
citation_precision = supported_citations / total_citations
```

Evaluation method: For each citation marker `[N]` in the answer:
1. Extract the sentence/claim that the citation is attached to
2. Retrieve the cited chunk
3. Use LLM to judge: "Does this chunk support the specific claim it's cited for?"
4. Return supported/unsupported with reasoning

**Citation Recall**: Of the claims that *should* have a citation (statements derived from source material), what fraction actually have one?

```python
citation_recall = cited_source_claims / total_source_derived_claims
```

Evaluation method:
1. Identify all factual claims in the answer that appear to come from source material
2. Check which ones have citation markers
3. Score = cited / should_have_cited

**Citation Grounding Accuracy**: For cited claims, does the citation point to the *correct* chunk (not just any relevant chunk)?

```python
citation_grounding = correctly_routed_citations / total_citations
```

Evaluation method:
1. For each citation, identify the claim it supports
2. Check if the cited chunk is the *best* chunk for that claim (vs. other retrieved chunks)
3. This catches cases where the system cites a tangentially related chunk instead of the specific one

## 6. Synthetic Dataset Generation

### 6.1 Pipeline

```
Source chunks
→ Filter chunks with sufficient content (>100 tokens, has clear information)
→ For each chunk, generate 2-3 question-answer pairs via LLM
→ Include ground truth: chunk IDs, citation spans
→ Difficulty stratification:
    - Easy: Direct factual question answerable from one chunk
    - Medium: Requires synthesizing information from 2-3 chunks
    - Hard: Requires understanding nuance, comparing perspectives, or identifying what's NOT in the sources
→ Quality filter: Remove questions where the LLM's answer is too similar to the question
→ Store as EvaluationDataset with version tracking
```

### 6.2 Question Generation Prompt

```
Given this source text chunk:
---
{chunk_content}
---

Generate a question-answer pair that:
1. Is answerable primarily from this chunk
2. Requires understanding, not just copy-paste
3. Would be a realistic question a user would ask

Output format:
{
  "question": "...",
  "answer": "...",
  "difficulty": "easy|medium|hard",
  "key_facts": ["fact1", "fact2", ...]  // Facts that must appear in any correct answer
}
```

### 6.3 Quality Gate

After generation, filter out:
- Questions with <5 words
- Questions that are trivially answered by title/metadata alone
- Answers that are >80% identical to the source chunk (copy-paste)
- Questions where the answer is "yes" or "no" without requiring explanation

## 7. Two-Tier Evaluation System

### 7.1 Smoke Test (Fast, Cheap)

- **Dataset**: 5-10 questions (stratified by difficulty)
- **Judge**: Cheap model (GPT-4o-mini or equivalent)
- **Metrics**: Retrieval metrics only (free) + simplified faithfulness check
- **Runtime**: <30 seconds
- **Cost**: ~$0.01
- **Trigger**: Every code change to retrieval/generation pipeline

### 7.2 Full Regression Test

- **Dataset**: 50+ questions (full dataset)
- **Judge**: Strong model (GPT-4o or equivalent) for faithfulness/groundedness
- **Metrics**: All metrics including full citation evaluation
- **Runtime**: 3-5 minutes
- **Cost**: $0.50-$1.50
- **Trigger**: PR merge, nightly, or manual

### 7.3 Confidence Intervals

For full regression tests, run each metric evaluation 3 times with temperature > 0 on the judge, and report:
- Mean score
- Standard deviation
- 95% confidence interval (bootstrap with 1000 samples)

This is what makes the scores scientifically defensible in an interview.

## 8. Judge Calibration

Before trusting LLM-as-judge scores, establish human agreement baseline.

### 8.1 Calibration Dataset

- 30-50 examples across all metrics
- Each example: question + answer + retrieved chunks + human-labeled scores
- Stratified by score (include clearly good, clearly bad, and ambiguous examples)
- Created manually by the developer (this is a one-time investment)

### 8.2 Calibration Metrics

For each metric, measure judge vs. human agreement:
- **Continuous scores** (0-1): Spearman rank correlation (target: >0.85)
- **Binary judgments** (supported/unsupported): Cohen's kappa (target: >0.80)
- **Score distribution**: KS test for distributional shift

### 8.3 Calibration Cadence

- On initial setup: Full calibration
- On judge model change: Full calibration
- Monthly: Spot-check with 10 new examples

## 9. API Endpoints

### 9.1 Dataset Management

```
POST   /api/evaluation/datasets                    # Create dataset (manual or synthetic)
POST   /api/evaluation/datasets/{id}/generate      # Generate synthetic questions from notebook chunks
GET    /api/evaluation/datasets                    # List datasets for notebook
GET    /api/evaluation/datasets/{id}               # Get dataset with questions
PATCH  /api/evaluation/datasets/{id}               # Update dataset metadata
DELETE /api/evaluation/datasets/{id}               # Delete dataset
POST   /api/evaluation/datasets/{id}/questions     # Add questions manually
PATCH  /api/evaluation/datasets/questions/{qid}    # Update question
DELETE /api/evaluation/datasets/questions/{qid}    # Delete question
```

### 9.2 Evaluation Runs

```
POST   /api/evaluation/runs                        # Create run (specify dataset + config)
POST   /api/evaluation/runs/{id}/start             # Start execution
POST   /api/evaluation/runs/{id}/cancel            # Cancel running evaluation
GET    /api/evaluation/runs/{id}                   # Get run with summary
GET    /api/evaluation/runs/{id}/query-results     # Get per-question results
GET    /api/evaluation/runs/{id}/query-results/{qid}  # Get single question result with judge reasoning
GET    /api/evaluation/runs                        # List runs with filters
GET    /api/evaluation/runs/compare?run_ids=a,b    # Compare two runs side-by-side
GET    /api/evaluation/runs/trends?dataset_id=X    # Get metric trends over time for a dataset
GET    /api/evaluation/runs/{id}/export            # Export results as CSV
```

### 9.3 Dashboard Stats

```
GET    /api/evaluation/dashboard/summary           # Overview: dataset count, run count, latest scores
GET    /api/evaluation/dashboard/regressions       # Detected regressions (score drops beyond CI)
```

## 10. Frontend Changes

### 10.1 New Pages/Sections

1. **Datasets Tab**: Manage evaluation datasets, view questions, generate synthetic data
2. **Compare View**: Side-by-side comparison of two runs with metric diffs
3. **Trends View**: Time-series charts for each metric across runs on the same dataset
4. **Query Result Detail**: Drill into individual question results showing judge reasoning

### 10.2 Dashboard Enhancements

- Confidence intervals displayed alongside mean scores
- Cost tracking shown per run
- Regression indicators (red badge when scores drop beyond CI)
- Config snapshot diff when comparing runs

### 10.3 Demo Flow

The 5-minute interview demo:

1. **"Here's my knowledge base"** — Show notebook with sources
2. **"I generated a test dataset"** — Show 50 synthetic questions with ground truth
3. **"Here's the evaluation run"** — Show dashboard with metrics, CIs, cost
4. **"Citation precision is the novel metric"** — Drill into a citation evaluation showing judge reasoning
5. **"I tuned chunking and caught the regression"** — Show A/B comparison: Run A vs Run B, recall dropped from 0.87 to 0.74 after changing overlap
6. **"The trend view shows stability over time"** — Show trends chart

## 11. Implementation Plan

### Phase 1: Data Model & Dataset Management
- Database migration for new tables (EvaluationDataset, DatasetQuestion, EvaluationQueryResult)
- Modify EvaluationRun and EvaluationMetric schemas
- Dataset CRUD API endpoints
- Synthetic question generation pipeline
- Frontend dataset management tab

### Phase 2: LLM-as-Judge Evaluators
- Replace heuristic evaluators with LLM-based implementations
- Implement structured judge prompts for faithfulness, groundedness, completeness
- Add judge reasoning storage in EvaluationMetric
- Add new retrieval metrics (precision@K, hit_rate, NDCG)
- Judge calibration pipeline with human-labeling workflow

### Phase 3: Citation Evaluation (Core IP)
- Citation precision evaluator with per-citation judge reasoning
- Citation recall evaluator
- Citation grounding accuracy evaluator
- Claim extraction from answers
- Claim-to-chunk alignment algorithm

### Phase 4: Batch Execution & Aggregation
- Run orchestrator for batch evaluation (50+ questions)
- Statistical aggregation (mean, std, CI)
- Cost tracking (token counting, cost estimation)
- Two-tier system (smoke test + full regression)
- SSE progress streaming for long-running evaluations

### Phase 5: Trend Tracking & Comparison
- Trends API and time-series chart
- A/B comparison view with metric diffs
- Regression detection (score drop beyond CI)
- Config snapshot diffing
- CSV/JSON export with full per-question data

## 12. Interview Talking Points

### For "Tell me about your evaluation system":

> "I built a citation-first evaluation framework for a RAG knowledge base. The key insight was that no existing tool — RAGAS, TruLens, DeepEval — evaluates whether citations actually support the claims they're attached to. So I designed three novel citation metrics: citation precision, citation recall, and citation grounding accuracy. These use LLM-as-judge to evaluate each citation-claim pair individually, with explainable reasoning stored for every score."

### For "Why not use RAGAS?":

> "I evaluated RAGAS carefully. Their faithfulness metric uses claim decomposition which is good, but they have no concept of citation binding — the core feature of our product. RAGAS can tell you if an answer is faithful to retrieved chunks, but it can't tell you if citation [3] actually supports the sentence it's attached to. That's the gap I filled. For standard metrics, I use the same patterns RAGAS established. For citation metrics, I built custom."

### For "How do you validate the judge?":

> "I maintain a calibration set of 30-50 human-labeled examples. For each metric, I measure Spearman correlation between the judge and human labels. My threshold is >0.85 correlation. I re-calibrate whenever I change the judge model. I also run each evaluation 3 times and report 95% confidence intervals via bootstrap, so I can distinguish real improvements from judge variance."

### For "Walk me through a regression you caught":

> "I increased chunking overlap from 50 to 100 tokens to improve recall. The smoke test showed recall@10 went up from 0.82 to 0.91. But the full regression test showed citation grounding accuracy dropped from 0.88 to 0.71 — the larger overlap meant the system was citing bigger chunks that were only partially relevant. I reverted the overlap change and instead improved the retrieval scoring to prefer more specific chunks."

## 13. Cost Model

| Tier | Questions | Judge Calls | Tokens | Est. Cost |
|------|-----------|-------------|--------|-----------|
| Smoke | 5-10 | 20-40 | 10-20K | $0.01-0.03 |
| Full | 50+ | 400-500 | 200-500K | $0.50-1.50 |
| With CI (3x) | 50+ | 1200-1500 | 600K-1.5M | $1.50-4.50 |

Monthly estimate with daily smoke + weekly full: ~$5-10/month

## 14. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Judge-human agreement <0.85 | Medium | High | Iterate on prompts, add few-shot examples, try different judge models |
| Synthetic questions too easy | High | Medium | Hard question generation via multi-chunk synthesis, adversarial questions |
| Data model migration breaks existing eval data | Low | High | Migration script copies old runs to new schema, keeps old tables during transition |
| Cost exceeds budget | Low | Low | Two-tier system with caching, budget alerts |
| Demo doesn't tell a compelling story | Medium | High | Prepare specific before/after examples, rehearse narrative |

## 15. Success Criteria

1. **Technical**: All metric scores have confidence intervals. Judge-human agreement >0.85 on calibration set. Citation metrics produce meaningful differentiation between good and bad answers.
2. **Interview-ready**: Can demo the full system in 5 minutes with a clear "I caught this regression" story. Can explain every architectural decision.
3. **Production-viable**: Smoke test runs in <30 seconds. Full regression in <5 minutes. Cost < $10/month for regular use.
4. **Novel contribution**: Citation precision, citation recall, and citation grounding accuracy are metrics that don't exist in any off-the-shelf framework.
