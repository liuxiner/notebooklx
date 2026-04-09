"""
Evaluation service for computing retrieval and answer quality metrics.

Feature 6.3: Evaluation Dashboard
"""
import asyncio
import uuid
from typing import List, Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)


class RetrievalEvaluator:
    """Evaluates retrieval quality using recall@K and MRR."""

    @staticmethod
    def calculate_recall_at_k(
        retrieved_chunk_ids: List[uuid.UUID],
        ground_truth_chunk_ids: List[uuid.UUID],
        k: int,
    ) -> float:
        """
        Calculate recall@K metric.

        Recall@K = (number of relevant chunks in top K) / (total relevant chunks)

        AC: Track retrieval metrics: recall@5, recall@10
        """
        if not ground_truth_chunk_ids:
            return 0.0

        # Get top K retrieved chunks
        top_k_retrieved = retrieved_chunk_ids[:k]

        # Count how many of the ground truth chunks are in top K
        relevant_found = sum(
            1 for chunk_id in top_k_retrieved
            if chunk_id in ground_truth_chunk_ids
        )

        recall = relevant_found / len(ground_truth_chunk_ids)
        logger.debug(
            f"[Recall@{k}] Found {relevant_found}/{len(ground_truth_chunk_ids)} "
            f"relevant chunks in top {k}, recall={recall:.4f}"
        )
        return recall

    @staticmethod
    def calculate_mrr(
        retrieved_chunk_ids_list: List[List[uuid.UUID]],
        ground_truth_chunk_ids_list: List[List[uuid.UUID]],
    ) -> float:
        """
        Calculate Mean Reciprocal Rank (MRR).

        MRR = average of (1 / rank_of_first_relevant) for each query

        AC: Track retrieval metrics: recall@5, recall@10, MRR
        """
        if not ground_truth_chunk_ids_list:
            return 0.0

        reciprocal_ranks = []

        for retrieved_ids, ground_truth_ids in zip(
            retrieved_chunk_ids_list, ground_truth_chunk_ids_list
        ):
            if not ground_truth_ids:
                continue

            # Find the rank of the first relevant chunk
            first_relevant_rank = None
            for rank, chunk_id in enumerate(retrieved_ids, start=1):
                if chunk_id in ground_truth_ids:
                    first_relevant_rank = rank
                    break

            if first_relevant_rank is not None:
                # Found relevant chunk, use reciprocal of rank
                reciprocal_rank = 1.0 / first_relevant_rank
            else:
                # No relevant chunk found
                reciprocal_rank = 0.0

            reciprocal_ranks.append(reciprocal_rank)
            logger.debug(
                f"[MRR] First relevant at rank {first_relevant_rank}, "
                f"reciprocal={reciprocal_rank:.4f}"
            )

        if not reciprocal_ranks:
            return 0.0

        mrr = sum(reciprocal_ranks) / len(reciprocal_ranks)
        logger.debug(f"[MRR] Calculated MRR={mrr:.4f} over {len(reciprocal_ranks)} queries")
        return mrr


class CitationEvaluator:
    """Evaluates citation quality."""

    @staticmethod
    def evaluate_citations(
        answer: str,
        retrieved_chunks: List[Dict[str, Any]],
        citation_indices: List[int],
    ) -> Tuple[float, float]:
        """
        Evaluate citation quality.

        Returns (support_rate, wrong_citation_rate).

        Support rate = (supported citations) / (total citations)
        Wrong citation rate = (wrong citations) / (total citations)

        A citation supports the answer if the chunk content contains
        evidence for the claim it's citing.

        AC: Track citation metrics: support rate, wrong citation rate
        """
        if not citation_indices:
            return 1.0, 0.0  # No citations to evaluate

        total_citations = len(citation_indices)
        supported_count = 0
        wrong_count = 0

        for idx in citation_indices:
            if idx >= len(retrieved_chunks):
                wrong_count += 1
                continue

            chunk = retrieved_chunks[idx]
            chunk_content = chunk.get("content", "").lower()

            # Simple heuristic: if chunk has relevant keywords, mark as supported
            # In production, this would use LLM-based evaluation
            keywords = answer.lower().split()[:5]  # Check first 5 keywords
            has_relevant_content = any(
                keyword in chunk_content
                for keyword in keywords
                if len(keyword) > 3  # Ignore short words
            )

            if has_relevant_content:
                supported_count += 1
            else:
                wrong_count += 1

        support_rate = supported_count / total_citations if total_citations > 0 else 1.0
        wrong_citation_rate = wrong_count / total_citations if total_citations > 0 else 0.0

        logger.debug(
            f"[CitationEval] Supported: {supported_count}/{total_citations}, "
            f"Wrong: {wrong_count}/{total_citations}, "
            f"SupportRate={support_rate:.4f}, WrongRate={wrong_citation_rate:.4f}"
        )

        return support_rate, wrong_citation_rate


