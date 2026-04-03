#!/usr/bin/env python3
"""
Find and load historical RAG debug reports for comparison.

This script scans the project root for rag-debug-*.md files,
extracts metadata, and provides utilities for loading report data.
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


def find_history_reports(project_root: str = None) -> List[Dict[str, str]]:
    """
    Find all RAG debug reports in the project root.

    Args:
        project_root: Path to project root (defaults to current directory)

    Returns:
        List of dicts with keys: filename, date, model, filepath
    """
    if project_root is None:
        # Default to repository root (3 levels up from this script)
        script_dir = Path(__file__).parent
        project_root = script_dir.parent.parent.parent.parent

    project_path = Path(project_root)
    reports = []

    # Pattern: rag-debug-YYYY-MM-DD-{MODEL}.md
    pattern = re.compile(r'rag-debug-(\d{4}-\d{2}-\d{2})-(.+?)\.md')

    for file in project_path.glob('rag-debug-*.md'):
        match = pattern.match(file.name)
        if match:
            date_str, model = match.groups()
            try:
                datetime.strptime(date_str, '%Y-%m-%d')  # Validate date
                reports.append({
                    'filename': file.name,
                    'date': date_str,
                    'model': model,
                    'filepath': str(file)
                })
            except ValueError:
                # Invalid date format, skip
                continue

    # Sort by date descending (newest first)
    reports.sort(key=lambda x: x['date'], reverse=True)
    return reports


def load_report_data(filepath: str) -> Dict[str, str]:
    """
    Load and parse key metrics from a RAG debug report.

    Args:
        filepath: Path to the report file

    Returns:
        Dict with extracted metrics (model, total_time, llm_time, etc.)
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    data = {}

    # Extract model (from LLM 模型 row)
    model_match = re.search(r'\|\s*\*\*LLM 模型\*\*\s*\|\s*(.+?)\s*\|', content)
    if model_match:
        data['model'] = model_match.group(1).strip()

    # Extract total time
    total_match = re.search(r'\|\s*\*\*总耗时\*\*\s*\|\s*([\d.]+s)', content)
    if total_match:
        data['total_time'] = total_match.group(1)

    # Extract LLM time
    llm_match = re.search(r'└─ LLM 调用.*?\|\s*([\d.]+s)', content)
    if llm_match:
        data['llm_time'] = llm_match.group(1)

    # Extract chunk count
    chunk_match = re.search(r'检索到\s*(\d+)\s*个 chunks', content)
    if chunk_match:
        data['chunk_count'] = int(chunk_match.group(1))

    # Extract answer quality score (综合评分)
    quality_match = re.search(r'\|\s*\*\*综合评分\*\*\s*\|\s*([\d.]+)', content)
    if quality_match:
        data['answer_quality'] = float(quality_match.group(1))

    # Extract chunk relevance
    relevance_match = re.search(r'\|\s*\*\*Chunks 相关性\*\*\s*\|\s*([\d.]+)', content)
    if relevance_match:
        data['chunk_relevance'] = float(relevance_match.group(1))

    return data


def format_reports_list(reports: List[Dict[str, str]]) -> str:
    """
    Format reports list for display to user.

    Args:
        reports: List of report dicts from find_history_reports()

    Returns:
        Formatted string for display
    """
    if not reports:
        return "未找到历史报告。"

    lines = ["📚 历史报告列表:\n"]
    for i, report in enumerate(reports, 1):
        lines.append(f"{i}. {report['filename']}")
        lines.append(f"   日期: {report['date']}, 模型: {report['model']}")
        lines.append("")

    return "\n".join(lines)


def main():
    """CLI for testing and manual use."""
    import sys

    reports = find_history_reports()
    print(format_reports_list(reports))

    if len(sys.argv) > 1:
        # Load specific report
        report_file = sys.argv[1]
        report_path = Path.cwd() / report_file
        if report_path.exists():
            data = load_report_data(str(report_path))
            print(f"\n📊 报告数据: {report_file}")
            for key, value in data.items():
                print(f"  {key}: {value}")


if __name__ == '__main__':
    main()
