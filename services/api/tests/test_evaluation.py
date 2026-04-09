"""
Tests for evaluation API endpoints and logic.

Feature 6.3: Evaluation Dashboard
All tests based on acceptance criteria from DEVELOPMENT_PLAN.md
"""
import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from services.api.modules.evaluation.models import (
    EvaluationRun,
    EvaluationMetric,
    EvaluationStatus,
    MetricType,
)
from services.api.modules.evaluation.service import (
    RetrievalEvaluator,
    CitationEvaluator,
    AnswerQualityEvaluator,
)
from services.api.modules.evaluation.schemas import EvaluationCreate


class TestCreateEvaluation:
    """Tests for POST /api/evaluation/runs endpoint."""

    def test_create_evaluation_with_valid_data(
        self,
        client: TestClient,
        sample_notebook,
    ):
        """
        AC: Create evaluation with valid data
        """
        response = client.post(
            "/api/evaluation/runs",
            json={
                "notebook_id": str(sample_notebook.id),
                "query": "What is machine learning?",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["notebook_id"] == str(sample_notebook.id)
        assert data["query"] == "What is machine learning?"
        assert data["status"] == "pending"
        assert "id" in data
        assert "created_at" in data

    def test_create_evaluation_with_ground_truth_chunks(
        self,
        client: TestClient,
        sample_notebook,
    ):
        """
        AC: Create evaluation with ground truth chunk IDs
        """
        ground_truth_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        response = client.post(
            "/api/evaluation/runs",
            json={
                "notebook_id": str(sample_notebook.id),
                "query": "Test question",
                "ground_truth_chunk_ids": ground_truth_ids,
            },
        )
        assert response.status_code == 201

    def test_create_evaluation_fails_for_nonexistent_notebook(
        self,
        client: TestClient,
    ):
        """
        AC: Return 404 for nonexistent notebook
        """
        response = client.post(
            "/api/evaluation/runs",
            json={
                "notebook_id": str(uuid.uuid4()),
                "query": "Test question",
            },
        )
        assert response.status_code == 404
        assert "not_found" in response.json()["detail"]["error"]

    def test_create_evaluation_validates_query_length(
        self,
        client: TestClient,
        sample_notebook,
    ):
        """
        AC: Validate query length (min 1, max 1000)
        """
        # Empty query should fail
        response = client.post(
            "/api/evaluation/runs",
            json={
                "notebook_id": str(sample_notebook.id),
                "query": "",
            },
        )
        assert response.status_code == 422  # Validation error


class TestGetEvaluation:
    """Tests for GET /api/evaluation/runs/{id} endpoint."""

    def test_get_evaluation_by_id(
        self,
        db: Session,
        client: TestClient,
        sample_user,
        sample_notebook,
    ):
        """
        AC: Get single evaluation by ID with all metadata
        """
        # Create an evaluation run
        evaluation = EvaluationRun(
            notebook_id=sample_notebook.id,
            query="Test query",
            status=EvaluationStatus.COMPLETED,
        )
        db.add(evaluation)
        db.commit()
        db.refresh(evaluation)

        response = client.get(f"/api/evaluation/runs/{evaluation.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(evaluation.id)
        assert data["query"] == "Test query"
        assert data["status"] == "completed"
        assert "metrics" in data

    def test_get_evaluation_includes_metrics(
        self,
        db: Session,
        client: TestClient,
        sample_user,
        sample_notebook,
    ):
        """
        AC: Get evaluation includes associated metrics
        """
        # Create evaluation run with metrics
        evaluation = EvaluationRun(
            notebook_id=sample_notebook.id,
            query="Test query",
            status=EvaluationStatus.COMPLETED,
        )
        db.add(evaluation)
        db.commit()
        db.refresh(evaluation)

        metric = EvaluationMetric(
            evaluation_run_id=evaluation.id,
            metric_type=MetricType.RECALL_AT_K,
            metric_value=0.8,
        )
        db.add(metric)
        db.commit()

        response = client.get(f"/api/evaluation/runs/{evaluation.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["metrics"]) == 1
        assert data["metrics"][0]["metric_type"] == "recall_at_k"
        assert data["metrics"][0]["metric_value"] == 0.8

    def test_get_evaluation_returns_404_for_nonexistent(
        self,
        client: TestClient,
    ):
        """
        AC: Return 404 for nonexistent evaluation
        """
        response = client.get(f"/api/evaluation/runs/{uuid.uuid4()}")
        assert response.status_code == 404


class TestStartEvaluation:
    """Tests for POST /api/evaluation/runs/{id}/start endpoint."""

    def test_start_evaluation_persists_retrieval_metrics_for_ground_truth_chunks(
        self,
        db: Session,
        client: TestClient,
        sample_notebook,
        sample_source,
    ):
        """
        AC: Track retrieval metrics: recall@5, recall@10, MRR
        Repro: runs created with ground-truth chunks must expose metrics after start
        """
        from services.api.modules.chunking.models import SourceChunk

        chunk_one = SourceChunk(
            source_id=sample_source.id,
            chunk_index=0,
            content="Difficult people management requires calm listening and clear boundaries.",
            token_count=10,
            char_start=0,
            char_end=78,
            chunk_metadata={"page": 1},
        )
        chunk_two = SourceChunk(
            source_id=sample_source.id,
            chunk_index=1,
            content="Managers should document behavior patterns and agree on next steps.",
            token_count=10,
            char_start=79,
            char_end=152,
            chunk_metadata={"page": 1},
        )
        db.add_all([chunk_one, chunk_two])
        db.commit()
        db.refresh(chunk_one)
        db.refresh(chunk_two)

        create_response = client.post(
            "/api/evaluation/runs",
            json={
                "notebook_id": str(sample_notebook.id),
                "query": "difficult people management",
                "ground_truth_chunk_ids": [str(chunk_one.id), str(chunk_two.id)],
            },
        )

        assert create_response.status_code == 201
        run_id = create_response.json()["id"]

        start_response = client.post(f"/api/evaluation/runs/{run_id}/start")
        assert start_response.status_code == 200
        assert start_response.json()["status"] == "completed"

        detail_response = client.get(f"/api/evaluation/runs/{run_id}")
        assert detail_response.status_code == 200
        detail_data = detail_response.json()
        metric_types = {metric["metric_type"] for metric in detail_data["metrics"]}
        assert {"recall_at_5", "recall_at_10", "mrr"} <= metric_types

        list_response = client.get(
            f"/api/evaluation/runs?notebook_id={sample_notebook.id}"
        )
        assert list_response.status_code == 200
        list_data = list_response.json()
        assert "recall_at_5" in list_data["summary"]
        assert "recall_at_10" in list_data["summary"]
        assert "mrr" in list_data["summary"]


class TestListEvaluations:
    """Tests for GET /api/evaluation/runs endpoint."""

    def test_list_evaluations_for_notebook(
        self,
        db: Session,
        client: TestClient,
        sample_user,
        sample_notebook,
    ):
        """
        AC: Filterable by notebook
        """
        # Create multiple evaluations
        for i in range(3):
            evaluation = EvaluationRun(
                notebook_id=sample_notebook.id,
                query=f"Test query {i}",
                status=EvaluationStatus.COMPLETED,
            )
            db.add(evaluation)
        db.commit()

        response = client.get(
            f"/api/evaluation/runs?notebook_id={sample_notebook.id}"
        )
        assert response.status_code == 200
        data = response.json()
        assert "evaluation_runs" in data
        assert len(data["evaluation_runs"]) == 3

    def test_list_evaluations_filters_by_time_range(
        self,
        db: Session,
        client: TestClient,
        sample_user,
        sample_notebook,
    ):
        """
        AC: Filterable by time range
        """
        now = datetime.utcnow()

        # Create old evaluation
        old_evaluation = EvaluationRun(
            notebook_id=sample_notebook.id,
            query="Old query",
            status=EvaluationStatus.COMPLETED,
            created_at=now - timedelta(days=10),
        )
        db.add(old_evaluation)

        # Create recent evaluation
        recent_evaluation = EvaluationRun(
            notebook_id=sample_notebook.id,
            query="Recent query",
            status=EvaluationStatus.COMPLETED,
            created_at=now - timedelta(days=1),
        )
        db.add(recent_evaluation)
        db.commit()

        # Filter by start date
        start_date = (now - timedelta(days=5)).isoformat()
        response = client.get(
            f"/api/evaluation/runs?start_date={start_date}"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["evaluation_runs"]) == 1
        assert data["evaluation_runs"][0]["query"] == "Recent query"

    def test_list_evaluations_includes_summary(
        self,
        db: Session,
        client: TestClient,
        sample_user,
        sample_notebook,
    ):
        """
        AC: Dashboard shows trends over time (summary metrics)
        """
        # Create evaluation with metrics
        evaluation = EvaluationRun(
            notebook_id=sample_notebook.id,
            query="Test query",
            status=EvaluationStatus.COMPLETED,
        )
        db.add(evaluation)
        db.commit()
        db.refresh(evaluation)

        # Add metrics
        for i, value in enumerate([0.7, 0.8, 0.9]):
            metric = EvaluationMetric(
                evaluation_run_id=evaluation.id,
                metric_type=list(MetricType)[i],
                metric_value=value,
            )
            db.add(metric)
        db.commit()

        response = client.get(f"/api/evaluation/runs?notebook_id={sample_notebook.id}")
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert len(data["summary"]) > 0


class TestRetrievalMetrics:
    """Tests for retrieval metric calculations."""

    def test_calculate_recall_at_k_with_perfect_retrieval(
        self,
    ):
        """
        AC: Track retrieval metrics: recall@5, recall@10
        Test perfect retrieval (all relevant chunks in top K)
        """
        retrieved = [uuid.uuid4() for _ in range(10)]
        ground_truth = retrieved[:5]  # First 5 are relevant

        recall_5 = RetrievalEvaluator.calculate_recall_at_k(
            retrieved, ground_truth, k=5
        )
        recall_10 = RetrievalEvaluator.calculate_recall_at_k(
            retrieved, ground_truth, k=10
        )

        assert recall_5 == 1.0  # All 5 relevant in top 5
        assert recall_10 == 1.0  # All 5 relevant in top 10

    def test_calculate_recall_at_k_with_partial_retrieval(
        self,
    ):
        """
        AC: Track retrieval metrics: recall@5, recall@10
        Test partial retrieval (some relevant chunks not in top K)
        """
        relevant_chunks = [uuid.uuid4() for _ in range(5)]
        irrelevant_chunks = [uuid.uuid4() for _ in range(5)]

        # Retrieved: 2 relevant, then 3 irrelevant, then 3 more relevant
        retrieved = (
            relevant_chunks[:2] + irrelevant_chunks[:3] + relevant_chunks[2:]
        )

        recall_5 = RetrievalEvaluator.calculate_recall_at_k(
            retrieved, relevant_chunks, k=5
        )

        # Top 5 has 2 relevant chunks out of 5 total relevant
        assert recall_5 == 0.4

    def test_calculate_recall_at_k_with_no_relevant_found(
        self,
    ):
        """
        AC: Track retrieval metrics: recall@5, recall@10
        Test case where no relevant chunks are retrieved
        """
        retrieved = [uuid.uuid4() for _ in range(10)]
        ground_truth = [uuid.uuid4() for _ in range(5)]

        recall_5 = RetrievalEvaluator.calculate_recall_at_k(
            retrieved, ground_truth, k=5
        )

        assert recall_5 == 0.0

    def test_calculate_mrr(
        self,
    ):
        """
        AC: Track retrieval metrics: MRR
        Test Mean Reciprocal Rank calculation
        """
        # Query 1: First relevant at rank 1 -> 1/1 = 1.0
        # Query 2: First relevant at rank 3 -> 1/3 = 0.333
        # Query 3: First relevant at rank 5 -> 1/5 = 0.2

        retrieved_list = [
            [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()],  # Will set ground truth
            [uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()],
            [uuid.uuid4() for _ in range(10)],
        ]

        ground_truth_list = [
            [retrieved_list[0][0]],  # First result is relevant
            [retrieved_list[1][2]],  # Third result is relevant
            [retrieved_list[2][4]],  # Fifth result is relevant
        ]

        mrr = RetrievalEvaluator.calculate_mrr(
            retrieved_list, ground_truth_list
        )

        expected_mrr = (1.0 + 1/3 + 1/5) / 3
        assert abs(mrr - expected_mrr) < 0.01

    def test_calculate_mrr_with_no_relevant_found(
        self,
    ):
        """
        AC: Track retrieval metrics: MRR
        Test MRR when no relevant chunks are found
        """
        retrieved_list = [
            [uuid.uuid4() for _ in range(10)],
            [uuid.uuid4() for _ in range(10)],
        ]

        ground_truth_list = [
            [uuid.uuid4()],  # Not in retrieved
            [uuid.uuid4()],  # Not in retrieved
        ]

        mrr = RetrievalEvaluator.calculate_mrr(
            retrieved_list, ground_truth_list
        )

        assert mrr == 0.0


class TestCitationMetrics:
    """Tests for citation metric calculations."""

    def test_evaluate_citations_with_support(
        self,
    ):
        """
        AC: Track citation metrics: support rate, wrong citation rate
        Test citation support rate when chunks support the answer
        """
        answer = "Machine learning is a subset of artificial intelligence"
        chunks = [
            {"content": "Machine learning is a subset of AI that focuses on algorithms"},
            {"content": "Artificial intelligence includes machine learning and deep learning"},
        ]

        support_rate, wrong_rate = CitationEvaluator.evaluate_citations(
            answer, chunks, [0, 1]
        )

        # Should have high support rate since keywords match
        assert support_rate > 0.5
        assert wrong_rate < 0.5

    def test_evaluate_citations_with_wrong_citations(
        self,
    ):
        """
        AC: Track citation metrics: support rate, wrong citation rate
        Test wrong citation rate when chunks don't support the answer
        """
        answer = "Quantum computing uses qubits instead of classical bits"
        chunks = [
            {"content": "Traditional computers use binary digits or bits"},
            {"content": "Bits can be either 0 or 1 in classical computing"},
        ]

        support_rate, wrong_rate = CitationEvaluator.evaluate_citations(
            answer, chunks, [0, 1]
        )

        # Should have low or mixed support rate since keywords don't match well
        assert support_rate <= 0.5
        assert wrong_rate >= 0.5

    def test_evaluate_citations_with_empty_list(
        self,
    ):
        """
        AC: Track citation metrics: support rate, wrong citation rate
        Test edge case with no citations
        """
        support_rate, wrong_rate = CitationEvaluator.evaluate_citations(
            "Test answer", [], []
        )

        # No citations to evaluate
        assert support_rate == 1.0
        assert wrong_rate == 0.0


class TestAnswerQualityMetrics:
    """Tests for answer quality metric calculations."""

    def test_evaluate_groundedness_with_grounded_answer(
        self,
    ):
        """
        AC: Track answer quality: groundedness, completeness, faithfulness
        Test groundedness when answer comes from source content
        """
        answer = "Machine learning models learn patterns from data to make predictions"
        chunks = [
            {"content": "Machine learning models learn patterns from data"},
            {"content": "These models can make predictions based on training data"},
        ]

        groundedness = AnswerQualityEvaluator.evaluate_groundedness(
            answer, chunks
        )

        # Should have high groundedness since answer words come from chunks
        assert groundedness > 0.5

    def test_evaluate_groundedness_with_ungrounded_answer(
        self,
    ):
        """
        AC: Track answer quality: groundedness, completeness, faithfulness
        Test groundedness when answer has content not from sources
        """
        answer = "According to recent research in 2025, quantum entanglement enables instant communication"
        chunks = [
            {"content": "Quantum physics studies subatomic particles"},
            {"content": "Entanglement is a quantum phenomenon"},
        ]

        groundedness = AnswerQualityEvaluator.evaluate_groundedness(
            answer, chunks
        )

        # Should have lower groundedness since answer introduces new concepts
        assert groundedness < 0.5

    def test_evaluate_completeness_with_complete_answer(
        self,
    ):
        """
        AC: Track answer quality: groundedness, completeness, faithfulness
        Test completeness when answer fully addresses question
        """
        question = "What is machine learning?"
        answer = """Machine learning is a subset of artificial intelligence that focuses on
        developing algorithms that can learn from data. These algorithms improve their
        performance through experience without being explicitly programmed for each task.
        They identify patterns in training data and use them to make predictions or decisions."""

        completeness = AnswerQualityEvaluator.evaluate_completeness(
            answer, question
        )

        # Should have high completeness since answer is comprehensive
        assert completeness == 1.0

    def test_evaluate_completeness_with_incomplete_answer(
        self,
    ):
        """
        AC: Track answer quality: groundedness, completeness, faithfulness
        Test completeness when answer is too brief
        """
        question = "What is machine learning and how does it work?"
        answer = "ML is AI."

        completeness = AnswerQualityEvaluator.evaluate_completeness(
            answer, question
        )

        # Should have lower completeness since answer is too short
        assert completeness < 1.0

    def test_evaluate_faithfulness_with_faithful_answer(
        self,
    ):
        """
        AC: Track answer quality: groundedness, completeness, faithfulness
        Test faithfulness when answer doesn't contradict sources
        """
        answer = "Machine learning models can be trained on various datasets"
        chunks = [
            {"content": "Machine learning models can be trained on various datasets"},
        ]

        faithfulness = AnswerQualityEvaluator.evaluate_faithfulness(
            answer, chunks
        )

        # Should have high faithfulness
        assert faithfulness > 0.7

    def test_evaluate_faithfulness_with_potential_contradiction(
        self,
    ):
        """
        AC: Track answer quality: groundedness, completeness, faithfulness
        Test faithfulness when answer might contradict sources
        """
        answer = "Machine learning models always achieve 100% accuracy. However, this is not true in practice."
        chunks = [
            {"content": "Machine learning models rarely achieve perfect accuracy"},
        ]

        faithfulness = AnswerQualityEvaluator.evaluate_faithfulness(
            answer, chunks
        )

        # Should detect potential contradiction
        assert faithfulness < 1.0


class TestExportMetricsCSV:
    """Tests for CSV export functionality."""

    def test_export_metrics_as_csv(
        self,
        db: Session,
        client: TestClient,
        sample_user,
        sample_notebook,
    ):
        """
        AC: Export metrics as CSV
        """
        # Create evaluation with metrics
        evaluation = EvaluationRun(
            notebook_id=sample_notebook.id,
            query="Test query",
            status=EvaluationStatus.COMPLETED,
        )
        db.add(evaluation)
        db.commit()
        db.refresh(evaluation)

        metric = EvaluationMetric(
            evaluation_run_id=evaluation.id,
            metric_type=MetricType.RECALL_AT_K,
            metric_value=0.8,
        )
        db.add(metric)
        db.commit()

        response = client.get("/api/evaluation/metrics/export")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "attachment" in response.headers["content-disposition"]

        # Verify CSV content
        csv_content = response.content.decode()
        assert "run_id" in csv_content
        assert "metric_type" in csv_content
        assert "metric_value" in csv_content

    def test_export_filters_by_notebook(
        self,
        db: Session,
        client: TestClient,
        sample_user,
        sample_notebook,
    ):
        """
        AC: Export filters by notebook
        """
        # Create evaluation
        evaluation = EvaluationRun(
            notebook_id=sample_notebook.id,
            query="Test query",
            status=EvaluationStatus.COMPLETED,
        )
        db.add(evaluation)
        db.commit()
        db.refresh(evaluation)

        # Add a metric to ensure data appears in CSV
        metric = EvaluationMetric(
            evaluation_run_id=evaluation.id,
            metric_type=MetricType.RECALL_AT_K,
            metric_value=0.8,
        )
        db.add(metric)
        db.commit()

        response = client.get(
            f"/api/evaluation/metrics/export?notebook_id={sample_notebook.id}"
        )
        assert response.status_code == 200

        csv_content = response.content.decode()
        assert str(sample_notebook.id) in csv_content
