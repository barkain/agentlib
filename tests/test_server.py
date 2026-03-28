"""Tests for the MCP server tools."""
# ruff: noqa: S101
from __future__ import annotations

import json
from pathlib import Path

from lib.models import CatalogEntry, Manifest
from lib.storage import update_catalog_entry, write_chunk, write_manifest


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
