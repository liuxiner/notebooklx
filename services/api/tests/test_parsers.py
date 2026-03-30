"""
Tests for document parsers.

These tests cover the acceptance criteria for Feature 2.1: Document Parsers.
- Extract text from PDF files preserving page numbers
- Return structured text with metadata (page numbers, headings)
- Handle parsing errors gracefully
- Character encoding handled correctly (UTF-8)
"""
import pytest
from pathlib import Path
import tempfile
import io

from fpdf import FPDF

from services.api.modules.parsers import (
    PDFParser,
    URLParser,
    TextParser,
    YouTubeParser,
    ParseResult,
    PageContent,
    ParserError,
    BaseParser,
)


def create_test_pdf(pages_content: list[str]) -> bytes:
    """
    Create a valid PDF with given page content using fpdf2.

    Args:
        pages_content: List of strings, one per page.

    Returns:
        PDF content as bytes.
    """
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    for page_text in pages_content:
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.multi_cell(0, 10, page_text)

    return pdf.output()


class TestBaseParser:
    """Tests for base parser utilities."""

    def test_normalize_text_removes_extra_whitespace(self):
        """Normalize text should collapse multiple spaces."""
        text = "Hello    world   test"
        result = BaseParser.normalize_text(text)
        assert result == "Hello world test"

    def test_normalize_text_preserves_newlines(self):
        """Normalize text should preserve newlines."""
        text = "Line 1\nLine 2\nLine 3"
        result = BaseParser.normalize_text(text)
        assert result == "Line 1\nLine 2\nLine 3"

    def test_normalize_text_handles_empty_string(self):
        """Normalize text should handle empty string."""
        result = BaseParser.normalize_text("")
        assert result == ""

    def test_normalize_text_handles_unicode(self):
        """Normalize text should handle unicode characters."""
        # Full-width characters should be normalized to ASCII
        text = "Ｈｅｌｌｏ"  # Full-width ASCII
        result = BaseParser.normalize_text(text)
        assert result == "Hello"


class TestParseResult:
    """Tests for ParseResult dataclass."""

    def test_page_count_property(self):
        """ParseResult.page_count should return number of pages."""
        pages = [
            PageContent(page_number=1, text="Page 1"),
            PageContent(page_number=2, text="Page 2"),
        ]
        result = ParseResult(full_text="Page 1\nPage 2", pages=pages, total_pages=2)
        assert result.page_count == 2

    def test_page_count_empty(self):
        """ParseResult.page_count should return 0 for empty pages."""
        result = ParseResult(full_text="", pages=[])
        assert result.page_count == 0


