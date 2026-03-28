"""
Google Docs parser for public documents.

Extracts text content from publicly shared Google Docs via the export API.
"""
from pathlib import Path
import re
import logging

import requests

from services.api.modules.parsers.base import (
    BaseParser,
    ParseResult,
    PageContent,
    ParserError,
)

logger = logging.getLogger(__name__)


class GoogleDocsParser(BaseParser):
    """
    Parser for Google Docs public documents.

    Extracts text content from publicly shared Google Docs by
    fetching the document via the export API.
    """

    # Regex pattern for extracting document IDs from Google Docs URLs
    DOC_ID_PATTERN = r"docs\.google\.com/document/d/([a-zA-Z0-9_-]+)"

    # Timeout for HTTP requests (seconds)
    REQUEST_TIMEOUT = 30

    def parse(self, file_path: Path) -> ParseResult:
        """
        Parse is not applicable for Google Docs - use parse_url instead.

        Raises:
            ParserError: Always, as Google Docs requires URL-based parsing.
        """
        raise ParserError(
            "Google Docs parser requires a URL. Use parse_url() instead."
        )

    def parse_bytes(self, content: bytes, filename: str = "") -> ParseResult:
        """
        Parse bytes is not applicable for Google Docs - use parse_url instead.

        Raises:
            ParserError: Always, as Google Docs requires URL-based parsing.
        """
        raise ParserError(
            "Google Docs parser requires a URL. Use parse_url() instead."
        )

    def parse_url(self, url: str) -> ParseResult:
        """
        Parse a Google Docs URL and extract its text content.

        Args:
            url: Google Docs URL in any supported format.

        Returns:
            ParseResult with extracted text and metadata.

        Raises:
            ParserError: If document ID extraction or content retrieval fails.
        """
        # Extract document ID
        doc_id = self.extract_doc_id(url)

        # Build export URL for plain text
        export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"

        try:
            # Fetch the document as plain text
            response = requests.get(
                export_url,
                timeout=self.REQUEST_TIMEOUT,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; NotebookLX/1.0)",
                },
            )
            response.raise_for_status()

            # Get the text content
            text_content = response.text

            # Normalize the text
            normalized_text = self.normalize_text(text_content)

            # Create single page (Google Docs are not paginated in export)
            page_content = PageContent(
                page_number=1,
                text=normalized_text,
                headings=[],
                char_start=0,
                char_end=len(normalized_text),
            )

            # Build metadata
            metadata = {
                "url": url,
                "doc_id": doc_id,
                "parser": "google-docs-export",
            }

            return ParseResult(
                full_text=normalized_text,
                pages=[page_content],
                metadata=metadata,
                title=None,  # Title could be extracted from first line if needed
                total_pages=1,
                encoding="utf-8",
            )

        except requests.HTTPError as e:
            if e.response is not None:
                if e.response.status_code == 404:
                    raise ParserError(
                        f"Document not found: {doc_id}"
                    )
                elif e.response.status_code == 403:
                    raise ParserError(
                        f"Access denied - document may not be public: {doc_id}"
                    )
            logger.error(f"HTTP error fetching Google Doc {doc_id}: {e}")
            raise ParserError(f"Failed to fetch document: {e}")
        except requests.RequestException as e:
            logger.error(f"Request error fetching Google Doc {doc_id}: {e}")
            raise ParserError(f"Failed to fetch document: {e}")
        except Exception as e:
            logger.error(f"Unexpected error parsing Google Doc {doc_id}: {e}")
            raise ParserError(f"Failed to parse document: {e}")

    def extract_doc_id(self, url: str) -> str:
        """
        Extract document ID from a Google Docs URL.

        Supports various Google Docs URL formats:
        - https://docs.google.com/document/d/DOC_ID/edit
        - https://docs.google.com/document/d/DOC_ID/view
        - https://docs.google.com/document/d/DOC_ID/preview
        - https://docs.google.com/document/d/DOC_ID/pub
        - With query parameters like ?usp=sharing

        Args:
            url: Google Docs URL in any supported format.

        Returns:
            Document ID string.

        Raises:
            ParserError: If URL is invalid or document ID cannot be extracted.
        """
        if not url:
            raise ParserError("Empty Google Docs URL provided")

        match = re.search(self.DOC_ID_PATTERN, url)
        if match:
            return match.group(1)

        raise ParserError(f"Could not extract document ID from URL: {url}")
