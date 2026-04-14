"""
Source snapshot builders and persistence helpers.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha1, sha256
import json
import logging
import os
import re
from typing import Any, Protocol
import uuid

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from services.api.core.ai import BigModelChatProvider
from services.api.core.language import infer_language
from services.api.modules.chunking import ChunkResult, count_tokens
from services.api.modules.parsers import ParseResult
from services.api.modules.snapshots.models import SourceSnapshot
from services.api.modules.sources.models import Source


logger = logging.getLogger(__name__)

SOURCE_SNAPSHOT_SCHEMA_VERSION = "1.0"
MAX_CONTENT_DIGEST_OVERVIEW_TOKENS = 120
MAX_COVERED_THEMES = 8
MAX_KEY_ASSERTIONS = 5
MAX_REPRESENTATIVE_PASSAGES = 3
MAX_KEYWORDS = 15
MAX_STRUCTURE_EXPORT_DEPTH = 3
MAX_LLM_CHUNK_CONTENT_CHARS = 1200
MAX_SNAPSHOT_LOG_PREVIEW_CHARS = 240
SNAPSHOT_LLM_TIMEOUT_SECONDS = max(
    1.0,
    float(os.getenv("SNAPSHOT_LLM_TIMEOUT_SECONDS", "30")),
)
SNAPSHOT_PAYLOAD_KEYS = (
    "overview",
    "covered_themes",
    "key_assertions",
    "representative_passages",
    "unresolved_gaps",
    "keywords",
)
LATIN_TERM_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_.:/-]{2,}")
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?。！？])\s+")
HAN_SEQUENCE_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,8}")

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "with",
}

CHINESE_STOPWORDS = {
    "我们",
    "你们",
    "他们",
    "以及",
    "这个",
    "那个",
    "这里",
    "那里",
    "因为",
    "所以",
    "如果",
    "但是",
    "然后",
}


class SnapshotGenerationError(Exception):
    """Raised when snapshot generation fails."""


@dataclass(frozen=True)
class PreparedSourceChunk:
    """Chunk metadata enriched with a stable ID for snapshot traceability."""

    chunk_id: uuid.UUID
    source_id: uuid.UUID
    chunk_index: int
    content: str
    token_count: int
    char_start: int
    char_end: int
    page_number: int | None
    page_numbers: list[int]
    heading_context: list[str]
    source_title: str

    def to_trace_ref(self) -> dict[str, Any]:
        return {
            "chunk_id": str(self.chunk_id),
            "chunk_index": self.chunk_index,
            "page_number": self.page_number,
            "page_numbers": list(self.page_numbers),
            "headings": list(self.heading_context),
            "char_start": self.char_start,
            "char_end": self.char_end,
        }


@dataclass(frozen=True)
class SemanticSnapshotDraft:
    """Provider output before trace refs and budgets are normalized."""

    content_digest: dict[str, Any]
    keywords: list[dict[str, Any]]
    generation_method: str
    model_name: str | None = None


class SnapshotSemanticProvider(Protocol):
    """Protocol for semantic snapshot providers."""

    def generate(
        self,
        *,
        source: Source,
        parse_result: ParseResult,
        prepared_chunks: list[PreparedSourceChunk],
        deterministic_snapshot: dict[str, Any],
    ) -> SemanticSnapshotDraft:
        ...


class _LLMRepresentativePassage(BaseModel):
    chunk_id: str
    text: str


class _LLMKeyword(BaseModel):
    term: str
    weight: float = 1.0
    chunk_ids: list[str] = Field(default_factory=list)


class _LLMSnapshotPayload(BaseModel):
    overview: str
    covered_themes: list[str] = Field(default_factory=list)
    key_assertions: list[str] = Field(default_factory=list)
    representative_passages: list[_LLMRepresentativePassage] = Field(default_factory=list)
    unresolved_gaps: list[str] = Field(default_factory=list)
    keywords: list[_LLMKeyword] = Field(default_factory=list)


def _snapshot_payload_score(payload: dict[str, Any]) -> tuple[int, int, int]:
    """Rank JSON object candidates by how closely they match the snapshot schema."""
    key_matches = sum(1 for key in SNAPSHOT_PAYLOAD_KEYS if key in payload)
    overview_value = payload.get("overview")
    overview_present = int(
        isinstance(overview_value, str) and bool(overview_value.strip())
    )
    return (overview_present, key_matches, len(payload))


def _load_json_object_candidates_from_llm_output(raw_output: str) -> list[dict[str, Any]]:
    """Extract ranked JSON object candidates from a model response string."""
    stripped_output = raw_output.strip()
    if not stripped_output:
        raise SnapshotGenerationError("Snapshot provider returned empty output")

    decoder = json.JSONDecoder()
    first_decode_error: json.JSONDecodeError | None = None
    candidates: list[tuple[tuple[int, int, int], int, dict[str, Any]]] = []

    for match in re.finditer(r"\{", stripped_output):
        try:
            parsed, _ = decoder.raw_decode(stripped_output[match.start():])
        except json.JSONDecodeError as exc:
            if first_decode_error is None:
                first_decode_error = exc
            continue

        if isinstance(parsed, dict):
            candidates.append(
                (_snapshot_payload_score(parsed), match.start(), parsed)
            )

    if candidates:
        # Prefer payloads that actually resemble the snapshot schema; on ties,
        # prefer later objects because model outputs often add the final answer last.
        ranked = sorted(candidates, key=lambda item: (item[0], item[1]), reverse=True)
        return [item[2] for item in ranked]

    if first_decode_error is not None:
        raise SnapshotGenerationError(
            f"Snapshot provider returned invalid JSON: {first_decode_error}"
        ) from first_decode_error

    raise SnapshotGenerationError("Snapshot provider returned invalid JSON: no JSON object found")


def _preview_log_text(text: str | None, max_chars: int = MAX_SNAPSHOT_LOG_PREVIEW_CHARS) -> str:
    """Collapse whitespace so provider output can be inspected safely in logs."""
    normalized = re.sub(r"\s+", " ", (text or "")).strip()
    if len(normalized) <= max_chars:
        return normalized
    return f"{normalized[: max_chars - 3]}..."


def _coerce_uuid(value: uuid.UUID | str) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def prepare_source_chunks(source: Source, chunks: list[ChunkResult]) -> list[PreparedSourceChunk]:
    """Assign stable chunk IDs before snapshot generation and DB persistence."""
    source_uuid = _coerce_uuid(source.id)
    prepared: list[PreparedSourceChunk] = []

    for chunk in chunks:
        stable_name = (
            f"{chunk.chunk_index}:{chunk.char_start}:{chunk.char_end}:"
            f"{sha1(chunk.content.encode('utf-8')).hexdigest()[:12]}"
        )
        prepared.append(
            PreparedSourceChunk(
                chunk_id=uuid.uuid5(source_uuid, stable_name),
                source_id=source_uuid,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                token_count=chunk.token_count,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                page_number=chunk.page_number,
                page_numbers=list(chunk.page_numbers),
                heading_context=list(chunk.heading_context),
                source_title=chunk.source_title,
            )
        )

    return prepared


def _build_runtime_semantic_provider() -> SnapshotSemanticProvider:
    try:
        return LLMSourceSnapshotSemanticProvider()
    except (ImportError, ValueError):
        return HeuristicSnapshotSemanticProvider()


def _trim_text_to_token_budget(text: str, max_tokens: int) -> str:
    normalized = " ".join(text.split())
    if not normalized:
        return ""
    if count_tokens(normalized) <= max_tokens:
        return normalized

    words = normalized.split()
    trimmed: list[str] = []
    for word in words:
        candidate = " ".join(trimmed + [word])
        if count_tokens(candidate) > max_tokens:
            break
        trimmed.append(word)
    return " ".join(trimmed).strip()


def _dedupe_strings(values: list[str], *, max_items: int) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()

    for value in values:
        normalized = " ".join(value.split()).strip()
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
        if len(deduped) >= max_items:
            break

    return deduped


def _excerpt(text: str, max_chars: int = 220) -> str:
    normalized = " ".join(text.split()).strip()
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 3].rstrip() + "..."


def _split_sentences(text: str) -> list[str]:
    normalized = text.strip()
    if not normalized:
        return []

    sentences = [segment.strip() for segment in SENTENCE_SPLIT_PATTERN.split(normalized)]
    if len(sentences) == 1:
        sentences = [
            segment.strip()
            for segment in re.split(r"(?<=[.!?。！？])", normalized)
            if segment.strip()
        ]
    return [sentence for sentence in sentences if sentence]


def _build_fallback_overview(full_text: str, prepared_chunks: list[PreparedSourceChunk]) -> str:
    """Build a deterministic non-empty overview from parsed source content."""
    sentences = _split_sentences(full_text)
    if sentences:
        candidate = " ".join(sentences[:2])
    elif prepared_chunks:
        candidate = " ".join(chunk.content for chunk in prepared_chunks[:2])
    else:
        candidate = full_text

    return _trim_text_to_token_budget(candidate, MAX_CONTENT_DIGEST_OVERVIEW_TOKENS)


def _merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not intervals:
        return []

    merged: list[tuple[int, int]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
            continue
        merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged


def _compute_coverage_ratio(char_length: int, prepared_chunks: list[PreparedSourceChunk]) -> float:
    if char_length <= 0:
        return 0.0
    intervals = _merge_intervals(
        [(chunk.char_start, chunk.char_end) for chunk in prepared_chunks if chunk.char_end > chunk.char_start]
    )
    covered = sum(end - start for start, end in intervals)
    return min(1.0, round(covered / char_length, 4))


def _slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "-", value.strip().lower())
    return slug.strip("-") or "node"


def _build_structure_outline(prepared_chunks: list[PreparedSourceChunk]) -> list[dict[str, Any]]:
    nodes: dict[str, dict[str, Any]] = {}

    for chunk in prepared_chunks:
        if not chunk.heading_context:
            continue

        path_labels: list[str] = []
        parent_id: str | None = None

        for depth, label in enumerate(chunk.heading_context[:MAX_STRUCTURE_EXPORT_DEPTH], start=1):
            normalized_label = " ".join(label.split()).strip()
            if not normalized_label:
                continue

            path_labels.append(normalized_label)
            node_id = f"heading:{depth}:{_slugify('/'.join(path_labels))}"
            node = nodes.setdefault(
                node_id,
                {
                    "node_id": node_id,
                    "node_type": "heading",
                    "label": normalized_label,
                    "depth": depth,
                    "parent_id": parent_id,
                    "path": list(path_labels),
                    "chunk_refs": [],
                },
            )
            trace_ref = chunk.to_trace_ref()
            if not any(ref["chunk_id"] == trace_ref["chunk_id"] for ref in node["chunk_refs"]):
                node["chunk_refs"].append(trace_ref)
            parent_id = node_id

    return sorted(
        nodes.values(),
        key=lambda node: (node["depth"], "/".join(node["path"])),
    )


def _extract_keyword_candidates(
    prepared_chunks: list[PreparedSourceChunk],
) -> list[dict[str, Any]]:
    scores: dict[str, float] = defaultdict(float)
    labels: dict[str, str] = {}
    chunk_refs: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)

    def add_candidate(term: str, chunk: PreparedSourceChunk, weight: float) -> None:
        normalized = " ".join(term.split()).strip()
        if not normalized:
            return

        key = normalized.casefold()
        scores[key] += weight
        labels.setdefault(key, normalized)
        chunk_refs[key][str(chunk.chunk_id)] = chunk.to_trace_ref()

    for chunk in prepared_chunks:
        for heading in chunk.heading_context[:MAX_STRUCTURE_EXPORT_DEPTH]:
            if heading:
                add_candidate(heading, chunk, 3.0)

        for token in LATIN_TERM_PATTERN.findall(chunk.content):
            normalized = token.strip()
            if normalized.casefold() in STOPWORDS:
                continue
            add_candidate(normalized, chunk, 1.0)

        for han_term in HAN_SEQUENCE_PATTERN.findall(chunk.content):
            if han_term in CHINESE_STOPWORDS:
                continue
            add_candidate(han_term, chunk, 0.8)

    ranked = sorted(
        scores.items(),
        key=lambda item: (-item[1], labels[item[0]].casefold()),
    )
    keywords: list[dict[str, Any]] = []

    for key, score in ranked[:MAX_KEYWORDS]:
        keywords.append(
            {
                "term": labels[key],
                "weight": round(score, 3),
                "chunk_refs": list(chunk_refs[key].values())[:3],
            }
        )

    return keywords


def _build_representative_refs(prepared_chunks: list[PreparedSourceChunk]) -> list[dict[str, Any]]:
    if not prepared_chunks:
        return []

    selected_indexes = {0, len(prepared_chunks) // 2, len(prepared_chunks) - 1}
    refs: list[dict[str, Any]] = []

    for index in sorted(selected_indexes):
        trace_ref = prepared_chunks[index].to_trace_ref()
        if not any(existing["chunk_id"] == trace_ref["chunk_id"] for existing in refs):
            refs.append(trace_ref)

    return refs[:MAX_REPRESENTATIVE_PASSAGES]


class HeuristicSnapshotSemanticProvider:
    """Fallback provider that derives compact semantic fields without network access."""

    def generate(
        self,
        *,
        source: Source,
        parse_result: ParseResult,
        prepared_chunks: list[PreparedSourceChunk],
        deterministic_snapshot: dict[str, Any],
    ) -> SemanticSnapshotDraft:
        sentences = _split_sentences(parse_result.full_text)
        overview = _trim_text_to_token_budget(
            " ".join(sentences[:2]) if sentences else parse_result.full_text,
            MAX_CONTENT_DIGEST_OVERVIEW_TOKENS,
        )

        structure_outline = deterministic_snapshot["structure_outline"]
        structure_labels = [node["label"] for node in structure_outline]
        keyword_candidates = _extract_keyword_candidates(prepared_chunks)
        keyword_terms = [item["term"] for item in keyword_candidates]

        covered_themes = _dedupe_strings(
            structure_labels + keyword_terms,
            max_items=MAX_COVERED_THEMES,
        )
        key_assertions = _dedupe_strings(sentences, max_items=MAX_KEY_ASSERTIONS)

        representative_passages: list[dict[str, Any]] = []
        for chunk in prepared_chunks[:MAX_REPRESENTATIVE_PASSAGES]:
            representative_passages.append(
                {
                    "chunk_id": str(chunk.chunk_id),
                    "text": _excerpt(chunk.content),
                }
            )

        unresolved_gaps: list[str] = []
        if not structure_outline:
            unresolved_gaps.append("No explicit heading structure detected in the source.")

        return SemanticSnapshotDraft(
            content_digest={
                "overview": overview,
                "covered_themes": covered_themes,
                "key_assertions": key_assertions,
                "representative_passages": representative_passages,
                "unresolved_gaps": unresolved_gaps,
            },
            keywords=keyword_candidates,
            generation_method="heuristic",
            model_name=None,
        )


class LLMSourceSnapshotSemanticProvider:
    """LLM-backed semantic snapshot provider using the shared chat client."""

    SYSTEM_PROMPT = """