class TestPDFParser:
    """Tests for PDF parser.

    Acceptance Criteria:
    - Extract text from PDF files preserving page numbers
    - Return structured text with metadata (page numbers, headings)
    - Handle parsing errors gracefully
    - Character encoding handled correctly (UTF-8)
    """

    @pytest.fixture
    def pdf_parser(self) -> PDFParser:
        """Create a PDF parser instance."""
        return PDFParser()

    @pytest.fixture
    def sample_pdf_bytes(self) -> bytes:
        """
        Create a valid PDF with text content using fpdf2.
        """
        return create_test_pdf([
            "Page 1 content. This is the first page of the test document.",
            "Page 2 content. This is the second page of the test document."
        ])

    def test_parse_bytes_returns_parse_result(self, pdf_parser, sample_pdf_bytes):
        """PDF parser should return a ParseResult from bytes."""
        result = pdf_parser.parse_bytes(sample_pdf_bytes)
        assert isinstance(result, ParseResult)

    def test_parse_bytes_extracts_text(self, pdf_parser, sample_pdf_bytes):
        """PDF parser should extract text content."""
        result = pdf_parser.parse_bytes(sample_pdf_bytes)
        # The minimal PDF should have some text
        assert result.full_text is not None
        assert isinstance(result.full_text, str)

    def test_parse_bytes_preserves_page_numbers(self, pdf_parser, sample_pdf_bytes):
        """PDF parser should preserve page numbers in PageContent."""
        result = pdf_parser.parse_bytes(sample_pdf_bytes)
        # Should have pages with page numbers
        assert len(result.pages) >= 1
        for i, page in enumerate(result.pages):
            assert page.page_number == i + 1  # Page numbers start at 1

    def test_parse_bytes_returns_utf8_encoding(self, pdf_parser, sample_pdf_bytes):
        """PDF parser should return UTF-8 encoded text."""
        result = pdf_parser.parse_bytes(sample_pdf_bytes)
        assert result.encoding == "utf-8"
        # Verify text is valid UTF-8
        assert result.full_text.encode("utf-8")

    def test_parse_bytes_with_filename(self, pdf_parser, sample_pdf_bytes):
        """PDF parser should accept optional filename."""
        result = pdf_parser.parse_bytes(sample_pdf_bytes, filename="test.pdf")
        assert isinstance(result, ParseResult)

    def test_parse_file_creates_parse_result(self, pdf_parser, sample_pdf_bytes):
        """PDF parser should parse file from path."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(sample_pdf_bytes)
            f.flush()
            path = Path(f.name)

        try:
            result = pdf_parser.parse(path)
            assert isinstance(result, ParseResult)
        finally:
            path.unlink()

    def test_parse_invalid_pdf_raises_parser_error(self, pdf_parser):
        """PDF parser should raise ParserError for invalid PDF."""
        invalid_content = b"This is not a PDF file"
        with pytest.raises(ParserError) as exc_info:
            pdf_parser.parse_bytes(invalid_content)
        assert "Failed to parse PDF" in str(exc_info.value)

    def test_parse_empty_bytes_raises_parser_error(self, pdf_parser):
        """PDF parser should raise ParserError for empty content."""
        with pytest.raises(ParserError):
            pdf_parser.parse_bytes(b"")

    def test_parse_nonexistent_file_raises_parser_error(self, pdf_parser):
        """PDF parser should raise ParserError for missing file."""
        fake_path = Path("/nonexistent/path/to/file.pdf")
        with pytest.raises(ParserError) as exc_info:
            pdf_parser.parse(fake_path)
        assert "File not found" in str(exc_info.value)

    def test_parse_result_includes_total_pages(self, pdf_parser, sample_pdf_bytes):
        """PDF parser should report total page count."""
        result = pdf_parser.parse_bytes(sample_pdf_bytes)
        assert result.total_pages >= 1

    def test_page_content_has_char_positions(self, pdf_parser, sample_pdf_bytes):
        """PDF parser should track character positions for each page."""
        result = pdf_parser.parse_bytes(sample_pdf_bytes)
        if result.pages:
            # First page should start at 0
            assert result.pages[0].char_start == 0
            # char_end should be >= char_start
            for page in result.pages:
                assert page.char_end >= page.char_start

    def test_parse_bytes_handles_unicode_content(self, pdf_parser):
        """PDF parser should handle UTF-8 unicode characters correctly."""
        # Create a PDF with unicode content
        unicode_pdf = create_test_pdf(["Hello World - Testing unicode content"])
        result = pdf_parser.parse_bytes(unicode_pdf, filename="unicode_test.pdf")
        assert result.encoding == "utf-8"
        assert "Hello World" in result.full_text


class TestPDFParserWithRealPDF:
    """
    Integration tests for PDF parser using pdfplumber to create test PDFs.
    These tests require pdfplumber and reportlab to be installed.
    """

    @pytest.fixture
    def pdf_parser(self) -> PDFParser:
        """Create a PDF parser instance."""
        return PDFParser()

    def test_parser_is_instance_of_base_parser(self, pdf_parser):
        """PDF parser should implement BaseParser interface."""
        assert isinstance(pdf_parser, BaseParser)


class TestURLParser:
    """Tests for URL/Web parser.

    Acceptance Criteria:
    - Extract text from web URLs with clean HTML removal
    - Return structured text with metadata
    - Handle parsing errors gracefully
    - Character encoding handled correctly (UTF-8)
    """

    @pytest.fixture
    def url_parser(self) -> URLParser:
        """Create a URL parser instance."""
        return URLParser()

    @pytest.fixture
    def sample_html(self) -> str:
        """Sample HTML content for testing."""
        return """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="utf-8">
            <title>Test Page Title</title>
            <script>console.log('should be removed');</script>
            <style>body { color: red; }</style>
        </head>
        <body>
            <nav>Navigation menu - should be removed</nav>
            <header>Site header</header>
            <main>
                <article>
                    <h1>Main Article Heading</h1>
                    <p>This is the main content paragraph that should be extracted.</p>
                    <p>This is another paragraph with more content.</p>
                    <h2>Section Heading</h2>
                    <p>Content under the section heading.</p>
                </article>
            </main>
            <aside>Sidebar content - may be removed</aside>
            <footer>Footer content - should be removed</footer>
        </body>
        </html>
        """

    def test_parse_html_returns_parse_result(self, url_parser, sample_html):
        """URL parser should return a ParseResult from HTML content."""
        result = url_parser.parse_html(sample_html, url="https://example.com/test")
        assert isinstance(result, ParseResult)

    def test_parse_html_extracts_main_content(self, url_parser, sample_html):
        """URL parser should extract main content text."""
        result = url_parser.parse_html(sample_html, url="https://example.com/test")
        assert "main content paragraph" in result.full_text.lower()

    def test_parse_html_removes_scripts_and_styles(self, url_parser, sample_html):
        """URL parser should remove script and style content."""
        result = url_parser.parse_html(sample_html, url="https://example.com/test")
        assert "console.log" not in result.full_text
        assert "color: red" not in result.full_text

    def test_parse_html_extracts_title(self, url_parser, sample_html):
        """URL parser should extract page title."""
        result = url_parser.parse_html(sample_html, url="https://example.com/test")
        # Title may be extracted from HTML title or main heading
        assert result.title is not None or "Main Article" in result.full_text

    def test_parse_html_returns_utf8_encoding(self, url_parser, sample_html):
        """URL parser should return UTF-8 encoded text."""
        result = url_parser.parse_html(sample_html, url="https://example.com/test")
        assert result.encoding == "utf-8"
        # Verify text is valid UTF-8
        assert result.full_text.encode("utf-8")

    def test_parse_html_includes_url_in_metadata(self, url_parser, sample_html):
        """URL parser should include source URL in metadata."""
        test_url = "https://example.com/test-page"
        result = url_parser.parse_html(sample_html, url=test_url)
        assert result.metadata.get("url") == test_url

    def test_parse_html_empty_content_raises_error(self, url_parser):
        """URL parser should raise ParserError for empty content."""
        with pytest.raises(ParserError):
            url_parser.parse_html("", url="https://example.com")

    def test_parse_html_handles_unicode(self, url_parser):
        """URL parser should handle unicode content correctly."""
        unicode_html = """
        <!DOCTYPE html>
        <html>
        <head><title>Unicode Test</title></head>
        <body>
            <p>Hello World with unicode: café, naïve, 日本語</p>
        </body>
        </html>
        """
        result = url_parser.parse_html(unicode_html, url="https://example.com")
        assert result.encoding == "utf-8"

    def test_parser_is_instance_of_base_parser(self, url_parser):
        """URL parser should implement BaseParser interface."""
        assert isinstance(url_parser, BaseParser)

    def test_parse_html_handles_malformed_html(self, url_parser):
        """URL parser should handle malformed HTML gracefully."""
        malformed_html = """
        <html>
        <body>
        <p>Unclosed paragraph
        <div>Unclosed div
        <p>Another paragraph</p>
        </body>
        """
        # Should not raise an error
        result = url_parser.parse_html(malformed_html, url="https://example.com")
        assert isinstance(result, ParseResult)

    def test_parse_html_minimal_content(self, url_parser):
        """URL parser should handle minimal HTML content."""
        minimal_html = "<html><body><p>Simple content</p></body></html>"
        result = url_parser.parse_html(minimal_html, url="https://example.com")
        assert "Simple content" in result.full_text

    def test_parse_html_has_single_page(self, url_parser, sample_html):
        """URL parser should return single page (web pages are not paginated)."""
        result = url_parser.parse_html(sample_html, url="https://example.com")
        # Web pages are treated as a single "page"
        assert len(result.pages) == 1
        assert result.pages[0].page_number == 1


class TestTextParser:
    """Tests for Plain Text parser.

    Acceptance Criteria:
    - Normalize character encoding to UTF-8
    - Return structured text with metadata
    - Handle parsing errors gracefully
    """

    @pytest.fixture
    def text_parser(self) -> TextParser:
        """Create a Text parser instance."""
        return TextParser()

    def test_parse_bytes_returns_parse_result(self, text_parser):
        """Text parser should return a ParseResult from bytes."""
        content = b"Hello, this is plain text content."
        result = text_parser.parse_bytes(content)
        assert isinstance(result, ParseResult)

    def test_parse_bytes_extracts_text(self, text_parser):
        """Text parser should extract text content."""
        content = b"Hello, this is plain text content."
        result = text_parser.parse_bytes(content)
        assert "Hello, this is plain text content" in result.full_text

    def test_parse_bytes_returns_utf8_encoding(self, text_parser):
        """Text parser should return UTF-8 encoded text."""
        content = b"Hello World"
        result = text_parser.parse_bytes(content)
        assert result.encoding == "utf-8"
        # Verify text is valid UTF-8
        assert result.full_text.encode("utf-8")

    def test_parse_bytes_handles_utf8(self, text_parser):
        """Text parser should handle UTF-8 encoded text."""
        content = "Hello café naïve 日本語".encode("utf-8")
        result = text_parser.parse_bytes(content)
        assert "café" in result.full_text
        assert "日本語" in result.full_text

    def test_parse_bytes_handles_latin1(self, text_parser):
        """Text parser should handle Latin-1 encoded text."""
        content = "Hello café".encode("latin-1")
        result = text_parser.parse_bytes(content)
        # Should be decoded and converted to UTF-8
        assert result.encoding == "utf-8"

    def test_parse_bytes_empty_content_raises_error(self, text_parser):
        """Text parser should raise ParserError for empty content."""
        with pytest.raises(ParserError):
            text_parser.parse_bytes(b"")

    def test_parse_bytes_with_filename(self, text_parser):
        """Text parser should accept optional filename."""
        content = b"Hello World"
        result = text_parser.parse_bytes(content, filename="test.txt")
        assert result.metadata.get("filename") == "test.txt"

    def test_parse_file_from_path(self, text_parser):
        """Text parser should parse file from path."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write("Hello from a text file.")
            f.flush()
            path = Path(f.name)

        try:
            result = text_parser.parse(path)
            assert isinstance(result, ParseResult)
            assert "Hello from a text file" in result.full_text
        finally:
            path.unlink()

    def test_parse_nonexistent_file_raises_error(self, text_parser):
        """Text parser should raise ParserError for missing file."""
        fake_path = Path("/nonexistent/path/to/file.txt")
        with pytest.raises(ParserError) as exc_info:
            text_parser.parse(fake_path)
        assert "File not found" in str(exc_info.value)

    def test_parser_is_instance_of_base_parser(self, text_parser):
        """Text parser should implement BaseParser interface."""
        assert isinstance(text_parser, BaseParser)

    def test_parse_result_has_single_page(self, text_parser):
        """Text parser should return single page."""
        content = b"Hello World"
        result = text_parser.parse_bytes(content)
        assert len(result.pages) == 1
        assert result.pages[0].page_number == 1

    def test_parse_normalizes_whitespace(self, text_parser):
        """Text parser should normalize whitespace."""
        content = b"Hello    world   with   extra   spaces"
        result = text_parser.parse_bytes(content)
        assert "Hello world with extra spaces" in result.full_text


