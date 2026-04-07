#!/usr/bin/env python3
"""
Evaluate batch RAG test results and generate metrics.

This script loads batch test results, calculates evaluation metrics,
and generates tables for aggregate reporting.
"""
import json
from typing import Dict, List, Any
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EvalMetrics:
    """Evaluation metrics for a test or aggregate."""
    total_tests: int
    successful_tests: int
    failed_tests: int
    success_rate: float
    avg_time: float
    avg_chunks_retrieved: float
    recall_at_k: float
    mrr: float
    citation_accuracy: float
    answer_quality: float


def load_batch_results(results_path: str) -> Dict:
    """Load batch test results from JSON file."""
    with open(results_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_dataset(dataset_path: str) -> Dict:
    """Load test dataset from JSON file."""
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


def calculate_recall_at_k(
    retrieved_chunk_ids: List[str],
    expected_chunk_ids: List[str],
    k: int = 10,
) -> float:
    """
    Calculate Recall@K metric.

    Recall@K = |{relevant docs} ∩ {retrieved docs}| / |{relevant docs}|

    Args:
        retrieved_chunk_ids: List of retrieved chunk IDs
        expected_chunk_ids: List of expected (relevant) chunk IDs
        k: Consider top-K results

    Returns:
        Recall score between 0 and 1
    """
    if not expected_chunk_ids:
        return 1.0  # No relevant docs = perfect recall

    retrieved_k = set(retrieved_chunk_ids[:k])
    expected_set = set(expected_chunk_ids)

    hits = len(retrieved_k & expected_set)
    return hits / len(expected_set)


def calculate_mrr(
    retrieved_chunk_ids: List[str],
    expected_chunk_ids: List[str],
) -> float:
    """
    Calculate Mean Reciprocal Rank.

    MRR = 1 / rank_of_first_relevant_doc

    Args:
        retrieved_chunk_ids: List of retrieved chunk IDs (ranked)
        expected_chunk_ids: List of expected chunk IDs

    Returns:
        MRR score between 0 and 1
    """
    if not expected_chunk_ids:
        return 1.0

    expected_set = set(expected_chunk_ids)

    for i, chunk_id in enumerate(retrieved_chunk_ids, 1):
        if chunk_id in expected_set:
            return 1.0 / i

    return 0.0  # No relevant docs found


def calculate_citation_accuracy(
    citation_indices: List[int],
    retrieved_chunks: List[Dict],
    expected_chunks: List[str],
) -> float:
    """
    Calculate citation accuracy percentage.

    Checks if cited chunks match expected chunks.

    Args:
        citation_indices: Citation marker positions
        retrieved_chunks: All retrieved chunks
        expected_chunks: Expected chunk IDs

    Returns:
        Accuracy percentage (0-100)
    """
    if not citation_indices:
        return 0.0

    # Get chunk IDs for citations
    cited_chunk_ids = [
        retrieved_chunks[i].get("chunk_id")
        for i in citation_indices
        if i < len(retrieved_chunks)
    ]

    # Count how many are in expected set
    expected_set = set(expected_chunks)
    correct = sum(1 for cid in cited_chunk_ids if cid in expected_set)

    return (correct / len(cited_chunk_ids)) * 100 if cited_chunk_ids else 0.0


def evaluate_single_test(
    test_result: Dict,
    test_case: Dict,
) -> Dict:
    """
    Evaluate a single test result against expected outcomes.

    Args:
        test_result: Result from batch_test.py
        test_case: Original test case with expected chunks

    Returns:
        Dict with evaluation metrics
    """
    retrieved_chunk_ids = [
        c.get("chunk_id")
        for c in test_result.get("retrieved_chunks", [])
    ]
    expected_chunk_ids = test_case.get("expected_chunks", [])

    recall_at_k = calculate_recall_at_k(
        retrieved_chunk_ids,
        expected_chunk_ids,
        k=len(retrieved_chunk_ids),
    )
    mrr = calculate_mrr(retrieved_chunk_ids, expected_chunk_ids)

    citation_accuracy = calculate_citation_accuracy(
        test_result.get("citation_indices", []),
        test_result.get("retrieved_chunks", []),
        expected_chunk_ids,
    )

    return {
        "test_id": test_result.get("test_id"),
        "question": test_result.get("question"),
        "success": test_result.get("success", False),
        "total_time": test_result.get("total_time", 0),
        "chunks_retrieved": len(retrieved_chunk_ids),
        "expected_chunks": len(expected_chunk_ids),
        "recall_at_k": recall_at_k,
        "mrr": mrr,
        "citation_accuracy": citation_accuracy,
        "has_answer": bool(test_result.get("answer")),
    }


def evaluate_batch_results(
    results_path: str,
    dataset_path: str,
) -> Dict:
    """
    Evaluate batch test results against dataset expectations.

    Args:
        results_path: Path to batch test results JSON
        dataset_path: Path to original test dataset

    Returns:
        Dict with aggregate metrics and per-test results
    """
    results = load_batch_results(results_path)
    dataset = load_dataset(dataset_path)

    # Map test cases by ID for lookup
    test_cases_by_id = {
        tc.get("id", f"test-{i}"): tc
        for i, tc in enumerate(dataset.get("test_cases", []))
    }

    # Evaluate each test
    evaluations = []
    for result in results.get("results", []):
        test_id = result.get("test_id")
        test_case = test_cases_by_id.get(test_id, {})

        eval_result = evaluate_single_test(result, test_case)
        evaluations.append(eval_result)

    # Calculate aggregate metrics
    successful_evals = [e for e in evaluations if e["success"]]

    if not successful_evals:
        return {
            "total_tests": len(evaluations),
            "successful_tests": 0,
            "aggregate_metrics": None,
            "per_test_results": evaluations,
        }

    avg_recall = sum(e["recall_at_k"] for e in successful_evals) / len(successful_evals)
    avg_mrr = sum(e["mrr"] for e in successful_evals) / len(successful_evals)
    avg_citation_acc = sum(e["citation_accuracy"] for e in successful_evals) / len(successful_evals)
    avg_time = sum(e["total_time"] for e in successful_evals) / len(successful_evals)
    avg_chunks = sum(e["chunks_retrieved"] for e in successful_evals) / len(successful_evals)

    return {
        "total_tests": len(evaluations),
        "successful_tests": len(successful_evals),
        "failed_tests": len(evaluations) - len(successful_evals),
        "success_rate": len(successful_evals) / len(evaluations),
        "aggregate_metrics": {
            "avg_recall_at_k": avg_recall,
            "avg_mrr": avg_mrr,
            "avg_citation_accuracy": avg_citation_acc,
            "avg_time": avg_time,
            "avg_chunks_retrieved": avg_chunks,
        },
        "per_test_results": evaluations,
    }


def generate_results_table(evaluations: List[Dict]) -> str:
    """
    Generate markdown table from evaluation results.

    Args:
        evaluations: List of evaluation dicts

    Returns:
        Markdown table string
    """
    lines = [
        "| Test ID | Question | Success | Recall@K | MRR | Citation Acc | Time | Chunks |",
        "|---------|----------|---------|----------|-----|--------------|------|--------|",
    ]

    for e in evaluations:
        question_short = e["question"][:40] + "..." if len(e["question"]) > 40 else e["question"]
        status = "✓" if e["success"] else "✗"

        lines.append(
            f"| {e['test_id']} | {question_short} | {status} | "
            f"{e['recall_at_k']:.2f} | {e['mrr']:.2f} | "
            f"{e['citation_accuracy']:.1f}% | {e['total_time']:.2f}s | "
            f"{e['chunks_retrieved']} |"
        )

    return "\n".join(lines)


def generate_summary_report(evaluation: Dict) -> str:
    """
    Generate summary markdown report from evaluation.

    Args:
        evaluation: Evaluation dict from evaluate_batch_results

    Returns:
        Markdown summary string
    """
    metrics = evaluation.get("aggregate_metrics", {})

    if not metrics:
        return "**No successful tests to evaluate.**"

    lines = [
        "## Evaluation Summary",
        "",
        f"**Total Tests**: {evaluation['total_tests']}",
        f"**Successful**: {evaluation['successful_tests']}",
        f"**Failed**: {evaluation['failed_tests']}",
        f"**Success Rate**: {evaluation['success_rate']:.1%}",
        "",
        "### Aggregate Metrics",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| **Avg Recall@K** | {metrics['avg_recall_at_k']:.3f} |",
        f"| **Avg MRR** | {metrics['avg_mrr']:.3f} |",
        f"| **Avg Citation Accuracy** | {metrics['avg_citation_accuracy']:.1f}% |",
        f"| **Avg Response Time** | {metrics['avg_time']:.2f}s |",
        f"| **Avg Chunks Retrieved** | {metrics['avg_chunks_retrieved']:.1f} |",
        "",
    ]

    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python evaluate_batch.py <results.json> <dataset.json>")
        sys.exit(1)

    results_path = sys.argv[1]
    dataset_path = sys.argv[2]

    evaluation = evaluate_batch_results(results_path, dataset_path)

    print(generate_summary_report(evaluation))
    print("\n## Per-Test Results\n")
    print(generate_results_table(evaluation["per_test_results"]))
