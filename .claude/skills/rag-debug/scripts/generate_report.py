#!/usr/bin/env python3
"""
Generate RAG evaluation report from batch test results.

This script creates a comprehensive markdown report including
metrics tables, per-test results, and recommendations.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


def load_template(template_path: str) -> str:
    """Load report template from file."""
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


def load_evaluation(evaluation_path: str) -> Dict:
    """Load evaluation results from JSON."""
    with open(evaluation_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_results(results_path: str) -> Dict:
    """Load batch test results from JSON."""
    with open(results_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_dataset(dataset_path: str) -> Dict:
    """Load test dataset from JSON."""
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_results_table(evaluations: List[Dict]) -> str:
    """Generate markdown table of per-test results."""
    lines = [
        "| Test ID | Question | Success | Recall@K | MRR | Citation Acc | Time (s) | Chunks |",
        "|---------|----------|---------|----------|-----|--------------|----------|--------|",
    ]

    for e in evaluations:
        # Truncate question for table
        question = e["question"]
        if len(question) > 35:
            question = question[:32] + "..."

        status = "✓" if e["success"] else "✗"

        lines.append(
            f"| {e['test_id']} | {question} | {status} | "
            f"{e['recall_at_k']:.2f} | {e['mrr']:.2f} | "
            f"{e['citation_accuracy']:.1f}% | {e['total_time']:.2f} | "
            f"{e['chunks_retrieved']} |"
        )

    return "\n".join(lines)


def generate_category_breakdown(evaluations: List[Dict], dataset: Dict) -> str:
    """Generate breakdown by test category."""
    # Group by category
    by_category = {}

    for eval_result in evaluations:
        test_id = eval_result["test_id"]

        # Find corresponding test case
        test_case = next(
            (tc for tc in dataset.get("test_cases", []) if tc.get("id") == test_id),
            None
        )

        if not test_case:
            continue

        category = test_case.get("category", "other")

        if category not in by_category:
            by_category[category] = {
                "count": 0,
                "recall_sum": 0,
                "mrr_sum": 0,
                "time_sum": 0,
            }

        if eval_result["success"]:
            by_category[category]["count"] += 1
            by_category[category]["recall_sum"] += eval_result["recall_at_k"]
            by_category[category]["mrr_sum"] += eval_result["mrr"]
            by_category[category]["time_sum"] += eval_result["total_time"]

    # Generate table
    lines = [
        "### Performance by Category",
        "",
        "| Category | Count | Avg Recall | Avg MRR | Avg Time |",
        "|----------|-------|------------|---------|----------|",
    ]

    for category, stats in sorted(by_category.items()):
        count = stats["count"]
        if count > 0:
            avg_recall = stats["recall_sum"] / count
            avg_mrr = stats["mrr_sum"] / count
            avg_time = stats["time_sum"] / count

            lines.append(
                f"| {category} | {count} | {avg_recall:.3f} | {avg_mrr:.3f} | {avg_time:.2f}s |"
            )

    return "\n".join(lines)


def generate_failed_tests(evaluations: List[Dict]) -> str:
    """Generate section for failed tests."""
    failed = [e for e in evaluations if not e["success"]]

    if not failed:
        return "### Failed Tests\n\nNone ✅"

    lines = [
        "### Failed Tests",
        "",
        "| Test ID | Question | Error |",
        "|---------|----------|-------|",
    ]

    for f in failed:
        question = f["question"][:50] + "..." if len(f["question"]) > 50 else f["question"]
        error = f.get("error_message", "Unknown error")

        lines.append(f"| {f['test_id']} | {question} | {error} |")

    return "\n".join(lines)


def generate_recommendations(evaluation: Dict) -> str:
    """Generate recommendations based on metrics."""
    metrics = evaluation.get("aggregate_metrics", {})

    if not metrics:
        return ""

    recommendations = []

    # Recall analysis
    recall = metrics.get("avg_recall_at_k", 0)
    if recall < 0.7:
        recommendations.append({
            "severity": "HIGH",
            "issue": "Low retrieval recall",
            "suggestion": "Consider increasing top_k, improving embedding quality, or adding hybrid search with BM25.",
        })
    elif recall < 0.85:
        recommendations.append({
            "severity": "MEDIUM",
            "issue": "Moderate retrieval recall",
            "suggestion": "Review chunk quality and consider chunking strategy improvements.",
        })

    # MRR analysis
    mrr = metrics.get("avg_mrr", 0)
    if mrr < 0.6:
        recommendations.append({
            "severity": "HIGH",
            "issue": "Low ranking quality (MRR)",
            "suggestion": "Consider adding reranking step or improving embedding similarity.",
        })

    # Citation accuracy analysis
    citation_acc = metrics.get("avg_citation_accuracy", 0)
    if citation_acc < 70:
        recommendations.append({
            "severity": "HIGH",
            "issue": "Low citation accuracy",
            "suggestion": "Review citation generation logic and chunk-to-answer alignment.",
        })

    # Time analysis
    avg_time = metrics.get("avg_time", 0)
    if avg_time > 30:
        recommendations.append({
            "severity": "MEDIUM",
            "issue": "Slow response times",
            "suggestion": "Consider faster LLM model, optimizing prompt size, or parallelizing retrieval.",
        })

    if not recommendations:
        return "### Recommendations\n\nAll metrics look good! 🎉"

    lines = [
        "### Recommendations",
        "",
        "| Severity | Issue | Suggestion |",
        "|----------|-------|------------|",
    ]

    for rec in recommendations:
        lines.append(
            f"| {rec['severity']} | {rec['issue']} | {rec['suggestion']} |"
        )

    return "\n".join(lines)


def generate_report(
    results_path: str,
    dataset_path: str,
    template_path: Optional[str] = None,
    output_path: Optional[str] = None,
    model_name: str = "unknown",
) -> str:
    """
    Generate complete RAG evaluation report.

    Args:
        results_path: Path to batch test results JSON
        dataset_path: Path to test dataset JSON
        template_path: Optional path to report template
        output_path: Optional path to save report
        model_name: Name of LLM model being tested

    Returns:
        Generated markdown report
    """
    from scripts.evaluate_batch import evaluate_batch_results

    # Run evaluation
    evaluation = evaluate_batch_results(results_path, dataset_path)
    dataset = load_dataset(dataset_path)
    results = load_results(results_path)

    # Generate report sections
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    sections = [
        "# RAG System Evaluation Report",
        "",
        f"**Generated**: {timestamp}",
        f"**Model**: {model_name}",
        f"**Dataset**: {Path(dataset_path).stem}",
        "",
        "---",
        "",
    ]

    # Summary section
    sections.append("## Summary")
    sections.append("")
    sections.append(f"- **Total Tests**: {evaluation['total_tests']}")
    sections.append(f"- **Successful**: {evaluation['successful_tests']}")
    sections.append(f"- **Failed**: {evaluation['failed_tests']}")
    sections.append(f"- **Success Rate**: {evaluation['success_rate']:.1%}")
    sections.append("")

    # Aggregate metrics
    metrics = evaluation.get("aggregate_metrics")
    if metrics:
        sections.append("## Aggregate Metrics")
        sections.append("")
        sections.append("| Metric | Value | Target | Status |")
        sections.append("|--------|-------|--------|--------|")

        targets = {
            "avg_recall_at_k": (0.9, "≥0.90"),
            "avg_mrr": (0.8, "≥0.80"),
            "avg_citation_accuracy": (95, "≥95%"),
            "avg_time": (5.0, "≤5s"),
        }

        for metric, (target, target_str) in targets.items():
            value = metrics.get(metric, 0)
            if metric == "avg_citation_accuracy":
                status = "✓" if value >= target else "✗"
                value_str = f"{value:.1f}%"
            elif metric == "avg_time":
                status = "✓" if value <= target else "✗"
                value_str = f"{value:.2f}s"
            else:
                status = "✓" if value >= target else "✗"
                value_str = f"{value:.3f}"

            metric_name = metric.replace("avg_", "").replace("_", " ").title()
            sections.append(f"| **{metric_name}** | {value_str} | {target_str} | {status} |")

        sections.append("")

    # Per-test results table
    sections.append("## Per-Test Results")
    sections.append("")
    sections.append(generate_results_table(evaluation["per_test_results"]))
    sections.append("")

    # Category breakdown
    sections.append(generate_category_breakdown(evaluation["per_test_results"], dataset))
    sections.append("")

    # Failed tests
    sections.append(generate_failed_tests(evaluation["per_test_results"]))
    sections.append("")

    # Recommendations
    sections.append(generate_recommendations(evaluation))
    sections.append("")

    # Raw data references
    sections.append("---")
    sections.append("")
    sections.append("## Data Files")
    sections.append("")
    sections.append(f"- **Dataset**: `{dataset_path}`")
    sections.append(f"- **Results**: `{results_path}`")
    sections.append("")

    report = "\n".join(sections)

    # Save if output path provided
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"✅ Report saved to: {output_path}")

    return report


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python generate_report.py <results.json> <dataset.json> [output.md] [model_name]")
        sys.exit(1)

    results_path = sys.argv[1]
    dataset_path = sys.argv[2]
    output_path = sys.argv[3] if len(sys.argv) > 3 else None
    model_name = sys.argv[4] if len(sys.argv) > 4 else "unknown"

    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_path = f"rag-evaluation-report-{timestamp}.md"

    report = generate_report(
        results_path=results_path,
        dataset_path=dataset_path,
        output_path=output_path,
        model_name=model_name,
    )

    print("\n" + "="*60)
    print("REPORT PREVIEW")
    print("="*60)
    print(report[:1000] + "..." if len(report) > 1000 else report)