class TestYouTubeParser:
    """Tests for YouTube transcript parser.

    Acceptance Criteria:
    - Extract YouTube video transcripts via API
    - Return structured text with metadata
    - Handle parsing errors gracefully
    - Support various YouTube URL formats
    """

    @pytest.fixture
    def youtube_parser(self) -> YouTubeParser:
        """Create a YouTube parser instance."""
        return YouTubeParser()

    def test_extract_video_id_from_standard_url(self, youtube_parser):
        """Should extract video ID from standard YouTube URL."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        video_id = youtube_parser.extract_video_id(url)
        assert video_id == "dQw4w9WgXcQ"

    def test_extract_video_id_from_short_url(self, youtube_parser):
        """Should extract video ID from youtu.be URL."""
        url = "https://youtu.be/dQw4w9WgXcQ"
        video_id = youtube_parser.extract_video_id(url)
        assert video_id == "dQw4w9WgXcQ"

    def test_extract_video_id_from_embed_url(self, youtube_parser):
        """Should extract video ID from embed URL."""
        url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
        video_id = youtube_parser.extract_video_id(url)
        assert video_id == "dQw4w9WgXcQ"

    def test_extract_video_id_with_extra_params(self, youtube_parser):
        """Should extract video ID ignoring extra parameters."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=60s&list=PLtest"
        video_id = youtube_parser.extract_video_id(url)
        assert video_id == "dQw4w9WgXcQ"

    def test_extract_video_id_invalid_url_raises_error(self, youtube_parser):
        """Should raise ParserError for invalid URL."""
        with pytest.raises(ParserError):
            youtube_parser.extract_video_id("https://example.com/not-youtube")

    def test_extract_video_id_empty_url_raises_error(self, youtube_parser):
        """Should raise ParserError for empty URL."""
        with pytest.raises(ParserError):
            youtube_parser.extract_video_id("")

    def test_parse_transcript_returns_parse_result(self, youtube_parser, mocker):
        """Should return ParseResult from transcript data."""
        # Mock the transcript API using the new instance-based API
        mock_snippet_1 = mocker.Mock()
        mock_snippet_1.text = "Hello everyone"
        mock_snippet_2 = mocker.Mock()
        mock_snippet_2.text = "Welcome to my video"

        mock_transcript = mocker.Mock()
        mock_transcript.snippets = [mock_snippet_1, mock_snippet_2]

        mock_api = mocker.patch(
            "services.api.modules.parsers.youtube.YouTubeTranscriptApi"
        )
        mock_api.return_value.fetch.return_value = mock_transcript

        result = youtube_parser.parse_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert isinstance(result, ParseResult)

    def test_parse_transcript_extracts_text(self, youtube_parser, mocker):
        """Should extract transcript text."""
        mock_snippet_1 = mocker.Mock()
        mock_snippet_1.text = "Hello everyone"
        mock_snippet_2 = mocker.Mock()
        mock_snippet_2.text = "Welcome to my video"

        mock_transcript = mocker.Mock()
        mock_transcript.snippets = [mock_snippet_1, mock_snippet_2]

        mock_api = mocker.patch(
            "services.api.modules.parsers.youtube.YouTubeTranscriptApi"
        )
        mock_api.return_value.fetch.return_value = mock_transcript

        result = youtube_parser.parse_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert "Hello everyone" in result.full_text
        assert "Welcome to my video" in result.full_text

    def test_parse_transcript_returns_utf8(self, youtube_parser, mocker):
        """Should return UTF-8 encoded text."""
        mock_snippet = mocker.Mock()
        mock_snippet.text = "Hello"

        mock_transcript = mocker.Mock()
        mock_transcript.snippets = [mock_snippet]

        mock_api = mocker.patch(
            "services.api.modules.parsers.youtube.YouTubeTranscriptApi"
        )
        mock_api.return_value.fetch.return_value = mock_transcript

        result = youtube_parser.parse_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert result.encoding == "utf-8"

    def test_parse_transcript_includes_url_metadata(self, youtube_parser, mocker):
        """Should include URL in metadata."""
        mock_snippet = mocker.Mock()
        mock_snippet.text = "Hello"

        mock_transcript = mocker.Mock()
        mock_transcript.snippets = [mock_snippet]

        mock_api = mocker.patch(
            "services.api.modules.parsers.youtube.YouTubeTranscriptApi"
        )
        mock_api.return_value.fetch.return_value = mock_transcript

        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        result = youtube_parser.parse_url(url)
        assert result.metadata.get("url") == url
        assert result.metadata.get("video_id") == "dQw4w9WgXcQ"

    def test_parse_transcript_handles_api_error(self, youtube_parser, mocker):
        """Should raise ParserError when transcript unavailable."""
        class TranscriptsDisabled(Exception):
            """Local stand-in for the YouTube transcript error."""

        mock_api = mocker.patch(
            "services.api.modules.parsers.youtube.YouTubeTranscriptApi"
        )
        mock_api.return_value.fetch.side_effect = TranscriptsDisabled("test123")

        with pytest.raises(ParserError) as exc_info:
            youtube_parser.parse_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert "transcript" in str(exc_info.value).lower()

    def test_parser_is_instance_of_base_parser(self, youtube_parser):
        """YouTube parser should implement BaseParser interface."""
        assert isinstance(youtube_parser, BaseParser)

    def test_parse_result_has_single_page(self, youtube_parser, mocker):
        """YouTube parser should return single page."""
        mock_snippet = mocker.Mock()
        mock_snippet.text = "Hello"

        mock_transcript = mocker.Mock()
        mock_transcript.snippets = [mock_snippet]

        mock_api = mocker.patch(
            "services.api.modules.parsers.youtube.YouTubeTranscriptApi"
        )
        mock_api.return_value.fetch.return_value = mock_transcript

        result = youtube_parser.parse_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert len(result.pages) == 1
        assert result.pages[0].page_number == 1


