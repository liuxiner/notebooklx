"""
PDF document parser using pdfplumber.

Extracts text from PDF files preserving page numbers and structure.
"""
import io
from pathlib import Path
from typing import List, Optional
import logging

import pdfplumber

from services.api.modules.parsers.base import (
    BaseParser,
    ParseResult,
    PageContent,
    ParserError,
)

logger = logging.getLogger(__name__)


class PDFParser(BaseParser):
    """
    Parser for PDF documents.

    Uses pdfplumber to extract text while preserving page structure
    and metadata like page numbers and character positions.
    """

    def parse(self, file_path: Path) -> ParseResult:
        """
        Parse a PDF file from disk.

        Args:
            file_path: Path to the PDF file.

        Returns:
            ParseResult with extracted text and metadata.

        Raises:
            ParserError: If the file doesn't exist or parsing fails.
        """
        if not file_path.exists():
            raise ParserError(f"File not found: {file_path}")

        try:
            with open(file_path, "rb") as f:
                content = f.read()
            return self.parse_bytes(content, filename=str(file_path.name))
        except ParserError:
            raise
        except Exception as e:
            logger.error(f"Failed to read PDF file {file_path}: {e}")
            raise ParserError(f"Failed to read PDF file: {e}")

    def parse_bytes(self, content: bytes, filename: str = "") -> ParseResult:
        """
        Parse PDF content from bytes.

        Args:
            content: Raw PDF bytes.
            filename: Optional filename for context.

        Returns:
            ParseResult with extracted text and metadata.

        Raises:
            ParserError: If parsing fails.
        """
        if not content:
            raise ParserError("Empty PDF content provided")

        try:
            pdf_stream = io.BytesIO(content)
            return self._extract_from_stream(pdf_stream, filename)
        except ParserError:
            raise
        except Exception as e:
            logger.error(f"Failed to parse PDF{f' ({filename})' if filename else ''}: {e}")
            raise ParserError(f"Failed to parse PDF: {e}")

    def _extract_from_stream(self, pdf_stream: io.BytesIO, filename: str) -> ParseResult:
        """
        Extract text content from a PDF stream.

        Args:
            pdf_stream: BytesIO stream of PDF content.
            filename: Optional filename for metadata.

        Returns:
            ParseResult with extracted text and metadata.
        """
        pages: List[PageContent] = []
        full_text_parts: List[str] = []
        char_offset = 0
        total_pages = 0
        title: Optional[str] = None

        try:
            with pdfplumber.open(pdf_stream) as pdf:
                total_pages = len(pdf.pages)

                # Try to extract title from PDF metadata
                if pdf.metadata:
                    title = pdf.metadata.get("Title")

                for page_num, page in enumerate(pdf.pages, start=1):
                    # Extract text from page
                    page_text = page.extract_text() or ""

                    # Normalize the text
                    normalized_text = self.normalize_text(page_text)

                    # Calculate character positions
                    char_start = char_offset
                    char_end = char_offset + len(normalized_text)

                    # Extract headings (simplified - look for larger font text)
                    headings = self._extract_headings(page)

                    # Create PageContent
                    page_content = PageContent(
                        page_number=page_num,
                        text=normalized_text,
                        headings=headings,
                        char_start=char_start,
                        char_end=char_end,
                    )
                    pages.append(page_content)

                    # Build full text
                    if normalized_text:
                        full_text_parts.append(normalized_text)
                        # Account for newline between pages
                        char_offset = char_end + 1

        except Exception as e:
            raise ParserError(f"Failed to parse PDF: {e}")

        # Combine all text with page separators
        full_text = "\n".join(full_text_parts)

        # Build metadata
        metadata = {
            "filename": filename,
            "parser": "pdfplumber",
        }

        return ParseResult(
            full_text=full_text,
            pages=pages,
            metadata=metadata,
            title=title,
            total_pages=total_pages,
            encoding="utf-8",
        )

    def _extract_headings(self, page) -> List[str]:
        """
        Extract potential headings from a PDF page.

        This is a simplified implementation that looks for text
        with larger font sizes, which often indicates headings.

        Args:
            page: pdfplumber Page object.

        Returns:
            List of heading strings found on the page.
        """
        headings: List[str] = []

        try:
            # Get all characters with font info
            chars = page.chars
            if not chars:
                return headings

            # Find the most common font size (body text)
            font_sizes = [c.get("size", 0) for c in chars if c.get("size")]
            if not font_sizes:
                return headings

            # Calculate average body text size
            avg_size = sum(font_sizes) / len(font_sizes)

            # Group consecutive characters with larger font into potential headings
            current_heading = []
            current_size = 0

            for char in chars:
                char_size = char.get("size", 0)
                char_text = char.get("text", "")

                # If significantly larger than average (1.2x), might be a heading
                if char_size > avg_size * 1.2:
                    if not current_heading or abs(char_size - current_size) < 0.5:
                        current_heading.append(char_text)
                        current_size = char_size
                    else:
                        # New heading detected
                        if current_heading:
                            heading_text = "".join(current_heading).strip()
                            if heading_text and len(heading_text) > 2:
                                headings.append(heading_text)
                        current_heading = [char_text]
                        current_size = char_size
                else:
                    # End of potential heading
                    if current_heading:
                        heading_text = "".join(current_heading).strip()
                        if heading_text and len(heading_text) > 2:
                            headings.append(heading_text)
                        current_heading = []

            # Don't forget last heading
            if current_heading:
                heading_text = "".join(current_heading).strip()
                if heading_text and len(heading_text) > 2:
                    headings.append(heading_text)

        except Exception as e:
            logger.debug(f"Could not extract headings: {e}")

        return headings
