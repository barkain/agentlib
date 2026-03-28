"""Tests for batched concept extraction and related helpers."""
# ruff: noqa: S101
from __future__ import annotations

import asyncio
import json
import time
from unittest.mock import patch, MagicMock

from lib.summariser import (
    ChapterSummary,
    SectionSummary,
    ConceptMapping,
    async_summarise_chapter,
    _format_chapters_text,
    _parse_concept_response,
    extract_concepts,
    _CONCEPT_BATCH_SIZE,
)
from lib.llm import async_call_llm, LLMConfig

DUMMY_CONFIG = LLMConfig(provider="openai", model="test", api_key="test-key")


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


# ---------------------------------------------------------------------------
# Mock LLM response for async tests
# ---------------------------------------------------------------------------

MOCK_CHAPTER_RESPONSE = json.dumps({
    "chapter_summary": "Test summary",
    "key_concepts": ["concept1"],
    "section_summaries": [
        {"section_id": "ch01-s01", "title": "Sec 1", "summary": "Sec summary"}
    ]
})


# ---------------------------------------------------------------------------
# TestAsyncSummariseChapter
# ---------------------------------------------------------------------------

class TestAsyncSummariseChapter:
    @patch("lib.llm.call_llm")
    def test_async_returns_same_as_sync(self, mock_llm):
        """Mock call_llm, call async_summarise_chapter, verify ChapterSummary fields."""
        mock_llm.return_value = MOCK_CHAPTER_RESPONSE

        sections = [{"section_id": "ch01-s01", "title": "Sec 1", "text": "Some text", "chunk_ids": ["ch01-s01-001"]}]
        result = asyncio.run(async_summarise_chapter(
            chapter_id="ch01",
            chapter_title="Chapter 1",
            sections=sections,
            llm_config=DUMMY_CONFIG,
        ))

        assert isinstance(result, ChapterSummary)
        assert result.chapter_id == "ch01"
        assert result.title == "Chapter 1"
        assert result.summary == "Test summary"
        assert result.key_concepts == ["concept1"]
        assert len(result.sections) == 1
        assert result.sections[0].section_id == "ch01-s01"
        assert result.sections[0].title == "Sec 1"
        assert result.sections[0].summary == "Sec summary"

    @patch("lib.llm.call_llm")
    def test_async_respects_semaphore(self, mock_llm):
        """Semaphore with value 2 should limit concurrency across 5 tasks."""
        max_concurrent = {"value": 0}
        current_concurrent = {"value": 0}

        original_return = MOCK_CHAPTER_RESPONSE

        async def _run():
            semaphore = asyncio.Semaphore(2)

            async def _tracked_summarise(ch_id):
                # We wrap async_summarise_chapter but track concurrency via the mock
                return await async_summarise_chapter(
                    chapter_id=ch_id,
                    chapter_title=f"Chapter {ch_id}",
                    sections=[{"section_id": f"{ch_id}-s01", "title": "S1", "text": "txt", "chunk_ids": []}],
                    semaphore=semaphore,
                    llm_config=DUMMY_CONFIG,
                )

            tasks = [_tracked_summarise(f"ch{i:02d}") for i in range(1, 6)]
            return await asyncio.gather(*tasks)

        def _slow_llm(config, prompt, max_tokens=1024, images=None):
            current_concurrent["value"] += 1
            if current_concurrent["value"] > max_concurrent["value"]:
                max_concurrent["value"] = current_concurrent["value"]
            import time as _time
            _time.sleep(0.05)
            current_concurrent["value"] -= 1
            return original_return

        mock_llm.side_effect = _slow_llm

        results = asyncio.run(_run())

        assert len(results) == 5
        assert all(isinstance(r, ChapterSummary) for r in results)
        assert max_concurrent["value"] <= 2


# ---------------------------------------------------------------------------
# TestAsyncCallLlm
# ---------------------------------------------------------------------------

class TestAsyncCallLlm:
    @patch("lib.llm.call_llm")
    def test_async_call_llm_returns_result(self, mock_llm):
        """Mock call_llm, call async_call_llm, verify same result."""
        mock_llm.return_value = "test response"

        from lib.llm import LLMConfig
        config = LLMConfig(provider="openai", model="gpt-4", api_key="fake")
        result = asyncio.run(async_call_llm(config, "test prompt"))

        assert result == "test response"
        mock_llm.assert_called_once()


# ---------------------------------------------------------------------------
# TestParallelSummarization
# ---------------------------------------------------------------------------

class TestParallelSummarization:
    @patch("lib.llm.call_llm")
    def test_parallel_faster_than_sequential(self, mock_llm):
        """10 chapters with semaphore=5 should take ~2 waves, not 10 sequential calls."""

        def _slow_llm(config, prompt, max_tokens=1024, images=None):
            import time as _time
            _time.sleep(0.1)
            return MOCK_CHAPTER_RESPONSE

        mock_llm.side_effect = _slow_llm

        async def _run():
            semaphore = asyncio.Semaphore(5)
            tasks = [
                async_summarise_chapter(
                    chapter_id=f"ch{i:02d}",
                    chapter_title=f"Chapter {i}",
                    sections=[{"section_id": f"ch{i:02d}-s01", "title": "S1", "text": "txt", "chunk_ids": []}],
                    semaphore=semaphore,
                    llm_config=DUMMY_CONFIG,
                )
                for i in range(1, 11)
            ]
            return await asyncio.gather(*tasks)

        start = time.time()
        results = asyncio.run(_run())
        elapsed = time.time() - start

        assert len(results) == 10
        assert all(isinstance(r, ChapterSummary) for r in results)
        # Should be ~0.2s (2 waves of 5), definitely less than 0.5s
        assert elapsed < 0.5, f"Parallel execution took {elapsed:.2f}s, expected < 0.5s"