You generate source-grounded notebook snapshot metadata for retrieval and notebook overview.

Rules:
- Use only the provided source content and metadata.
- Do not invent facts, sections, themes, or keywords that are not supported.
- Keep the overview concise and source-grounded.
- Representative passages must quote or paraphrase the provided chunk content only.
- Return JSON only in this schema:
{
  "overview": "string",
  "covered_themes": ["theme"],
  "key_assertions": ["assertion"],
  "representative_passages": [{"chunk_id": "uuid", "text": "short excerpt"}],
  "unresolved_gaps": ["gap"],
  "keywords": [{"term": "keyword", "weight": 1.0, "chunk_ids": ["uuid"]}]
}
"""

    def __init__(self, *, chat_provider: BigModelChatProvider | None = None) -> None:
        self.chat_provider = chat_provider or BigModelChatProvider()

    @property
    def model_name(self) -> str | None:
        return getattr(self.chat_provider, "model", None)

    def _generate_heuristic_fallback(
        self,
        *,
        source: Source,
        parse_result: ParseResult,
        prepared_chunks: list[PreparedSourceChunk],
        deterministic_snapshot: dict[str, Any],
        reason: str,
    ) -> SemanticSnapshotDraft:
        logger.warning(
            "Falling back to heuristic snapshot for source %s: %s",
            source.id,
            reason,
        )
        return HeuristicSnapshotSemanticProvider().generate(
            source=source,
            parse_result=parse_result,
            prepared_chunks=prepared_chunks,
            deterministic_snapshot=deterministic_snapshot,
        )

    def _build_messages(
        self,
        *,
        source: Source,
        parse_result: ParseResult,
        prepared_chunks: list[PreparedSourceChunk],
        deterministic_snapshot: dict[str, Any],
    ) -> list[dict[str, str]]:
        chunk_payload = []
        for chunk in prepared_chunks:
            chunk_payload.append(
                {
                    "chunk_id": str(chunk.chunk_id),
                    "chunk_index": chunk.chunk_index,
                    "page_numbers": chunk.page_numbers,
                    "headings": chunk.heading_context,
                    "content": chunk.content[:MAX_LLM_CHUNK_CONTENT_CHARS],
                }
            )

        language = infer_language(parse_result.full_text[:2000])
        if language == "zh":
            language_instruction = "Return all natural-language fields in Simplified Chinese."
        elif language == "en":
            language_instruction = "Return all natural-language fields in English."
        else:
            language_instruction = (
                "Return all natural-language fields in the same language as the source content."
            )

        return [
            {"role": "system", "content": self.SYSTEM_PROMPT.strip()},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "language_instruction": language_instruction,
                        "source": {
                            "source_id": str(source.id),
                            "title": source.title,
                            "source_type": (
                                source.source_type.value
                                if hasattr(source.source_type, "value")
                                else str(source.source_type)
                            ),
                        },
                        "deterministic_snapshot": deterministic_snapshot,
                        "chunks": chunk_payload,
                    },
                    ensure_ascii=False,
                ),
            },
        ]

    def _parse_raw_output(
        self,
        *,
        raw_output: str,
        source: Source,
        parse_result: ParseResult,
        prepared_chunks: list[PreparedSourceChunk],
        deterministic_snapshot: dict[str, Any],
    ) -> SemanticSnapshotDraft:
        logger.info(
            "Snapshot provider returned output for source %s chars=%s",
            source.id,
            len((raw_output or "").strip()),
        )

        try:
            candidates = _load_json_object_candidates_from_llm_output(raw_output)
        except SnapshotGenerationError as exc:
            logger.warning(
                "Snapshot provider output could not be parsed for source %s: %s preview=%r",
                source.id,
                exc,
                _preview_log_text(raw_output),
            )
            return self._generate_heuristic_fallback(
                source=source,
                parse_result=parse_result,
                prepared_chunks=prepared_chunks,
                deterministic_snapshot=deterministic_snapshot,
                reason=str(exc),
            )
        except ValidationError as exc:
            logger.warning(
                "Snapshot provider returned invalid payload for source %s: %s preview=%r",
                source.id,
                exc,
                _preview_log_text(raw_output),
            )
            return self._generate_heuristic_fallback(
                source=source,
                parse_result=parse_result,
                prepared_chunks=prepared_chunks,
                deterministic_snapshot=deterministic_snapshot,
                reason=f"Snapshot provider returned invalid payload: {exc}",
            )

        parsed: _LLMSnapshotPayload | None = None
        last_validation_error: ValidationError | None = None
        for candidate in candidates:
            try:
                parsed = _LLMSnapshotPayload.model_validate(candidate)
                break
            except ValidationError as exc:
                last_validation_error = exc
                continue

        if parsed is None:
            logger.warning(
                "Snapshot provider returned invalid payload for source %s: %s preview=%r",
                source.id,
                last_validation_error,
                _preview_log_text(raw_output),
            )
            return self._generate_heuristic_fallback(
                source=source,
                parse_result=parse_result,
                prepared_chunks=prepared_chunks,
                deterministic_snapshot=deterministic_snapshot,
                reason=f"Snapshot provider returned invalid payload: {last_validation_error}",
            )

        return SemanticSnapshotDraft(
            content_digest={
                "overview": parsed.overview,
                "covered_themes": parsed.covered_themes,
                "key_assertions": parsed.key_assertions,
                "representative_passages": [
                    passage.model_dump() for passage in parsed.representative_passages
                ],
                "unresolved_gaps": parsed.unresolved_gaps,
            },
            keywords=[keyword.model_dump() for keyword in parsed.keywords],
            generation_method="llm",
            model_name=self.model_name,
        )

    def generate(
        self,
        *,
        source: Source,
        parse_result: ParseResult,
        prepared_chunks: list[PreparedSourceChunk],
        deterministic_snapshot: dict[str, Any],
    ) -> SemanticSnapshotDraft:
        messages = self._build_messages(
            source=source,
            parse_result=parse_result,
            prepared_chunks=prepared_chunks,
            deterministic_snapshot=deterministic_snapshot,
        )

        logger.info(
            "Requesting semantic snapshot for source %s with %s chunks",
            source.id,
            len(prepared_chunks),
        )
        raw_output = self.chat_provider.chat(messages)
        return self._parse_raw_output(
            raw_output=raw_output,
            source=source,
            parse_result=parse_result,
            prepared_chunks=prepared_chunks,
            deterministic_snapshot=deterministic_snapshot,
        )

    async def generate_async(
        self,
        *,
        source: Source,
        parse_result: ParseResult,
        prepared_chunks: list[PreparedSourceChunk],
        deterministic_snapshot: dict[str, Any],
    ) -> SemanticSnapshotDraft:
        """
        Async wrapper for semantic snapshot generation.

        The provider call is executed in a worker thread so one slow snapshot
        response does not block the event loop from starting other ingestion jobs.
        """
        messages = self._build_messages(
            source=source,
            parse_result=parse_result,
            prepared_chunks=prepared_chunks,
            deterministic_snapshot=deterministic_snapshot,
        )

        logger.info(
            "Requesting semantic snapshot for source %s with %s chunks (async)",
            source.id,
            len(prepared_chunks),
        )
        try:
            raw_output = await asyncio.wait_for(
                asyncio.to_thread(self.chat_provider.chat, messages),
                timeout=SNAPSHOT_LLM_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            return self._generate_heuristic_fallback(
                source=source,
                parse_result=parse_result,
                prepared_chunks=prepared_chunks,
                deterministic_snapshot=deterministic_snapshot,
                reason=(
                    "Snapshot LLM timed out after "
                    f"{SNAPSHOT_LLM_TIMEOUT_SECONDS:.0f}s"
                ),
            )
        return self._parse_raw_output(
            raw_output=raw_output,
            source=source,
            parse_result=parse_result,
            prepared_chunks=prepared_chunks,
            deterministic_snapshot=deterministic_snapshot,
        )


class SourceSnapshotService:
    """Build and upsert source snapshots from parsed and chunked source data."""

    def __init__(
        self,
        db: Session,
        semantic_provider: SnapshotSemanticProvider | None = None,
        *,
        schema_version: str = SOURCE_SNAPSHOT_SCHEMA_VERSION,
    ) -> None:
        self.db = db
        self.semantic_provider = semantic_provider or _build_runtime_semantic_provider()
        self.schema_version = schema_version

    def build_and_persist_snapshot(
        self,
        *,
        source: Source,
        parse_result: ParseResult,
        prepared_chunks: list[PreparedSourceChunk],
    ) -> SourceSnapshot:
        source_content_hash = sha256(parse_result.full_text.encode("utf-8")).hexdigest()
        structure_outline = _build_structure_outline(prepared_chunks)
        keyword_candidates = _extract_keyword_candidates(prepared_chunks)
        representative_refs = _build_representative_refs(prepared_chunks)

        deterministic_snapshot = {
            "content_metrics": {
                "char_length": len(parse_result.full_text),
                "estimated_token_count": count_tokens(parse_result.full_text),
                "chunk_count": len(prepared_chunks),
                "section_count": len(structure_outline),
                "heading_depth_max": max(
                    (node["depth"] for node in structure_outline),
                    default=0,
                ),
                "keyword_count": len(keyword_candidates),
                "coverage_ratio": _compute_coverage_ratio(
                    len(parse_result.full_text),
                    prepared_chunks,
                ),
            },
            "structure_outline": structure_outline,
            "traceability": {
                "representative_chunk_refs": representative_refs,
                "source_ranges": [
                    {
                        "char_start": 0,
                        "char_end": len(parse_result.full_text),
                    }
                ],
            },
        }

        semantic_draft = self._generate_semantic_draft(
            source=source,
            parse_result=parse_result,
            prepared_chunks=prepared_chunks,
            deterministic_snapshot=deterministic_snapshot,
        )
        return self._persist_snapshot_payload(
            source=source,
            parse_result=parse_result,
            prepared_chunks=prepared_chunks,
            source_content_hash=source_content_hash,
            deterministic_snapshot=deterministic_snapshot,
            keyword_candidates=keyword_candidates,
            semantic_draft=semantic_draft,
        )

    async def build_and_persist_snapshot_async(
        self,
        *,
        source: Source,
        parse_result: ParseResult,
        prepared_chunks: list[PreparedSourceChunk],
    ) -> SourceSnapshot:
        source_content_hash = sha256(parse_result.full_text.encode("utf-8")).hexdigest()
        structure_outline = _build_structure_outline(prepared_chunks)
        keyword_candidates = _extract_keyword_candidates(prepared_chunks)
        representative_refs = _build_representative_refs(prepared_chunks)

        deterministic_snapshot = {
            "content_metrics": {
                "char_length": len(parse_result.full_text),
                "estimated_token_count": count_tokens(parse_result.full_text),
                "chunk_count": len(prepared_chunks),
                "section_count": len(structure_outline),
                "heading_depth_max": max(
                    (node["depth"] for node in structure_outline),
                    default=0,
                ),
                "keyword_count": len(keyword_candidates),
                "coverage_ratio": _compute_coverage_ratio(
                    len(parse_result.full_text),
                    prepared_chunks,
                ),
            },
            "structure_outline": structure_outline,
            "traceability": {
                "representative_chunk_refs": representative_refs,
                "source_ranges": [
                    {
                        "char_start": 0,
                        "char_end": len(parse_result.full_text),
                    }
                ],
            },
        }

        semantic_draft = await self._generate_semantic_draft_async(
            source=source,
            parse_result=parse_result,
            prepared_chunks=prepared_chunks,
            deterministic_snapshot=deterministic_snapshot,
        )
        return self._persist_snapshot_payload(
            source=source,
            parse_result=parse_result,
            prepared_chunks=prepared_chunks,
            source_content_hash=source_content_hash,
            deterministic_snapshot=deterministic_snapshot,
            keyword_candidates=keyword_candidates,
            semantic_draft=semantic_draft,
        )

    def _generate_semantic_draft(
        self,
        *,
        source: Source,
        parse_result: ParseResult,
        prepared_chunks: list[PreparedSourceChunk],
        deterministic_snapshot: dict[str, Any],
    ) -> SemanticSnapshotDraft:
        try:
            return self.semantic_provider.generate(
                source=source,
                parse_result=parse_result,
                prepared_chunks=prepared_chunks,
                deterministic_snapshot=deterministic_snapshot,
            )
        except SnapshotGenerationError:
            raise
        except Exception as exc:
            raise SnapshotGenerationError(str(exc)) from exc

    async def _generate_semantic_draft_async(
        self,
        *,
        source: Source,
        parse_result: ParseResult,
        prepared_chunks: list[PreparedSourceChunk],
        deterministic_snapshot: dict[str, Any],
    ) -> SemanticSnapshotDraft:
        generate_async = getattr(self.semantic_provider, "generate_async", None)
        try:
            if callable(generate_async):
                return await generate_async(
                    source=source,
                    parse_result=parse_result,
                    prepared_chunks=prepared_chunks,
                    deterministic_snapshot=deterministic_snapshot,
                )
            return self.semantic_provider.generate(
                source=source,
                parse_result=parse_result,
                prepared_chunks=prepared_chunks,
                deterministic_snapshot=deterministic_snapshot,
            )
        except SnapshotGenerationError:
            raise
        except Exception as exc:
            raise SnapshotGenerationError(str(exc)) from exc

    def _persist_snapshot_payload(
        self,
        *,
        source: Source,
        parse_result: ParseResult,
        prepared_chunks: list[PreparedSourceChunk],
        source_content_hash: str,
        deterministic_snapshot: dict[str, Any],
        keyword_candidates: list[dict[str, Any]],
        semantic_draft: SemanticSnapshotDraft,
    ) -> SourceSnapshot:
        raw_overview = " ".join(str(semantic_draft.content_digest.get("overview", "")).split()).strip()
        raw_covered_themes = [
            value
            for value in semantic_draft.content_digest.get("covered_themes", [])
            if isinstance(value, str) and value.strip()
        ]
        if (
            semantic_draft.generation_method == "llm"
            and not raw_overview
            and (raw_covered_themes or semantic_draft.keywords)
        ):
            logger.warning(
                "LLM snapshot payload returned empty overview with non-empty themes/keywords "
                "source=%s themes=%s keywords=%s",
                source.id,
                len(raw_covered_themes),
                len(semantic_draft.keywords),
            )

        semantic_snapshot = self._normalize_semantic_snapshot(
            semantic_draft=semantic_draft,
            prepared_chunks=prepared_chunks,
            fallback_keywords=keyword_candidates,
            fallback_overview=_build_fallback_overview(
                parse_result.full_text,
                prepared_chunks,
            ),
        )
        overview_value = (
            semantic_snapshot.get("content_digest", {}).get("overview")
            if isinstance(semantic_snapshot, dict)
            else None
        )
        if not isinstance(overview_value, str) or not overview_value.strip():
            logger.warning(
                "Snapshot overview remained empty after normalization source=%s; applying deterministic fallback",
                source.id,
            )
            semantic_snapshot.setdefault("content_digest", {})["overview"] = _build_fallback_overview(
                parse_result.full_text,
                prepared_chunks,
            )

        deterministic_snapshot["content_metrics"]["keyword_count"] = len(
            semantic_snapshot["keywords"]
        )

        payload = {
            "source_identity": {
                "source_id": str(source.id),
                "notebook_id": str(source.notebook_id),
                "title": source.title,
                "source_type": (
                    source.source_type.value
                    if hasattr(source.source_type, "value")
                    else str(source.source_type)
                ),
                "parser_version": parse_result.metadata.get("parser_version", "unknown"),
                "snapshot_version": self.schema_version,
                "source_content_hash": source_content_hash,
            },
            "deterministic": deterministic_snapshot,
            "semantic": semantic_snapshot,
        }

        existing = (
            self.db.query(SourceSnapshot)
            .filter(SourceSnapshot.source_id == source.id)
            .first()
        )

        if existing is None:
            snapshot = SourceSnapshot(
                source_id=source.id,
                notebook_id=source.notebook_id,
                schema_version=self.schema_version,
                source_content_hash=source_content_hash,
                generation_method=semantic_draft.generation_method,
                model_name=semantic_draft.model_name,
                snapshot_data=payload,
            )
            self.db.add(snapshot)
        else:
            snapshot = existing
            snapshot.notebook_id = source.notebook_id
            snapshot.schema_version = self.schema_version
            snapshot.source_content_hash = source_content_hash
            snapshot.generation_method = semantic_draft.generation_method
            snapshot.model_name = semantic_draft.model_name
            snapshot.snapshot_data = payload

        self.db.flush()
        return snapshot

    def _normalize_semantic_snapshot(
        self,
        *,
        semantic_draft: SemanticSnapshotDraft,
        prepared_chunks: list[PreparedSourceChunk],
        fallback_keywords: list[dict[str, Any]],
        fallback_overview: str,
    ) -> dict[str, Any]:
        chunk_lookup = {str(chunk.chunk_id): chunk for chunk in prepared_chunks}
        content_digest = semantic_draft.content_digest
        overview = _trim_text_to_token_budget(
            str(content_digest.get("overview", "")),
            MAX_CONTENT_DIGEST_OVERVIEW_TOKENS,
        )
        if not overview:
            overview = fallback_overview

        representative_passages: list[dict[str, Any]] = []
        for passage in content_digest.get("representative_passages", []):
            chunk = chunk_lookup.get(str(passage.get("chunk_id")))
            if chunk is None:
                continue
            representative_passages.append(
                {
                    "text": _excerpt(str(passage.get("text", ""))),
                    "chunk_ref": chunk.to_trace_ref(),
                }
            )
            if len(representative_passages) >= MAX_REPRESENTATIVE_PASSAGES:
                break

        if not representative_passages:
            for chunk in prepared_chunks[:MAX_REPRESENTATIVE_PASSAGES]:
                representative_passages.append(
                    {
                        "text": _excerpt(chunk.content),
                        "chunk_ref": chunk.to_trace_ref(),
                    }
                )

        keywords: list[dict[str, Any]] = []
        for keyword in semantic_draft.keywords:
            term = " ".join(str(keyword.get("term", "")).split()).strip()
            if not term:
                continue

            refs: list[dict[str, Any]] = []
            for chunk_id in keyword.get("chunk_ids", []):
                chunk = chunk_lookup.get(str(chunk_id))
                if chunk is None:
                    continue
                refs.append(chunk.to_trace_ref())

            if not refs and prepared_chunks:
                refs.append(prepared_chunks[0].to_trace_ref())

            keywords.append(
                {
                    "term": term,
                    "weight": round(float(keyword.get("weight", 1.0)), 3),
                    "chunk_refs": refs[:3],
                }
            )
            if len(keywords) >= MAX_KEYWORDS:
                break

        if not keywords:
            keywords = fallback_keywords[:MAX_KEYWORDS]

        return {
            "content_digest": {
                "overview": overview,
                "covered_themes": _dedupe_strings(
                    list(content_digest.get("covered_themes", [])),
                    max_items=MAX_COVERED_THEMES,
                ),
                "key_assertions": _dedupe_strings(
                    list(content_digest.get("key_assertions", [])),
                    max_items=MAX_KEY_ASSERTIONS,
                ),
                "representative_passages": representative_passages[:MAX_REPRESENTATIVE_PASSAGES],
                "unresolved_gaps": _dedupe_strings(
                    list(content_digest.get("unresolved_gaps", [])),
                    max_items=MAX_KEY_ASSERTIONS,
                ),
            },
            "keywords": keywords[:MAX_KEYWORDS],
        }
