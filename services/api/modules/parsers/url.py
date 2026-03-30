"""
URL/Web document parser using trafilatura.

Extracts clean text content from web pages with HTML removal.
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


class URLParser(BaseParser):
    """
    Parser for web URLs and HTML content.

    Uses trafilatura to extract clean text content from HTML,
    removing scripts, styles, navigation, and other boilerplate.
    """

    def parse(self, file_path: Path) -> ParseResult:
        """
        Parse an HTML file from disk.

        Args:
            file_path: Path to the HTML file.

        Returns:
            ParseResult with extracted text and metadata.

        Raises:
            ParserError: If the file doesn't exist or parsing fails.
        """
        if not file_path.exists():
            raise ParserError(f"File not found: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            return self.parse_html(html_content, url=str(file_path))
        except ParserError:
            raise
        except Exception as e:
            logger.error(f"Failed to read HTML file {file_path}: {e}")
            raise ParserError(f"Failed to read HTML file: {e}")

    def parse_bytes(self, content: bytes, filename: str = "") -> ParseResult:
        """
        Parse HTML content from bytes.

        Args:
            content: Raw HTML bytes.
            filename: Optional filename/URL for context.

        Returns:
            ParseResult with extracted text and metadata.

        Raises:
            ParserError: If parsing fails.
        """
        if not content:
            raise ParserError("Empty HTML content provided")

        try:
            # Detect encoding and decode
            html_string = self._decode_html(content)
            return self.parse_html(html_string, url=filename)
        except ParserError:
            raise
        except Exception as e:
            logger.error(f"Failed to parse HTML bytes: {e}")
            raise ParserError(f"Failed to parse HTML: {e}")

    def parse_html(self, html_content: str, url: str = "") -> ParseResult:
        """
        Parse HTML string content.

        Args:
            html_content: HTML content as string.
            url: Source URL for metadata.

        Returns:
            ParseResult with extracted text and metadata.

        Raises:
            ParserError: If parsing fails.
        """
        if not html_content or not html_content.strip():
            raise ParserError("Empty HTML content provided")

        try:
            import trafilatura

            # Use trafilatura to extract main content
            extracted = trafilatura.extract(
                html_content,
                include_comments=False,
                include_tables=True,
                no_fallback=False,  # Use fallback extraction if main fails
                output_format="txt",
            )

            # If trafilatura returns None, try fallback extraction
            if not extracted:
                extracted = self._fallback_extraction(html_content)

            if not extracted:
                extracted = ""

            # Normalize the text
            normalized_text = self.normalize_text(extracted)

            # Try to extract title
            title = self._extract_title(html_content)

            # Create single page (web pages are not paginated)
            page_content = PageContent(
                page_number=1,
                text=normalized_text,
                headings=self._extract_headings_from_text(normalized_text),
                char_start=0,
                char_end=len(normalized_text),
            )

            # Build metadata
            metadata = {
                "url": url,
                "parser": "trafilatura",
            }

            return ParseResult(
                full_text=normalized_text,
                pages=[page_content],
                metadata=metadata,
                title=title,
                total_pages=1,
                encoding="utf-8",
            )

        except ParserError:
            raise
        except Exception as e:
            logger.error(f"Failed to parse HTML content: {e}")
            raise ParserError(f"Failed to parse HTML: {e}")

    def _decode_html(self, content: bytes) -> str:
        """
        Decode HTML bytes to string, detecting encoding.

        Args:
            content: Raw HTML bytes.

        Returns:
            Decoded HTML string.
        """
        # Try UTF-8 first
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            pass

        # Try to detect encoding using chardet
        try:
            import chardet
            detected = chardet.detect(content)
            encoding = detected.get("encoding", "utf-8")
            return content.decode(encoding, errors="replace")
        except Exception:
            # Fall back to latin-1 which accepts any byte sequence
            return content.decode("latin-1")

    def _extract_title(self, html_content: str) -> Optional[str]:
        """
        Extract title from HTML content.

        Args:
            html_content: HTML content string.

        Returns:
            Extracted title or None.
        """
        try:
            import trafilatura

            # Try to extract using trafilatura's metadata extraction
            metadata = trafilatura.extract_metadata(html_content)
            if metadata and metadata.title:
                return metadata.title
        except Exception:
            pass

        # Fallback: simple regex extraction
        try:
            import re
            title_match = re.search(r"<title[^>]*>([^<]+)</title>", html_content, re.IGNORECASE)
            if title_match:
                return title_match.group(1).strip()
        except Exception:
            pass

        return None

    def _extract_headings_from_text(self, text: str) -> list[str]:
        """
        Extract potential headings from extracted text.

        Since trafilatura flattens the HTML, we look for
        lines that might be headings (short, title-like).

        Args:
            text: Extracted text content.

        Returns:
            List of potential heading strings.
        """
        headings = []
        lines = text.split("\n")

        for line in lines:
            line = line.strip()
            # Potential heading: short line, not ending with punctuation
            if line and len(line) < 100 and not line.endswith((".", ",", ";", ":")):
                # Check if it's likely a heading (capitalized or short)
                words = line.split()
                if len(words) <= 10:
                    headings.append(line)

        # Limit to first 10 potential headings
        return headings[:10]

    def _fallback_extraction(self, html_content: str) -> Optional[str]:
        """
        Fallback text extraction when trafilatura fails.

        Uses simple HTML stripping as a last resort.

        Args:
            html_content: HTML content string.

        Returns:
            Extracted text or None.
        """
        try:
            import re

            # Remove script and style content
            text = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", html_content, flags=re.IGNORECASE)
            text = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", text, flags=re.IGNORECASE)

            # Remove all HTML tags
            text = re.sub(r"<[^>]+>", " ", text)

            # Decode HTML entities
            try:
                import html
                text = html.unescape(text)
            except Exception:
                pass

            # Clean up whitespace
            text = " ".join(text.split())

            return text if text else None

        except Exception as e:
            logger.debug(f"Fallback extraction failed: {e}")
            return None
