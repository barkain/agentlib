"""Semantic chunking: ParsedSection[] → chunk files (300-500 tokens)."""
from __future__ import annotations

import re
from dataclasses import dataclass

import tiktoken  # type: ignore[import-not-found]

from lib.models import ChunkMeta, ParsedSection


# Lazy-init encoder
_encoder: tiktoken.Encoding | None = None


def _get_encoder() -> tiktoken.Encoding:
    global _encoder
    if _encoder is None:
        _encoder = tiktoken.get_encoding("cl100k_base")
    return _encoder


def count_tokens(text: str) -> int:
    """Count tokens using cl100k_base encoding."""
    return len(_get_encoder().encode(text))


MIN_CHUNK_TOKENS = 300
MAX_CHUNK_TOKENS = 500


def _split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs on blank lines, preserving content."""
    paragraphs = re.split(r"\n\s*\n", text.strip())
    return [p.strip() for p in paragraphs if p.strip()]


def _format_chunk(meta: ChunkMeta, body: str) -> str:
    """Format a chunk as markdown with YAML frontmatter."""
    lines = [
        "---",
        f"chunk_id: {meta.chunk_id}",
        f"source_id: {meta.source_id}",
        f"section: {meta.section}",
    ]
    if meta.prev:
        lines.append(f"prev: {meta.prev}")
    if meta.next:
        lines.append(f"next: {meta.next}")
    if meta.related:
        lines.append(f"related: [{', '.join(meta.related)}]")
    lines.append(f"token_count: {meta.token_count}")
    lines.append("---")
    lines.append("")
    lines.append(body)
    return "\n".join(lines)


@dataclass
class Chunk:
    """A single chunk ready to be written to disk."""
    chunk_id: str
    meta: ChunkMeta
    body: str
    formatted: str


def chunk_section(
    section: ParsedSection,
    source_id: str,
    start_index: int = 1,
) -> list[Chunk]:
    """Chunk a single ParsedSection into 300-500 token chunks.

    Paragraphs are merged greedily without crossing section boundaries.
    If a single paragraph exceeds MAX_CHUNK_TOKENS, it becomes its own chunk.

    Args:
        section: Parsed section to chunk.
        source_id: Book identifier for chunk metadata.
        start_index: Starting chunk number within this section.

    Returns:
        List of Chunk objects ready to be written to disk.
    """
    paragraphs = _split_paragraphs(section.text)
    if not paragraphs:
        return []

    chunks: list[Chunk] = []
    current_paras: list[str] = []
    current_tokens = 0
    idx = start_index

    def _make_chunk_id() -> str:
        return f"{section.section_id}-{idx:03d}"

    def _flush() -> None:
        nonlocal current_paras, current_tokens, idx
        if not current_paras:
            return
        body = "\n\n".join(current_paras)
        chunk_id = _make_chunk_id()
        token_count = count_tokens(body)
        section_label = f"{section.chapter_title} > {section.section_title}"
        meta = ChunkMeta(
            chunk_id=chunk_id,
            source_id=source_id,
            section=section_label,
            token_count=token_count,
        )
        formatted = _format_chunk(meta, body)
        chunks.append(Chunk(
            chunk_id=chunk_id,
            meta=meta,
            body=body,
            formatted=formatted,
        ))
        idx += 1
        current_paras = []
        current_tokens = 0

    for para in paragraphs:
        para_tokens = count_tokens(para)

        # If adding this paragraph would exceed max, flush first
        if current_paras and (current_tokens + para_tokens > MAX_CHUNK_TOKENS):
            _flush()

        current_paras.append(para)
        current_tokens += para_tokens

        # If single paragraph exceeds max, flush it as its own chunk
        if para_tokens > MAX_CHUNK_TOKENS:
            _flush()

    # Flush remaining paragraphs
    _flush()

    # Link prev/next pointers
    for i, chunk in enumerate(chunks):
        if i > 0:
            chunk.meta.prev = chunks[i - 1].chunk_id
        if i < len(chunks) - 1:
            chunk.meta.next = chunks[i + 1].chunk_id
        # Re-format with updated prev/next
        chunk.formatted = _format_chunk(chunk.meta, chunk.body)

    return chunks


def chunk_sections(
    sections: list[ParsedSection],
    source_id: str,
) -> list[Chunk]:
    """Chunk multiple sections, maintaining continuous indexing per section_id group."""
    all_chunks: list[Chunk] = []
    for section in sections:
        section_chunks = chunk_section(section, source_id)
        all_chunks.extend(section_chunks)
    return all_chunks
