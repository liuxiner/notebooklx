"""
Plain text parser.

Normalizes character encoding for plain text content.
"""
from pathlib import Path
from typing import Optional
import logging

from services.api.modules.parsers.base import (
    BaseParser,
    ParseResult,
    PageContent,
    ParserError,
)

logger = logging.getLogger(__name__)


class TextParser(BaseParser):
    """
    Parser for plain text files.

    Normalizes character encoding to UTF-8 and provides
    structured output consistent with other parsers.
    """

    def parse(self, file_path: Path) -> ParseResult:
        """
        Parse a text file from disk.

        Args:
            file_path: Path to the text file.

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
            logger.error(f"Failed to read text file {file_path}: {e}")
            raise ParserError(f"Failed to read text file: {e}")

    def parse_bytes(self, content: bytes, filename: str = "") -> ParseResult:
        """
        Parse text content from bytes.

        Args:
            content: Raw text bytes.
            filename: Optional filename for context.

        Returns:
            ParseResult with extracted text and metadata.

        Raises:
            ParserError: If parsing fails.
        """
        if not content:
            raise ParserError("Empty text content provided")

        try:
            # Decode and normalize the text
            text = self._decode_text(content)
            normalized_text = self.normalize_text(text)

            # Create single page (text files are not paginated)
            page_content = PageContent(
                page_number=1,
                text=normalized_text,
                headings=[],
                char_start=0,
                char_end=len(normalized_text),
            )

            # Build metadata
            metadata = {
                "filename": filename,
                "parser": "text",
                "original_size": len(content),
            }

            return ParseResult(
                full_text=normalized_text,
                pages=[page_content],
                metadata=metadata,
                title=self._extract_title(normalized_text, filename),
                total_pages=1,
                encoding="utf-8",
            )

        except ParserError:
            raise
        except Exception as e:
            logger.error(f"Failed to parse text content: {e}")
            raise ParserError(f"Failed to parse text: {e}")

    def _decode_text(self, content: bytes) -> str:
        """
        Decode text bytes to string, detecting encoding.

        Args:
            content: Raw text bytes.

        Returns:
            Decoded text string in UTF-8.
        """
        # Try UTF-8 first (most common)
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            pass

        # Try to detect encoding using chardet
        try:
            import chardet
            detected = chardet.detect(content)
            encoding = detected.get("encoding")
            if encoding:
                return content.decode(encoding, errors="replace")
        except Exception:
            pass

        # Fall back to latin-1 which accepts any byte sequence
        return content.decode("latin-1")

    def _extract_title(self, text: str, filename: str) -> Optional[str]:
        """
        Extract a title from the text content or filename.

        Args:
            text: Normalized text content.
            filename: Original filename.

        Returns:
            Extracted title or None.
        """
        # Try to use filename without extension as title
        if filename:
            name = Path(filename).stem
            if name:
                return name

        # Try first non-empty line as title
        lines = text.strip().split("\n")
        for line in lines:
            line = line.strip()
            if line and len(line) < 200:
                return line

        return None
