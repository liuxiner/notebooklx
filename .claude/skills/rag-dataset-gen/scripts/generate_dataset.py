#!/usr/bin/env python3
"""
RAG Test Dataset Generator

Generates comprehensive test datasets from source documents for RAG evaluation.
Creates diverse question types, annotates expected chunks, and produces
test_dataset.json compatible with rag-eval skill.
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from document_parser import DocumentParser, ParsedDocument, Section, Chunk


@dataclass
class QuestionType:
    """Question type classification."""
    name: str
    description: str
    difficulty: str  # easy, medium, hard
    template: str


@dataclass
class TestCase:
    """A single test case for RAG evaluation."""
    id: str
    question: str
    notebook_id: str
    expected_chunks: List[str]
    expected_keywords: List[str]
    ground_truth_summary: str
    min_recall: float
    min_mrr: float
    category: str
    difficulty: str
    question_type: str
    source_document: str


QUESTION_TYPES = {
    "factual": QuestionType(
        name="factual",
        description="Direct facts from text",
        difficulty="easy",
        template="什么是{term}?"
    ),
    "conceptual": QuestionType(
        name="conceptual",
        description="Definitions and explanations",
        difficulty="medium",
        template="{term}的特征/要点是什么?"
    ),
    "procedural": QuestionType(
        name="procedural",
        description="How-to questions",
        difficulty="medium",
        template="如何{action}?"
    ),
    "comparative": QuestionType(
        name="comparative",
        description="Compare items",
        difficulty="hard",
        template="{term_a}和{term_b}有什么区别?"
    ),
    "comprehensive": QuestionType(
        name="comprehensive",
        description="Multi-aspect summary",
        difficulty="hard",
        template="总结一下{topic}的要点"
    )
}


class DatasetGenerator:
    """Generate test datasets from source documents."""

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 80,
        questions_per_document: int = 8,
        notebook_id: str = "default-notebook"
    ):
        self.parser = DocumentParser(chunk_size, chunk_overlap)
        self.questions_per_document = questions_per_document
        self.notebook_id = notebook_id
        self.documents: List[ParsedDocument] = []
        self.test_cases: List[TestCase] = []

    def add_source(self, file_path: str) -> None:
        """Add a source document."""
        doc = self.parser.parse(file_path)
        self.documents.append(doc)
        print(f"✅ 已加载: {Path(file_path).name} ({doc.metadata.get('page_count', 0)} 页, {len(doc.chunks)} chunks)")

    def add_sources(self, file_paths: List[str]) -> None:
        """Add multiple source documents."""
        for path in file_paths:
            try:
                self.add_source(path)
            except Exception as e:
                print(f"⚠️  跳过 {path}: {e}")

    def generate(self) -> Dict[str, Any]:
        """Generate the complete test dataset."""
        print("\n🔍 分析文档内容...")

        all_chunks = []
        chunk_index = 0

        # Collect all chunks from all documents
        for doc in self.documents:
            for chunk in doc.chunks:
                # Assign global chunk ID
                chunk.chunk_id = f"chunk_{chunk_index}"
                all_chunks.append(chunk)
                chunk_index += 1

        print(f"   总共 {len(all_chunks)} 个 chunks")

        # Generate questions for each document
        print("\n❓ 生成测试问题...")
        test_case_id = 1

        for doc_idx, doc in enumerate(self.documents):
            print(f"   处理: {Path(doc.source_path).name}")

            # Determine question count based on document size
            word_count = doc.metadata.get('word_count', 0)
            if word_count < 2000:
                num_questions = min(5, self.questions_per_document)
            elif word_count < 10000:
                num_questions = min(10, self.questions_per_document)
            else:
                num_questions = min(15, self.questions_per_document)

            # Generate questions
            doc_cases = self._generate_questions_for_document(
                doc, all_chunks, test_case_id, num_questions
            )
            self.test_cases.extend(doc_cases)
            test_case_id += len(doc_cases)

        print(f"   总共生成 {len(self.test_cases)} 个问题")

        # Build dataset
        dataset = {
            "metadata": {
                "version": "1.0",
                "created": datetime.now().strftime("%Y-%m-%d"),
                "description": f"Generated from {len(self.documents)} source documents",
                "sources": [
                    {
                        "path": doc.source_path,
                        "pages": doc.metadata.get('page_count', 0),
                        "chunks": len(doc.chunks),
                        "words": doc.metadata.get('word_count', 0)
                    }
                    for doc in self.documents
                ],
                "total_chunks": len(all_chunks),
                "total_test_cases": len(self.test_cases)
            },
            "test_cases": [self._serialize_test_case(tc) for tc in self.test_cases],
            "evaluation_thresholds": {
                "performance": {
                    "min_score": 70,
                    "retrieval_latency_ms": 300,
                    "chat_first_token_s": 2.0
                },
                "retrieval": {
                    "min_score": 3.5,
                    "min_recall_at_10": 90,
                    "min_mrr": 0.8
                },
                "answer": {
                    "min_score": 3.5,
                    "min_groundedness": 90,
                    "min_completeness": 85,
                    "min_faithfulness": 95
                },
                "citation": {
                    "min_score": 3.5,
                    "min_support_rate": 95,
                    "max_wrong_rate": 5
                }
            }
        }

        return dataset

    def _generate_questions_for_document(
        self,
        doc: ParsedDocument,
        all_chunks: List[Chunk],
        start_id: int,
        num_questions: int
    ) -> List[TestCase]:
        """Generate test questions for a document."""
        test_cases = []

        # Extract key concepts and entities
        concepts = self._extract_concepts(doc)
        categories = self._infer_categories(doc)

        # Allocate question types
        type_allocation = self._allocate_question_types(num_questions)
        case_id = start_id

        for qtype, count in type_allocation.items():
            for _ in range(count):
                # Generate a question of this type
                case = self._generate_question(
                    doc, all_chunks, concepts, categories, qtype, case_id
                )
                if case:
                    test_cases.append(case)
                    case_id += 1

        return test_cases

    def _extract_concepts(self, doc: ParsedDocument) -> List[str]:
        """Extract key concepts and entities from document."""
        concepts = []

        # From section headings
        for section in doc.sections:
            if section.heading:
                words = re.findall(r'[\w]+', section.heading)
                concepts.extend([w for w in words if len(w) > 2])

        # From chunk content (high frequency words)
        word_freq = {}
        for chunk in doc.chunks:
            words = re.findall(r'[\w]+', chunk.content.lower())
            for word in words:
                if len(word) > 2:
                    word_freq[word] = word_freq.get(word, 0) + 1

        # Get top frequent words
        top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:50]
        concepts.extend([word for word, freq in top_words if freq > 3])

        # Remove duplicates and limit
        return list(set(concepts))[:100]

    def _infer_categories(self, doc: ParsedDocument) -> List[str]:
        """Infer categories from document structure."""
        categories = []

        for section in doc.sections:
            if section.heading:
                # Convert heading to category name
                category = re.sub(r'[^\w\u4e00-\u9fff]+', '_', section.heading.lower())
                category = category.strip('_')
                if category and len(category) > 2:
                    categories.append(category)

        # Default category
        if not categories:
            categories.append("general")

        return list(set(categories))

    def _allocate_question_types(self, total: int) -> Dict[str, int]:
        """Allocate question types with balanced distribution."""
        allocation = {}

        # Distribution: 40% factual, 25% conceptual, 20% procedural, 10% comparative, 5% comprehensive
        allocation["factual"] = max(1, int(total * 0.4))
        allocation["conceptual"] = max(1, int(total * 0.25))
        allocation["procedural"] = max(1, int(total * 0.20))

        remaining = total - sum(allocation.values())
        if remaining > 0:
            allocation["comparative"] = max(1, remaining // 2)
            allocation["comprehensive"] = max(1, remaining - allocation.get("comparative", 0))

        return allocation

    def _generate_question(
        self,
        doc: ParsedDocument,
        all_chunks: List[Chunk],
        concepts: List[str],
        categories: List[str],
        qtype: str,
        case_id: int
    ) -> Optional[TestCase]:
        """Generate a single test question."""
        # Pick a random chunk as the source
        import random
        source_chunk = random.choice(doc.chunks)

        # Generate question based on type
        if qtype == "factual":
            question = self._generate_factual_question(source_chunk, concepts)
        elif qtype == "conceptual":
            question = self._generate_conceptual_question(source_chunk, concepts)
        elif qtype == "procedural":
            question = self._generate_procedural_question(source_chunk, concepts)
        elif qtype == "comparative":
            question = self._generate_comparative_question(doc, concepts)
        elif qtype == "comprehensive":
            question = self._generate_comprehensive_question(doc, concepts)
        else:
            return None

        if not question:
            return None

        # Find relevant chunks (simulate expected retrieval)
        expected_chunks = self._find_relevant_chunks(question, all_chunks)

        # Extract keywords
        keywords = self._extract_keywords_from_text(question + " " + source_chunk.content)

        # Generate ground truth summary
        summary = self._generate_ground_truth(source_chunk, question)

        # Pick category
        category = random.choice(categories)

        # Set thresholds based on difficulty
        qtype_info = QUESTION_TYPES.get(qtype, QUESTION_TYPES["factual"])
        if qtype_info.difficulty == "easy":
            min_recall, min_mrr = 0.95, 0.85
        elif qtype_info.difficulty == "medium":
            min_recall, min_mrr = 0.90, 0.80
        else:  # hard
            min_recall, min_mrr = 0.85, 0.75

        return TestCase(
            id=f"test-{case_id:03d}",
            question=question,
            notebook_id=self.notebook_id,
            expected_chunks=expected_chunks,
            expected_keywords=keywords[:10],
            ground_truth_summary=summary,
            min_recall=min_recall,
            min_mrr=min_mrr,
            category=category,
            difficulty=qtype_info.difficulty,
            question_type=qtype,
            source_document=Path(doc.source_path).name
        )

    def _generate_factual_question(self, chunk: Chunk, concepts: List[str]) -> Optional[str]:
        """Generate a factual question."""
        # Find a definition or key term in the chunk
        sentences = re.split(r'[。！？.!?]', chunk.content)

        for sent in sentences:
            sent = sent.strip()
            if len(sent) > 20 and len(sent) < 150:
                # Look for definition patterns
                if '是' in sent or '指' in sent or '定义' in sent:
                    # Extract the subject
                    match = re.match(r'([^，,]{2,10})[是指]', sent)
                    if match:
                        term = match.group(1)
                        return f"什么是{term}?"

        # Fallback: ask about a concept
        if concepts:
            concept = concepts[0]
            return f"什么是{concept}?"

        return None

    def _generate_conceptual_question(self, chunk: Chunk, concepts: List[str]) -> Optional[str]:
        """Generate a conceptual question."""
        if concepts:
            concept = concepts[0] if concepts else "相关概念"
            return f"{concept}的特征是什么?"
        return None

    def _generate_procedural_question(self, chunk: Chunk, concepts: List[str]) -> Optional[str]:
        """Generate a procedural question."""
        # Look for action verbs
        action_patterns = ['如何', '怎样', '怎么', '方法', '步骤', '流程']

        for pattern in action_patterns:
            if pattern in chunk.content:
                # Extract nearby context
                idx = chunk.content.find(pattern)
                context = chunk.content[idx:idx+50]
                return context if len(context) > 10 else None

        # Fallback
        if concepts:
            return f"如何识别{concepts[0]}?"

        return None

    def _generate_comparative_question(self, doc: ParsedDocument, concepts: List[str]) -> Optional[str]:
        """Generate a comparative question."""
        if len(concepts) >= 2:
            return f"{concepts[0]}和{concepts[1]}有什么区别?"
        return None

    def _generate_comprehensive_question(self, doc: ParsedDocument, concepts: List[str]) -> Optional[str]:
        """Generate a comprehensive question."""
        if concepts:
            topic = concepts[0]
            return f"总结一下{topic}的主要要点"
        return None

    def _find_relevant_chunks(self, question: str, all_chunks: List[Chunk]) -> List[str]:
        """Find chunks relevant to the question (simulate expected retrieval)."""
        # Simple keyword matching
        question_words = set(re.findall(r'[\w]+', question.lower()))

        scored_chunks = []
        for chunk in all_chunks:
            chunk_words = set(re.findall(r'[\w]+', chunk.content.lower()))
            overlap = len(question_words & chunk_words)
            if overlap > 0:
                scored_chunks.append((chunk.chunk_id, overlap))

        # Sort by overlap and return top chunk IDs
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        return [chunk_id for chunk_id, _ in scored_chunks[:3]]

    def _extract_keywords_from_text(self, text: str) -> List[str]:
        """Extract keywords from text."""
        words = re.findall(r'[\w\u4e00-\u9fff]+', text)
        word_freq = {}

        for word in words:
            if len(word) > 1:
                word_freq[word] = word_freq.get(word, 0) + 1

        # Return top words by frequency
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, freq in sorted_words[:15]]

    def _generate_ground_truth(self, chunk: Chunk, question: str) -> str:
        """Generate ground truth summary from chunk content."""
        # Take first few sentences
        sentences = re.split(r'[。！？.!?]', chunk.content)

        summary_parts = []
        char_count = 0

        for sent in sentences:
            sent = sent.strip()
            if sent and char_count + len(sent) < 200:
                summary_parts.append(sent)
                char_count += len(sent)

        return '。'.join(summary_parts) + ('。' if summary_parts else '')

    def _serialize_test_case(self, case: TestCase) -> Dict[str, Any]:
        """Serialize test case to dictionary."""
        return {
            "id": case.id,
            "question": case.question,
            "notebook_id": case.notebook_id,
            "expected_chunks": case.expected_chunks,
            "expected_keywords": case.expected_keywords,
            "ground_truth_summary": case.ground_truth_summary,
            "min_recall": case.min_recall,
            "min_mrr": case.min_mrr,
            "category": case.category,
            "difficulty": case.difficulty,
            "question_type": case.question_type,
            "source_document": case.source_document
        }

    def save(self, output_path: str) -> None:
        """Generate and save dataset to file."""
        dataset = self.generate()

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        with open(output, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, ensure_ascii=False, indent=2)

        # Print summary
        self._print_summary(dataset, output)

    def _print_summary(self, dataset: Dict[str, Any], output_path: Path) -> None:
        """Print generation summary."""
        test_cases = dataset["test_cases"]

        # Count by type
        type_counts = {}
        difficulty_counts = {}
        category_counts = {}

        for case in test_cases:
            qtype = case.get("question_type", "unknown")
            difficulty = case.get("difficulty", "unknown")
            category = case.get("category", "unknown")

            type_counts[qtype] = type_counts.get(qtype, 0) + 1
            difficulty_counts[difficulty] = difficulty_counts.get(difficulty, 0) + 1
            category_counts[category] = category_counts.get(category, 0) + 1

        print("\n" + "="*60)
        print("✅ 测试数据集生成完成")
        print("="*60)
        print(f"\n📄 输出文件: {output_path}")
        print(f"\n📊 数据集统计:")
        print(f"   • 源文档: {len(dataset['metadata']['sources'])} 个")
        print(f"   • 总页数: {sum(s.get('pages', 0) for s in dataset['metadata']['sources'])} 页")
        print(f"   • 生成 Chunks: {dataset['metadata']['total_chunks']} 个")
        print(f"   • 生成问题: {len(test_cases)} 个")

        if type_counts:
            print(f"\n📋 问题分布:")
            for qtype, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
                qtype_name = QUESTION_TYPES.get(qtype, QuestionType(qtype, "", "", "")).name
                print(f"   • {qtype_name}: {count} 个")

        if difficulty_counts:
            print(f"\n🎯 难度分布:")
            for difficulty, count in sorted(difficulty_counts.items(), key=lambda x: x[1], reverse=True):
                print(f"   • {difficulty}: {count} 个")

        if category_counts:
            print(f"\n🏷️  主题分布 (前5):")
            sorted_cats = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            for category, count in sorted_cats:
                print(f"   • {category}: {count} 个")

        print(f"\n💾 下一步:")
        print(f"   1. 检查生成的问题质量")
        print(f"   2. 使用 rag-eval skill 进行评估")
        print(f"   3. 根据需要调整阈值")
        print("\n" + "="*60)


def main():
    """CLI for manual dataset generation."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python generate_dataset.py <file1> [file2] ...")
        print("\nExample:")
        print("  python generate_dataset.py /path/to/doc1.pdf /path/to/doc2.txt")
        sys.exit(1)

    generator = DatasetGenerator(
        questions_per_document=8,
        notebook_id="test-notebook"
    )

    # Add all provided files
    for file_path in sys.argv[1:]:
        try:
            generator.add_source(file_path)
        except Exception as e:
            print(f"Error loading {file_path}: {e}")

    if not generator.documents:
        print("No valid documents loaded.")
        sys.exit(1)

    # Save to default location
    script_dir = Path(__file__).parent
    output_path = script_dir.parent / "data" / "test_dataset.json"

    generator.save(str(output_path))


if __name__ == '__main__':
    main()
