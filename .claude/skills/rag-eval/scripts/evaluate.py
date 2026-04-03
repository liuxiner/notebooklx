#!/usr/bin/env python3
"""
RAG Evaluation and Scoring System

This script provides comprehensive evaluation for RAG systems including:
- Performance metrics scoring
- Retrieval quality scoring
- Answer quality scoring
- Citation accuracy scoring
- Problem analysis and optimization suggestions
"""

import json
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from pathlib import Path
from datetime import datetime


@dataclass
class PerformanceMetrics:
    """Performance metrics for RAG evaluation."""
    ingestion_success_rate: Optional[float] = None  # Target: >95%
    retrieval_latency_ms: Optional[float] = None     # Target: <300ms
    chat_first_token_s: Optional[float] = None       # Target: <2s
    api_uptime: Optional[float] = None               # Target: >99.5%

    def calculate_score(self) -> float:
        """Calculate overall performance score (0-100)."""
        scores = []

        if self.ingestion_success_rate is not None:
            score = min(100, (self.ingestion_success_rate / 95) * 100)
            scores.append(score)

        if self.retrieval_latency_ms is not None:
            penalty = max(0, (self.retrieval_latency_ms - 300) / 10)
            score = max(0, 100 - penalty)
            scores.append(score)

        if self.chat_first_token_s is not None:
            penalty = max(0, (self.chat_first_token_s - 2) * 20)
            score = max(0, 100 - penalty)
            scores.append(score)

        if self.api_uptime is not None:
            score = min(100, (self.api_uptime / 99.5) * 100)
            scores.append(score)

        return sum(scores) / len(scores) if scores else 0.0


@dataclass
class RetrievalMetrics:
    """Retrieval quality metrics."""
    recall_at_10: Optional[float] = None    # Target: >90%
    mrr: Optional[float] = None              # Target: >0.8
    chunk_relevance: Optional[float] = None  # 1-5 scale, target: 4.5
    coverage: Optional[float] = None         # Target: >85%

    def calculate_score(self) -> float:
        """Calculate overall retrieval score (0-5)."""
        scores = []

        if self.recall_at_10 is not None:
            score = min(5, (self.recall_at_10 / 90) * 5)
            scores.append(score)

        if self.mrr is not None:
            score = min(5, (self.mrr / 0.8) * 5)
            scores.append(score)

        if self.chunk_relevance is not None:
            scores.append(self.chunk_relevance)

        if self.coverage is not None:
            score = min(5, (self.coverage / 85) * 5)
            scores.append(score)

        return sum(scores) / len(scores) if scores else 0.0


@dataclass
class AnswerMetrics:
    """Answer quality metrics."""
    groundedness: Optional[float] = None   # Target: >90%
    completeness: Optional[float] = None   # Target: >85%
    faithfulness: Optional[float] = None   # Target: >95%
    conciseness: Optional[float] = None    # 1-5 scale

    def calculate_score(self) -> float:
        """Calculate overall answer score (0-5)."""
        scores = []

        if self.groundedness is not None:
            score = min(5, (self.groundedness / 90) * 5)
            scores.append(score)

        if self.completeness is not None:
            score = min(5, (self.completeness / 85) * 5)
            scores.append(score)

        if self.faithfulness is not None:
            score = min(5, (self.faithfulness / 95) * 5)
            scores.append(score)

        if self.conciseness is not None:
            scores.append(self.conciseness)

        return sum(scores) / len(scores) if scores else 0.0


@dataclass
class CitationMetrics:
    """Citation accuracy metrics."""
    support_rate: Optional[float] = None   # Target: >95%
    wrong_citation_rate: Optional[float] = None  # Target: <5%

    def calculate_score(self) -> float:
        """Calculate overall citation score (0-5)."""
        scores = []

        if self.support_rate is not None:
            score = min(5, (self.support_rate / 95) * 5)
            scores.append(score)

        if self.wrong_citation_rate is not None:
            score = max(0, 5 - (self.wrong_citation_rate / 5) * 5)
            scores.append(score)

        return sum(scores) / len(scores) if scores else 0.0


