"""
YouTube transcript parser.

Extracts transcripts from YouTube videos using the youtube-transcript-api.
"""
from pathlib import Path
from typing import Optional
import re
import logging

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)

from services.api.modules.parsers.base import (
    BaseParser,
    ParseResult,
    PageContent,
    ParserError,
)

logger = logging.getLogger(__name__)


class YouTubeParser(BaseParser):
    """
    Parser for YouTube video transcripts.

    Extracts transcript text from YouTube videos using the
    youtube-transcript-api library.
    """

    # Regex patterns for extracting video IDs from various YouTube URL formats
    VIDEO_ID_PATTERNS = [
        # Standard watch URL: https://www.youtube.com/watch?v=VIDEO_ID
        r"(?:youtube\.com/watch\?.*v=|youtube\.com/watch\?v=)([a-zA-Z0-9_-]{11})",
        # Short URL: https://youtu.be/VIDEO_ID
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
        # Embed URL: https://www.youtube.com/embed/VIDEO_ID
        r"youtube\.com/embed/([a-zA-Z0-9_-]{11})",
        # Mobile URL: https://m.youtube.com/watch?v=VIDEO_ID
        r"m\.youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})",
    ]

    def parse(self, file_path: Path) -> ParseResult:
        """
        Parse is not applicable for YouTube - use parse_url instead.

        Raises:
            ParserError: Always, as YouTube requires URL-based parsing.
        """
        raise ParserError(
            "YouTube parser requires a URL. Use parse_url() instead."
        )

    def parse_bytes(self, content: bytes, filename: str = "") -> ParseResult:
        """
        Parse bytes is not applicable for YouTube - use parse_url instead.

        Raises:
            ParserError: Always, as YouTube requires URL-based parsing.
        """
        raise ParserError(
            "YouTube parser requires a URL. Use parse_url() instead."
        )

    def parse_url(self, url: str) -> ParseResult:
        """
        Parse a YouTube video URL and extract its transcript.

        Args:
            url: YouTube video URL in any supported format.

        Returns:
            ParseResult with extracted transcript and metadata.

        Raises:
            ParserError: If video ID extraction or transcript retrieval fails.
        """
        # Extract video ID
        video_id = self.extract_video_id(url)

        try:
            # Get transcript from YouTube using new API
            api = YouTubeTranscriptApi()
            transcript = api.fetch(video_id, languages=["en"])

            # Combine transcript segments into full text
            text_segments = []
            for snippet in transcript.snippets:
                text = snippet.text.strip()
                if text:
                    text_segments.append(text)

            full_text = " ".join(text_segments)
            normalized_text = self.normalize_text(full_text)

            # Create single page (transcripts are not paginated)
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
                "video_id": video_id,
                "parser": "youtube-transcript-api",
                "segment_count": len(transcript.snippets),
            }

            return ParseResult(
                full_text=normalized_text,
                pages=[page_content],
                metadata=metadata,
                title=None,  # Could potentially fetch video title via another API
                total_pages=1,
                encoding="utf-8",
            )

        except TranscriptsDisabled:
            raise ParserError(
                f"Transcripts are disabled for video {video_id}"
            )
        except NoTranscriptFound:
            raise ParserError(
                f"No transcript found for video {video_id}"
            )
        except VideoUnavailable:
            raise ParserError(
                f"Video {video_id} is unavailable"
            )
        except Exception as e:
            logger.error(f"Failed to get transcript for {video_id}: {e}")
            raise ParserError(f"Failed to get transcript: {e}")

    def extract_video_id(self, url: str) -> str:
        """
        Extract video ID from a YouTube URL.

        Supports various YouTube URL formats:
        - https://www.youtube.com/watch?v=VIDEO_ID
        - https://youtu.be/VIDEO_ID
        - https://www.youtube.com/embed/VIDEO_ID
        - https://m.youtube.com/watch?v=VIDEO_ID

        Args:
            url: YouTube URL in any supported format.

        Returns:
            11-character video ID.

        Raises:
            ParserError: If URL is invalid or video ID cannot be extracted.
        """
        if not url:
            raise ParserError("Empty YouTube URL provided")

        for pattern in self.VIDEO_ID_PATTERNS:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        raise ParserError(f"Could not extract video ID from URL: {url}")
