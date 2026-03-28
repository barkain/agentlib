"""Tests for batched concept extraction and related helpers."""
# ruff: noqa: S101
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

from lib.summariser import (
    ChapterSummary,
    SectionSummary,
    ConceptMapping,
    _format_chapters_text,
    _parse_concept_response,
    extract_concepts,
    _CONCEPT_BATCH_SIZE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chapter(index: int) -> ChapterSummary:
    """Create a minimal ChapterSummary for testing."""
    ch_id = f"ch{index:02d}"
    sec_id = f"{ch_id}-s01"
    chunk_id = f"{sec_id}-001"
    return ChapterSummary(
        chapter_id=ch_id,
        title=f"Chapter {index}",
        summary=f"Summary for chapter {index}.",
        key_concepts=[f"concept_{index}a", f"concept_{index}b"],
        sections=[
            SectionSummary(
                section_id=sec_id,
                title=f"Section {index}.1",
                summary=f"Section summary {index}.1.",
                chunk_ids=[chunk_id],
            )
        ],
    )


def _llm_response_for_batch(batch_chapters: list[ChapterSummary]) -> str:
    """Build a valid JSON concept-extraction response covering the given chapters."""
    concepts: dict = {}
    for ch in batch_chapters:
        concept_name = f"Concept from {ch.chapter_id}"
        sec = ch.sections[0]
        concepts[concept_name] = {
            "aliases": [f"alias_{ch.chapter_id}"],
            "locations": [
                {"ch": ch.chapter_id, "sec": sec.section_id, "chunks": sec.chunk_ids}
            ],
        }
    return json.dumps(concepts)


# ---------------------------------------------------------------------------
# _format_chapters_text
# ---------------------------------------------------------------------------

class TestFormatChaptersText:
    def test_single_chapter(self):
        ch = _make_chapter(1)
        result = _format_chapters_text([ch])

        assert "Chapter 1" in result
        assert "ch01" in result
        assert "Summary for chapter 1." in result
        assert "concept_1a" in result
        assert "Section 1.1" in result
        assert "ch01-s01" in result
        assert "ch01-s01-001" in result

    def test_multiple_chapters(self):
        chapters = [_make_chapter(i) for i in range(1, 4)]
        result = _format_chapters_text(chapters)

        for i in range(1, 4):
            assert f"ch{i:02d}" in result
            assert f"Chapter {i}" in result

    def test_empty_list(self):
        assert _format_chapters_text([]) == ""


# ---------------------------------------------------------------------------
# _parse_concept_response
# ---------------------------------------------------------------------------

class TestParseConceptResponse:
    def test_new_format_with_aliases_and_locations(self):
        data = {
            "Concept A": {
                "aliases": ["alias1"],
                "locations": [
                    {"ch": "ch01", "sec": "ch01-s01", "chunks": ["ch01-s01-001"]}
                ],
            }
        }
        result = _parse_concept_response(data)

        assert "Concept A" in result
        mappings = result["Concept A"]
        assert len(mappings) == 1
        m = mappings[0]
        assert isinstance(m, ConceptMapping)
        assert m.concept == "Concept A"
        assert m.ch == "ch01"
        assert m.sec == "ch01-s01"
        assert m.chunks == ["ch01-s01-001"]
        assert m.aliases == ["alias1"]

    def test_old_format_list(self):
        data = {
            "Concept B": [
                {"ch": "ch02", "sec": "ch02-s01", "chunks": ["ch02-s01-001"]}
            ]
        }
        result = _parse_concept_response(data)

        assert "Concept B" in result
        mappings = result["Concept B"]
        assert len(mappings) == 1
        assert mappings[0].aliases == []
        assert mappings[0].ch == "ch02"

    def test_multiple_locations(self):
        data = {
            "Concept C": {
                "aliases": ["c"],
                "locations": [
                    {"ch": "ch01", "sec": "ch01-s01", "chunks": ["ch01-s01-001"]},
                    {"ch": "ch03", "sec": "ch03-s02", "chunks": ["ch03-s02-001"]},
                ],
            }
        }
        result = _parse_concept_response(data)
        assert len(result["Concept C"]) == 2

    def test_skips_invalid_value(self):
        data = {"Bad": "not a dict or list"}
        result = _parse_concept_response(data)
        assert result == {}

    def test_empty_input(self):
        assert _parse_concept_response({}) == {}


# ---------------------------------------------------------------------------
# extract_concepts — batching
# ---------------------------------------------------------------------------

class TestExtractConceptsBatching:
    """Verify that extract_concepts splits chapters into batches correctly."""

    @patch("lib.summariser.call_llm")
    @patch("lib.summariser.detect_provider")
    def test_small_book_single_batch(self, mock_provider, mock_llm):
        """10 chapters should produce 1 batch and 1 LLM call."""
        chapters = [_make_chapter(i) for i in range(1, 11)]
        mock_provider.return_value = MagicMock()
        mock_llm.return_value = _llm_response_for_batch(chapters)

        result = extract_concepts("test-book", chapters)

        assert mock_llm.call_count == 1
        assert len(result) == 10

    @patch("lib.summariser.call_llm")
    @patch("lib.summariser.detect_provider")
    def test_large_book_multiple_batches(self, mock_provider, mock_llm):
        """120 chapters should produce 3 batches (50+50+20) and 3 LLM calls."""
        chapters = [_make_chapter(i) for i in range(1, 121)]
        mock_provider.return_value = MagicMock()

        # Return appropriate response per batch
        def side_effect(config, prompt, **kwargs):
            # Figure out which chapters are in this batch by checking the prompt
            batch_chs = []
            for ch in chapters:
                if ch.chapter_id in prompt:
                    batch_chs.append(ch)
            return _llm_response_for_batch(batch_chs)

        mock_llm.side_effect = side_effect

        result = extract_concepts("test-book", chapters)

        assert mock_llm.call_count == 3
        # 120 unique concepts capped to 50
        assert len(result) == 50

    @patch("lib.summariser.call_llm")
    @patch("lib.summariser.detect_provider")
    def test_merge_concepts_across_batches(self, mock_provider, mock_llm):
        """Same concept name in two batches should have locations merged."""
        chapters = [_make_chapter(i) for i in range(1, _CONCEPT_BATCH_SIZE + 2)]
        mock_provider.return_value = MagicMock()

        shared_concept = "Shared Concept"
        call_counter = {"n": 0}

        def side_effect(config, prompt, **kwargs):
            call_counter["n"] += 1
            if call_counter["n"] == 1:
                # First batch: shared concept at ch01
                return json.dumps({
                    shared_concept: {
                        "aliases": ["shared"],
                        "locations": [
                            {"ch": "ch01", "sec": "ch01-s01", "chunks": ["ch01-s01-001"]}
                        ],
                    }
                })
            else:
                # Second batch: same concept at ch51
                ch_id = f"ch{_CONCEPT_BATCH_SIZE + 1:02d}"
                return json.dumps({
                    shared_concept: {
                        "aliases": ["shared"],
                        "locations": [
                            {"ch": ch_id, "sec": f"{ch_id}-s01", "chunks": [f"{ch_id}-s01-001"]}
                        ],
                    }
                })

        mock_llm.side_effect = side_effect

        result = extract_concepts("test-book", chapters)

        assert mock_llm.call_count == 2
        assert shared_concept in result
        # Locations from both batches should be merged
        assert len(result[shared_concept]) == 2
        chapter_ids = {m.ch for m in result[shared_concept]}
        assert "ch01" in chapter_ids
        assert f"ch{_CONCEPT_BATCH_SIZE + 1:02d}" in chapter_ids

    @patch("lib.summariser.call_llm")
    @patch("lib.summariser.detect_provider")
    def test_dedup_locations_across_batches(self, mock_provider, mock_llm):
        """Duplicate locations from two batches should be deduplicated."""
        chapters = [_make_chapter(i) for i in range(1, _CONCEPT_BATCH_SIZE + 2)]
        mock_provider.return_value = MagicMock()

        shared_concept = "Shared Concept"

        def side_effect(config, prompt, **kwargs):
            # Both batches return the same concept with the same location + a unique one
            return json.dumps({
                shared_concept: {
                    "aliases": ["shared", "sc"],
                    "locations": [
                        {"ch": "ch01", "sec": "ch01-s01", "chunks": ["ch01-s01-001"]},
                    ],
                }
            })

        mock_llm.side_effect = side_effect

        result = extract_concepts("test-book", chapters)

        assert shared_concept in result
        # Same location from both batches should be deduplicated to 1
        assert len(result[shared_concept]) == 1
        # Aliases should be deduplicated
        assert result[shared_concept][0].aliases == ["shared", "sc"]

    @patch("lib.summariser.call_llm")
    @patch("lib.summariser.detect_provider")
    def test_concept_cap_at_50(self, mock_provider, mock_llm):
        """More than 50 concepts should be capped to 50."""
        chapters = [_make_chapter(1)]
        mock_provider.return_value = MagicMock()

        # Return 60 concepts, each with varying number of locations
        concepts: dict = {}
        for i in range(60):
            locations = [
                {"ch": f"ch{j:02d}", "sec": f"ch{j:02d}-s01", "chunks": [f"ch{j:02d}-s01-001"]}
                for j in range(1, i + 2)  # concept i has i+1 locations
            ]
            concepts[f"Concept {i:03d}"] = {
                "aliases": [f"c{i}"],
                "locations": locations,
            }
        mock_llm.return_value = json.dumps(concepts)

        result = extract_concepts("test-book", chapters)

        assert len(result) == 50
        # Verify the kept concepts are the ones with most locations
        kept_counts = [len(v) for v in result.values()]
        assert min(kept_counts) >= 11  # top 50 of 60 means at least 11 locations
