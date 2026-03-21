"""Tests for the semantic chunker."""
# ruff: noqa: S101
from __future__ import annotations

from lib.chunker import (
    chunk_section,
    chunk_sections,
    count_tokens,
    _split_paragraphs,
)
from lib.models import ParsedSection


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


class TestChunkSection:
    def _make_section(self, text: str) -> ParsedSection:
        return ParsedSection(
            chapter_id="ch01",
            chapter_title="Test Chapter",
            section_id="ch01-s01",
            section_title="Test Section",
            text=text,
        )

    def test_empty_text(self) -> None:
        section = self._make_section("")
        chunks = chunk_section(section, "test-book")
        assert chunks == []

    def test_single_paragraph(self) -> None:
        section = self._make_section("A simple paragraph with a few words.")
        chunks = chunk_section(section, "test-book")
        assert len(chunks) == 1
        assert chunks[0].chunk_id == "ch01-s01-001"
        assert chunks[0].meta.source_id == "test-book"

    def test_paragraphs_merged_under_limit(self) -> None:
        # Several small paragraphs should merge into one chunk
        paras = ["Short paragraph." for _ in range(5)]
        section = self._make_section("\n\n".join(paras))
        chunks = chunk_section(section, "test-book")
        assert len(chunks) == 1

    def test_large_text_splits(self) -> None:
        # Generate enough text to require multiple chunks
        para = "This is a substantial paragraph with enough words to count. " * 20
        text = "\n\n".join([para] * 10)
        section = self._make_section(text)
        chunks = chunk_section(section, "test-book")
        assert len(chunks) > 1

    def test_prev_next_links(self) -> None:
        para = "This is a substantial paragraph with enough words. " * 25
        text = "\n\n".join([para] * 10)
        section = self._make_section(text)
        chunks = chunk_section(section, "test-book")

        if len(chunks) > 1:
            assert chunks[0].meta.prev is None
            assert chunks[0].meta.next == chunks[1].chunk_id
            assert chunks[-1].meta.next is None
            assert chunks[-1].meta.prev == chunks[-2].chunk_id

    def test_chunk_id_format(self) -> None:
        section = self._make_section("Some text content.")
        chunks = chunk_section(section, "test-book")
        assert chunks[0].chunk_id.startswith("ch01-s01-")

    def test_chunk_has_yaml_frontmatter(self) -> None:
        section = self._make_section("Some text content for the chunk.")
        chunks = chunk_section(section, "test-book")
        assert chunks[0].formatted.startswith("---\n")
        assert "chunk_id:" in chunks[0].formatted
        assert "source_id: test-book" in chunks[0].formatted


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
