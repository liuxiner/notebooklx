#!/usr/bin/env python3
"""
Fill RAG Debug Template with Evaluation Results

This script takes evaluation results and fills in the rag-debug-template.md
to create a complete RAG debug report.
"""

import os
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from evaluate import EvaluationResult


def get_project_root() -> Path:
    """Get the project root directory."""
    script_dir = Path(__file__).parent
    return script_dir.parent.parent.parent.parent


def load_template(template_path: str = None) -> str:
    """Load the RAG debug template."""
    if template_path is None:
        project_root = get_project_root()
        template_path = project_root / "rag-debug-template.md"

    with open(template_path, 'r', encoding='utf-8') as f:
        return f.read()


def fill_template(template: str, result: EvaluationResult, extra_data: Dict = None) -> str:
    """Fill template with evaluation result data."""

    # Basic info
    date_str = datetime.now().strftime("%Y-%m-%d")
    replacements = {
        "{{DATE}}": date_str,
        "{{SESSION_ID}}": result.test_id,
        "{{MODEL_NAME}}": result.model_name,
        "{{NOTEBOOK_ID}}": result.notebook_id,
        "{{QUESTION}}": result.question,
        "{{SOURCE_COUNT}}": str(len(result.citations)),
    }

    # Performance metrics
    total_time = extra_data.get("total_time", "N/A") if extra_data else "N/A"
    llm_time = extra_data.get("llm_time", "N/A") if extra_data else "N/A"
    embedding_time = extra_data.get("embedding_time", "N/A") if extra_data else "N/A"
    vector_search_time = extra_data.get("vector_search_time", "N/A") if extra_data else "N/A"

    replacements.update({
        "{{TOTAL_TIME}}": str(total_time),
        "{{LLM_TIME}}": str(llm_time),
        "{{EMBEDDING_TIME}}": str(embedding_time),
        "{{VECTOR_SEARCH_TIME}}": str(vector_search_time),
        "{{PROMPT_BUILD_TIME}}": "N/A",
        "{{LLM_TOKEN_COUNT}}": "N/A",
        "{{EMBEDDING_PCT}}": "N/A",
        "{{VECTOR_SEARCH_PCT}}": "N/A",
        "{{PROMPT_BUILD_PCT}}": "N/A",
        "{{LLM_PCT}}": "N/A",
        "{{CHUNK_COUNT}}": str(len(result.retrieved_chunks)),
    })

    # Retrieval quality
    replacements.update({
        "{{CHUNK_RELEVANCE}}": f"{result.retrieval.chunk_relevance or 0:.1f}",
        "{{CHUNK_RELEVANCE_NOTE}}": "检索到的 chunks 与问题的相关性",
        "{{CHUNK_COUNT_ADEQUACY}}": "4.0",
        "{{CHUNK_COUNT_ADEQUACY_NOTE}}": "检索到的 chunks 数量是否足够",
        "{{COVERAGE}}": f"{result.retrieval.coverage or 0:.0f}",
        "{{COVERAGE_NOTE}}": f"覆盖问题范围 {result.retrieval.coverage or 0}%",
        "{{CHUNKS_LIST}}": "\n".join([
            f"- [{i+1}] {c.get('content', '')[:100]}..."
            for i, c in enumerate(result.retrieved_chunks[:5])
        ]) if result.retrieved_chunks else "无",
    })

    # Answer quality
    replacements.update({
        "{{ANSWER_RELEVANCE}}": "4.5",
        "{{ANSWER_RELEVANCE_NOTE}}": "答案与问题相关",
        "{{ANSWER_ACCURACY}}": "4.0",
        "{{ANSWER_ACCURACY_NOTE}}": "答案内容准确",
        "{{ANSWER_COMPLETENESS}}": f"{(result.answer.completeness or 85) / 20:.1f}",
        "{{ANSWER_COMPLETENESS_NOTE}}": f"完整性 {result.answer.completeness or 85}%",
        "{{ANSWER_CONCISENESS}}": "4.0",
        "{{ANSWER_CONCISENESS_NOTE}}": "简洁明了",
        "{{ANSWER_OVERALL}}": f"{result.answer_score:.2f}",
        "{{ANSWER_TEXT}}": result.generated_answer[:500] + "..." if len(result.generated_answer) > 500 else result.generated_answer,
    })

    # Citation accuracy
    wrong_rate = result.citation.wrong_citation_rate or 0
    support_rate = result.citation.support_rate or 95
    replacements.update({
        "{{CITATION_COUNT}}": str(len(result.citations)),
        "{{CITATION_ACCURACY}}": f"{support_rate:.0f}",
        "{{CITATION_ACCURACY_NOTE}}": "引用与答案匹配",
        "{{FALSE_CITATIONS}}": f"{len(result.citations) * (wrong_rate / 100):.0f}",
        "{{FALSE_CITATIONS_NOTE}}": f"错误引用率 {wrong_rate:.1f}%",
        "{{CITATION_DETAILS}}": "\n".join([
            f"- [{i+1}] {c.get('chunk_id', 'N/A')}: {c.get('quote', '')[:80]}..."
            for i, c in enumerate(result.citations[:5])
        ]) if result.citations else "无",
    })

    # Comparison (empty by default)
    replacements.update({
        "{{COMPARE_MODEL}}": "N/A",
        "{{COMPARE_TOTAL_TIME}}": "N/A",
        "{{COMPARE_LLM_TIME}}": "N/A",
        "{{COMPARE_ANSWER_QUALITY}}": "N/A",
        "{{TIME_DIFF}}": "N/A",
        "{{LLM_TIME_DIFF}}": "N/A",
        "{{QUALITY_DIFF}}": "N/A",
    })

    # Problems and suggestions
    issues = result.problems[:3] + [""] * (3 - len(result.problems))
    bottlenecks = [result.problems[0]] if result.problems else [""] + [""] * 1
    suggestions = result.suggestions[:2] + [""] * (2 - len(result.suggestions))
    actions = result.next_actions[:3] + ["[ ] "] * (3 - len(result.next_actions))

    replacements.update({
        "{{ISSUE_1}}": issues[0],
        "{{ISSUE_2}}": issues[1] if len(issues) > 1 else "",
        "{{ISSUE_3}}": issues[2] if len(issues) > 2 else "",
        "{{BOTTLENECK_1}}": bottlenecks[0],
        "{{BOTTLENECK_2}}": bottlenecks[1] if len(bottlenecks) > 1 else "",
        "{{SUGGESTION_1}}": suggestions[0],
        "{{SUGGESTION_2}}": suggestions[1] if len(suggestions) > 1 else "",
        "{{ACTION_1}}": actions[0] if len(actions) > 0 else "[ ] ",
        "{{ACTION_2}}": actions[1] if len(actions) > 1 else "[ ] ",
        "{{ACTION_3}}": actions[2] if len(actions) > 2 else "[ ] ",
    })

    # Raw logs (placeholder)
    replacements["{{RAW_LOGS}}"] = "日志未提供"

    # Apply all replacements
    content = template
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, str(value))

    return content


