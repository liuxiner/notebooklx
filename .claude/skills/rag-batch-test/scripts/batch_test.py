#!/usr/bin/env python3
"""
Batch RAG testing script - runs multiple test cases via chat API.

This script loads a test dataset, executes each test case via the chat API,
records responses including retrieved chunks, and saves results for evaluation.
"""
import json
import uuid
import time
import requests
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path


@dataclass
class TestResult:
    """Result of a single RAG test case."""
    test_id: str
    question: str
    success: bool
    answer: Optional[str] = None
    raw_answer: Optional[str] = None
    retrieved_chunks: List[Dict] = None
    citation_indices: List[int] = None
    missing_citation_indices: List[int] = None
    total_time: float = 0.0
    error_message: Optional[str] = None
    timestamp: str = None

    def __post_init__(self):
        if self.retrieved_chunks is None:
            self.retrieved_chunks = []
        if self.citation_indices is None:
            self.citation_indices = []
        if self.missing_citation_indices is None:
            self.missing_citation_indices = []
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()


class RAGBatchTester:
    """Batch tester for RAG system via chat API."""

    def __init__(
        self,
        api_base_url: str = "http://localhost:8000",
        user_id: Optional[uuid.UUID] = None,
    ):
        """Initialize batch tester with API configuration."""
        self.api_base_url = api_base_url.rstrip("/")
        self.user_id = user_id or uuid.uuid4()
        self.session = requests.Session()
        self.results: List[TestResult] = []

    def load_dataset(self, dataset_path: str) -> Dict:
        """
        Load test dataset from JSON file.

        Args:
            dataset_path: Path to test_dataset.json

        Returns:
            Dataset dict with test_cases
        """
        with open(dataset_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def run_single_test(
        self,
        question: str,
        notebook_id: uuid.UUID,
        top_k: int = 5,
        test_id: Optional[str] = None,
    ) -> TestResult:
        """
        Run a single test case via chat API.

        Args:
            question: Test question
            notebook_id: Target notebook UUID
            top_k: Number of chunks to retrieve
            test_id: Optional test case ID

        Returns:
            TestResult with answer and retrieved chunks
        """
        url = f"{self.api_base_url}/api/notebooks/{notebook_id}/chat/stream"
        params = {"user_id": str(self.user_id)}

        payload = {"question": question, "top_k": top_k}

        start_time = time.time()
        citations = []
        citation_indices = []
        missing_citation_indices = []
        answer = None
        raw_answer = None
        success = False
        error_message = None

        try:
            # Stream response
            with self.session.post(
                url,
                json=payload,
                params=params,
                stream=True,
                timeout=300,
                headers={"Accept": "text/event-stream"},
            ) as response:
                response.raise_for_status()

                for line in response.iter_lines():
                    if not line:
                        continue

                    line = line.decode("utf-8")

                    # Parse SSE format: "event: <event>\ndata: <json>\n\n"
                    if line.startswith("event:"):
                        event_type = line.split(":", 1)[1].strip()
                        continue

                    if line.startswith("data:"):
                        try:
                            data = json.loads(line.split(":", 1)[1].strip())

                            if event_type == "citations":
                                citations = data.get("citations", [])
                                citation_indices = data.get("citation_indices", [])
                                missing_citation_indices = data.get("missing_citation_indices", [])

                            elif event_type == "answer":
                                answer = data.get("answer")
                                raw_answer = data.get("raw_answer")

                            elif event_type == "done":
                                success = True

                            elif event_type == "error":
                                error_message = data.get("message", "Unknown error")
                                success = False

                        except json.JSONDecodeError:
                            continue

        except requests.exceptions.Timeout:
            error_message = "Request timed out"
            success = False
        except requests.exceptions.RequestException as e:
            error_message = str(e)
            success = False
        except Exception as e:
            error_message = f"Unexpected error: {e}"
            success = False

        total_time = time.time() - start_time

        # Build chunk list from citations
        retrieved_chunks = []
        for citation in citations:
            retrieved_chunks.append({
                "chunk_id": citation.get("chunk_id"),
                "source_id": citation.get("source_id"),
                "content": citation.get("quote", ""),
                "score": citation.get("score", 0.0),
                "page": citation.get("page"),
            })

        return TestResult(
            test_id=test_id,
            question=question,
            success=success,
            answer=answer,
            raw_answer=raw_answer,
            retrieved_chunks=retrieved_chunks,
            citation_indices=citation_indices,
            missing_citation_indices=missing_citation_indices,
            total_time=total_time,
            error_message=error_message,
        )

    def run_batch_test(
        self,
        dataset: Dict,
        notebook_id: Optional[uuid.UUID] = None,
        top_k: int = 5,
    ) -> List[TestResult]:
        """
        Run all test cases in a dataset.

        Args:
            dataset: Dataset dict with test_cases
            notebook_id: Target notebook (uses dataset default if None)
            top_k: Number of chunks to retrieve

        Returns:
            List of TestResult for all test cases
        """
        test_cases = dataset.get("test_cases", [])

        if notebook_id is None:
            notebook_id_str = test_cases[0].get("notebook_id") if test_cases else None
            if not notebook_id_str:
                raise ValueError("No notebook_id provided and none found in dataset")
            notebook_id = uuid.UUID(notebook_id_str)

        print(f"Running {len(test_cases)} test cases...")
        print(f"Notebook: {notebook_id}")
        print(f"Top-K: {top_k}")

        results = []
        for i, test_case in enumerate(test_cases, 1):
            test_id = test_case.get("id", f"test-{i:03d}")
            question = test_case["question"]

            print(f"\n[{i}/{len(test_cases)}] Running: {test_id}")
            print(f"  Question: {question[:50]}...")

            result = self.run_single_test(
                question=question,
                notebook_id=notebook_id,
                top_k=top_k,
                test_id=test_id,
            )

            results.append(result)

            status = "✓" if result.success else "✗"
            print(f"  {status} Status: {result.success}")
            if result.success:
                print(f"    Time: {result.total_time:.2f}s")
                print(f"    Chunks: {len(result.retrieved_chunks)}")
                print(f"    Answer: {result.answer[:80] if result.answer else 'N/A'}...")
            else:
                print(f"    Error: {result.error_message}")

        self.results = results
        return results

    def save_results(self, output_path: str) -> None:
        """
        Save test results to JSON file.

        Args:
            output_path: Path to save results
        """
        # Convert to serializable format
        results_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_tests": len(self.results),
            "successful": sum(1 for r in self.results if r.success),
            "failed": sum(1 for r in self.results if not r.success),
            "results": [asdict(r) for r in self.results],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results_data, f, ensure_ascii=False, indent=2)

        print(f"\n✅ Results saved to: {output_path}")

    def generate_summary(self) -> Dict:
        """
        Generate summary statistics from test results.

        Returns:
            Dict with summary stats
        """
        successful = [r for r in self.results if r.success]
        failed = [r for r in self.results if not r.success]

        avg_time = sum(r.total_time for r in successful) / len(successful) if successful else 0
        avg_chunks = sum(len(r.retrieved_chunks) for r in successful) / len(successful) if successful else 0

        return {
            "total_tests": len(self.results),
            "successful": len(successful),
            "failed": len(failed),
            "success_rate": len(successful) / len(self.results) if self.results else 0,
            "avg_time": avg_time,
            "avg_chunks": avg_chunks,
        }


