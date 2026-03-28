"""
Base parser interface and shared types for document parsing.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List
from pathlib import Path


class ParserError(Exception):
    """Base exception for parser errors."""
    pass


@dataclass
class PageContent:
    """Content extracted from a single page."""
    page_number: int
    text: str
    headings: List[str] = field(default_factory=list)
    char_start: int = 0
    char_end: int = 0


@dataclass
class ParseResult:
    """Result of parsing a document."""
    full_text: str
    pages: List[PageContent]
    metadata: dict = field(default_factory=dict)
    title: Optional[str] = None
    total_pages: int = 0
    encoding: str = "utf-8"

    @property
    def page_count(self) -> int:
        """Return the number of pages parsed."""
        return len(self.pages)


class BaseParser(ABC):
    """Abstract base class for document parsers."""

    @abstractmethod
    def parse(self, file_path: Path) -> ParseResult:
        """
        Parse a document and return structured content.

        Args:
            file_path: Path to the document file.

        Returns:
            ParseResult with extracted text and metadata.

        Raises:
            ParserError: If parsing fails.
        """
        pass

    @abstractmethod
    def parse_bytes(self, content: bytes, filename: str = "") -> ParseResult:
        """
        Parse document content from bytes.

        Args:
            content: Raw bytes of the document.
            filename: Optional filename for context.

        Returns:
            ParseResult with extracted text and metadata.

        Raises:
            ParserError: If parsing fails.
        """
        pass

    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Normalize text encoding and whitespace.

        Args:
            text: Raw text to normalize.

        Returns:
            Normalized UTF-8 text.
        """
        if not text:
            return ""
        # Normalize unicode characters
        import unicodedata
        text = unicodedata.normalize("NFKC", text)
        # Replace multiple whitespace with single space (preserve newlines)
        lines = text.split("\n")
        normalized_lines = []
        for line in lines:
            # Collapse multiple spaces within a line
            normalized_line = " ".join(line.split())
            normalized_lines.append(normalized_line)
        return "\n".join(normalized_lines)