@dataclass
class EvaluationResult:
    """Complete evaluation result for a single test case."""
    test_id: str
    question: str
    model_name: str
    notebook_id: str

    performance: PerformanceMetrics
    retrieval: RetrievalMetrics
    answer: AnswerMetrics
    citation: CitationMetrics

    generated_answer: str
    retrieved_chunks: List[Dict[str, Any]]
    citations: List[Dict[str, Any]]

    # Overall scores
    performance_score: float = field(init=False)
    retrieval_score: float = field(init=False)
    answer_score: float = field(init=False)
    citation_score: float = field(init=False)

    # Analysis
    problems: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    next_actions: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.performance_score = self.performance.calculate_score()
        self.retrieval_score = self.retrieval.calculate_score()
        self.answer_score = self.answer.calculate_score()
        self.citation_score = self.citation.calculate_score()
        self._analyze()

    def _analyze(self):
        """Analyze scores and generate problems, suggestions, and actions."""
        # Performance issues
        if self.performance_score < 70:
            if self.performance.retrieval_latency_ms and self.performance.retrieval_latency_ms > 300:
                self.problems.append(f"检索延迟超标 ({self.performance.retrieval_latency_ms}ms > 300ms目标)")
                self.suggestions.append("创建 HNSW 索引以加速向量搜索")
                self.next_actions.append("[ ] 创建 HNSW 索引")

            if self.performance.chat_first_token_s and self.performance.chat_first_token_s > 2:
                self.problems.append(f"首字延迟超标 ({self.performance.chat_first_token_s}s > 2s目标)")
                self.suggestions.append("减少 prompt 长度或使用更快的模型")
                self.next_actions.append("[ ] 优化 prompt 长度")

        # Retrieval issues
        if self.retrieval_score < 3.5:
            if self.retrieval.recall_at_10 and self.retrieval.recall_at_10 < 90:
                self.problems.append(f"Recall@10 偏低 ({self.retrieval.recall_at_10}% < 90%目标)")
                self.suggestions.append("调整 chunking 策略提高召回率")
                self.next_actions.append("[ ] 重新评估 chunking 参数")

            if self.retrieval.mrr and self.retrieval.mrr < 0.8:
                self.problems.append(f"MRR 偏低 ({self.retrieval.mrr} < 0.8目标)")
                self.suggestions.append("实现重排序(reranking)机制")
                self.next_actions.append("[ ] 实现重排序")

            if self.retrieval.chunk_relevance and self.retrieval.chunk_relevance < 4.0:
                self.problems.append(f"Chunks 相关性偏低 ({self.retrieval.chunk_relevance}/5)")
                self.suggestions.append("实现查询重写/扩展")
                self.next_actions.append("[ ] 实现查询重写")

        # Answer issues
        if self.answer_score < 3.5:
            if self.answer.groundedness and self.answer.groundedness < 90:
                self.problems.append(f"答案基础性偏低 ({self.answer.groundedness}% < 90%目标)")
                self.suggestions.append("改进 prompt 添加约束条件")
                self.next_actions.append("[ ] 优化 prompt 约束")

            if self.answer.completeness and self.answer.completeness < 85:
                self.problems.append(f"答案完整性偏低 ({self.answer.completeness}% < 85%目标)")
                self.suggestions.append("增加检索的 chunks 数量")
                self.next_actions.append("[ ] 增加 top_k 值")

        # Citation issues
        if self.citation_score < 3.5:
            if self.citation.support_rate and self.citation.support_rate < 95:
                self.problems.append(f"引用支持率偏低 ({self.citation.support_rate}% < 95%目标)")
                self.suggestions.append("修复引用对齐逻辑")
                self.next_actions.append("[ ] 修复引用绑定")

            if self.citation.wrong_citation_rate and self.citation.wrong_citation_rate > 5:
                self.problems.append(f"错误引用率偏高 ({self.citation.wrong_citation_rate}% > 5%目标)")
                self.suggestions.append("验证引用存在性后再输出")
                self.next_actions.append("[ ] 添加引用验证")


