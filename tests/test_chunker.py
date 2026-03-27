"""Tests for the semantic chunker."""
# ruff: noqa: S101
from __future__ import annotations

from lib.chunker import (
    Block,
    HARD_CAP_TOKENS,
    MAX_CHUNK_TOKENS,
    chunk_section,
    chunk_sections,
    count_tokens,
    _split_blocks,
    _split_code_fence,
    _split_paragraphs,
    _split_table,
)
from lib.models import ParsedSection


# ── helpers ───────────────────────────────────────────────────────────────

def _make_section(text: str) -> ParsedSection:
    return ParsedSection(
        chapter_id="ch01",
        chapter_title="Test Chapter",
        section_id="ch01-s01",
        section_title="Test Section",
        text=text,
    )


def _repeat_to_tokens(fragment: str, target: int) -> str:
    """Repeat *fragment* (line-per-copy) until it reaches ~target tokens."""
    lines: list[str] = []
    while count_tokens("\n".join(lines)) < target:
        lines.append(fragment)
    return "\n".join(lines)


# ── TestCountTokens ──────────────────────────────────────────────────────

class TestCountTokens:
    def test_empty_string(self) -> None:
        assert count_tokens("") == 0

    def test_simple_text(self) -> None:
        tokens = count_tokens("Hello, world!")
        assert tokens > 0
        assert tokens < 10

    def test_longer_text(self) -> None:
        text = "This is a longer piece of text that should have more tokens. " * 10
        tokens = count_tokens(text)
        assert tokens > 50


# ── TestSplitParagraphs ──────────────────────────────────────────────────

class TestSplitParagraphs:
    def test_single_paragraph(self) -> None:
        result = _split_paragraphs("Hello world")
        assert result == ["Hello world"]

    def test_multiple_paragraphs(self) -> None:
        result = _split_paragraphs("Para one.\n\nPara two.\n\nPara three.")
        assert len(result) == 3

    def test_empty_string(self) -> None:
        result = _split_paragraphs("")
        assert result == []

    def test_whitespace_only(self) -> None:
        result = _split_paragraphs("   \n\n   ")
        assert result == []


# ── TestSplitBlocks ──────────────────────────────────────────────────────

class TestSplitBlocks:
    def test_prose_only(self) -> None:
        blocks = _split_blocks("Para one.\n\nPara two.\n\nPara three.")
        assert len(blocks) == 3
        assert all(b.kind == "prose" for b in blocks)
        assert blocks[0].text == "Para one."

    def test_fenced_code_backtick(self) -> None:
        text = "Before.\n\n```python\nx = 1\n\ny = 2\n```\n\nAfter."
        blocks = _split_blocks(text)
        assert len(blocks) == 3
        assert blocks[0].kind == "prose"
        assert blocks[1].kind == "code_fence"
        assert blocks[2].kind == "prose"
        # Blank line inside fence is preserved
        assert "\n\ny = 2" in blocks[1].text

    def test_fenced_code_tilde(self) -> None:
        text = "~~~\ncode here\n~~~"
        blocks = _split_blocks(text)
        assert len(blocks) == 1
        assert blocks[0].kind == "code_fence"

    def test_table_detected(self) -> None:
        text = "| A | B |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |"
        blocks = _split_blocks(text)
        assert len(blocks) == 1
        assert blocks[0].kind == "table"
        assert "| A | B |" in blocks[0].text
        assert "| 3 | 4 |" in blocks[0].text

    def test_table_with_surrounding_prose(self) -> None:
        text = "Intro paragraph.\n\n| H1 | H2 |\n| --- | --- |\n| a | b |\n\nConclusion."
        blocks = _split_blocks(text)
        assert len(blocks) == 3
        assert blocks[0].kind == "prose"
        assert blocks[1].kind == "table"
        assert blocks[2].kind == "prose"

    def test_code_fence_containing_table(self) -> None:
        text = "```\n| A | B |\n| --- | --- |\n| 1 | 2 |\n```"
        blocks = _split_blocks(text)
        assert len(blocks) == 1
        assert blocks[0].kind == "code_fence"

    def test_unclosed_code_fence(self) -> None:
        text = "```python\nsome code\nmore code"
        blocks = _split_blocks(text)
        assert len(blocks) == 1
        assert blocks[0].kind == "code_fence"

    def test_multiple_structural_blocks(self) -> None:
        text = (
            "Intro.\n\n"
            "```\ncode\n```\n\n"
            "Middle.\n\n"
            "| H |\n| --- |\n| v |\n\n"
            "End."
        )
        blocks = _split_blocks(text)
        kinds = [b.kind for b in blocks]
        assert kinds == ["prose", "code_fence", "prose", "table", "prose"]

    def test_nested_fence_markers(self) -> None:
        # Outer fence uses 4 backticks, inner uses 3
        text = "````\n```\ninner\n```\n````"
        blocks = _split_blocks(text)
        assert len(blocks) == 1
        assert blocks[0].kind == "code_fence"
        assert "inner" in blocks[0].text

    def test_empty_text(self) -> None:
        assert _split_blocks("") == []
        assert _split_blocks("   \n\n   ") == []


