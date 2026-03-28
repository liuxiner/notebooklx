"""
Document parsers module.

Provides parsers for different document types to extract structured text
with metadata (page numbers, headings, etc.).
"""
from services.api.modules.parsers.base import (
    ParseResult,
    PageContent,
    ParserError,
    BaseParser,
)
from services.api.modules.parsers.pdf import PDFParser
from services.api.modules.parsers.url import URLParser
from services.api.modules.parsers.text import TextParser
from services.api.modules.parsers.youtube import YouTubeParser
from services.api.modules.parsers.googledocs import GoogleDocsParser

__all__ = [
    "ParseResult",
    "PageContent",
    "ParserError",
    "BaseParser",
    "PDFParser",
    "URLParser",
    "TextParser",
    "YouTubeParser",
    "GoogleDocsParser",
]
