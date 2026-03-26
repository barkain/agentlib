"""Semantic chunking: ParsedSection[] → chunk files (300-500 tokens).

Structural blocks (markdown tables, fenced code) are kept atomic up to
HARD_CAP_TOKENS.  Oversized blocks are split at row/line boundaries with
header propagation (tables) or fence-marker preservation (code).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import tiktoken  # type: ignore[import-not-found]

from lib.models import ChunkMeta, ParsedSection


# ---------------------------------------------------------------------------
# Token counting
# ---------------------------------------------------------------------------

_encoder: tiktoken.Encoding | None = None


def _get_encoder() -> tiktoken.Encoding:
    global _encoder
    if _encoder is None:
        _encoder = tiktoken.get_encoding("cl100k_base")
    return _encoder


def count_tokens(text: str) -> int:
    """Count tokens using cl100k_base encoding."""
    return len(_get_encoder().encode(text))


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_CHUNK_TOKENS = 300
MAX_CHUNK_TOKENS = 500       # soft cap (prose)
HARD_CAP_TOKENS = 1000       # hard cap (structural blocks)


# ---------------------------------------------------------------------------
# Block model
# ---------------------------------------------------------------------------

@dataclass
class Block:
    """A contiguous piece of text with a detected content type."""
    text: str
    kind: str   # "prose" | "table" | "code_fence"


# ---------------------------------------------------------------------------
# Paragraph splitter (kept for backward-compat / tests)
# ---------------------------------------------------------------------------

def _split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs on blank lines, preserving content."""
    paragraphs = re.split(r"\n\s*\n", text.strip())
    return [p.strip() for p in paragraphs if p.strip()]


# ---------------------------------------------------------------------------
# Block splitter  (replaces _split_paragraphs in the merge loop)
# ---------------------------------------------------------------------------

_FENCE_OPEN_RE = re.compile(r"^(\s*(`{3,}|~{3,}))(.*)?$")
_TABLE_SEP_RE = re.compile(
    r"^\|\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|\s*$"
)


def _is_table_row(line: str) -> bool:
    """Return True if *line* looks like a markdown pipe-table row."""
    stripped = line.strip()
    return stripped.startswith("|") or ("|" in stripped and _TABLE_SEP_RE.match(stripped) is not None)


def _split_blocks(text: str) -> list[Block]:
    """Split *text* into a sequence of typed blocks.

    Code fences take priority — anything inside a fence (including table-like
    syntax) is treated as code, not as a table.
    """
    lines = text.split("\n")
    blocks: list[Block] = []
    prose_lines: list[str] = []

    def _flush_prose() -> None:
        if not prose_lines:
            return
        # Sub-split prose on blank lines, same as _split_paragraphs
        joined = "\n".join(prose_lines)
        for para in re.split(r"\n\s*\n", joined):
            stripped = para.strip()
            if stripped:
                blocks.append(Block(text=stripped, kind="prose"))
        prose_lines.clear()

    i = 0
    while i < len(lines):
        line = lines[i]

        # --- Code fence detection ---
        m = _FENCE_OPEN_RE.match(line)
        if m:
            _flush_prose()
            marker = m.group(2)          # e.g. "```" or "~~~"
            marker_char = marker[0]
            marker_len = len(marker)
            fence_lines = [line]
            i += 1
            while i < len(lines):
                fline = lines[i]
                fence_lines.append(fline)
                # Closing fence: same char, at least same length, nothing else
                cm = re.match(
                    rf"^\s*{re.escape(marker_char)}{{{marker_len},}}\s*$",
                    fline,
                )
                if cm:
                    i += 1
                    break
                i += 1
            blocks.append(Block(text="\n".join(fence_lines), kind="code_fence"))
            continue

        # --- Table detection (look for separator row) ---
        if _TABLE_SEP_RE.match(line.strip()):
            # Collect header rows above: walk back through prose_lines
            header_lines: list[str] = []
            while prose_lines and prose_lines[-1].strip().startswith("|"):
                header_lines.insert(0, prose_lines.pop())
            _flush_prose()

            table_lines = header_lines + [line]
            i += 1
            # Collect contiguous data rows
            while i < len(lines):
                row = lines[i]
                if row.strip() == "" or not row.strip().startswith("|"):
                    break
                table_lines.append(row)
                i += 1
            blocks.append(Block(text="\n".join(table_lines), kind="table"))
            continue

        # --- Default: accumulate as prose ---
        prose_lines.append(line)
        i += 1

    _flush_prose()
    return blocks


# ---------------------------------------------------------------------------
# Oversized-block splitters
# ---------------------------------------------------------------------------