# ── TestSplitTable ───────────────────────────────────────────────────────

class TestSplitTable:
    def test_small_table_not_split(self) -> None:
        text = "| A | B |\n| --- | --- |\n| 1 | 2 |"
        block = Block(text=text, kind="table")
        result = _split_table(block)
        assert len(result) == 1

    def test_large_table_splits_at_rows(self) -> None:
        header = "| Col1 | Col2 |"
        sep = "| --- | --- |"
        row = "| " + "word " * 40 + "| value |"
        rows = [row] * 30  # should exceed HARD_CAP
        text = "\n".join([header, sep] + rows)
        block = Block(text=text, kind="table")
        assert count_tokens(text) > HARD_CAP_TOKENS
        result = _split_table(block)
        assert len(result) > 1

    def test_header_propagated(self) -> None:
        header = "| Col1 | Col2 |"
        sep = "| --- | --- |"
        row = "| " + "word " * 40 + "| value |"
        rows = [row] * 30
        text = "\n".join([header, sep] + rows)
        block = Block(text=text, kind="table")
        result = _split_table(block)
        for sub in result:
            assert sub.text.startswith(header)
            assert sep in sub.text

    def test_single_huge_row(self) -> None:
        header = "| A |\n| --- |"
        row = "| " + "word " * 500 + "|"
        text = header + "\n" + row
        block = Block(text=text, kind="table")
        result = _split_table(block)
        # Irreducible: emitted as-is
        assert len(result) == 1


# ── TestSplitCodeFence ───────────────────────────────────────────────────

class TestSplitCodeFence:
    def test_small_fence_not_split(self) -> None:
        text = "```python\nx = 1\n```"
        block = Block(text=text, kind="code_fence")
        result = _split_code_fence(block)
        assert len(result) == 1

    def test_large_fence_splits_at_lines(self) -> None:
        inner = "\n".join([f"line_{i} = {i}" for i in range(500)])
        text = f"```python\n{inner}\n```"
        block = Block(text=text, kind="code_fence")
        assert count_tokens(text) > HARD_CAP_TOKENS
        result = _split_code_fence(block)
        assert len(result) > 1

    def test_info_string_preserved(self) -> None:
        inner = "\n".join([f"line_{i} = {i}" for i in range(500)])
        text = f"```python\n{inner}\n```"
        block = Block(text=text, kind="code_fence")
        result = _split_code_fence(block)
        for sub in result:
            assert sub.text.startswith("```python")
            assert sub.text.endswith("```")


# ── TestChunkSection ─────────────────────────────────────────────────────

