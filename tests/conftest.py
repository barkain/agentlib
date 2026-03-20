"""Shared test fixtures for AgentLib tests."""
from __future__ import annotations

from pathlib import Path

import pytest  # type: ignore[import-not-found]

from lib.models import (
    CatalogEntry,
    ChapterInfo,
    ConceptEntry,
    Manifest,
    SectionInfo,
)


@pytest.fixture
def tmp_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set up a temporary data directory and point AGENTLIB_DATA at it."""
    data_dir = tmp_path / "library"
    data_dir.mkdir()
    monkeypatch.setenv("AGENTLIB_DATA", str(data_dir))
    return data_dir


@pytest.fixture
def sample_catalog_entry() -> CatalogEntry:
    return CatalogEntry(
        id="test-book",
        title="Test Book",
        domain_tags=["testing", "python"],
        summary="A test book for unit testing.",
        chapter_count=2,
        total_chunks=10,
    )


@pytest.fixture
def sample_manifest() -> Manifest:
    return Manifest(
        book_id="test-book",
        chapters=[
            ChapterInfo(
                id="ch01",
                title="Introduction",
                summary="An introduction to testing.",
                key_concepts=["unit testing", "fixtures"],
                sections=[
                    SectionInfo(
                        id="ch01-s01",
                        title="Getting Started",
                        summary="How to get started with testing.",
                        chunk_ids=["ch01-s01-001", "ch01-s01-002"],
                    ),
                ],
            ),
            ChapterInfo(
                id="ch02",
                title="Advanced Topics",
                summary="Advanced testing techniques.",
                key_concepts=["mocking", "integration"],
                sections=[
                    SectionInfo(
                        id="ch02-s01",
                        title="Mocking",
                        summary="How to mock dependencies.",
                        chunk_ids=["ch02-s01-001"],
                    ),
                ],
            ),
        ],
        concept_index={
            "unit testing": [ConceptEntry(ch="ch01", sec="ch01-s01", chunks=["ch01-s01-001"])],
            "mocking": [ConceptEntry(ch="ch02", sec="ch02-s01", chunks=["ch02-s01-001"])],
        },
    )


@pytest.fixture
def sample_chunk_content() -> str:
    return """---
chunk_id: ch01-s01-001
source_id: test-book
section: Introduction > Getting Started
token_count: 42
---

This is a test chunk with some content about getting started with testing.
It contains multiple sentences to simulate real content."""