class RAGEvaluator:
    """RAG Evaluator with automatic scoring."""

    def __init__(self, rag_api_url: str = None, api_key: str = None):
        self.rag_api_url = rag_api_url or "http://localhost:8000/api/chat"
        self.api_key = api_key

    def evaluate_manual(
        self,
        question: str,
        answer: str,
        retrieved_chunks: List[Dict] = None,
        citations: List[Dict] = None,
        performance_data: Dict = None,
        retrieval_ratings: Dict = None,
        answer_ratings: Dict = None,
        citation_ratings: Dict = None,
        model_name: str = "unknown",
        notebook_id: str = "unknown"
    ) -> EvaluationResult:
        """Evaluate a manually provided RAG response."""

        # Build metrics from ratings
        performance = PerformanceMetrics(
            ingestion_success_rate=performance_data.get("ingestion_success_rate") if performance_data else None,
            retrieval_latency_ms=performance_data.get("retrieval_latency_ms") if performance_data else None,
            chat_first_token_s=performance_data.get("chat_first_token_s") if performance_data else None,
            api_uptime=performance_data.get("api_uptime") if performance_data else None,
        )

        retrieval = RetrievalMetrics(
            recall_at_10=retrieval_ratings.get("recall_at_10") if retrieval_ratings else None,
            mrr=retrieval_ratings.get("mrr") if retrieval_ratings else None,
            chunk_relevance=retrieval_ratings.get("chunk_relevance") if retrieval_ratings else None,
            coverage=retrieval_ratings.get("coverage") if retrieval_ratings else None,
        )

        answer = AnswerMetrics(
            groundedness=answer_ratings.get("groundedness") if answer_ratings else None,
            completeness=answer_ratings.get("completeness") if answer_ratings else None,
            faithfulness=answer_ratings.get("faithfulness") if answer_ratings else None,
            conciseness=answer_ratings.get("conciseness") if answer_ratings else None,
        )

        citation = CitationMetrics(
            support_rate=citation_ratings.get("support_rate") if citation_ratings else None,
            wrong_citation_rate=citation_ratings.get("wrong_citation_rate") if citation_ratings else None,
        )

        return EvaluationResult(
            test_id=f"manual-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            question=question,
            model_name=model_name,
            notebook_id=notebook_id,
            performance=performance,
            retrieval=retrieval,
            answer=answer,
            citation=citation,
            generated_answer=answer,
            retrieved_chunks=retrieved_chunks or [],
            citations=citations or [],
        )

    def calculate_recall_at_k(self, retrieved_ids: List[str], expected_ids: List[str], k: int = 10) -> float:
        """Calculate Recall@K: percentage of expected items found in top K results."""
        if not expected_ids:
            return 100.0
        top_k = set(retrieved_ids[:k])
        found = len(top_k.intersection(set(expected_ids)))
        return (found / len(expected_ids)) * 100

    def calculate_mrr(self, retrieved_ids: List[str], expected_ids: List[str]) -> float:
        """Calculate Mean Reciprocal Rank: average of 1/rank for first relevant item."""
        if not expected_ids:
            return 1.0
        expected_set = set(expected_ids)
        for i, item_id in enumerate(retrieved_ids, 1):
            if item_id in expected_set:
                return 1.0 / i
        return 0.0

    def print_summary(self, result: EvaluationResult):
        """Print evaluation summary."""
        print("\n" + "="*60)
        print("📊 RAG 评估结果")
        print("="*60)
        print(f"\n测试 ID: {result.test_id}")
        print(f"模型: {result.model_name}")
        print(f"\n📈 综合评分:")
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
    import sys

    # Example manual evaluation
    evaluator = RAGEvaluator()

    # Example: manual evaluation with ratings
    result = evaluator.evaluate_manual(
        question="刺头定义和管理...",
        answer="刺头是指在组织中...",
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

    evaluator.print_summary(result)


if __name__ == '__main__':
    main()