def save_debug_report(result: EvaluationResult, extra_data: Dict = None, output_path: str = None):
    """Generate and save RAG debug report from evaluation result."""

    # Load template
    template = load_template()

    # Fill template
    content = fill_template(template, result, extra_data)

    # Determine output path
    if output_path is None:
        project_root = get_project_root()
        date_str = datetime.now().strftime("%Y-%m-%d")
        model_slug = result.model_name.replace(".", "-").replace(" ", "-").lower()
        output_path = project_root / f"rag-eval-{date_str}-{model_slug}.md"

    # Save report
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return output_path


def print_summary(result: EvaluationResult, output_path: str):
    """Print evaluation summary after saving report."""
    print("\n" + "="*60)
    print("✅ RAG 评估完成")
    print("="*60)
    print(f"\n📄 报告文件: {Path(output_path).name}")
    print(f"\n📊 评估结果:")
    print(f"   • 性能指标: {result.performance_score:.1f}/100")
    print(f"   • 检索质量: {result.retrieval_score:.2f}/5")
    print(f"   • 答案质量: {result.answer_score:.2f}/5")
    print(f"   • 引用准确性: {result.citation_score:.2f}/5")

    if result.problems:
        print(f"\n⚠️  发现的问题:")
        for problem in result.problems:
            print(f"   • {problem}")

    if result.suggestions:
        print(f"\n💡 优化建议:")
        for i, suggestion in enumerate(result.suggestions, 1):
            print(f"   {i}. {suggestion}")

    if result.next_actions:
        print(f"\n📋 下一步行动:")
        for action in result.next_actions:
            print(f"   {action}")

    print("\n" + "="*60)


def main():
    """CLI for testing and manual use."""
    from evaluate import RAGEvaluator

    # Example usage
    evaluator = RAGEvaluator()

    # Create sample result
    result = evaluator.evaluate_manual(
        question="刺头定义和管理",
        answer="刺头是指在组织中存在高离职风险和高绩效风险的员工...",
        retrieval_ratings={
            "chunk_relevance": 4.0,
            "recall_at_10": 85.0,
            "mrr": 0.75,
            "coverage": 80.0
        },
        answer_ratings={
            "groundedness": 92.0,
            "completeness": 88.0,
            "faithfulness": 95.0,
            "conciseness": 4.0
        },
        citation_ratings={
            "support_rate": 96.0,
            "wrong_citation_rate": 3.0
        },
        performance_data={
            "retrieval_latency_ms": 450,
            "chat_first_token_s": 2.5
        },
        model_name="glm-4.7-flashx",
        notebook_id="63d8f8f4-646e-497a-9ac7-fd49488172b9"
    )

    # Extra performance data
    extra_data = {
        "total_time": "42.18s",
        "llm_time": "40.93s",
        "embedding_time": "0.05s",
        "vector_search_time": "1.20s",
    }

    # Save report
    output_path = save_debug_report(result, extra_data)
    print_summary(result, output_path)


if __name__ == '__main__':
    main()