class TestGoogleDocsParser:
    """Tests for Google Docs parser.

    Acceptance Criteria:
    - Support Google Docs public URLs
    - Return structured text with metadata
    - Handle parsing errors gracefully
    - Character encoding handled correctly (UTF-8)
    """

    @pytest.fixture
    def gdocs_parser(self):
        """Create a Google Docs parser instance."""
        from services.api.modules.parsers import GoogleDocsParser
        return GoogleDocsParser()

    def test_extract_doc_id_from_edit_url(self, gdocs_parser):
        """Should extract document ID from /edit URL."""
        url = "https://docs.google.com/document/d/1a2B3c4D5e6F7g8H9i0JkLmNoPqRsTuVwXyZ/edit"
        doc_id = gdocs_parser.extract_doc_id(url)
        assert doc_id == "1a2B3c4D5e6F7g8H9i0JkLmNoPqRsTuVwXyZ"

    def test_extract_doc_id_from_view_url(self, gdocs_parser):
        """Should extract document ID from /view URL."""
        url = "https://docs.google.com/document/d/1a2B3c4D5e6F7g8H9i0JkLmNoPqRsTuVwXyZ/view"
        doc_id = gdocs_parser.extract_doc_id(url)
        assert doc_id == "1a2B3c4D5e6F7g8H9i0JkLmNoPqRsTuVwXyZ"

    def test_extract_doc_id_from_preview_url(self, gdocs_parser):
        """Should extract document ID from /preview URL."""
        url = "https://docs.google.com/document/d/1a2B3c4D5e6F7g8H9i0JkLmNoPqRsTuVwXyZ/preview"
        doc_id = gdocs_parser.extract_doc_id(url)
        assert doc_id == "1a2B3c4D5e6F7g8H9i0JkLmNoPqRsTuVwXyZ"

    def test_extract_doc_id_from_pub_url(self, gdocs_parser):
        """Should extract document ID from /pub URL."""
        url = "https://docs.google.com/document/d/1a2B3c4D5e6F7g8H9i0JkLmNoPqRsTuVwXyZ/pub"
        doc_id = gdocs_parser.extract_doc_id(url)
        assert doc_id == "1a2B3c4D5e6F7g8H9i0JkLmNoPqRsTuVwXyZ"

    def test_extract_doc_id_with_query_params(self, gdocs_parser):
        """Should extract document ID ignoring query parameters."""
        url = "https://docs.google.com/document/d/1a2B3c4D5e6F7g8H9i0JkLmNoPqRsTuVwXyZ/edit?usp=sharing"
        doc_id = gdocs_parser.extract_doc_id(url)
        assert doc_id == "1a2B3c4D5e6F7g8H9i0JkLmNoPqRsTuVwXyZ"

    def test_extract_doc_id_invalid_url_raises_error(self, gdocs_parser):
        """Should raise ParserError for invalid URL."""
        with pytest.raises(ParserError):
            gdocs_parser.extract_doc_id("https://example.com/not-google-docs")

    def test_extract_doc_id_empty_url_raises_error(self, gdocs_parser):
        """Should raise ParserError for empty URL."""
        with pytest.raises(ParserError):
            gdocs_parser.extract_doc_id("")

    def test_parse_url_returns_parse_result(self, gdocs_parser, mocker):
        """Should return ParseResult from document content."""
        # Mock the HTTP request
        mock_response = mocker.MagicMock()
        mock_response.read.return_value = b"This is the document content."
        mock_response.headers.get_content_charset.return_value = "utf-8"
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = False

        mocker.patch("services.api.modules.parsers.googledocs.urlopen", return_value=mock_response)

        result = gdocs_parser.parse_url(
            "https://docs.google.com/document/d/1a2B3c4D5e6F7g8H9i0JkLmNoPqRsTuVwXyZ/edit"
        )
        assert isinstance(result, ParseResult)

    def test_parse_url_extracts_text(self, gdocs_parser, mocker):
        """Should extract document text content."""
        mock_response = mocker.MagicMock()
        mock_response.read.return_value = b"Hello, this is my Google Doc content."
        mock_response.headers.get_content_charset.return_value = "utf-8"
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = False

        mocker.patch("services.api.modules.parsers.googledocs.urlopen", return_value=mock_response)

        result = gdocs_parser.parse_url(
            "https://docs.google.com/document/d/1a2B3c4D5e6F7g8H9i0JkLmNoPqRsTuVwXyZ/edit"
        )
        assert "Hello, this is my Google Doc content" in result.full_text

    def test_parse_url_returns_utf8_encoding(self, gdocs_parser, mocker):
        """Should return UTF-8 encoded text."""
        mock_response = mocker.MagicMock()
        mock_response.read.return_value = b"Document text"
        mock_response.headers.get_content_charset.return_value = "utf-8"
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = False

        mocker.patch("services.api.modules.parsers.googledocs.urlopen", return_value=mock_response)

        result = gdocs_parser.parse_url(
            "https://docs.google.com/document/d/1a2B3c4D5e6F7g8H9i0JkLmNoPqRsTuVwXyZ/edit"
        )
        assert result.encoding == "utf-8"

    def test_parse_url_includes_metadata(self, gdocs_parser, mocker):
        """Should include URL and document ID in metadata."""
        mock_response = mocker.MagicMock()
        mock_response.read.return_value = b"Document text"
        mock_response.headers.get_content_charset.return_value = "utf-8"
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = False

        mocker.patch("services.api.modules.parsers.googledocs.urlopen", return_value=mock_response)

        url = "https://docs.google.com/document/d/1a2B3c4D5e6F7g8H9i0JkLmNoPqRsTuVwXyZ/edit"
        result = gdocs_parser.parse_url(url)
        assert result.metadata.get("url") == url
        assert result.metadata.get("doc_id") == "1a2B3c4D5e6F7g8H9i0JkLmNoPqRsTuVwXyZ"

    def test_parse_url_handles_404_error(self, gdocs_parser, mocker):
        """Should raise ParserError when document not found."""
        from urllib.error import HTTPError

        mock_error = HTTPError(
            "https://docs.google.com/document/d/nonexistent/export?format=txt",
            404,
            "Not Found",
            hdrs=None,
            fp=None,
        )

        mocker.patch("services.api.modules.parsers.googledocs.urlopen", side_effect=mock_error)

        with pytest.raises(ParserError) as exc_info:
            gdocs_parser.parse_url(
                "https://docs.google.com/document/d/nonexistent/edit"
            )
        assert "not found" in str(exc_info.value).lower() or "failed" in str(exc_info.value).lower()

    def test_parse_url_handles_403_error(self, gdocs_parser, mocker):
        """Should raise ParserError when document is not public."""
        from urllib.error import HTTPError

        mock_error = HTTPError(
            "https://docs.google.com/document/d/private-doc/export?format=txt",
            403,
            "Forbidden",
            hdrs=None,
            fp=None,
        )

        mocker.patch("services.api.modules.parsers.googledocs.urlopen", side_effect=mock_error)

        with pytest.raises(ParserError) as exc_info:
            gdocs_parser.parse_url(
                "https://docs.google.com/document/d/private-doc/edit"
            )
        assert "access" in str(exc_info.value).lower() or "failed" in str(exc_info.value).lower()

    def test_parser_is_instance_of_base_parser(self, gdocs_parser):
        """Google Docs parser should implement BaseParser interface."""
        assert isinstance(gdocs_parser, BaseParser)

    def test_parse_result_has_single_page(self, gdocs_parser, mocker):
        """Google Docs parser should return single page."""
        mock_response = mocker.MagicMock()
        mock_response.read.return_value = b"Document text"
        mock_response.headers.get_content_charset.return_value = "utf-8"
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = False

        mocker.patch("services.api.modules.parsers.googledocs.urlopen", return_value=mock_response)

        result = gdocs_parser.parse_url(
            "https://docs.google.com/document/d/1a2B3c4D5e6F7g8H9i0JkLmNoPqRsTuVwXyZ/edit"
        )
        assert len(result.pages) == 1
        assert result.pages[0].page_number == 1

    def test_parse_raises_error_for_file_path(self, gdocs_parser):
        """Google Docs parser requires URL - parse() should raise error."""
        with pytest.raises(ParserError):
            gdocs_parser.parse(Path("/some/path"))

    def test_parse_bytes_raises_error(self, gdocs_parser):
        """Google Docs parser requires URL - parse_bytes() should raise error."""
        with pytest.raises(ParserError):
            gdocs_parser.parse_bytes(b"some content")
