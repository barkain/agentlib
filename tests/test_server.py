"""Tests for the MCP server tools."""
# ruff: noqa: S101
from __future__ import annotations

import json
from pathlib import Path

from lib.models import (
    CatalogEntry,
    ChunkIndex,
    ChunkIndexEntry,
    LibraryConceptEntry,
    LibraryConceptSource,
    LibraryIndex,
    Manifest,
    PatternEntry,
    PatternIndex,
)
from lib.storage import (
    update_catalog_entry,
    write_chunk,
    write_chunk_index,
    write_library_index,
    write_manifest,
    write_pattern_index,
)


class TestBrowseLibrary:
    def test_empty_library(self, tmp_data_dir: Path) -> None:
        from server import browse_library
        result = json.loads(browse_library())
        assert result["books"] == []

    def test_with_books(self, tmp_data_dir: Path, sample_catalog_entry: CatalogEntry) -> None:
        from server import browse_library
        update_catalog_entry(sample_catalog_entry)

        result = json.loads(browse_library())
        assert len(result["books"]) == 1
        assert result["books"][0]["id"] == "test-book"


class TestOpenBook:
    def test_nonexistent_book(self, tmp_data_dir: Path) -> None:
        from server import open_book
        result = open_book("nonexistent")
        assert "not found" in result.lower() or "error" in result.lower()

    def test_existing_book(self, tmp_data_dir: Path, sample_manifest: Manifest) -> None:
        from server import open_book
        write_manifest(sample_manifest)

        result = json.loads(open_book("test-book"))
        assert result["book_id"] == "test-book"
        assert len(result["chapters"]) == 2


class TestReadChunks:
    def test_read_existing_chunks(self, tmp_data_dir: Path) -> None:
        from server import read_chunks
        write_chunk("test-book", "ch01-001", "Content 1")
        write_chunk("test-book", "ch01-002", "Content 2")

        result = json.loads(read_chunks("test-book", ["ch01-001", "ch01-002"]))
        assert result["ch01-001"] == "Content 1"
        assert result["ch01-002"] == "Content 2"

    def test_too_many_chunks(self, tmp_data_dir: Path) -> None:
        from server import read_chunks
        chunk_ids = [f"ch01-{i:03d}" for i in range(15)]
        result = read_chunks("test-book", chunk_ids)
        assert "error" in result.lower() or "max" in result.lower()

    def test_missing_chunks(self, tmp_data_dir: Path) -> None:
        from server import read_chunks
        result = json.loads(read_chunks("test-book", ["nonexistent"]))
        assert result["nonexistent"] is None


class TestSearchConcepts:
    def test_search(self, tmp_data_dir: Path, sample_manifest: Manifest) -> None:
        from server import search_concepts
        write_manifest(sample_manifest)
        update_catalog_entry(CatalogEntry(id="test-book", title="Test"))

        result = json.loads(search_concepts("unit testing"))
        assert len(result) > 0

    def test_search_empty(self, tmp_data_dir: Path) -> None:
        from server import search_concepts
        result = json.loads(search_concepts("anything"))
        assert result == {}


class TestSearchLibrary:
    def test_search_unified(self, tmp_data_dir: Path) -> None:
        from server import search_library
        lib_index = LibraryIndex(concepts={
            "OAuth 2.0": LibraryConceptEntry(
                sources=[LibraryConceptSource(source="book:api-sec", chunks=["ch03-001"])],
                aliases=["OAuth"],
                related=["JWT"],
                patterns=["credential-cycling"],
            ),
        })
        write_library_index(lib_index)

        result = json.loads(search_library("OAuth"))
        assert "OAuth 2.0" in result
        assert result["OAuth 2.0"]["patterns"] == ["credential-cycling"]
        assert result["OAuth 2.0"]["related"] == ["JWT"]

    def test_search_by_related(self, tmp_data_dir: Path) -> None:
        from server import search_library
        lib_index = LibraryIndex(concepts={
            "token lifecycle": LibraryConceptEntry(
                sources=[LibraryConceptSource(source="book:auth", chunks=["ch01-001"])],
                aliases=[],
                related=["refresh tokens"],
                patterns=["credential-cycling"],
            ),
        })
        write_library_index(lib_index)

        result = json.loads(search_library("refresh tokens"))
        assert "token lifecycle" in result

    def test_search_empty_library(self, tmp_data_dir: Path) -> None:
        from server import search_library
        result = json.loads(search_library("anything"))
        assert result == {}


class TestExplorePatterns:
    def test_explore_pattern(self, tmp_data_dir: Path) -> None:
        from server import explore_patterns
        pat_index = PatternIndex(patterns={
            "credential-cycling": [
                PatternEntry(concept="OAuth tokens", source="book:api-sec", chunks=["ch03-001"]),
                PatternEntry(concept="TLS certs", source="book:tls", chunks=["ch08-001"]),
            ],
        })
        write_pattern_index(pat_index)

        result = json.loads(explore_patterns("credential"))
        assert "credential-cycling" in result
        assert len(result["credential-cycling"]) == 2

    def test_no_match_shows_available(self, tmp_data_dir: Path) -> None:
        from server import explore_patterns
        pat_index = PatternIndex(patterns={"retry-with-backoff": []})
        write_pattern_index(pat_index)

        result = json.loads(explore_patterns("nonexistent"))
        assert result["no_match"] is True
        assert "retry-with-backoff" in result["available_patterns"]


class TestPreviewChunks:
    def test_preview_existing(self, tmp_data_dir: Path) -> None:
        from server import preview_chunks
        write_chunk("test-book", "ch01-001", "content")  # create book dir
        chunk_index = ChunkIndex(
            book_id="test-book",
            chunks={
                "ch01-001": ChunkIndexEntry(
                    section="Intro", concepts=["testing"], tokens=420,
                    prev=None, next="ch01-002",
                ),
            },
        )
        write_chunk_index("test-book", chunk_index)

        result = json.loads(preview_chunks("test-book", ["ch01-001", "ch01-999"]))
        assert result["ch01-001"]["section"] == "Intro"
        assert result["ch01-001"]["concepts"] == ["testing"]
        assert result["ch01-001"]["tokens"] == 420
        assert result["ch01-999"] is None

    def test_preview_nonexistent_book(self, tmp_data_dir: Path) -> None:
        from server import preview_chunks
        result = json.loads(preview_chunks("nonexistent", ["ch01-001"]))
        assert "error" in result
