"""
Semantic chunking module for splitting documents into overlapping chunks.

This module provides token-based chunking with configurable chunk sizes
and overlap to ensure no information is lost during retrieval.
"""
from dataclasses import dataclass, field
from typing import List, Optional
import re

import tiktoken

from services.api.modules.parsers.base import PageContent


# Default tokenizer for OpenAI models
_ENCODING: tiktoken.Encoding | None = None


def _get_encoding() -> tiktoken.Encoding:
    """Get or create the tiktoken encoding (lazy initialization)."""
    global _ENCODING
    if _ENCODING is None:
        # Use cl100k_base which is used by text-embedding-3-small and GPT-4
        _ENCODING = tiktoken.get_encoding("cl100k_base")
    return _ENCODING


def count_tokens(text: str) -> int:
    """
    Count the number of tokens in a text string.

    Args:
        text: The text to count tokens for.

    Returns:
        Number of tokens in the text.
    """
    if not text:
        return 0
    encoding = _get_encoding()
    return len(encoding.encode(text))


@dataclass
class ChunkResult:
    """Result of chunking a piece of text."""
    content: str
    chunk_index: int
    source_title: str
    token_count: int
    char_start: int
    char_end: int
    page_number: Optional[int] = None
    page_numbers: List[int] = field(default_factory=list)
    heading_context: List[str] = field(default_factory=list)


