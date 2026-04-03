---
name: rag-dataset-gen
description: RAG Test Dataset Generator - Automatically generates comprehensive test datasets from source documents for RAG evaluation. Analyzes source content, extracts key concepts, generates diverse questions (factual, conceptual, procedural), identifies expected chunks, keywords, and ground truth answers. Outputs test_dataset.json compatible with rag-eval skill. Trigger phrases: "生成测试集", "创建测试数据", "generate test dataset", "RAG 测试集生成".
---

# RAG Test Dataset Generator

## Overview

This skill automatically generates comprehensive test datasets from source documents for RAG evaluation. It analyzes your source files, extracts key concepts, creates diverse question types, and produces a `test_dataset.json` file compatible with the `rag-eval` skill.

## Quick Start

When triggered, this skill will:

1. **Source Collection** - Get paths to source documents
2. **Content Analysis** - Extract and analyze document structure
3. **Question Generation** - Create diverse question types
4. **Ground Truth Annotation** - Mark expected chunks and keywords
5. **Dataset Export** - Generate test_dataset.json

## Workflow

### Step 1: Source Collection

Ask user for source file paths:

```
请提供源文档路径 (支持 PDF, TXT, MD):

格式: 每行一个文件路径
例如:
/path/to/document1.pdf
/path/to/document2.txt
/path/to/document3.md
```

**Supported formats:**
- PDF files (`.pdf`)
- Plain text (`.txt`)
- Markdown (`.md`)
- HTML (`.html`)

### Step 2: Document Analysis

For each source document, extract:

1. **Structure**: Sections, headings, paragraphs
2. **Key concepts**: Domain terms, entities, definitions
3. **Topics**: Main themes and subtopics
4. **Chunks**: Simulate RAG chunking (300-800 tokens)

**Chunking simulation:**
```python
Target chunk size: 300-800 tokens
Overlap: 50-120 tokens
Boundaries: Respect paragraphs and sections
Metadata: page numbers, headings, char positions
```

### Step 3: Question Generation

Generate **diverse question types**:

| Question Type | Description | Example |
|--------------|-------------|---------|
| **Factual** | Direct facts from text | "什么是刺头员工?" |
| **Conceptual** | Definitions and explanations | "刺头员工的特征是什么?" |
| **Procedural** | How-to questions | "如何识别高风险员工?" |
| **Comparative** | Compare items | "A和B有什么区别?" |
| **Causal** | Cause-effect relationships | "为什么会出现X现象?" |
| **Comprehensive** | Multi-aspect summary | "总结一下绩效评估的要点" |

**Per-document question allocation:**
- Short document (<2K tokens): 3-5 questions
- Medium document (2K-10K tokens): 5-10 questions
- Long document (>10K tokens): 10-15 questions

**Question quality criteria:**
- Answerable from source content
- Specific enough to test retrieval
- Diverse in difficulty
- Covers multiple sections

### Step 4: Ground Truth Annotation

For each generated question:

1. **Expected Chunks**: Identify which chunks contain the answer
   ```json
   "expected_chunks": ["chunk_8", "chunk_11", "chunk_15"]
   ```

2. **Expected Keywords**: Extract key terms from answer
   ```json
   "expected_keywords": ["刺头", "定义", "管理", "风险", "预防"]
   ```

3. **Ground Truth Summary**: Create reference answer
   ```json
   "ground_truth_summary": "刺头是指在组织中存在高离职风险和高绩效风险的员工..."
   ```

4. **Category**: Classify by topic/domain
   ```json
   "category": "employee_management"
   ```

5. **Thresholds**: Set evaluation thresholds
   ```json
   "min_recall": 0.9,
   "min_mrr": 0.8
   ```

### Step 5: Dataset Export

Generate `test_dataset.json` with structure:

```json
{
  "metadata": {
    "version": "1.0",
    "created": "2026-04-01",
    "description": "Generated from N source documents",
    "sources": [
      {"path": "/path/to/doc1.pdf", "pages": 15, "chunks": 42},
      {"path": "/path/to/doc2.txt", "pages": 0, "chunks": 18}
    ]
  },
  "test_cases": [
    {
      "id": "test-001",
      "question": "...",
      "notebook_id": "...",
      "expected_chunks": ["chunk_8", "chunk_11"],
      "expected_keywords": ["keyword1", "keyword2"],
      "ground_truth_summary": "...",
      "min_recall": 0.9,
      "min_mrr": 0.8,
      "category": "category_name",
      "difficulty": "medium",
      "question_type": "factual"
    }
  ],
  "evaluation_thresholds": {
    "performance": {...},
    "retrieval": {...},
    "answer": {...},
    "citation": {...}
  }
}
```