def batch_test_dataset(
    dataset_path: str,
    notebook_id: Optional[str] = None,
    api_base_url: str = "http://localhost:8000",
    output_path: Optional[str] = None,
    top_k: int = 5,
) -> List[Dict]:
    """
    Convenience function to run batch tests on a dataset.

    Args:
        dataset_path: Path to test_dataset.json
        notebook_id: Target notebook UUID
        api_base_url: API base URL
        output_path: Optional path to save results
        top_k: Number of chunks to retrieve

    Returns:
        List of result dicts
    """
    tester = RAGBatchTester(api_base_url=api_base_url)

    # Load dataset
    dataset = tester.load_dataset(dataset_path)

    # Run tests
    results = tester.run_batch_test(
        dataset=dataset,
        notebook_id=uuid.UUID(notebook_id) if notebook_id else None,
        top_k=top_k,
    )

    # Save results
    if output_path is None:
        dataset_name = Path(dataset_path).stem
        output_path = f"rag-test-results-{dataset_name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"

    tester.save_results(output_path)

    # Print summary
    summary = tester.generate_summary()
    print("\n" + "="*50)
    print("SUMMARY")
    print("="*50)
    print(f"Total tests: {summary['total_tests']}")
    print(f"Successful: {summary['successful']}")
    print(f"Failed: {summary['failed']}")
    print(f"Success rate: {summary['success_rate']:.1%}")
    print(f"Avg time: {summary['avg_time']:.2f}s")
    print(f"Avg chunks: {summary['avg_chunks']:.1f}")

    return [asdict(r) for r in results]


if __name__ == "__main__":
    import sys
    import os

    if len(sys.argv) < 2:
        print("Usage: python batch_test.py <dataset.json> [notebook_id] [output.json]")
        sys.exit(1)

    dataset_path = sys.argv[1]
    notebook_id = sys.argv[2] if len(sys.argv) > 2 else None
    output_path = sys.argv[3] if len(sys.argv) > 3 else None

    api_url = os.environ.get("API_BASE_URL", "http://localhost:8000")

    batch_test_dataset(
        dataset_path=dataset_path,
        notebook_id=notebook_id,
        api_base_url=api_url,
        output_path=output_path,
    )