class Chunker:
    """
    Token-based text chunker with configurable overlap.

    Splits text into chunks of approximately min_tokens to max_tokens,
    with overlap_tokens of overlap between consecutive chunks.
    """

    def __init__(
        self,
        min_tokens: int = 300,
        max_tokens: int = 800,
        overlap_tokens: int = 75,
    ):
        """
        Initialize the chunker.

        Args:
            min_tokens: Minimum tokens per chunk (300-800 range target).
            max_tokens: Maximum tokens per chunk.
            overlap_tokens: Token overlap between consecutive chunks (50-120 range).

        Raises:
            ValueError: If parameters are invalid.
        """
        if min_tokens >= max_tokens:
            raise ValueError(f"min_tokens ({min_tokens}) must be less than max_tokens ({max_tokens})")
        if overlap_tokens >= min_tokens:
            raise ValueError(f"overlap_tokens ({overlap_tokens}) must be less than min_tokens ({min_tokens})")

        self.min_tokens = min_tokens
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens

    def chunk_text(
        self,
        text: str,
        source_title: str,
        page_number: Optional[int] = None,
        heading_context: Optional[List[str]] = None,
        pages: Optional[List[PageContent]] = None,
    ) -> List[ChunkResult]:
        """
        Split text into overlapping chunks.

        Args:
            text: The text to chunk.
            source_title: Title of the source document.
            page_number: Optional page number for metadata.
            heading_context: Optional list of headings for context.
            pages: Optional parser page metadata used to derive per-chunk page
                coverage and heading hierarchy.

        Returns:
            List of ChunkResult objects.
        """
        # Handle empty or whitespace-only text
        if not text or not text.strip():
            return []

        # Split into sentences for more natural boundaries
        sentences = self._split_into_sentences(text)
        if not sentences:
            return []

        chunks: List[ChunkResult] = []
        current_sentences: List[str] = []
        current_tokens = 0
        current_char_start = 0

        # Track positions
        sentence_positions: List[tuple[int, int]] = []  # (start, end) for each sentence
        pos = 0
        for sentence in sentences:
            start = text.find(sentence, pos)
            if start == -1:
                start = pos
            end = start + len(sentence)
            sentence_positions.append((start, end))
            pos = end

        sentence_index = 0

        while sentence_index < len(sentences):
            sentence = sentences[sentence_index]
            sentence_tokens = count_tokens(sentence)

            # If adding this sentence would exceed max_tokens, finalize current chunk
            if current_sentences and (current_tokens + sentence_tokens > self.max_tokens):
                # Create chunk from current sentences
                chunk_char_end = sentence_positions[sentence_index - 1][1] if sentence_index > 0 else 0
                resolved_page_number, resolved_page_numbers, resolved_heading_context = (
                    self._resolve_chunk_metadata(
                        chunk_char_start=current_char_start,
                        chunk_char_end=chunk_char_end,
                        page_number=page_number,
                        heading_context=heading_context,
                        pages=pages,
                    )
                )

                chunks.append(ChunkResult(
                    content=text[current_char_start:chunk_char_end],
                    chunk_index=len(chunks),
                    source_title=source_title,
                    token_count=count_tokens(text[current_char_start:chunk_char_end]),
                    char_start=current_char_start,
                    char_end=chunk_char_end,
                    page_number=resolved_page_number,
                    page_numbers=resolved_page_numbers,
                    heading_context=resolved_heading_context,
                ))

                # Calculate overlap: go back to include overlap_tokens worth of content
                overlap_sentences: List[str] = []
                overlap_tokens = 0
                overlap_start_idx = sentence_index - 1

                while overlap_start_idx >= 0 and overlap_tokens < self.overlap_tokens:
                    overlap_sent = sentences[overlap_start_idx]
                    overlap_sent_tokens = count_tokens(overlap_sent)

                    # Skip overlap when a single segment already meets or exceeds
                    # the overlap budget. Otherwise we can requeue the entire
                    # previous chunk and never advance.
                    if overlap_sent_tokens > self.overlap_tokens:
                        break

                    overlap_tokens += overlap_sent_tokens
                    overlap_sentences.insert(0, overlap_sent)
                    overlap_start_idx -= 1

                # Start new chunk with overlap
                if overlap_sentences:
                    current_sentences = overlap_sentences.copy()
                    current_tokens = sum(count_tokens(s) for s in current_sentences)
                    current_char_start = sentence_positions[overlap_start_idx + 1][0]
                else:
                    current_sentences = []
                    current_tokens = 0
                    current_char_start = sentence_positions[sentence_index][0]

                # Don't increment sentence_index - we'll add the current sentence next iteration
                continue

            # Add sentence to current chunk
            current_sentences.append(sentence)
            current_tokens += sentence_tokens
            sentence_index += 1

        # Handle remaining sentences
        if current_sentences:
            chunk_char_end = len(text)
            resolved_page_number, resolved_page_numbers, resolved_heading_context = (
                self._resolve_chunk_metadata(
                    chunk_char_start=current_char_start,
                    chunk_char_end=chunk_char_end,
                    page_number=page_number,
                    heading_context=heading_context,
                    pages=pages,
                )
            )
            chunks.append(ChunkResult(
                content=text[current_char_start:chunk_char_end],
                chunk_index=len(chunks),
                source_title=source_title,
                token_count=count_tokens(text[current_char_start:chunk_char_end]),
                char_start=current_char_start,
                char_end=chunk_char_end,
                page_number=resolved_page_number,
                page_numbers=resolved_page_numbers,
                heading_context=resolved_heading_context,
            ))

        return chunks

    def _resolve_chunk_metadata(
        self,
        chunk_char_start: int,
        chunk_char_end: int,
        page_number: Optional[int],
        heading_context: Optional[List[str]],
        pages: Optional[List[PageContent]],
    ) -> tuple[Optional[int], List[int], List[str]]:
        """
        Resolve page coverage and heading context for a chunk span.

        When structured parser pages are available, chunk metadata is derived
        from the pages that overlap the chunk. The page where the chunk starts
        provides the primary page number and heading hierarchy.
        """
        fallback_page_numbers = [page_number] if page_number is not None else []
        fallback_heading_context = list(heading_context or [])

        if not pages:
            return page_number, fallback_page_numbers, fallback_heading_context

        overlapping_pages = [
            page
            for page in pages
            if self._ranges_overlap(
                range_start=chunk_char_start,
                range_end=chunk_char_end,
                span_start=page.char_start,
                span_end=page.char_end,
            )
        ]
        if not overlapping_pages:
            return page_number, fallback_page_numbers, fallback_heading_context

        start_page = next(
            (
                page
                for page in pages
                if self._position_in_span(
                    position=chunk_char_start,
                    span_start=page.char_start,
                    span_end=page.char_end,
                )
            ),
            overlapping_pages[0],
        )

        resolved_page_numbers: List[int] = []
        seen_page_numbers: set[int] = set()
        for page in overlapping_pages:
            if page.page_number not in seen_page_numbers:
                seen_page_numbers.add(page.page_number)
                resolved_page_numbers.append(page.page_number)

        resolved_heading_context = (
            list(start_page.headings) if start_page.headings else fallback_heading_context
        )

        return start_page.page_number, resolved_page_numbers, resolved_heading_context

    @staticmethod
    def _ranges_overlap(
        range_start: int,
        range_end: int,
        span_start: int,
        span_end: int,
    ) -> bool:
        """Return True when two half-open ranges overlap."""
        return range_start < span_end and range_end > span_start

    @staticmethod
    def _position_in_span(position: int, span_start: int, span_end: int) -> bool:
        """Return True when position falls within a half-open span."""
        return span_start <= position < span_end

    def _split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences.

        Handles common English and CJK sentence boundaries, while falling back to
        token-window splits when a single segment still exceeds ``max_tokens``.

        Args:
            text: Text to split.

        Returns:
            List of sentences.
        """
        pattern = re.compile(
            r".+?(?:\n+|[。！？；]\s*|[.!?;](?:\s+|$)|$)",
            re.DOTALL,
        )
        raw_sentences = [match.group(0) for match in pattern.finditer(text.strip())]

        sentences: List[str] = []
        for raw_sentence in raw_sentences:
            if not raw_sentence.strip():
                continue

            if count_tokens(raw_sentence) <= self.max_tokens:
                sentences.append(raw_sentence)
                continue

            sentences.extend(self._split_oversized_segment(raw_sentence))

        return sentences

    def _split_oversized_segment(self, text: str) -> List[str]:
        """
        Split a single oversized segment into token-bounded pieces.

        This keeps ingestion safe even when sentence detection misses natural
        boundaries, which is common with PDFs containing links, bullets, or CJK
        text that does not follow English punctuation rules.
        """
        encoding = _get_encoding()
        token_ids = encoding.encode(text)
        segments: List[str] = []

        for start in range(0, len(token_ids), self.max_tokens):
            end = min(start + self.max_tokens, len(token_ids))
            segment = encoding.decode(token_ids[start:end])
            if segment.strip():
                segments.append(segment)

        return segments