class AnswerQualityEvaluator:
    """Evaluates answer quality metrics."""

    @staticmethod
    def evaluate_groundedness(
        answer: str,
        retrieved_chunks: List[Dict[str, Any]],
    ) -> float:
        """
        Evaluate groundedness - does the answer stay within source content?

        Groundedness = (answer content from sources) / (total answer)

        AC: Track answer quality: groundedness, completeness, faithfulness
        """
        if not answer or not retrieved_chunks:
            return 0.0

        # Collect all chunk content
        chunk_contents = " ".join(
            chunk.get("content", "") for chunk in retrieved_chunks
        ).lower()

        answer_words = set(answer.lower().split())
        chunk_words = set(chunk_contents.split())

        # Count how many answer words come from chunks
        source_words_in_answer = len(answer_words.intersection(chunk_words))

        groundedness = (
            source_words_in_answer / len(answer_words)
            if answer_words
            else 0.0
        )

        logger.debug(
            f"[Groundedness] {source_words_in_answer}/{len(answer_words)} "
            f"words from sources, groundedness={groundedness:.4f}"
        )

        return groundedness

    @staticmethod
    def evaluate_completeness(
        answer: str,
        question: str,
    ) -> float:
        """
        Evaluate completeness - does the answer fully address the question?

        Completeness = (answer covers all aspects) / (expected coverage)

        AC: Track answer quality: groundedness, completeness, faithfulness
        """
        if not answer or not question:
            return 0.0

        # Simple heuristic based on answer length relative to question
        # In production, this would use LLM-based evaluation
        question_words = len(question.split())
        answer_words = len(answer.split())

        # Answer should be at least 2x question length to be complete
        min_expected_words = question_words * 2

        # For very short questions, use a minimum threshold of 10 words
        if min_expected_words < 10:
            min_expected_words = 10

        if answer_words >= min_expected_words:
            return 1.0
        else:
            return answer_words / min_expected_words

    @staticmethod
    def evaluate_faithfulness(
        answer: str,
        retrieved_chunks: List[Dict[str, Any]],
    ) -> float:
        """
        Evaluate faithfulness - does the answer contradict sources?

        Faithfulness = 1 - (contradictions found) / (total statements)

        AC: Track answer quality: groundedness, completeness, faithfulness
        """
        if not answer:
            return 0.0

        if not retrieved_chunks:
            # No sources to check against - can't verify faithfulness
            return 1.0

        # Simple heuristic: check for common contradictions
        # In production, this would use LLM-based evaluation
        chunk_contents = " ".join(
            chunk.get("content", "") for chunk in retrieved_chunks
        ).lower()

        # Look for negation patterns that might indicate contradictions
        contradiction_keywords = [
            "however",
            "but",
            "although",
            "contrary",
            "opposite",
            "disagree",
        ]

        has_contradiction = any(
            keyword in answer.lower()
            for keyword in contradiction_keywords
        )

        if has_contradiction:
            # Check if the contradiction is in the sources
            sources_have_contradiction = any(
                keyword in chunk_contents
                for keyword in contradiction_keywords
            )

            if sources_have_contradiction:
                # Contradiction is from sources - may be faithful
                faithfulness = 0.8
            else:
                # Contradiction not in sources - less faithful
                faithfulness = 0.5
        else:
            faithfulness = 1.0

        logger.debug(
            f"[Faithfulness] Has contradiction: {has_contradiction}, "
            f"Sources have contradiction: {sources_have_contradiction if has_contradiction else 'N/A'}, "
            f"faithfulness={faithfulness:.4f}"
        )

        return faithfulness