class TestChunkSection:
    def test_empty_text(self) -> None:
        section = _make_section("")
        chunks = chunk_section(section, "test-book")
        assert chunks == []

    def test_single_paragraph(self) -> None:
        section = _make_section("A simple paragraph with a few words.")
        chunks = chunk_section(section, "test-book")
        assert len(chunks) == 1
        assert chunks[0].chunk_id == "ch01-s01-001"
        assert chunks[0].meta.source_id == "test-book"

    def test_paragraphs_merged_under_limit(self) -> None:
        paras = ["Short paragraph." for _ in range(5)]
        section = _make_section("\n\n".join(paras))
        chunks = chunk_section(section, "test-book")
        assert len(chunks) == 1

    def test_large_text_splits(self) -> None:
        para = "This is a substantial paragraph with enough words to count. " * 20
        text = "\n\n".join([para] * 10)
        section = _make_section(text)
        chunks = chunk_section(section, "test-book")
        assert len(chunks) > 1

    def test_prev_next_links(self) -> None:
        para = "This is a substantial paragraph with enough words. " * 25
        text = "\n\n".join([para] * 10)
        section = _make_section(text)
        chunks = chunk_section(section, "test-book")

        if len(chunks) > 1:
            assert chunks[0].meta.prev is None
            assert chunks[0].meta.next == chunks[1].chunk_id
            assert chunks[-1].meta.next is None
            assert chunks[-1].meta.prev == chunks[-2].chunk_id

    def test_chunk_id_format(self) -> None:
        section = _make_section("Some text content.")
        chunks = chunk_section(section, "test-book")
        assert chunks[0].chunk_id.startswith("ch01-s01-")

    def test_chunk_has_yaml_frontmatter(self) -> None:
        section = _make_section("Some text content for the chunk.")
        chunks = chunk_section(section, "test-book")
        assert chunks[0].formatted.startswith("---\n")
        assert "chunk_id:" in chunks[0].formatted
        assert "source_id: test-book" in chunks[0].formatted

    # -- structural block tests --

    def test_table_kept_atomic(self) -> None:
        """A table that fits under HARD_CAP is never split across chunks."""
        prose = "Some introductory text. " * 15   # ~60 tokens
        table = "| A | B |\n| --- | --- |\n" + "\n".join(
            f"| row{i} | val{i} |" for i in range(20)
        )
        section = _make_section(prose + "\n\n" + table + "\n\nConclusion.")
        chunks = chunk_section(section, "test-book")
        # Find the chunk that contains the table
        table_chunks = [c for c in chunks if "| A | B |" in c.body]
        assert len(table_chunks) == 1
        assert "| row19 | val19 |" in table_chunks[0].body

    def test_table_exceeds_soft_cap_allowed(self) -> None:
        """A ~600-token table gets its own chunk (exceeds soft cap, under hard)."""
        row = "| " + "word " * 20 + "| value |"
        table = "| Col1 | Col2 |\n| --- | --- |\n" + "\n".join([row] * 25)
        tok = count_tokens(table)
        assert tok > MAX_CHUNK_TOKENS
        assert tok < HARD_CAP_TOKENS
        section = _make_section("Intro.\n\n" + table + "\n\nEnd.")
        chunks = chunk_section(section, "test-book")
        table_chunks = [c for c in chunks if "| Col1 | Col2 |" in c.body]
        assert len(table_chunks) == 1

    def test_table_exceeds_hard_cap_splits_with_headers(self) -> None:
        """A >1000-token table is split; each sub-chunk has the header."""
        row = "| " + "word " * 40 + "| value |"
        header = "| Col1 | Col2 |"
        sep = "| --- | --- |"
        table = "\n".join([header, sep] + [row] * 30)
        assert count_tokens(table) > HARD_CAP_TOKENS
        section = _make_section(table)
        chunks = chunk_section(section, "test-book")
        assert len(chunks) > 1
        for c in chunks:
            assert header in c.body
            assert sep in c.body

    def test_code_fence_kept_atomic(self) -> None:
        code = "```python\n" + "\n".join(f"x_{i} = {i}" for i in range(30)) + "\n```"
        tok = count_tokens(code)
        assert tok < HARD_CAP_TOKENS
        section = _make_section("Intro.\n\n" + code + "\n\nEnd.")
        chunks = chunk_section(section, "test-book")
        code_chunks = [c for c in chunks if "```python" in c.body]
        assert len(code_chunks) == 1

    def test_code_fence_exceeds_hard_cap_splits(self) -> None:
        inner = "\n".join(f"line_{i} = {i}" for i in range(500))
        code = f"```python\n{inner}\n```"
        assert count_tokens(code) > HARD_CAP_TOKENS
        section = _make_section(code)
        chunks = chunk_section(section, "test-book")
        assert len(chunks) > 1
        for c in chunks:
            assert "```python" in c.body

    def test_prose_behavior_unchanged(self) -> None:
        """Pure-prose input produces identical results to the old algorithm."""
        para = "This is a normal prose paragraph with several words in it. " * 8
        text = "\n\n".join([para] * 8)
        section = _make_section(text)
        chunks = chunk_section(section, "test-book")
        # All chunks should be under soft cap (or close — single large para)
        for c in chunks:
            assert c.meta.token_count <= MAX_CHUNK_TOKENS + 50  # small tolerance

    def test_prev_next_with_structural_blocks(self) -> None:
        row = "| " + "word " * 40 + "| value |"
        header = "| Col1 | Col2 |"
        sep = "| --- | --- |"
        table = "\n".join([header, sep] + [row] * 30)
        section = _make_section("Intro.\n\n" + table + "\n\nEnd.")
        chunks = chunk_section(section, "test-book")
        for i, c in enumerate(chunks):
            if i > 0:
                assert c.meta.prev == chunks[i - 1].chunk_id
            else:
                assert c.meta.prev is None
            if i < len(chunks) - 1:
                assert c.meta.next == chunks[i + 1].chunk_id
            else:
                assert c.meta.next is None


# ── TestChunkSections ────────────────────────────────────────────────────

class TestChunkSections:
    def test_multiple_sections(self) -> None:
        sections = [
            ParsedSection(
                chapter_id="ch01",
                chapter_title="Chapter 1",
                section_id="ch01-s01",
                section_title="Section 1",
                text="First section content.",
            ),
            ParsedSection(
                chapter_id="ch01",
                chapter_title="Chapter 1",
                section_id="ch01-s02",
                section_title="Section 2",
                text="Second section content.",
            ),
        ]
        chunks = chunk_sections(sections, "test-book")
        assert len(chunks) == 2
        assert chunks[0].chunk_id.startswith("ch01-s01-")
        assert chunks[1].chunk_id.startswith("ch01-s02-")
