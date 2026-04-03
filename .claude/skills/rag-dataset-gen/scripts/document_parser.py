#!/usr/bin/env python3
"""
Document Parser for RAG Test Dataset Generation

Supports parsing various document formats (PDF, TXT, MD, HTML)
and extracting structured content with simulated RAG chunking.
"""

import re
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Section:
    """A document section with heading and content."""
    heading: str
    level: int  # 1 for H1, 2 for H2, etc.
    content: str
    char_start: int
    char_end: int
    page_number: Optional[int] = None


@dataclass
class Chunk:
    """A simulated RAG chunk."""
    chunk_id: str
    content: str
    char_start: int
    char_end: int
    page_numbers: List[int] = field(default_factory=list)
    headings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    """A parsed document with structured content."""
    source_path: str
    content: str
    sections: List[Section]
    chunks: List[Chunk]
    metadata: Dict[str, Any]
    parsed_at: str = field(default_factory=lambda: datetime.now().isoformat())


class DocumentParser:
    """Parse documents and simulate RAG chunking."""

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 80,
        min_chunk_size: int = 200
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

    def parse(self, file_path: str) -> ParsedDocument:
        """Parse a document file."""
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Parse based on file type
        if path.suffix.lower() == '.pdf':
            return self._parse_pdf(file_path)
        elif path.suffix.lower() in ['.txt', '.text']:
            return self._parse_text(file_path)
        elif path.suffix.lower() in ['.md', '.markdown']:
            return self._parse_markdown(file_path)
        elif path.suffix.lower() in ['.html', '.htm']:
            return self._parse_html(file_path)
        else:
            raise ValueError(f"Unsupported file type: {path.suffix}")

    def _parse_pdf(self, file_path: str) -> ParsedDocument:
        """Parse PDF document."""
        try:
            import PyPDF2
        except ImportError:
            raise ImportError("PyPDF2 required for PDF parsing. Install with: pip install PyPDF2")

        content_parts = []
        sections = []
        current_pos = 0

        with open(file_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            num_pages = len(pdf_reader.pages)

            for page_num, page in enumerate(pdf_reader.pages, 1):
                page_text = page.extract_text()
                if page_text.strip():
                    content_parts.append(page_text)

        full_content = "\n\n".join(content_parts)

        # Extract sections (simple heuristic for headings)
        sections = self._extract_sections_from_text(full_content)

        # Create chunks
        chunks = self._create_chunks(full_content)

        metadata = {
            "file_type": "pdf",
            "page_count": num_pages,
            "word_count": len(full_content.split()),
            "char_count": len(full_content)
        }

        return ParsedDocument(
            source_path=file_path,
            content=full_content,
            sections=sections,
            chunks=chunks,
            metadata=metadata
        )

    def _parse_text(self, file_path: str) -> ParsedDocument:
        """Parse plain text document."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        sections = self._extract_sections_from_text(content)
        chunks = self._create_chunks(content)

        metadata = {
            "file_type": "txt",
            "page_count": 0,
            "word_count": len(content.split()),
            "char_count": len(content)
        }

        return ParsedDocument(
            source_path=file_path,
            content=content,
            sections=sections,
            chunks=chunks,
            metadata=metadata
        )

    def _parse_markdown(self, file_path: str) -> ParsedDocument:
        """Parse markdown document."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract markdown sections
        sections = self._extract_markdown_sections(content)
        chunks = self._create_chunks(content)

        metadata = {
            "file_type": "md",
            "page_count": 0,
            "word_count": len(content.split()),
            "char_count": len(content)
        }

        return ParsedDocument(
            source_path=file_path,
            content=content,
            sections=sections,
            chunks=chunks,
            metadata=metadata
        )

    def _parse_html(self, file_path: str) -> ParsedDocument:
        """Parse HTML document."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            raise ImportError("beautifulsoup4 required for HTML parsing. Install with: pip install beautifulsoup4")

        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, 'html.parser')

        # Extract text content
        content = soup.get_text(separator='\n\n', strip=True)

        sections = self._extract_sections_from_text(content)
        chunks = self._create_chunks(content)

        metadata = {
            "file_type": "html",
            "page_count": 0,
            "word_count": len(content.split()),
            "char_count": len(content)
        }

        return ParsedDocument(
            source_path=file_path,
            content=content,
            sections=sections,
            chunks=chunks,
            metadata=metadata
        )

    def _extract_markdown_sections(self, content: str) -> List[Section]:
        """Extract sections from markdown content."""
        sections = []
        lines = content.split('\n')

        current_section = Section("", 0, "", 0, 0)
        section_content = []
        current_pos = 0

        for line in lines:
            # Check for heading
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if heading_match:
                # Save previous section
                if current_section.heading:
                    current_section.content = '\n'.join(section_content)
                    current_section.char_end = current_pos
                    sections.append(current_section)

                # Start new section
                level = len(heading_match.group(1))
                heading = heading_match.group(2).strip()
                current_section = Section(heading, level, "", current_pos, 0)
                section_content = []
            else:
                section_content.append(line)

            current_pos += len(line) + 1

        # Add last section
        if current_section.heading:
            current_section.content = '\n'.join(section_content)
            current_section.char_end = current_pos
            sections.append(current_section)

        return sections

    def _extract_sections_from_text(self, content: str) -> List[Section]:
        """Extract sections from plain text using simple heuristics."""
        sections = []

        # Look for all-caps lines as potential headings
        lines = content.split('\n')
        current_section = Section("", 0, "", 0, 0)
        section_content = []
        current_pos = 0

        for line in lines:
            # Check if line looks like a heading (short, possibly all caps)
            stripped = line.strip()
            if stripped and len(stripped) < 80 and stripped.isupper() and not stripped.endswith('.'):
                # Save previous section
                if current_section.heading:
                    current_section.content = '\n'.join(section_content)
                    current_section.char_end = current_pos
                    sections.append(current_section)

                # Start new section
                current_section = Section(stripped, 1, "", current_pos, 0)
                section_content = []
            else:
                section_content.append(line)

            current_pos += len(line) + 1

        # Add last section
        if current_section.content or current_section.heading:
            current_section.content = '\n'.join(section_content)
            current_section.char_end = current_pos
            sections.append(current_section)

        # If no sections found, create one with all content
        if not sections:
            sections.append(Section("Introduction", 1, content, 0, len(content)))

        return sections

    def _create_chunks(self, content: str) -> List[Chunk]:
        """Create chunks from content simulating RAG chunking."""
        chunks = []

        # Split into paragraphs first
        paragraphs = re.split(r'\n\n+', content)

        current_chunk = ""
        chunk_start = 0
        chunk_index = 0
        overlap_buffer = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Check if adding this paragraph exceeds chunk size
            test_chunk = current_chunk + "\n\n" + para if current_chunk else para

            if len(test_chunk) > self.chunk_size and current_chunk:
                # Save current chunk
                if len(current_chunk) >= self.min_chunk_size:
                    chunk_end = chunk_start + len(current_chunk)
                    chunks.append(Chunk(
                        chunk_id=f"chunk_{chunk_index}",
                        content=current_chunk,
                        char_start=chunk_start,
                        char_end=chunk_end,
                        headings=self._get_headings_at_position(content, chunk_start)
                    ))
                    chunk_index += 1

                # Keep overlap buffer
                words = current_chunk.split()
                overlap_words = words[-self.chunk_overlap//5:] if len(words) > self.chunk_overlap//5 else []
                overlap_buffer = ' '.join(overlap_words)

                # Start new chunk
                chunk_start = chunk_end
                current_chunk = overlap_buffer + "\n\n" + para if overlap_buffer else para
            else:
                current_chunk = test_chunk

        # Add final chunk
        if current_chunk and len(current_chunk) >= self.min_chunk_size:
            chunks.append(Chunk(
                chunk_id=f"chunk_{chunk_index}",
                content=current_chunk,
                char_start=chunk_start,
                char_end=chunk_start + len(current_chunk),
                headings=self._get_headings_at_position(content, chunk_start)
            ))

        return chunks

    def _get_headings_at_position(self, content: str, pos: int) -> List[str]:
        """Get relevant headings for a position in content."""
        # Simple heuristic: find nearest preceding headings
        lines = content[:pos].split('\n')
        headings = []

        for line in reversed(lines):
            stripped = line.strip()
            if stripped.startswith('#'):
                level = len(stripped) - len(stripped.lstrip('#'))
                heading = stripped.lstrip('#').strip()
                headings.insert(0, f"H{level}: {heading}")
            elif stripped.isupper() and len(stripped) < 80:
                headings.insert(0, stripped)

        return headings[-3:] if headings else []  # Return last 3 headings


def main():
    """CLI for testing."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python document_parser.py <file_path>")
        sys.exit(1)

    parser = DocumentParser(chunk_size=500, chunk_overlap=80)
    doc = parser.parse(sys.argv[1])

    print(f"\n📄 Document: {Path(sys.argv[1]).name}")
    print(f"   Content length: {len(doc.content)} chars")
    print(f"   Sections: {len(doc.sections)}")
    print(f"   Chunks: {len(doc.chunks)}")
    print(f"\n📋 Metadata:")
    for key, value in doc.metadata.items():
        print(f"   {key}: {value}")

    if doc.sections:
        print(f"\n📑 Sections (first 5):")
        for section in doc.sections[:5]:
            print(f"   - {section.heading[:50]}")

    if doc.chunks:
        print(f"\n🧩 Chunks (first 3):")
        for chunk in doc.chunks[:3]:
            print(f"   - {chunk.chunk_id}: {chunk.content[:60]}...")


if __name__ == '__main__':
    main()