class EvaluationService:
    """Main service for running evaluations."""

    def __init__(self, db_session):
        """Initialize evaluation service with database session."""
        self.db = db_session

    def retrieve_chunks_for_query(
        self,
        notebook_id: uuid.UUID | str,
        query: str,
        top_k: int = 10,
    ) -> Tuple[List[uuid.UUID], List[Dict[str, Any]]]:
        """
        Retrieve ranked notebook chunks for an evaluation query.

        Prefers hybrid retrieval when query embeddings can be generated, and
        falls back to BM25-only retrieval in stripped-down local environments.
        """
        from services.api.modules.embeddings import (
            EmbeddingService,
            BigModelEmbeddingProvider,
        )
        from services.api.modules.retrieval.hybrid import (
            BM25SearchService,
            HybridSearchService,
        )

        notebook_id_str = str(notebook_id)

        try:
            try:
                provider = BigModelEmbeddingProvider()
                embedding_service = EmbeddingService(
                    provider=provider,
                    model_name=provider.model,
                    dimension=provider.dimension,
                )
            except (ImportError, ValueError):
                embedding_service = EmbeddingService()

            embedding_result = asyncio.run(embedding_service.embed_batch([query]))
            query_embedding = embedding_result[0].embedding if embedding_result else []
            retrieval_results = HybridSearchService(self.db).search_sync(
                query=query,
                query_embedding=query_embedding,
                notebook_id=notebook_id_str,
                top_k=top_k,
            )
        except Exception:
            logger.exception("[Evaluation] Hybrid retrieval failed, falling back to BM25 only")
            retrieval_results = BM25SearchService(self.db).search(
                query=query,
                notebook_id=notebook_id_str,
                top_k=top_k,
            )

        retrieved_chunk_ids: List[uuid.UUID] = []
        retrieved_chunks: List[Dict[str, Any]] = []
        for result in retrieval_results:
            retrieved_chunk_ids.append(uuid.UUID(str(result.chunk_id)))
            retrieved_chunks.append(
                {
                    "id": str(result.chunk_id),
                    "content": result.content,
                    "metadata": result.metadata,
                    "source_title": result.source_title,
                    "chunk_index": result.chunk_index,
                    "score": result.score,
                }
            )

        return retrieved_chunk_ids, retrieved_chunks

    def run_evaluation(
        self,
        evaluation_run,
        retrieved_chunk_ids_list: List[List[uuid.UUID]],
        ground_truth_chunk_ids_list: List[List[uuid.UUID]],
        answers: List[str],
        questions: List[str],
        retrieved_chunks_list: List[List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """
        Run a complete evaluation and return all metrics.

        AC: Track retrieval metrics: recall@5, recall@10, MRR
        AC: Track citation metrics: support rate, wrong citation rate
        AC: Track answer quality: groundedness, completeness, faithfulness

        Returns:
            Dictionary with metric_type -> metric_value mappings
        """
        metrics = {}

        # Calculate retrieval metrics
        if retrieved_chunk_ids_list and ground_truth_chunk_ids_list:
            for k in [5, 10]:
                recall = RetrievalEvaluator.calculate_recall_at_k(
                    retrieved_chunk_ids_list[0] if retrieved_chunk_ids_list else [],
                    ground_truth_chunk_ids_list[0] if ground_truth_chunk_ids_list else [],
                    k,
                )
                metrics[f"recall_at_{k}"] = {
                    "value": recall,
                    "metadata": {
                        "k": k,
                        "type": "recall_at_k",
                    },
                }

            mrr = RetrievalEvaluator.calculate_mrr(
                retrieved_chunk_ids_list,
                ground_truth_chunk_ids_list,
            )
            metrics["mrr"] = {
                "value": mrr,
                "metadata": {
                    "query_count": len(retrieved_chunk_ids_list),
                },
            }

        # Calculate citation metrics
        citation_evaluator = CitationEvaluator()
        total_support_rate = 0.0
        total_wrong_rate = 0.0
        total_citations = 0

        if answers and retrieved_chunks_list:
            for answer, retrieved_chunks in zip(answers, retrieved_chunks_list):
                support_rate, wrong_rate = citation_evaluator.evaluate_citations(
                    answer, retrieved_chunks, list(range(len(retrieved_chunks)))
                )
                total_support_rate += support_rate
                total_wrong_rate += wrong_rate
                total_citations += len(retrieved_chunks)

            if total_citations > 0:
                avg_support_rate = total_support_rate / len(answers)
                avg_wrong_rate = total_wrong_rate / len(answers)
                metrics["citation_support_rate"] = {
                    "value": avg_support_rate,
                    "metadata": {
                        "total_citations": total_citations,
                        "total_answers": len(answers),
                    },
                }
                metrics["wrong_citation_rate"] = {
                    "value": avg_wrong_rate,
                    "metadata": {
                        "total_citations": total_citations,
                        "total_answers": len(answers),
                    },
                }

        # Calculate answer quality metrics
        quality_evaluator = AnswerQualityEvaluator()
        total_groundedness = 0.0
        total_completeness = 0.0
        total_faithfulness = 0.0
        total_answers_evaluated = 0

        if answers and questions:
            for answer, question in zip(answers, questions):
                if retrieved_chunks_list:
                    groundedness = quality_evaluator.evaluate_groundedness(
                        answer, retrieved_chunks_list[0]
                    )
                    total_groundedness += groundedness

                    faithfulness = quality_evaluator.evaluate_faithfulness(
                        answer, retrieved_chunks_list[0]
                    )
                    total_faithfulness += faithfulness

                completeness = quality_evaluator.evaluate_completeness(answer, question)
                total_completeness += completeness
                total_answers_evaluated += 1

            if total_answers_evaluated > 0:
                avg_groundedness = total_groundedness / total_answers_evaluated
                avg_completeness = total_completeness / total_answers_evaluated
                avg_faithfulness = total_faithfulness / total_answers_evaluated

                metrics["groundedness"] = {
                    "value": avg_groundedness,
                    "metadata": {
                        "total_answers": total_answers_evaluated,
                    },
                }
                metrics["completeness"] = {
                    "value": avg_completeness,
                    "metadata": {
                        "total_answers": total_answers_evaluated,
                    },
                }
                metrics["faithfulness"] = {
                    "value": avg_faithfulness,
                    "metadata": {
                        "total_answers": total_answers_evaluated,
                    },
                }

        logger.info(f"[Evaluation] Computed {len(metrics)} metric types")
        return metrics