## Resources

### scripts/generate_dataset.py

Main dataset generator script that:

```python
from scripts.generate_dataset import DatasetGenerator

generator = DatasetGenerator(
    chunk_size=500,
    chunk_overlap=80,
    questions_per_document=8
)

# Add sources
generator.add_source("/path/to/doc1.pdf")
generator.add_source("/path/to/doc2.txt")

# Generate dataset
dataset = generator.generate()

# Save to file
generator.save("data/test_dataset.json")
```

**Key methods:**
- `add_source(path)` - Add a source document
- `analyze_document(path)` - Extract structure and concepts
- `generate_questions(doc)` - Create diverse questions
- `annotate_ground_truth(question, doc)` - Find chunks and keywords
- `save(output_path)` - Export as JSON

### scripts/document_parser.py

Document parser supporting multiple formats:

```python
from scripts.document_parser import DocumentParser

parser = DocumentParser()
doc = parser.parse("/path/to/document.pdf")

# Returns:
# - content: Full text
# - sections: List of sections with headings
# - metadata: Page count, word count, etc.
# - chunks: Simulated RAG chunks
```

**Supported parsers:**
- PDF: PyPDF2 or pdfplumber
- Text: Direct file read
- Markdown: Parse frontmatter and sections
- HTML: BeautifulSoup with text extraction

## Example Output

After running the skill, user gets:

```
✅ 测试数据集生成完成

📄 输出文件: data/test_dataset.json

📊 数据集统计:
   • 源文档: 3 个
   • 总页数: 127 页
   • 生成 Chunks: 342 个
   • 生成问题: 28 个

📋 问题分布:
   • 事实性问题: 10 个
   • 概念性问题: 8 个
   • 流程性问题: 6 个
   • 综合性问题: 4 个

🏷️ 主题分布:
   • employee_management: 12 个
   • performance: 8 个
   • recruitment: 8 个

💾 下一步:
   1. 检查生成的问题质量
   2. 使用 rag-eval skill 进行评估
   3. 根据需要调整阈值
```

## Advanced Features

### Chunk-Level Annotations

For more precise evaluation, annotate at chunk level:

```json
{
  "id": "test-001",
  "question": "如何识别高风险员工?",
  "expected_chunks": [
    {
      "chunk_id": "chunk_15",
      "relevance": 0.95,
      "contains_answer": true
    },
    {
      "chunk_id": "chunk_22",
      "relevance": 0.80,
      "contains_answer": true
    }
  ]
}
```

### Difficulty Levels

Classify questions by difficulty:

| Level | Description | Example |
|-------|-------------|---------|
| **easy** | Direct lookup | "什么是X?" |
| **medium** | Requires synthesis | "X和Y有什么区别?" |
| **hard** | Multi-hop reasoning | "基于X和Y，如何解决Z?" |

### Category Mapping

Auto-generate categories from document structure:

```
Document sections → Categories
"Section 3: Employee Management" → "employee_management"
"Section 4: Performance Review" → "performance"
```

## User Interaction Guidelines

- **Progressive**: Show progress as each document is processed
- **Validation**: Ask user to review sample questions before final export
- **Editable**: Allow users to add/edit questions after generation
- **Flexible**: Skip optional fields if user doesn't have data
- **Bilingual**: Support Chinese and English content

## Quality Checklist

Before exporting, verify:

✅ Questions are answerable from sources
✅ Expected chunks are correct
✅ Keywords are representative
✅ Ground truth summaries are accurate
✅ Categories are consistent
✅ Thresholds are appropriate for difficulty

## Tips for Best Results

1. **Clean sources**: Ensure documents are well-formatted
2. **Diverse content**: Use documents with different structures
3. **Review output**: Always check generated questions for quality
4. **Iterate**: Add more questions manually if needed
5. **Version control**: Keep track of dataset versions

## Integration with rag-eval

Once generated, use with rag-eval:

```bash
# The generated test_dataset.json is directly compatible
# with rag-eval skill's auto mode
```

rag-eval will:
1. Load test cases from the dataset
2. Call RAG API for each question
3. Compare retrieved chunks with expected_chunks
4. Calculate Recall@10, MRR, and other metrics
5. Generate evaluation report

## Notes

- Generated questions should be reviewed by domain experts
- Update dataset regularly as documents change
- Keep track of dataset version and changelog
- Consider maintaining separate datasets for different domains