def _split_table(block: Block) -> list[Block]:
    """Split an oversized table at row boundaries, duplicating the header."""
    lines = block.text.split("\n")

    # Find separator row
    sep_idx = None
    for idx, line in enumerate(lines):
        if _TABLE_SEP_RE.match(line.strip()):
            sep_idx = idx
            break

    if sep_idx is None:
        # Can't parse structure — return as-is
        return [block]

    header_lines = lines[: sep_idx + 1]       # includes separator
    data_lines = lines[sep_idx + 1:]
    header_text = "\n".join(header_lines)
    header_tokens = count_tokens(header_text)

    sub_blocks: list[Block] = []
    current_rows: list[str] = []
    current_tokens = header_tokens

    def _flush_rows() -> None:
        nonlocal current_rows, current_tokens
        if not current_rows:
            return
        text = header_text + "\n" + "\n".join(current_rows)
        sub_blocks.append(Block(text=text, kind="table"))
        current_rows = []
        current_tokens = header_tokens

    for row in data_lines:
        row_tokens = count_tokens(row)
        if current_rows and (current_tokens + row_tokens > HARD_CAP_TOKENS):
            _flush_rows()
        current_rows.append(row)
        current_tokens += row_tokens

    _flush_rows()
    return sub_blocks if sub_blocks else [block]


def _split_code_fence(block: Block) -> list[Block]:
    """Split an oversized code fence at line boundaries, preserving markers."""
    lines = block.text.split("\n")
    if len(lines) < 2:
        return [block]

    open_line = lines[0]

    # Detect closing fence
    m = _FENCE_OPEN_RE.match(open_line)
    if m:
        marker_char = m.group(2)[0]
        marker_len = len(m.group(2))
        close_re = re.compile(
            rf"^\s*{re.escape(marker_char)}{{{marker_len},}}\s*$"
        )
    else:
        close_re = re.compile(r"^\s*(`{3,}|~{3,})\s*$")

    # Check if last line is a closing fence
    if close_re.match(lines[-1]):
        close_line = lines[-1]
        inner_lines = lines[1:-1]
    else:
        close_line = m.group(2) if m else "```"
        inner_lines = lines[1:]

    open_tokens = count_tokens(open_line)
    close_tokens = count_tokens(close_line)
    overhead = open_tokens + close_tokens

    sub_blocks: list[Block] = []
    current_inner: list[str] = []
    current_tokens = overhead

    def _flush_inner() -> None:
        nonlocal current_inner, current_tokens
        if not current_inner:
            return
        text = open_line + "\n" + "\n".join(current_inner) + "\n" + close_line
        sub_blocks.append(Block(text=text, kind="code_fence"))
        current_inner = []
        current_tokens = overhead

    for inner in inner_lines:
        line_tokens = count_tokens(inner)
        if current_inner and (current_tokens + line_tokens > HARD_CAP_TOKENS):
            _flush_inner()
        current_inner.append(inner)
        current_tokens += line_tokens

    _flush_inner()
    return sub_blocks if sub_blocks else [block]


# ---------------------------------------------------------------------------
# Chunk formatting
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Core chunking
# ---------------------------------------------------------------------------

def chunk_section(
    section: ParsedSection,
    source_id: str,
    start_index: int = 1,
) -> list[Chunk]:
    """Chunk a single ParsedSection into token-budgeted chunks.

    Structural blocks (tables, fenced code) are kept atomic up to
    HARD_CAP_TOKENS.  Prose paragraphs use the original 300-500 soft cap.
    """
    blocks = _split_blocks(section.text)
    if not blocks:
        return []

    chunks: list[Chunk] = []
    current_blocks: list[Block] = []
    current_tokens = 0
    idx = start_index

    def _make_chunk_id() -> str:
        return f"{section.section_id}-{idx:03d}"

    def _flush() -> None:
        nonlocal current_blocks, current_tokens, idx
        if not current_blocks:
            return
        body = "\n\n".join(b.text for b in current_blocks)
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
        current_blocks = []
        current_tokens = 0

    for block in blocks:
        block_tokens = count_tokens(block.text)
        is_structural = block.kind in ("table", "code_fence")

        if is_structural:
            if block_tokens > HARD_CAP_TOKENS:
                # Split oversized structural block
                _flush()
                if block.kind == "table":
                    sub_blocks = _split_table(block)
                else:
                    sub_blocks = _split_code_fence(block)
                for sb in sub_blocks:
                    current_blocks = [sb]
                    current_tokens = count_tokens(sb.text)
                    _flush()
            else:
                # Structural block fits — flush accumulator if it would bust
                if current_blocks and (current_tokens + block_tokens > HARD_CAP_TOKENS):
                    _flush()
                elif current_blocks and (current_tokens + block_tokens > MAX_CHUNK_TOKENS):
                    _flush()
                current_blocks.append(block)
                current_tokens += block_tokens
        else:
            # Prose: same logic as before
            if current_blocks and (current_tokens + block_tokens > MAX_CHUNK_TOKENS):
                _flush()
            current_blocks.append(block)
            current_tokens += block_tokens
            if block_tokens > MAX_CHUNK_TOKENS:
                _flush()

    _flush()

    # Link prev/next pointers
    for i, chunk in enumerate(chunks):
        if i > 0:
            chunk.meta.prev = chunks[i - 1].chunk_id
        if i < len(chunks) - 1:
            chunk.meta.next = chunks[i + 1].chunk_id
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
